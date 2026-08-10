# Demo Scripting Guide

Scripts run out of **evidence items**. Put a script in an evidence description,
then play it with `/demo <id>` or `/demo <name>`. The server runs the script as
the area's own character, so whatever the script broadcasts appears in the area.

Here's the whole language at a glance:

| Instruction                    | What it does                                  |
| ------------------------------ | --------------------------------------------- |
| `wait <ms>`                    | Pause for `<ms>` milliseconds                 |
| `MS#...#%`, `CT#...#%`, etc.   | Send an AO packet to everyone in the area     |
| `/command <args>%`             | Run an OOC command as the area's character    |
| `set <var> <value>`            | Store a value in a variable                   |
| `get <var> <source>`           | Read live server state into a variable        |
| `concat <var> <value> <sep>`   | Add text to the end of a string variable      |
| `rand <var> <min> <max>`       | Store a random whole number in a variable     |
| `if <a> <op> <b> <label>`      | Jump to a label when a comparison is true     |
| `label <name>`                 | Mark a spot to jump to                        |
| `goto <name>`                  | Jump to a label (remembering where you were)  |
| `return`                       | Jump back to the matching `goto`; if there's  |
|                                | nothing to return to, the script just ends    |

## Writing a script

A script is a list of lines. How a line ends depends on what it is:

- **Packets and `/` commands end with `%`.** They can even span multiple lines -
  the newlines inside them are part of the packet. A multi-line message works
  fine:
  ```
  CT#narrator#Hello..
  there..
  everyone!!!%
  ```
- **Everything else ends with `%` *or* a newline.**
  That means you can write a script with real line breaks:

  ```
  set count 5
  label loop
  set count count-1
  if count gt 0 loop
  CT#narrator#Blastoff!%
  ```

  This is the same script but written using % as a one-liner:

  ```
  set count 5%label loop%set count count-1%if count gt 0 loop%CT#narrator#Blastoff!%
  ```

  Mix and match however you like. `%` is only *required* when you want several
  things on one physical line, but it absolutely will hurt readability.

Pre-scripting demos still work:

- A stray `#` before the `%` is ignored (`wait#5000#%` and `wait#5000%` are the same thing).
- `wait#5000#%` and `wait 5000` mean the same thing.

Within a line, spaces separate the parts. If a value itself contains spaces,
put it in quotes: `set greeting "Hello there"`.

## The absolute basics

### Wait Packet

**To pause, use** `wait <milliseconds>`, so one second is 1000 milliseconds.

```
CT#narrator#Scene change incoming!%
wait 3000
BN#BOTC-TownSquare%
```

### Commands

Any `/` command works, exactly as if a User typed it. ([Command Reference](https://github.com/Crystalwarrior/KFO-Server/blob/master/docs/commands.md)) Remember,
commands need their `%`:

```
/say Welcome to the roleplay!%
/timer 0 60s start%
/pos_lock wit%
```

### Packets

**Packets**, aka what you use to send information to the user's client,
is the header followed by `#`-separated fields. A demo may
broadcast these headers: `MS`, `CT`, `MC`, `BN`, `HP`, `RT`, `JD`, `GM`, `ST`.
(if choosing between "Client" and "Server" version of the packet, use the "Server" packet)

```
CT#narrator#Hello everyone!%
MC#~stop.mp3#-1##1#0#5%
BN#BOTC-TownSquare%
```

* [MS packet](https://github.com/AttorneyOnline/docs/blob/master/docs/Development/network/MS%20Packet%20Reference.md) is the in-character message.
* [CT packet](https://github.com/AttorneyOnline/docs/blob/master/docs/Development/network/Packet%20Reference.md#CT-Server) is the OOC message.
* [MC packet](https://github.com/AttorneyOnline/docs/blob/master/docs/Development/network/Packet%20Reference.md#MC) is the Music Change packet and is responsible for playing music (use "Client as Receiver" version of the packet)
* [BN packet](https://github.com/AttorneyOnline/docs/blob/master/docs/Development/network/Packet%20Reference.md#BN) is the Background Name packet and is responsbile for changing the background.
* [HP packet](https://github.com/AttorneyOnline/docs/blob/master/docs/Development/network/Packet%20Reference.md#hp) updates the penalty bar values.
* [RT packet](https://github.com/AttorneyOnline/docs/blob/master/docs/Development/network/Packet%20Reference.md#rt) is the witness testimony, cross examination, or an arbitrary animation with a noise. It is unaffected by the message queue and shows up instantly.
* [JD packet](https://github.com/AttorneyOnline/docs/blob/master/docs/Development/network/Packet%20Reference.md#jd) decides if the judge controls (WTCE, penalty + - buttons in the theme) should appear or hide for the client.
* GM packet is the DRO GameMode packet. It decides what theme gamemode to set (Prefer using /subtheme)
* [ST packet](https://github.com/AttorneyOnline/docs/blob/master/docs/Development/network/Packet%20Reference.md#ST) is the SubTheme packet. It decides what subtheme of the theme to use. (Prefer using /subtheme)

Note that packets do not change state - this means that if you use BN, it will ONLY apply the
Background for the clients that received that packet until something else sends it again, while
/bg actually changes the area's Background persistantly meaning anyone new entering this area will
see the new background as well. This means you should prefer to use /commands unless you want to
send an IC message or don't want to modify the area details!


## Variables

Variables are user-defined names - `count`, `showname`, `score`, etc. - that hold one
value. They live on the area, so they're shared by every demo and trigger
running within that area.

```
set count 5
set count count+1   // adds 1, so count is now 6
set name "Miles"
set alias name      // alias copies name: "Miles"
```

Anything that isn't a quoted string or a variable name is treated as a math
expression. `+ - * / ( ) .` are all allowed:

```
set gold 10
set total gold*2+5  // total = 25
get need players+2  // need = number of players + 2
```

If you write a bare word that isn't a variable, the script stops with an error.
`set name Miles` without quotes fails, instead write `set name "Miles"`.

## Strings

Text goes in quotes, `"..."` or `'...'`. You can copy one variable into
another, and `if` can compare strings directly:

```
set name "Alice"                  // The name we're gonna use here
if name == "Alice" greet          // if name equals to Alice, go to the greet label
if name != "Bob" nogreet          // if name equals to Alice, go to the nogreet label
label greet
CT#narrator#Hello, <!name>!%      // Hello, Alice!
goto finish                       // Skip ahead so we don't say Goodbye by accident
label nogreet
CT#narrator#Goodbye, <!name>!%    // Goodbye, Bob!
label finish
CT#narrator#I eat boogers!%
```

Ordering comparisons (`==` equal to, `!=` not equal to, `<` less than, `>` greater than, `<=` less or equal to, `>=` greater or equal to) need both sides to be the same
kind - two numbers, or two strings. Comparing a number to a string stops the
script with an error.

## Putting live values in your text

`<!name>` anywhere in a packet or command drops in the current value:

```
set count 5
CT#narrator#Only <!count> more minutes!%
/say The score is <!score>%
```

You can also drop live state straight in - see below - so `<!players>` works
too.

## Reading the server's state

`get` reads a value and stores it in a variable. These special names are
always available:

| Name                  | What you get                              |
| --------------------- | ----------------------------------------- |
| `players`             | How many people are in the area           |
| `max_players`         | The area's player cap                     |
| `hp_def`              | The defense HP bar value                  |
| `hp_pro`              | The prosecution HP bar value              |
| `char_count`          | How many characters are on the server     |

```
get total players
CT#narrator#There are <!total> players here!%
```

### Digging deeper with paths

`get` can also walk into the server's state with a **path**:

| Path                      | What you get                                  |
| ------------------------- | --------------------------------------------- |
| `clients.count`           | Number of real clients in the area            |
| `client[i].<field>`       | Something about the i-th person in the area   |
| `timer[i].<field>`        | Something about the i-th timer                |
| `evidence.count`          | Number of evidence items in the area          |
| `evidence[i].<field>`     | Something about the i-th evidence item        |
| `links.count`             | Number of area links                          |
| `links[i].<field>`        | Something about the i-th area link            |
| `area.<field>`            | Something about the current area              |
| `hub.<field>`             | Something about the current hub               |

`client[0]` is the first person in the area, `client[1]` the second, and so on
- in the same order `/getarea` lists them. You can even use a custom variable as the
index: `client[i]`, `client[i+1]`.

```
get first client[0].showname
CT#narrator#First in the room: <!first>%
```

**Timers.** Timer numbers are the same ones `/timer` shows: `timer[0]` is the
hub-wide timer, `timer[1]` through `timer[20]` are the area's own.

| Field           | What you get                                  |
| --------------- | --------------------------------------------- |
| `remaining_ms`  | Millis left on the timer (0 if it isn't set)  |
| `static_ms`     | The time the timer was set to (0 if unset)    |
| `set`           | `1` if the timer is set/shown, else `0`       |
| `started`       | `1` if the timer is running, else `0`         |

```
get left timer[3].remaining_ms
if left == 0 timeout
CT#narrator#<left> ms left on the deliberation timer!%
```

**What you can read from a person:** `id`, `char_id`, `char_name`, `showname`,
`name` (their OOC name), `char_folder`, `pos`, `pair`, `iniswap`,
`last_move_time` (ms since their last action), `remote_listen`, `subtheme`,
`time_of_day`, `char_url`, and the yes/no flags `is_cm`, `is_gm`, `is_owner`,
`is_afk`, `hidden`, `blinded`, `sneaking`, `frozen`. Moderator-only
details like IP/HDID hashes and `is_mod` are not exposed to scripts.

```
if client[i].hidden eq 1 skip
get showname client[i].showname
concat list showname ", "
```

**What you can read from the area:**

- Identity and description: `name`, `id`, `abbreviation`, `desc`, `status`, `doc`
- Background and position: `background`, `background_dark`, `background_suffix`,
  `overlay`, `pos_lock` (space-separated positions, empty when unlocked),
  `bg_lock`, `overlay_lock`, `pos_dark`, `desc_dark`, `dark`
- Permissions and behavior: `can_cm`, `locking_allowed`, `iniswap_allowed`,
  `showname_changes_allowed`, `shouts_allowed`, `non_int_pres_only`,
  `evidence_mod`, `blankposting_allowed`, `blankposting_forced`,
  `ooc_actions_enabled`, `present_reveals_evidence`, `passing_msg`,
  `can_whisper`, `can_wtce`, `can_change_status`, `can_spectate`, `can_getarea`,
  `use_backgrounds_yaml`, `hide_clients`, `force_sneak`, `locked`, `muted`,
  `password`, `hidden`, `max_players`, `hp_def`, `hp_pro`, `move_delay`,
  `msg_delay`, `medieval_mode`
- Music: `music`, `music_autoplay`, `music_looping`, `music_effects`,
  `music_ref`, `replace_music`, `client_music`, `ambience`, `can_dj`, `jukebox`,
  `music_locked`
- Minigames: `can_battle`, `auto_pair`, `auto_pair_max`, `auto_pair_cycle`,
  `can_cross_swords`, `can_scrum_debate`, `can_panic_talk_action`, and the
  matching `*_song_start`, `*_song_end`, `*_song_concede` tracks

The yes/no flags above return `1` or `0`.

**What you can read from the hub:** `name`, `id`, `abbreviation`, `subtheme`,
`time_of_day`, `doc` (its description), `info` (same as `doc`), `char_count`,
`char_list_ref`, `music_ref`, `move_delay`, `current_areas` (how many areas the
hub has), and the yes/no flags `arup_enabled`, `hide_clients`, `can_gm`,
`single_cm`, `replace_music`, `client_music`, `can_spectate`, `can_getareas`,
`passing_msg`, `autokick_to_latest_area`, plus `max_areas`.

**What you can read from an evidence item.** `evidence[i]` is the i-th piece
of evidence, 0-based, in the order the area lists it. Fields: `name`, `desc`,
`image`, `pos` (the positions it shows in), `show_in_dark` (0 = never in dark
areas, 1 = always, 2 = only in dark areas), and the yes/no flags `can_hide_in`,
`can_take`, `editable`. Who is hiding inside a piece of evidence is not
exposed.

```
get count evidence.count
set i 0
label loop
if i ge count done
get item evidence[i].name
CT#narrator#Evidence <!i>: <!item>%
set i i+1
goto loop
label done
```

**What you can read from an area link.** A link is a one-way connection to
another area. `links[i]` is 0-based, in the order the links were created.
Fields: `target` (the area ID the link leads to), `target_pos` (the position
you arrive in), `evidence` (space-separated evidence IDs you must have to pass
through), `password`, and the yes/no flags `locked`, `hidden`, `can_peek`.

```
get count links.count
set i 0
label loop
if i ge count done
get target links[i].target
get locked links[i].locked
if locked eq 1 blocked
CT#narrator#To area <!target>: open%
goto next
label blocked
CT#narrator#To area <!target>: locked%
label next
set i i+1
goto loop
label done
```

Only these fields exist - scripts can't reach into anything else on the server.
If you ask for a path or field that doesn't exist, the script stops with an
error.

## Joining text: `concat`

`concat` adds text to the end of a string variable. Handy for making a list of
names:

```
set list ""
concat list "Miles"
concat list "Apollo" ", "     # list is now "Miles, Apollo"
CT#narrator#Players here: <!list>%
```

The third part is the separator, and it only appears *between* items - so the
list never starts or ends with a comma. The separator is optional.

## Random numbers: `rand`

`rand` stores a random whole number between `min` and `max`, both ends
included:

```
rand roll 1 6
CT#narrator#You rolled a <!roll>!%
```

The bounds can be numbers, expressions, or variables. If `min` is bigger than
`max`, the script stops with an error.

## Making decisions: `if`

`if` jumps to a label when a comparison is true:

```
if total ge 5 full
CT#narrator#Plenty of room!%
label full
```

The comparisons are `eq` (equal), `ne` (not equal), `lt` (less than), `gt`
(greater than), `le` (less or equal), `ge` (greater or equal). The usual
symbols work too: `==`, `!=`, `<`, `>`, `<=`, `>=`.

```
if count == 0 done
if count > 0 keepgoing
if name != "Alice" alert
```

Both sides can be numbers, strings, variables, or live paths - anything a value
can be.

## Loops and subroutines

`label` marks a spot, `goto` jumps to it. That's how you loop:

```
set count 5
label loop
CT#narrator#<!count>!%
wait 1000
set count count-1
if count > 0 loop
CT#narrator#Blastoff!%
```
turns into: 5! 4! 3! 2! 1! Blastoff!

`goto` remembers where it came from, and `return` jumps back. Use that for a
"subroutine" you want to run from several places:

```
goto roll_for_damage
goto roll_for_damage
label done
...
label roll_for_damage
rand dmg 1 8
CT#narrator#You dealt <!dmg> damage!%
return
```

If `return` has nowhere to return to, the script just ends - no error. So you
can use a bare `return` at the end of a script to stop it early. Labels are
scoped to the current script, and jumping to a label that doesn't exist stops
the script.

## When things go wrong

- Any error prints `[Demo] [ERROR] ...` to the area and stops the script. The
  area's HP bars and background are restored before it stops.
- A script can't run forever. After 100,000 steps it stops on its own
  (configurable in `config.yaml` as `demo_max_steps`) - so an accidental
  infinite loop can't stall the server.
- `/stop_demo` (GMs and mods) stops playback at any time, and `/demo` with no
  argument does too.

## A couple of extras

**Chaining.** A script can run another demo:

```
/demo 3%
```

That *replaces* the current script with demo 3 - labels start over. It's a
jump, not a subroutine; use `goto`/`return` within the same demo if you want to come back.

**Escaping.** If your text ever needs a literal `#`, `&`, `%`, or `$`, write
them as `<num>`, `<and>`, `<percent>`, `<dollar>`. Use `<percent>` if you need
a `%` inside a quoted value.

## Timers

Every area has 21 countdown timers: `0` is hub-wide, `1` through `20` belong to
the area. Anyone can check a timer with `/timer <id>`; setting and changing
them takes CM/GM rights (and timer `0` needs GM):

```
/timer 1 5m          set timer 1 to 5 minutes
/timer 1 start       start the countdown
/timer 1 pause       pause it (or `stop`)
/timer 1 +30s        add 30 seconds to whatever it's at now
/timer 1 unset       hide it and forget its time (or `hide`)
```

Your script reads timers through the live paths from the table above:

```
get left timer[3].remaining_ms
if left == 0 timeout
CT#narrator#<left> ms left on the deliberation timer!%
```

### Run a script when the timer expires

A timer holds a stack of commands that run the moment it hits zero. Queue them
in OOC with `/timer <id> /<command>`:

```
/timer 1 /demo 3               run demo 3 when timer 1 expires
/timer 1 /h Time's up!         announce it in hub chat
/timer 1 /timer 1 hide         also hide the timer when it expires
/timer 1 /clear                wipe all queued commands
/timer 1 /                     list what's queued
```

These lines are ordinary OOC commands, so a demo can arm a timer too - put
`/timer 1 5m start%` in your script and it sets and starts the timer, and a
`/timer 1 /demo 4%` line queues demo 4 to run on expiry. Commands run in order
through the area's system executor (the same headless client that runs demos),
so they fire even with no CM/GM online. A demo started this way shares the
area's variables with everything else.

## Triggers

Triggers watch for something happening in the area and run a command when it
does. Area triggers are `join` and `leave`; an evidence item can also have a
`present` trigger. Only normal players set them off - hidden clients, CMs,
GMs and mods are ignored.

```
/trigger join /demo 2
/trigger leave /h <showname> left
/trigger present 1 /demo 4
```

The command runs through the area's system executor, so it works even if no
CM or GM is around. You can type these in OOC or also use them as script lines!

**Inline variables.** Before the command runs, three placeholders are replaced
with the player who caused the trigger: `<cid>`, `<showname>`, and `<char>`.
`/trigger join /g <showname> just joined!` becomes `/g Miles just joined!`
when Miles joins.

**Script context.** A trigger also drops three values into the area's script
variables, which a `/demo` it runs can read:

| Variable            | What you get                          |
| ------------------- | ------------------------------------- |
| `trigger_cid`       | The player's client ID                |
| `trigger_showname`  | Their showname                        |
| `trigger_char`      | Their character name                  |

So demo 2 could greet the person who triggered it:

```
/trigger join /demo 2
```

```
CT#narrator#Welcome to the area, <!trigger_showname>!%
```

The values stay until the next trigger fires (or a script overwrites them), so
a demo has time to pick them up.

**One shared state.** Demos, trigger commands and timer-expiry commands all run
in the same area and share `area.variables`. A demo can leave a flag behind for
a trigger to check, and a trigger's demo can set things up for a timer expiry
that comes later.

## Example: list everyone present

```
set i 0
get total clients.count
set list ""
label loop
if i ge total done
if client[i].hidden eq 1 skip
get showname client[i].showname
concat list showname ", "
label skip
set i i+1
goto loop
label done
CT#narrator#Players here: <!list>%
```
