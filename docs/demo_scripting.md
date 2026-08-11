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
| `save <char> <key> <value>`    | Persist a value into a character's data       |
| `if <a> <op> <b> <label>`      | Jump to a label when a comparison is true     |
| `label <name>`                 | Mark a spot to jump to                        |
| `goto <name>`                  | Jump to a label (remembering where you were)  |
| `return`                       | Jump back to the matching `goto`; if there's nothing to return to, the script just ends    |

## Writing a script

A script is a list of lines. How a line ends depends on what it is:

- **Packets and `/` commands end with `%`.** They can even span multiple lines -
  the newlines inside them are part of the packet. A multi-line message works
  fine:

  ```
  CT#narrator#Hello..
  there..
  everyone!!!#0%
  ```

- **Everything else ends with `%` *or* a newline.**
  That means you can write a script with real line breaks:

  ```
  set count 5
  label loop
  set count count-1
  if count > 0 loop
  CT#narrator#Blastoff!#0%
  ```

  This is the same script but written using % as a one-liner:

  ```
  set count 5%label loop%set count count-1%if count > 0 loop%CT#narrator#Blastoff!#0%
  ```

  Mix and match however you like. `%` is only *required* when you want several
  things on one physical line, but it absolutely will hurt readability.

Pre-scripting demos still work:

- A stray `#` before the `%` is ignored (`wait#5000#%` and `wait#5000%` are the same thing).
- `wait#5000#%` and `wait 5000` mean the same thing.

Within a line, spaces separate the parts. If a value itself contains spaces,
put it in quotes: `set greeting "Hello there"`.

## The Basics

### Wait Packet

**To pause, use** `wait <milliseconds>`, so one second is 1000 milliseconds.

```
CT#narrator#Scene change incoming!#0%
wait 3000
BN#BOTC-TownSquare%
```

### Commands

Any `/` command works, exactly as if a User typed it. ([Command Reference](https://github.com/Crystalwarrior/KFO-Server/blob/master/docs/commands.md)) Remember,
commands need their `%`:

```
CT#narrator#Welcome to the roleplay!#0%
/timer 0 60s start%
/pos_lock wit%
```

### Packets

**Packets**, aka what you use to send information to the user's client,
is the header followed by `#`-separated fields. A demo may
broadcast these headers: `MS`, `CT`, `MC`, `BN`, `HP`, `RT`, `JD`, `GM`, `ST`.
(if choosing between "Client" and "Server" version of the packet, use the "Server" packet)

```
CT#narrator#Hello everyone!#0%
MC#~stop.mp3#-1##1#0#5%
BN#BOTC-TownSquare%
```

- [MS packet](https://github.com/AttorneyOnline/docs/blob/master/docs/Development/network/MS%20Packet%20Reference.md) is the in-character message.
- [CT packet](https://github.com/AttorneyOnline/docs/blob/master/docs/Development/network/Packet%20Reference.md#CT-Server) is the OOC message.
- [MC packet](https://github.com/AttorneyOnline/docs/blob/master/docs/Development/network/Packet%20Reference.md#MC) is the Music Change packet and is responsible for playing music (use "Client as Receiver" version of the packet)
- [BN packet](https://github.com/AttorneyOnline/docs/blob/master/docs/Development/network/Packet%20Reference.md#BN) is the Background Name packet and is responsbile for changing the background.
- [HP packet](https://github.com/AttorneyOnline/docs/blob/master/docs/Development/network/Packet%20Reference.md#hp) updates the penalty bar values.
- [RT packet](https://github.com/AttorneyOnline/docs/blob/master/docs/Development/network/Packet%20Reference.md#rt) is the witness testimony, cross examination, or an arbitrary animation with a noise. It is unaffected by the message queue and shows up instantly.
- [JD packet](https://github.com/AttorneyOnline/docs/blob/master/docs/Development/network/Packet%20Reference.md#jd) decides if the judge controls (WTCE, penalty + - buttons in the theme) should appear or hide for the client.
- GM packet is the DRO GameMode packet. It decides what theme gamemode to set (Prefer using /subtheme)
- [ST packet](https://github.com/AttorneyOnline/docs/blob/master/docs/Development/network/Packet%20Reference.md#ST) is the SubTheme packet. It decides what subtheme of the theme to use. (Prefer using /subtheme)

Note that packets do not change state - this means that if you use BN, it will ONLY apply the
Background for the clients that received that packet until something else sends it again, while
/bg actually changes the area's Background persistantly meaning anyone new entering this area will
see the new background as well. This means you should prefer to use /commands unless you want to
send an IC message or don't want to modify the area details!

## Variables

Variables are user-defined names - `count`, `showname`, `score`, etc. - that hold one
value. They live on the area, so they're shared by every demo and trigger
running within that area.

A `//` marks the rest of a line as a comment - the script skips it, so the
examples use it to explain what each line does:

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
if name != "Bob" nogreet          // if name isn't Bob, go to the nogreet label
label greet
CT#narrator#Hello, <!name>!#0%      // Hello, Alice!
goto finish                       // Skip ahead so we don't say Goodbye by accident
label nogreet
CT#narrator#Goodbye, <!name>!#0%    // Goodbye, Bob!
label finish
CT#narrator#I eat boogers!#0%
```

Ordering comparisons (`==` equal to, `!=` not equal to, `<` less than, `>` greater than, `<=` less or equal to, `>=` greater or equal to) need both sides to be the same
kind - two numbers, or two strings. Comparing a number to a string stops the
script with an error.

## Variables in Text

`<!name>` anywhere in a packet or command drops in the current value:

```
set count 5
CT#narrator#Only <!count> more minutes!#0%
set score 10
CT#narrator#The score is <!score>#0%
```

You can also drop live state straight in - see below - so `<!players>` works
too.

## Reading Server Values

`get` reaches into the server, reads one value, and stashes it in a variable.
From then on you can use that variable anywhere in the script:

```
get total players
CT#narrator#There are <!total> players here!#0%
```

A few handy values are always available without any setup:

| Name          | What it is                                      |
| ------------- | ----------------------------------------------- |
| `players`     | How many people are in The area right now       |
| `max_players` | The most people The area allows                 |
| `hp_def`      | The defense side's penalty bar                  |
| `hp_pro`      | The prosecution side's penalty bar              |
| `char_count`  | How many characters the server has              |

### Paths

Everything else needs a **path** - one long name that points at an exact thing.
A path is an address: *what kind of thing*, *which one*, and *what you want to
read off it*:

```
client[0].showname
│       │     └─ what you want to read
│       └─ which one (0 = the first)
└─ what kind of thing
```

Here's the whole menu. Each row is its own section just below.

| Path                     | What it points at                             | Section         |
| ------------------------ | --------------------------------------------- | --------------- |
| `clients.count`          | How many people are in The area               | Clients         |
| `client[i].<field>`      | One person in The area                        | Clients         |
| `afk[i].<field>`         | A person who's marked AFK                     | Clients         |
| `timer[i].<field>`       | A countdown timer                             | Timers          |
| `evidence[i].<field>`    | A piece of evidence                           | Evidence        |
| `links[i].<field>`       | A door to another area                        | Area links      |
| `area.<field>`           | The area you're in                            | The area        |
| `hub.<field>`            | The hub your area is in                       | The hub         |
| `char[<name>].<key>`     | A character's saved data                      | Character data  |

Two small rules make paths easy to read:

- **Counting starts at zero.** The first person is `client[0]`, the second is
  `client[1]`, the third `client[2]`... It's the same for evidence, links,
  timers and AFK people.
- **`.count` gives a total.** Swap the `[i]` for `.count` to get how many
  there are: `clients.count`, `evidence.count`, `links.count`, `afk.count`.

The number in the brackets doesn't have to be typed out - it can be a variable,
so loops can walk through everyone (`client[i]`, `client[i+1]`). Ask for a path
or field that doesn't exist and the script stops with an error, so the lists
below are the whole menu.

### Clients

`client[0]` is the first person The area lists, `client[1]` the second, and so
on. `afk[i]` works the same way but only for people marked AFK (with `/afk`);
both read the same fields.

What you can read off a person:

| Field            | What it is                                          |
| ---------------- | --------------------------------------------------- |
| `id`             | The player's user number (the `[User]` number)      |
| `name`           | Their OOC name                                      |
| `char_name`      | The name of the character they're playing           |
| `char_id`        | Their character's number (see `/charids`)           |
| `char_folder`    | Their character's folder name                       |
| `showname`       | The name above their head (falls back to their character's name) |
| `pos`            | The position they're standing in                    |
| `pair`           | The character they're paired with (`-1` = not paired) |
| `iniswap`        | The character they look like via `/iniswap` (empty = normal) |
| `hidden_in`      | The evidence they're hiding in (empty = not hiding) |
| `listen_pos`     | Positions they're listening to (empty = the whole area) |
| `last_move_time` | A timestamp of when they last moved or spoke        |
| `subtheme`       | The subtheme they're forced to see (empty = normal) |
| `time_of_day`    | The time of day they're forced to see (empty = normal) |
| `char_url`       | The link shown on their character                   |
| `remote_listen`  | Their remote listening: `0` none, `1` IC only, `2` OOC, `3` everything |

The flags below come back as `1` (yes) or `0` (no):

| Flag         | `1` means...                  |
| ------------ | ----------------------------- |
| `is_cm`      | They're a CM of The area      |
| `is_gm`      | They're a GM of the hub       |
| `is_owner`   | They're a CM or GM            |
| `is_afk`     | They're marked AFK            |
| `hidden`     | They're hidden                |
| `blinded`    | They're blinded               |
| `sneaking`   | They're sneaking              |
| `frozen`     | They're frozen                |

```
set i 0
if client[i].hidden == 1 skip
get showname client[i].showname
concat list showname ", "
label skip
```

For safety, mod-only details such as IP/HDID hashes and `is_mod` are never
given to scripts.

### Timers

`timer[0]` is the hub-wide timer; `timer[1]` through `timer[20]` are The area's
own - the same numbers `/timer` shows.

| Field          | What it is                                     |
| -------------- | ---------------------------------------------- |
| `remaining_ms` | Milliseconds left (0 if it isn't running)      |
| `static_ms`    | The time it was set to (0 if it isn't set)     |
| `set`          | `1` if a timer is set/shown, else `0`          |
| `started`      | `1` if it's counting down, else `0`            |

```
get left timer[3].remaining_ms
if left == 0 timeout
CT#narrator#<!left> ms left on the deliberation timer!#0%
return
label timeout
CT#narrator#Time's up!#0%
```

### Evidence

`evidence[i]` is the i-th piece of evidence, in the order The area lists it.

| Field          | What it is                                          |
| -------------- | --------------------------------------------------- |
| `name`         | The evidence's name                                 |
| `desc`         | Its description                                     |
| `image`        | Its image file                                      |
| `pos`          | The positions it shows in                           |
| `show_in_dark` | `0` = never in dark areas, `1` = always, `2` = dark areas only |
| `hiding`       | The showname of whoever is hidden inside (empty if nobody) |
| `can_hide_in`  | `1` if people can hide in it                        |
| `can_take`     | `1` if it can be taken                              |
| `editable`     | `1` if players can edit it                          |

```
get count evidence.count
set i 0
label loop
if i >= count done
get item evidence[i].name
CT#narrator#Evidence <!i>: <!item>#0%
set i i+1
goto loop
label done
```

### Area links

A link is a one-way door to another area. `links[i]` walks through them in the
order they were made.

| Field         | What it is                                       |
| ------------- | ------------------------------------------------ |
| `target`      | The area number the link leads to                |
| `target_pos`  | The position you arrive in                       |
| `evidence`    | Evidence numbers you must have to pass (space-separated) |
| `password`    | The password to pass (empty = none)              |
| `locked`      | `1` if the link is locked                        |
| `hidden`      | `1` if the link is hidden                        |
| `can_peek`    | `1` if you can peek through it                   |

```
get count links.count
set i 0
label loop
if i >= count done
get target links[i].target
get locked links[i].locked
if locked == 1 blocked
CT#narrator#To area <!target>: open#0%
goto next
label blocked
CT#narrator#To area <!target>: locked#0%
label next
set i i+1
goto loop
label done
```

### The area

The area you're in is spelled `area` in paths - `area.<field>`. You can read
its name and looks, what people are allowed to do, the music, and the
minigames.

What The area is called and how it looks:

| Field               | What it is                                        |
| ------------------- | ------------------------------------------------- |
| `name`              | The area's name                                   |
| `id`                | The area's number                                 |
| `abbreviation`      | The area's short code                             |
| `desc`              | Its description                                   |
| `status`            | Its status tag                                    |
| `doc`               | Its info page                                     |
| `background`        | The current background                            |
| `background_dark`   | The background used in dark mode                  |
| `background_suffix` | A suffix added to every background name           |
| `overlay`           | The overlay image                                 |
| `pos_lock`          | Allowed positions, space-separated (empty = any)  |
| `bg_lock`           | `1` if only CMs can change the background         |
| `overlay_lock`      | `1` if only CMs can change the overlay            |
| `pos_dark`          | Positions allowed in dark mode                    |
| `desc_dark`         | The description shown in dark mode                |
| `dark`              | `1` if The area is in dark mode                   |

What people are allowed to do (flags are `1` for yes, `0` for no):

| Field                        | `1` means...                                    |
| ---------------------------- | ----------------------------------------------- |
| `can_cm`                     | Players can become CM here                      |
| `locking_allowed`            | CMs can lock/unlock links                       |
| `iniswap_allowed`            | `/iniswap` is allowed                           |
| `showname_changes_allowed`   | Players can change their showname               |
| `shouts_allowed`             | Shouting is allowed                             |
| `non_int_pres_only`          | Only non-interrupting presents are allowed      |
| `evidence_mod`               | How evidence is shared (`FFA`, `CM`, `Mods`, `HiddenCM`) |
| `blankposting_allowed`       | Blank posts are allowed                         |
| `blankposting_forced`        | Every IC post must be blank                     |
| `ooc_actions_enabled`        | OOC actions are on                              |
| `present_reveals_evidence`   | Presenting shows the evidence to everyone       |
| `passing_msg`                | `/passing` is enabled                           |
| `can_whisper`                | Whispers are allowed                            |
| `can_wtce`                   | Witness testimony / cross-exam is allowed       |
| `can_change_status`          | Players can change their status                 |
| `can_spectate`               | Spectating is allowed                           |
| `can_getarea`                | Players can see The area list                   |
| `use_backgrounds_yaml`       | Backgrounds come from `backgrounds.yaml`        |
| `hide_clients`               | The player list is hidden                       |
| `force_sneak`                | Everyone appears hidden                         |
| `locked`                     | The area is locked (no one can enter)           |
| `muted`                      | IC chat is muted                                |
| `password`                   | The password to enter (empty = none)            |
| `hidden`                     | The area is hidden from The area list           |
| `max_players`                | The most people allowed                         |
| `hp_def`                     | The defense penalty bar                         |
| `hp_pro`                     | The prosecution penalty bar                     |
| `move_delay`                 | Extra delay between moves, in milliseconds      |
| `msg_delay`                  | Delay between IC messages, in milliseconds      |
| `medieval_mode`              | Medieval mode is on                             |

The music:

| Field            | What it is                                       |
| ---------------- | ------------------------------------------------ |
| `music`          | The current song                                 |
| `music_autoplay` | `1` if the song autoplays                        |
| `music_looping`  | `1` if the song loops                            |
| `music_effects`  | The current sound effect                         |
| `music_ref`      | Which music list The area uses                   |
| `replace_music`  | `1` if The area's music overrides the hub's      |
| `client_music`   | `1` if players can play their own music          |
| `ambience`       | The ambience track                               |
| `can_dj`         | `1` if players can DJ                            |
| `jukebox`        | `1` if the jukebox is on                         |
| `music_locked`   | `1` if the music is locked                       |

Minigames:

| Field                                                       | What it is                                          |
| ----------------------------------------------------------- | --------------------------------------------------- |
| `can_battle`                                                | `1` if the battle minigame is allowed               |
| `auto_pair`                                                 | `1` if auto-pairing is on                           |
| `auto_pair_max`                                             | The longest auto-pair allowed                       |
| `auto_pair_cycle`                                           | `1` if pairs cycle through positions                |
| `can_cross_swords`                                          | `1` if the cross-swords minigame is allowed         |
| `can_scrum_debate`                                          | `1` if the scrum-debate minigame is allowed         |
| `can_panic_talk_action`                                     | `1` if the panic-talk-action minigame is allowed    |
| `cross_swords_song_start` / `_song_end` / `_song_concede`   | Music when that minigame starts / ends / is conceded |
| `scrum_debate_song_start` / `_song_end` / `_song_concede`   | Same, for scrum debate                               |
| `panic_talk_action_song_start` / `_song_end` / `_song_concede` | Same, for panic talk action                       |

### The hub

The hub is the group of areas your area belongs to - it decides the shared
character list, music list and movement delay. It's spelled `hub` in paths -
`hub.<field>`.

| Field                   | What it is                                         |
| ----------------------- | -------------------------------------------------- |
| `name`                  | The hub's name                                     |
| `id`                    | The hub's number                                   |
| `abbreviation`          | The hub's short code                               |
| `subtheme`              | The subtheme applied to every area                 |
| `time_of_day`           | The time of day applied to every area              |
| `doc`                   | The hub's description                              |
| `info`                  | Same as `doc`                                      |
| `char_count`            | How many characters the hub has                    |
| `char_list_ref`         | The character list file it uses                    |
| `music_ref`             | The music list it uses                             |
| `move_delay`            | Delay between moves for every area, in milliseconds |
| `current_areas`         | How many areas the hub has                         |
| `max_areas`             | The most areas allowed                             |
| `arup_enabled`          | `1` if the player-count announcement is on         |
| `can_gm`                | `1` if players can become GM                       |
| `single_cm`             | `1` if only one CM per area is allowed             |
| `hide_clients`          | `1` if player lists are hidden                     |
| `replace_music`         | `1` if server music overrides hub music            |
| `client_music`          | `1` if players can play their own music            |
| `can_spectate`          | `1` if spectating is allowed                       |
| `can_getareas`          | `1` if players can see The area list               |
| `passing_msg`           | `1` if `/passing` is enabled                       |
| `autokick_to_latest_area` | `1` if players are sent back to their last area  |

## Character data: remembering things between demos

Area variables live and die with the demo. **Character data** is the
persistent store: a bag of `key: value` pairs per character, saved to
`config/character_data.yaml`, surviving restarts, and shared by every area in
the hub. GMs already use it for keys, descriptions, movement delay and
inventory; demos and triggers can use it for anything else.

**Read** a saved value with the `char` path. `<name>` is a **character id**
(the index into the server's character list — the number `/charids` shows,
not the client/user id) or a quoted folder name (`char["Phoenix"]`):

```
get title char["Phoenix"].title
CT#narrator#Hello, <!title>!#0%
```

The special keys `.count` (how many keys that character has) and `.fields`
(their names, space-separated) don't need to be stored to be read. A key that
was never saved reads back as an empty string; a list value reads back as its
items joined with spaces.

**Write** a value with `save`. The character is written the same way as the
read path's `<name>` — a **character id** (index into the character list, as
`/charids` shows) or a quoted folder name (`"Phoenix"`) — just without the
brackets. The key is a plain word, and the value can be a
number (or expression), a quoted string, a variable, or a live path:

```
save "Phoenix" title "Attorney"
save 0 points 5
set gold 10
save 0 gold gold+10
save 0 lastarea area.name
```

Anything that isn't a number, variable, quoted string or live path is stored
verbatim as a string, so `save 0 note He's holding a badge` stores exactly
`He's holding a badge`. `save` writes the file to disk immediately, so data
you save here is there next time the server restarts.

**GMs** can inspect and edit the same data from OOC without a demo:

| Command | What it does |
| --- | --- |
| `/get_char_data Phoenix` | lists every key for the character |
| `/get_char_data Phoenix title` | shows just that key |
| `/set_char_data Phoenix title Attorney` | sets a key |
| `/set_char_data Phoenix title` | removes the key (no value) |

Character data is one of the few places a demo writes persistent state, so it
doubles as a shared "blackboard": a trigger's demo can `save` a flag that a
later timer-expiry demo reads with `char[...]`, and it survives the server
being restarted in between.

## Joining text: `concat`

`concat` adds text to the end of a string variable. Handy for making a list of
names:

```
set list ""
concat list "Miles"
concat list "Apollo" ", "     // list is now "Miles, Apollo"
CT#narrator#Players here: <!list>#0%
```

The third part is the separator, and it only appears *between* items - so the
list never starts or ends with a comma. The separator is optional.

## Random numbers: `rand`

`rand` stores a random whole number between `min` and `max`, both ends
included:

```
rand roll 1 6
CT#narrator#You rolled a <!roll>!#0%
```

The bounds can be numbers, expressions, or variables. If `min` is bigger than
`max`, the script stops with an error.

## Making decisions: `if`

`if` jumps to a label when a comparison is true:

```
get total players
if total >= 5 full
CT#narrator#Room's not full yet!#0%
return
label full
CT#narrator#Room's full!#0%
```

The comparisons use the usual symbols: `==` equal, `!=` not equal, `<` less
than, `>` greater than, `<=` less or equal, `>=` greater or equal. (The words
`eq`, `ne`, `lt`, `gt`, `le`, `ge` mean the same thing and also work.)

```
set count 3
set name "Miles"
if count == 3 three
if name != "Alice" stranger
CT#narrator#Checking done!#0%
return
label three
CT#narrator#Count is three!#0%
return
label stranger
CT#narrator#A stranger!#0%
```

Both sides can be numbers, strings, variables, or live paths - anything a value
can be.

## Loops and subroutines

`label` marks a spot, `goto` jumps to it. That's how you loop:

```
set count 5
label loop
CT#narrator#<!count>!#0%
wait 1000
set count count-1
if count > 0 loop
CT#narrator#Blastoff!#0%
```

turns into: 5! 4! 3! 2! 1! Blastoff!

`goto` remembers where it came from, and `return` jumps back. Use that for a
"subroutine" you want to run from several places:

```
goto roll_for_damage
goto roll_for_damage
return
label roll_for_damage
rand dmg 1 8
CT#narrator#You dealt <!dmg> damage!#0%
return
```

The two `goto`s run the same block twice - you see two damage rolls - then the
`return` at the end of the main script finishes it (there's nothing left to
return to).

If `return` has nowhere to return to, the script just ends - no error. So you
can use a bare `return` at the end of a script to stop it early. Labels are
scoped to the current script, and jumping to a label that doesn't exist stops
the script.

## Timers

Every area has 21 countdown timers: `0` is hub-wide, `1` through `20` belong to
the area. Anyone can check a timer with `/timer <id>`; setting and changing
them takes CM/GM rights (and timer `0` needs GM):

| Command | What it does |
| --- | --- |
| `/timer 1 5m` | set timer 1 to 5 minutes |
| `/timer 1 start` | start the countdown |
| `/timer 1 pause` | pause it (or `stop`) |
| `/timer 1 +30s` | add 30 seconds to whatever it's at now |
| `/timer 1 unset` | hide it and forget its time (or `hide`) |

Your script reads timers through the live paths from the table above:

```
get left timer[3].remaining_ms
CT#narrator#<!left> ms left on the deliberation timer!#0%
```

### Run a script when the timer expires

A timer holds a stack of commands that run the moment it hits zero. Queue them
in OOC with `/timer <id> /<command>`:

| Command | What it does |
| --- | --- |
| `/timer 1 /demo 3` | run demo 3 when timer 1 expires |
| `/timer 1 /h Time's up!` | announce it in hub chat |
| `/timer 1 /timer 1 hide` | also hide the timer when it expires |
| `/timer 1 /clear` | wipe all queued commands |
| `/timer 1 /` | list what's queued |

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

| Command | Runs when |
| --- | --- |
| `/trigger join /demo 2` | someone joins |
| `/trigger leave /h <showname> left` | someone leaves (announces in hub chat) |
| `/trigger present 1 /demo 4` | evidence item 1 is presented |

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
CT#narrator#Welcome to the area, <!trigger_showname>!#0%
```

The values stay until the next trigger fires (or a script overwrites them), so
a demo has time to pick them up.

**Everything shares the same variables.** A demo, a trigger's command and a
timer's command all run in the same room and read and write the same
variables. So one script can write a note that a later script reads. For
example, a trigger starts /demo 2, which sets:

```
set door_open 1
```

When the timer later runs its /demo 1 command, that script can check the note:

```
if door_open == 1 open_the_door
CT#narrator#The door stays shut.#0%
return
label open_the_door
CT#narrator#The door is open!#0%
```

The note is still there even though the demo that wrote it has finished.

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

The current script stops, and demo 3 starts from the top as if you'd just run
it with `/demo 3`. Anything the current script set up (like labels or a place
to `return` to) is gone - you can't come back to it. If you need to hop around
and come back, use `goto` and `return` inside the *same* demo instead.

**Escaping.** If your text ever needs a literal `#`, `&`, `%`, or `$`, write
them as `<num>`, `<and>`, `<percent>`, `<dollar>`. Use `<percent>` if you need
a `%` inside a quoted value.

## Example: list everyone present

```
set i 0
get total clients.count
set list ""
label loop
if i >= total done
if client[i].hidden == 1 skip
get showname client[i].showname
concat list showname ", "
label skip
set i i+1
goto loop
label done
CT#narrator#Players here: <!list>#0%
```
