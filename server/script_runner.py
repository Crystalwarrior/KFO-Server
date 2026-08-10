"""
Script runner: the shared automation engine for demo playback.

A `ScriptRunner` executes an ordered list of instructions -- `wait` delays,
AO packets, OOC commands, and Turing-complete control flow -- through the
area's system executor client (`Area.get_script_client`). Playback is
non-recursive: each instruction is processed in its own event-loop tick, so
scripts are safe to chain (`/demo` inside `/demo`) and can be arbitrarily long.

Instruction tuples:
- `("wait", seconds)`
- `("packet", header, args)`
- `("command", cmd, arg)`
- `("label", name)`, `("goto", name)`, `("return",)` — `goto` remembers
  where it jumped from; `return` jumps back, or ends the script if it wasn't
  called from anywhere.
- `("if", var, op, value, target)`
- `("set", name, expr)` / `("get", name, expr)` — store a number (expression),
  a quoted string literal, a copy of another variable's value, or (via `get`)
  a structured live source such as `client[i].showname`.
- `("concat", name, value, sep)` — append to a string variable.
- `("rand", name, low, high)` — store a random integer in `[low, high]`.
- `("save", char, key, value)` — persist a value into a character's data
  (`char` is a char id or quoted folder; the value may be a live path).

Lines use space-separated tokens; `#` is reserved for AO packet lines. A stray
trailing `#` on any non-packet line is tolerated (the old `#%` habit).

See `docs/demo_scripting.md` for the full language specification.
"""

import asyncio
import logging
import random
import re

from server import commands
from server.scripting import (
    _LIVE_PATH,
    _QUOTED,
    _resolve_char_index,
    live_get,
    live_sources,
    resolve_value,
    ScriptingError,
    substitute_placeholders,
)

logger = logging.getLogger("script")

# Server->client packet headers a demo is allowed to broadcast.
PACKET_HEADERS = ("MS", "CT", "MC", "BN", "HP", "RT", "JD", "GM", "ST")

# First token of an instruction line (space syntax). `#` is only used on
# packet lines.
INSTRUCTION_KEYWORDS = ("wait", "set", "get", "concat", "if", "label", "goto", "return", "rand", "save")

# Symbolic spellings of the `if` operators; both forms are accepted.
_IF_ALIASES = {"==": "eq", "!=": "ne", "<": "lt", "<=": "le", ">": "gt", ">=": "ge"}

# Comparison operators for the `if` instruction.
_IF_OPS = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "lt": lambda a, b: a < b,
    "gt": lambda a, b: a > b,
    "le": lambda a, b: a <= b,
    "ge": lambda a, b: a >= b,
}

# Default cap on instructions executed by one script run (config override:
# `demo_max_steps`). Guards against runaway goto loops.
DEFAULT_MAX_STEPS = 1000000


def parse_demo_description(desc):
    """
    Parse an evidence description into script instructions.

    `%` is the line terminator for AO packets and slash commands; newlines
    inside those are content, so multiline packets (multi-line MS text) and
    multiline command arguments keep working. Scripting instructions (`wait`,
    `set`, `get`, `concat`, `label`, `goto`, `return`, `if`, `rand`)
    are terminated by `%` **or** a newline, so demos can be written with real
    line breaks. Escaped characters (`<num>`, `<and>`, `<percent>`,
    `<dollar>`) are unescaped before splitting.

    Packet lines keep the AO `#` field separator; instruction lines use
    space-separated tokens. A stray trailing `#` is stripped from every
    non-packet line so the old `#%` habit still works. The legacy
    `wait#<ms>` form is also accepted alongside `wait <ms>`.
    """
    desc = desc.replace("<num>", "#").replace("<and>", "&").replace("<percent>", "%").replace("<dollar>", "$")
    instructions = []
    for line in _iter_lines(desc):
        stripped = line.strip().rstrip("#").strip()
        if not stripped:
            continue
        if stripped.startswith("/"):
            parts = stripped.split(" ")
            cmd = parts.pop(0).lstrip("/").lower()
            arg = " ".join(parts)[:1024] if parts else ""
            instructions.append(("command", cmd, arg))
            continue
        header = stripped.split("#", 1)[0].strip()
        if header in PACKET_HEADERS:
            fields = stripped.split("#")
            if len(fields) > 1 and fields[-1] == "":
                # AO demo lines end with a `#` terminator before the `%`
                # separator (`#%`); drop it so it can't become an empty
                # trailing field.
                fields = fields[:-1]
            instructions.append(("packet", header, tuple(fields[1:])))
        elif header == "wait":
            # Legacy `wait#<ms>` form (`wait <ms>` is handled below).
            fields = stripped.split("#")
            try:
                seconds = float(fields[1]) / 1000 if len(fields) > 1 else 0
            except (ValueError, IndexError):
                seconds = 0
            instructions.append(("wait", seconds))
        elif re.split(r"\s+", stripped, maxsplit=1)[0] in INSTRUCTION_KEYWORDS:
            parsed = _parse_instruction(stripped)
            if parsed is not None:
                instructions.append(parsed)
        # Unknown headers are ignored so stray text in a description can't
        # crash playback.
    return instructions


def _is_packet_or_command(content):
    """True if a chunk starts a packet or slash command (ends at `%` only)."""
    stripped = content.strip()
    return stripped.startswith("/") or stripped.split("#", 1)[0].strip() in PACKET_HEADERS


def _iter_lines(desc):
    """
    Yield description lines as strings.

    Packets and slash commands end at the next `%` (newlines are content, so
    multiline packets and command arguments are preserved). Anything else ends
    at the next `%` or newline. A `\n` after a `%` or `%` after a newline is a
    plain empty line and is skipped.
    """
    desc = desc.replace("\r\n", "\n").replace("\r", "\n")
    chunks = re.split(r"([%\n])", desc)
    i = 0
    n = len(chunks)
    while i < n:
        content = chunks[i]
        sep = chunks[i + 1] if i + 1 < n else None
        i += 2
        if not content.strip():
            continue
        if _is_packet_or_command(content):
            while sep is not None and sep != "%":
                if i < n:
                    content += "\n" + chunks[i]
                    sep = chunks[i + 1] if i + 1 < n else None
                    i += 2
                else:
                    sep = None
        yield content


def _split_save(line):
    """
    Split a `save <char> <key> <value...>` line into its three parts.

    The char and key tokens are split quote-aware (so a quoted character
    folder can contain spaces); the value is the verbatim remainder of the
    line, so multi-word or quoted values are preserved exactly as written.
    """
    tokens = []
    current = []
    quote_char = None
    value_start = 0
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if quote_char is not None:
            current.append(ch)
            if ch == quote_char:
                quote_char = None
        elif ch in "\"'":
            quote_char = ch
            current.append(ch)
        elif ch.isspace():
            if current:
                tokens.append("".join(current))
                current = []
                if len(tokens) == 3:
                    value_start = i
                    break
        else:
            current.append(ch)
        i += 1
    if current:
        tokens.append("".join(current))
        value_start = n
    if len(tokens) < 3:
        return None
    rest = line[value_start:].strip()
    if not rest:
        return None
    return tokens[1], tokens[2], rest


def _split_operands(text):
    """Split on whitespace, keeping quoted segments (`"..."` or `'...'`) intact."""
    tokens = []
    current = []
    quote_char = None
    for ch in text:
        if quote_char is not None:
            current.append(ch)
            if ch == quote_char:
                quote_char = None
        elif ch in "\"'":
            quote_char = ch
            current.append(ch)
        elif ch.isspace():
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(ch)
    if current:
        tokens.append("".join(current))
    return tokens


def _parse_instruction(line):
    """Build an instruction tuple from a space-separated instruction line."""
    parts = _split_operands(line)
    kind = parts[0]
    if kind == "wait":
        try:
            seconds = float(parts[1]) / 1000 if len(parts) > 1 else 0
        except (ValueError, IndexError):
            seconds = 0
        return ("wait", seconds)
    if kind in ("set", "get"):
        # The value is the rest of the line (quotes kept); split only the
        # first two tokens so unquoted multi-word values are preserved.
        pieces = re.split(r"\s+", line, maxsplit=2)
        if len(pieces) >= 3:
            return (kind, pieces[1], pieces[2])
        return None
    if kind == "concat":
        if len(parts) >= 3:
            return ("concat", parts[1], parts[2], parts[3] if len(parts) >= 4 else "")
        return None
    if kind == "save":
        split = _split_save(line)
        if split is not None:
            return ("save", split[0], split[1], split[2])
        return None
    if kind == "if":
        if len(parts) >= 5:
            return ("if", parts[1], parts[2], parts[3], parts[4])
        return None
    if kind in ("label", "goto"):
        if len(parts) >= 2:
            return (kind, parts[1])
        return None
    if kind == "return":
        return ("return",)
    if kind == "rand":
        if len(parts) >= 4:
            return ("rand", parts[1], parts[2], parts[3])
        return None
    return None


class ScriptRunner:
    """Runs a sequence of demo instructions through an executor client."""

    def __init__(self, area, executor):
        self.area = area
        self.executor = executor
        # Instructions are kept as a list with an explicit index so scripts
        # can jump backwards (loops) via goto -- a deque can't.
        self.instructions = []
        self.index = 0
        self.labels = {}
        self.stack = []
        self.schedule = None
        self.running = False
        self.steps = 0
        config = getattr(getattr(executor, "server", None), "config", None) or {}
        self.max_steps = int(config.get("demo_max_steps", DEFAULT_MAX_STEPS))
        self.modified_packets = set()

    # --- Lifecycle ---

    def start(self, instructions):
        """Replace the current queue and begin (or restart) playback."""
        self._replace(instructions)
        if not self.instructions:
            self.finish()
            return False
        self.running = True
        self.steps = 0
        logger.info("Demo started in area %s (%d instructions)", self.area.id, len(instructions))
        self._schedule_next(0)
        return True

    def stop(self):
        """Stop playback and clean up."""
        logger.info("Demo stopped in area %s", self.area.id)
        self.finish()

    def finish(self):
        """Cancel any pending step, reset script state and modified packets."""
        if self.schedule:
            self.schedule.cancel()
            self.schedule = None
        self.running = False
        self.instructions = []
        self.index = 0
        self.labels = {}
        self.stack = []
        self.steps = 0
        self._reset_modified_packets()

    def _replace(self, instructions):
        """Swap in a new instruction queue (used by chained `/demo` calls)."""
        if self.schedule:
            self.schedule.cancel()
            self.schedule = None
        self.instructions = list(instructions)
        self.index = 0
        self.stack = []
        self.labels = self._build_labels(self.instructions)

    def _build_labels(self, instructions):
        labels = {}
        for i, instruction in enumerate(instructions):
            if instruction[0] == "label" and len(instruction) >= 2:
                labels[instruction[1]] = i
        return labels

    def _schedule_next(self, delay):
        loop = asyncio.get_running_loop()
        if delay > 0:
            self.schedule = loop.call_later(delay, self.step)
        else:
            self.schedule = loop.call_later(0, self.step)

    # --- Stepping ---

    def step(self):
        if self.schedule:
            self.schedule.cancel()
            self.schedule = None
        if not self.running or self.index >= len(self.instructions):
            self.finish()
            return
        self.steps += 1
        if self.steps > self.max_steps:
            self.area.broadcast_ooc(f"[Demo] [ERROR] Max steps exceeded ({self.max_steps}); " "stopping playback.")
            self.finish()
            return
        instruction = self.instructions[self.index]
        self.index += 1
        kind = instruction[0]
        if kind == "wait":
            logger.info("Demo wait %s in area %s", instruction[1], self.area.id)
            self._schedule_next(instruction[1])
            return
        if kind == "packet":
            logger.info("Demo packet %s in area %s", instruction[1], self.area.id)
            self.send_packet(instruction[1], instruction[2])
        elif kind == "label":
            # No-op: labels exist only as goto targets.
            pass
        elif kind == "goto":
            # Like the old `call`: remember where we jumped from so `return`
            # can come back to it.
            self.stack.append(self.index)
            self._jump(instruction[1])
        elif kind == "return":
            if self.stack:
                self.index = self.stack.pop()
            else:
                # Nothing to return to -- the script is simply done.
                self.finish()
                return
        elif kind == "if":
            self._eval_if(instruction)
        elif kind == "set":
            self._eval_set(instruction, sources=False)
        elif kind == "get":
            self._eval_set(instruction, sources=True)
        elif kind == "concat":
            self._eval_concat(instruction)
        elif kind == "rand":
            self._eval_rand(instruction)
        elif kind == "save":
            self._eval_save(instruction)
        elif kind == "command":
            # If a chained /demo took over the queue, don't schedule another
            # step on top of the new script. If playback was stopped by an
            # error, don't keep stepping either.
            if self.run_command(instruction[1], instruction[2]):
                return
            if not self.running:
                return
        if not self.running:
            return
        self._schedule_next(0)

    def _jump(self, label):
        """Set the instruction index to a label; errors stop playback."""
        if label not in self.labels:
            self.area.broadcast_ooc(f"[Demo] [ERROR] Unknown label '{label}'; stopping playback.")
            self.finish()
            return False
        self.index = self.labels[label]
        return True

    def _resolve_operand(self, text, variables, sources):
        """Resolve an operand, allowing structured live paths (get-style)."""
        if _LIVE_PATH.fullmatch(text.strip()):
            return live_get(text, self.area, variables)
        return resolve_value(text, variables, sources)

    def _eval_if(self, instruction):
        """Evaluate `if <left> <op> <right> <target>` and branch on the result."""
        _, var, op, value, target = instruction
        op = _IF_ALIASES.get(op, op)
        if op not in _IF_OPS:
            self.area.broadcast_ooc(f"[Demo] [ERROR] Unknown comparison '{op}'; stopping playback.")
            self.finish()
            return
        variables = getattr(self.area, "variables", {})
        sources = live_sources(self.area)
        try:
            left = self._resolve_operand(var, variables, sources)
            right = self._resolve_operand(value, variables, sources)
        except ScriptingError as ex:
            self.area.broadcast_ooc(f"[Demo] [ERROR] {ex}")
            self.finish()
            return
        if op in ("lt", "gt", "le", "ge") and isinstance(left, str) != isinstance(right, str):
            self.area.broadcast_ooc("[Demo] [ERROR] Cannot compare a number and a string; stopping playback.")
            self.finish()
            return
        if _IF_OPS[op](left, right):
            self._jump(target)

    def _eval_set(self, instruction, sources):
        """Evaluate an operand (or live path) and store it in an area variable."""
        _, name, expr = instruction
        variables = getattr(self.area, "variables", {})
        try:
            if sources:
                value = self._resolve_operand(expr, variables, live_sources(self.area))
            else:
                value = resolve_value(expr, variables)
        except ScriptingError as ex:
            self.area.broadcast_ooc(f"[Demo] [ERROR] {ex}")
            self.finish()
            return
        variables[name] = value

    def _eval_concat(self, instruction):
        """Append a value to a string variable, inserting the separator first."""
        _, name, value, *rest = instruction
        sep = rest[0] if rest else ""
        variables = getattr(self.area, "variables", {})
        sources = live_sources(self.area)
        try:
            resolved = self._resolve_operand(value, variables, sources)
            resolved_sep = self._resolve_operand(sep, variables, sources) if sep.strip() else ""
        except ScriptingError as ex:
            self.area.broadcast_ooc(f"[Demo] [ERROR] {ex}")
            self.finish()
            return
        current = str(variables.get(name, ""))
        addition = f"{resolved_sep}{resolved}" if current else str(resolved)
        variables[name] = current + addition

    def _eval_rand(self, instruction):
        """Store a random integer in `[low, high]` (inclusive) into a variable."""
        _, name, low, high = instruction
        variables = getattr(self.area, "variables", {})
        sources = live_sources(self.area)
        try:
            lo = self._resolve_operand(low, variables, sources)
            hi = self._resolve_operand(high, variables, sources)
        except ScriptingError as ex:
            self.area.broadcast_ooc(f"[Demo] [ERROR] {ex}")
            self.finish()
            return
        if (
            isinstance(lo, bool)
            or not isinstance(lo, (int, float))
            or isinstance(hi, bool)
            or not isinstance(hi, (int, float))
        ):
            self.area.broadcast_ooc("[Demo] [ERROR] rand bounds must be numbers; stopping playback.")
            self.finish()
            return
        lo, hi = int(lo), int(hi)
        if lo > hi:
            self.area.broadcast_ooc(f"[Demo] [ERROR] rand min {lo} is greater than max {hi}; stopping playback.")
            self.finish()
            return
        variables[name] = random.randint(lo, hi)

    def _eval_save(self, instruction):
        """Persist a value into a character's data and save it to disk."""
        _, char_text, key, value_text = instruction
        variables = getattr(self.area, "variables", {})
        sources = live_sources(self.area)
        try:
            char = _resolve_char_index(char_text, self.area, variables, "Character")
            key = resolve_value(key, {}, {}) if _QUOTED.fullmatch(key) else key
            if _LIVE_PATH.fullmatch(value_text.strip()):
                value = live_get(value_text, self.area, variables)
            else:
                try:
                    value = resolve_value(value_text, variables, sources)
                except ScriptingError:
                    value = value_text
        except ScriptingError as ex:
            self.area.broadcast_ooc(f"[Demo] [ERROR] {ex}")
            self.finish()
            return
        hub = self.area.area_manager
        if isinstance(char, int) and not hub.is_valid_char_id(char):
            self.area.broadcast_ooc(f"[Demo] [ERROR] Unknown character id {char}; stopping playback.")
            self.finish()
            return
        hub.set_character_data(char, key, value)
        hub.save_character_data()

    def send_packet(self, header, args):
        """Broadcast an AO packet, honouring the executor's broadcast list."""
        area_list = [self.area]
        if len(self.executor.broadcast_list) > 0:
            area_list = self.executor.broadcast_list
        variables = getattr(self.area, "variables", {})
        try:
            packet_args = [
                substitute_placeholders(str(arg), variables, live_sources(self.area), self.area) for arg in args
            ]
        except ScriptingError as ex:
            self.area.broadcast_ooc(f"[Demo] [ERROR] {ex}")
            self.finish()
            return
        for area in area_list:
            if header == "MS":
                # If we're on narration pos, keep the same position as the
                # last IC message, falling back to the area's first pos-lock.
                if len(packet_args) > 5 and packet_args[5] == "":
                    if area.last_ic_message is not None:
                        packet_args[5] = area.last_ic_message[5]
                    elif len(self.area.pos_lock) > 0:
                        packet_args[5] = self.area.pos_lock[0]
            area.send_command(header, *packet_args)
            logger.info(
                "Demo broadcast %s to area %s (%d clients)",
                header,
                area.id,
                len(area.clients),
            )
        self.modified_packets.add(header)

    def run_command(self, cmd, arg):
        """
        Run a command through the executor.

        Returns True if the script was replaced by a chained `/demo` call.
        Broadcasts errors to the area and stops playback on failure.
        """
        resolved = commands.resolve_command(self.executor.server, cmd)
        if resolved is None:
            self.area.broadcast_ooc(f"[Demo] Invalid command: {cmd}. Use /help to find up-to-date commands.")
            self.finish()
            return False
        is_demo = resolved is getattr(commands, "ooc_cmd_demo", None)
        variables = getattr(self.area, "variables", {})
        try:
            arg = substitute_placeholders(arg, variables, live_sources(self.area), self.area)
        except ScriptingError as ex:
            self.area.broadcast_ooc(f"[Demo] [ERROR] {ex}")
            self.finish()
            return False
        self.executor.execute(cmd, arg)
        for msg in self.executor.output:
            if msg.startswith("[ERROR]"):
                self.area.broadcast_ooc(f"[Demo] {msg}")
                self.finish()
                return False
        return is_demo

    # --- Cleanup ---

    def _reset_modified_packets(self):
        """Restore area state for packets the script actually modified."""
        area = self.area
        if area is None:
            return
        if "HP" in self.modified_packets:
            area.send_command("HP", 1, area.hp_def)
            area.send_command("HP", 2, area.hp_pro)
        if "BN" in self.modified_packets:
            area.send_command("BN", area.background)
        self.modified_packets.clear()
