## TsuserverDR 3
### 180801 (3.0.1)
* Added /time12

### 180812 (3.1)
* Added /ddroll, /ddrollp for rolls with modifiers
* Added 'rp_getarea(s)' attributes to restrict /getarea(s)
* Added /toggle_rpgetarea(s) to change the above attribute
* Added /st for staff-only chat
* /g now includes OOC usernames as opposed to charname

### 180910 (3.2)
* Added reachable areas support with
  - /unilock
  - /bilock
  - /delete_areareachlock
  - /restore_areareachlock
* Added proper support for spectators (can talk OOC/use commands/change music&areas/use judge buttons now)
* Added support for IC locking with /iclock
* OOC usernames may no longer include the hostname or global message prefixe
* Fixed /kick crash on unrecognized parameters

### 190126 (3.3)
* Added AFK kicks
* Added user-initiated timers with
  - /timer start
  - /timer get
  - /timer cancel
* Area lists now only list reachable areas

### 190225 (3.4)
* Added inter-area OOC communication with /scream
* Added debugging tool /exec
* Added inter-area music setting with /rplay
* Renamed /ddroll -> /roll, /ddrollp -> /rollp

### 190323 (3.5)
* Added sneak support with /sneak and /reveal
* Added inter-area IC announcements with /globalic, /unglobalic
* Added server custom shownames with /shownames
* Added soundproof area attribute
* Expanded inter-area OOC communication with /knock

### 190519 (3.6)
* Added support for custom music lists with /music_list
* Added area list reloading with /area_list
* Added character restriction on a per-area basis with /char_restrict
* Added scream ranges on a per-area basis (deprecating soundproof attribute)
* Default server configuration now uses DRO standards

### 190602 (3.7)
* Added automatic passing messages with /autopass
* Added passage lock transientness with /transient
* Added showname moderation tools
  - /showname_freeze
  - /showname_history
  - /showname_list
  - /showname_nuke
  - /showname_set
* Enforced showname uniqueness per area
* Fixed /area_kick crash on unrecognized parameters
* Fixed /getareas listing an empty area if only people there are sneaking
* Players on server select no longer count in online playercount, nor in /getarea[s] and /area

### 190609 (3.8)
* Added movement handicaps with /handicap, /unhandicap
* Added area lights with /lights
* Added blood trails with
  - /bloodtrail
  - /bloodtrail_clean
  - /bloodtrail_list
  - /bloodtrail_set
* Added /toggle_shownames to disable receiving server shownames
* Allowed for more DRO client effects being used
* Fixed /autopass not sending messages from or for staff

### 190618 (first with date version system) (3.9)
* Added area descriptions with /look, /look_set
* Console now displays server opening/closing/reconnecting messages.
* Python errors now show additional debugging info on server log+client if error came as a result of command
* Renamed some commands
  - allow_iniswap -> /can_iniswap
  - delete_areareachlock -> /passage_clear
  - restore_areareachlock -> /passage_restore
  - toggle_areareachlock -> /can_passagelock
  - toggleglobal -> /toggle_global
  - toggle_rollp -> /can_rollp
  - toggle_rpgetarea -> /can_rpgetarea
  - toggle_rpgetareas -> /can_rpgetareas
* Reworked /area_kick so that it now allows area names as parameter
* Reworked /discord so that it now shows the server's Discord server invite link
* Fixed /autopass sending old character name in case of forced char switch on area change
* Fixed /bloodtrail_set not enforcing staff member rank
* Fixed /disemconsonant and /remove_h not working/crashing
* Fixed /follow allowing to follow yourself
* Fixed "Knock" client effect not being sent

### 190630 (3.10)
* Added support for user initiated day cycles with
  - /clock
  - /clock_cancel
  - /clock_pause
  - /clock_unpause
* Added various moderation tools
  - /judgelog
  - /shoutlog
  - /version
  - /whereis
* Added 'has_lights' parameters to areas to allow/disallow using /lights
* Enforced different staff passwords on server configuration
* Shouts now show character used as opposed to OOC name
* Turning lights on reveals who is bleeding and not sneaking
* Fixed area lists allowing for empty parameters
* Fixed blood announcements sent to wrong areas occasionally
* Fixed /kick requiring no arguments
* Fixed music flood guard crash
* Fixed server ghosting on master server list on incorrect server closing
* Fixed pre2.2.5 clients being unable to join

### 190708 (3.11)
* Added various moderation/debugging tools
  - /lasterror
  - /multiclients
  - /whois
* Added area parameters to allow for non-staff use of custom backgrounds/music
* Added /toggle_allrolls so staff get roll notifications from other areas
* Day cycle notifications now send 'CL' packets to clients
* GMs can no longer /area_kick users from lobby areas
* Renamed timer commands
  - /timer start -> /timer
  - /timer get -> /timer_get
  - /timer cancel -> /timer_cancel
* Fixed a player not unfollowing a player who disconnects and then crashing on area change
* Fixed /roll crashing on too many arguments

### 190721 (3.12)
* Added global IC prefixes with /globalic_pre
* Added first person mode with /toggle_fp
* Banned players now receive 'You are banned from this server' notifications on attempting to join+Notifies mods of this attempt
* Global IC messages now send notifications on each use
* Made daily gmpasses optional
* Multiple players may now follow the same player
* Renamed some commands from /toggle to /can
* Fixed clients being able to join too quickly on server select and crashing

## TsuserverDR 4.0 (The Party Update)

### 190801 (4.0)
* Added party support so players move with one another automatically with
  - /party
  - /party_disband
  - /party_id
  - /party_invite
  - /party_join
  - /party_kick
  - /party_lead
  - /party_list
  - /party_members
  - /party_uninvite
  - /party_unlead
* Added HDID bans with /banhdid, /unbanhdid
* CMs now get IPIDs in /getarea(s), /showname_list and /whois, as well as HDID in /whois
* Iniswapped folders are now shown with /whois
* Fixed security issue with webAO
* TsuserverDR now uses semantic versioning.

### 190801b (4.0.1)
* Introduced CI testing on Travis

### 190802 (4.0.2-4.0.3)
* Fixed server player limit not being enforced

### 190805 (4.0.4)
* Fixed invalid characters crash with /area_list and /music_list

### 190806 (4.0.5)
* Fixed logging in to a second rank making you keep the first one

## TsuserverDR 4.1 (The Sense Block Update)

### 190819 (4.1)
* Added sense block support with
  - /blind
  - /deaf
  - /gag
* Added /bloodtrail_smear to smear blood trails in the area
  - If player is blind or area lights are out, /bloodtrail_clean effectively runs this instead
* Added /ping to check for lost connection
* Added /showname_area to list shownames just in the current area
* CMs now receive Call Mod notifications
* Renamed /mutepm -> /toggle_pm, /showname_list -> /showname_areas
* Started including additional marks to certain staff privileged RP notifications
* Minor changes to messages sent on area change
  - Staff now receive autopass messages if lights are off instead of regular lights off messages
  - Reworded messages sent if someone arrives/leaves while bleeding/lights off and sneaking
  - Players now receive special notification if there is blood in the area and lights are off
* Fixed global IC OOC notifications showing message went one area past the last area actually sent to
* Fixed IPIDs on rare occasions being non-trivially not unique
* Fixed /pm not sending complete character names to recipient
* Minor bugfixes with respect to bleeding
  - Blood cleaning notifications will no longer be sent with lights off
  - Blood will now automatically be spilled on the area as soon as /bloodtrail is executed, not only on area change

### 190820 (4.1.1)
* Added special marks to more staff privileged RP notifications
* Reworded global IC notification messages

### 190822 (4.1.2)
* Added more special marks to more staff privileged RP notifications
* Normal players now get who cleaned/smeared blood in area if they are not blind and the lights are on

### 190903 (4.1.3)
* Renamed repository to TsuserverDR
* Added more special marks to more staff only RP notifications
* Fixed /multiclients failing for GMs/CMs on non-staff targets while in RP mode

### 190904 (4.1.4)
* Gagged messages are now randomly generated
* Staff get new messages when using /bloodtrail, with privilege marks added where needed

## TsuserverDR 4.2 (The DRO 2nd Anniversary Update/The Zone and Poison Update)

### 191031 (4.2)
* Added zones. Zones are groups of areas such that any privileged server notifications that come from a player action within the zone will be sent only to "watchers", who are people who watch the zone. They come with the following commands:
  - /zone
  - /zone_add
  - /zone_delete
  - /zone_global (alias /zg)
  - /zone_list
  - /zone_play
  - /zone_remove
  - /zone_unwatch
  - /zone_watch
* Zones will send notifications to all zone watchers for standard RP notifications as well as the following:
  - Players coming IN and OUT of the zone (with their shownames)
  - Players coming in a zone while having other clients open in the zone
  - Players in the zone disconnecting
  - Players in the zone changing character
  - Players in the zone changing showname
* Added poison through /poison. Poisoned targets will be inflicted an assortment of effects at the end of a timer (currently a selection of blindness, deafness and gagged). Targets can have their poison removed before it affects them by having /cure run on them
  - /cure will also remove effects if they have been already applied
* Improved password-less process of GM logins:
  - Added /make_gm so CMs and mods can log in other players as GMs
  - Added /gmself so GMs can log in all other clients they opened as GMs
* Custom shownames now appear if set in server notifications instead of character folders
* Improved /help
  - It can now take a command name and it will show a brief description and expected syntax, as well as the minimum required rank if the player is not authorized to use it
* Improved roll management mechanics
  - Added dice log commands to retrieve roll history through /dicelog (for one player) and /dicelog_area (for one area)
  - Roll options are now modifiable from server configurations
* Improved information sent to moderators on mod actions
  - /ban, /banhdid and /kick notifications are now sent to all mods and CMs in the server, as well as appropiate information on the targets.
* Reworded notifications for the following mechanics
  - Rolls failing
  - Enabling/disabling IC locks
  - Setting your own showname, or someone else's showname
  - Characters becoming restricted in an area
  - Revoking/restoring DJ permissions
* The following actions now send an IC message in conjunction with an OOC notification:
  - /knock (which has been restricted to non-lobby areas only)
  - /scream
* Private servers will now include the masterserver name when showing the server IP in the terminal
* Fixed clients with same HDID but different IPID not being recognized as multiclients. This fixes the following:
  - Players getting a new IP can now kick ghosting clients under their old IP with /kickself
  - Staff can now recognize such situations with /whois or /multiclients
* Fixed /play and /rplay not looping music tracks that appear in the server music list
* Fixed daily GM passwords switching at 3 pm incorrectly, they now switch correctly and at midnight
* Fixed day cycles not canceling on area list reload
* Fixed single space messages sent by gagged players not blankposting but being converted to jumbled text
* Fixed GMs receiving IPID information through /multiclients
* Explicitly allowed Python 3.8 support for server owners

### 191031b (4.2.0-post1)
* Fixed uncaught ValueError if server files do not contain a valid README.md when attempting to generate help text for commands
* Fixed zones being able to obtain duplicate zone ID values

### 191109a (4.2.0-post2)
* Fixed /multiclients not considering same HDID users as multiclients
* Fixed /unban considering the unbanning of an already unbanned person as an invalid IPID
* Reorganized /ban and /unban text to include backticks surrounding argument
* Made /unban notify all other mods and CMs in the server whenever executed
* Fixed /narrate crashing on use
* Fixed changelog listing incorrect dates for 4.2.0 releases

### 191122a (4.2.0-post3)
* Fixed /zone_watch and /zone_delete raising an uncaught KeyError if an invalid zone name was passed as an argument
* Fixed rare issue with new AWS instances raising a certificate error when pinging api.ipify.org on server boot-up
* Made unrecoverable server errors expect an operator Enter input on console before finishing the program so that they can see the error message if they launched the server by double-clicking `start_server.py`
* Made error log files be created if the server crashes on bootup, which would normally happen if some files are missing or have some parsing errors
* Fixed master server connection not being closed automatically on server shutdown, which displayed ignored exception messages if running Python 3.8

### 191209a (4.2.1)
* Added deprecation warnings to the following commands
  - **allow_iniswap**: Same as /can_iniswap.
  - **delete_areareachlock**: Same as /passage_clear.
  - **mutepm**: Same as /toggle_pm.
  - **restore_areareachlock**: Same as /passage_restore.
  - **showname_list**: Same as /showname_areas.
  - **toggleglobal**: Same as /toggle_global.
  - **toggle_areareachlock**: Same as /can_passagelock.
  - **toggle_rollp**: Same as /can_rollp.
  - **toggle_rpgetarea**: Same as /can_rpgetarea.
  - **toggle_rpgetareas**: Same as /can_rpgetareas.
* Added /files and /files_set for custom file linking
* Added logging messages to the server logs when the server starts up, shuts down, or it crashes and the server can manage to save the log
* Server logs files are now separated by month. Logging information will go to the file associated with the month and year the server was last launched on (so if in one session the server was launched December 2019 and was shut down January 2020, all logs for that session would go in `logs/server-2019-12.log`).
  - `logs/server.log` will now go unused, but server owners may keep this file for their archives.
* Improved cross-compatibility between multiple AO-like clients. For client-exclusive features, a best-effort-like approach will be taken to adapt to clients that do not have said features.
* Improved /help message so that it suggests to use the extended syntax (/help "command name") to get help with a particular command
* Improved README.md instructions so that server installation steps are more clear
* Fixed minor typos in `config_sample/config.yaml`
* Fixed /area_kick'ing someone off a locked area under special circumstances allowing the target to rejoin the locked area
* Fixed /help not showing extended syntax (/help "command name") when running /help help
* Fixed /narrate messages being replaced for deafened players
* Fixed /poison effects kicking in being notified to all players in the server as opposed to zone watchers or staff members if target is in an area not in a zone

### 191224a (4.2.2)
* Added /whisper for IC private communications between players (meant to be used for RPs, as staff members can read the contents of the message)
* Added /guide for providing personalized guidance specific to a particular player
* Made /invite be a public command as opposed to GM+
* Added helpful commands-to-run-next suggestions for the following actions
  - Setting files.
  - Setting up global IC messages
  - Creating/being invited to a party.
  - Entering a zone you that a GM+ is not watching/leaving a zone a GM+ is watching.
  - Logging in in an area part of a zone.
  - Being in an area when a zone is created involving that area, or that area is added to a zone.
  - Being in an area that is removed from the player's zone.
* The following commands can now take character name, edited-to character, showname or OOC name as identifiers, provided the target is in the same area
  - /files
  - /guide
  - /invite
  - /party_invite
  - /party_kick
  - /party_uninvite
  - /pm
  - /uninvite
  - /whisper
* Fixed normal players being able to use /uninvite with IPID.

### 191231a (4.2.3)
* Added /toggle_allpasses to be able to receive autopass notifications from players that do not have autopass on
* Added optional argument to /coinflip to call coin flip results
* Added optional argument to /8ball to directly ask questions to the magic 8 ball
* Added optional argument to /getarea and /showname_area to obtain details from a particular area
* Added source and destination areas to zone entry/exit notification sent to watchers when a player enters/leaves a zone
* Added anti-bullet tag as an area parameter
* Allowed /whois to take HDID as an identifier (CM and mod only)
* Removed leftover ability of GMs to use commands with IPID
* Reworked responses of the magic 8 ball so it now chooses from a pool of 25 answers as opposed to 8
* Fixed documentation of /unban not listing it can unban by IP address
* Fixed GMs not receiving privileged staff notifications for autopass when players leave/enter an area whose lights are off or they enter/leave an area while sneaking
* Fixed unsupported webAO clients lingering for too long and taking server spots away
* Fixed wrong messages being sent when a client is bleeding and they are sneaking or the area lights are out

### 191231b (4.2.3-post1)
* Fixed non-numerical HDIDs not being recognized with /whois

### 200110a (4.2.3-post2)
* Fixed players in first person mode being unable to talk after a server-initiated IC message

### 200112a (4.2.3-post3)
* Aligned wording of music list loading outputs with the ones from area list loading outputs
* Fixed players/server being able to load music lists with invalid syntax. An informative error message will be returned to assist in fixing the music list

### 200112b (4.2.3-post4)
* Fixed players/server being able to load any YAML files with invalid YAML syntax. An informative error message will be returned to assist in fixing said file

### 200201a (4.2.3-post5)
* Fixed /showname_freeze and /showname_nuke causing errors when notifying other users

### 200320a (4.2.3-post6)
* Fixed /bg turning on lights in previously dark rooms.

### 200327a (4.2.3-post7)
* Fixed players/server being able to load music lists with non-numerical track lengths. An informative error message will be returned to assist in fixing the music list
* Fixed duplicate /look_set output messages being sent to other zone watchers in the same area
* Fixed typo in /passage_restore: 'statue'->'state'

### 200410a (4.2.3-post8)
* Fixed clients who do not/cannot update their music list crashing when they attempt to join an area that no longer exists.
* Readded description of /login to README.md

### 200428a (4.2.3-post9)
* Fixed incorrect error messages being sent in case the server's system fails to open an area list or music list file.

### 200430a (4.2.3-post10)
* Reverted backwards incompatible change that prevented music lists that did not list length for a track (meaning they did not want them to be looped) from being loaded.

### 200503a (4.2.3-post11)
* Fixed /lights not turning lights back on if the background wasn't changed

### 200516a (4.2.4)
* Enforced Python 3.6+ requirement on server launch
* Server owners running Python 3.6 will now be warned on server launch of pending deprecation of support for Python 3.6 with the upcoming major release of TsuserverDR
* All asset files in `config_sample` now come with instructions as to how to use them and what parameters they recognize
* Added /cid to get your (or someone else's) client ID
* Added /spectate to switch to spectator
* Added client version to /whois
* Warnings are now sent to players in once-locked rooms that were reloaded via /area_list
* /whisper messages from private rooms are no longer sent to staff members
* GMs may now /make_gm their multiclients, and their multiclients only
* Login/logout notifications are now sent to other staff members
* Staff login+passwords messages are now censored both in IC and OOC
* Added /zone_lights to turn the lights of every area in your zone on or off
* Added command aliases:
  - /sa (Alias for /showname_area)
  - /sas (Alias for /showname_areas)
  - /shout (Alias for /scream)
  - /unsneak (Alias for /reveal)
  - /yell (Alias for /scream)
* Added server configuration setting to disable ms2-prober connections being logged in server logs
* Added server configuration setting to set a custom UTC offset to use for the output of /time and /time12
* Public servers now properly reject webAO connections, and log any other abnormal connections.
* Fixed potential DoS attack on clients
* Fixed /toggle_allrolls giving roll results from outside watched zones if the roller was in an area not part of a zone
* Fixed /multiclients failing to output results if target client was not staff and their area did not satisfy criteria for being printed in /getareas from the perspective of the /multiclients sender
* Undeprecated /showname_list in favor of making it a command alias
* Added best-effort support for (upcoming) Attorney Online 2.7

### 200522a (4.2.4-post1)
* Fixed server not discarding repeated messages
* Increased length of abnormal connection log for better inspection
* Fixed compatibility with the KFO client

### 200524a (4.2.4-post2)
* Fixed turning lights on in an area before a party disbands raising a silent error

### 200704a (4.2.4-post3)
* Fixed /toggle_allpasses and /gmlock having broken documentation in README.md (/gmlock is now pending deprecation and should not be used anymore)
* Improved server error messages for the following situations: missing config folder, unrecognized characters/reachable areas
* For non-local servers, console now indicates alternative IP to join to if attempting to join the server from the host machine
* All use cases of /charselect now display status messages
* Improved client termination messages for abnormal connections and packets
* Added best-effort support for (upcoming) Attorney Online 2.8 and similar clients. Unrecognized clients will now be warned in OOC when they join

### 200712a (4.2.4-post4)
* Fixed servers not launching if they did not set some daily gmpasses
* config.yaml now shows instructions on how to make daily gmpasses optional, as well as indications on password requirements

### 200720a (4.2.4-post5)
* Fixed situation where players that started a clock, paused it and disconnected did not have the clocks properly cleared

### 200731a (4.2.5)
* Added /party_whisper (aliases /pw and /huddle) so players in the same party may whisper to one another
* Added /zone_info (alias /zi) so zone watchers may quickly obtain details about their zone and a list of players in their zone.
* Added /logingm, alias to /loginrp.
* /play, /rplay, /zone_lights and /zone_play now send status messages to both the player executing the command as well as any player watching the zone if appropriate
* /play, /rplay and /zone_play now warn the player executing the command if the track name is not a recognized one and that it will not loop
* /scream now displays the scream in IC to the screamer
* Raised character limit in commands from 256 to 1024, except for IC-related commands (these remain at 256)
* (Temporarily) patched /globalic_pre so that GMs using /globalic with prefixes would have their client IC chatboxes and effects cleared once their message was sent
* All staff-privileged commands now send displayname and client ID rather than some combination of names
* /party_members and /zone_list now list client ID of members and zone watchers respectively
* Servers no longer stop launch if they are unable to obtain their public IP
* Improved wording in README
* Fixed /rplay failing if the reachable areas of an area was just the keyword '<ALL>'
* Fixed launching servers via double clicking start_server.py being unable to find configuration files and crashing immediately afterwards
* Fixed Attorney Online 2.8 not handling music and area list updates

### 200803a (4.2.5-post1)
* Fixed global IC areas and prefixes, as well as day cycle clocks not being canceled on /logout and /cleargm
* Fixed /cleargm not forcing GMs who were in an area that restricted some characters off their character if they were using one of those restricted characters
* Fixed global IC areas and prefixes not being reset on area list reloads, even when it would not make too much sense to keep them around
* /whois now shows global IC and global IC prefix status

### 200805a (4.2.5-post2)
* Fixed accidental uses of /logingm in IC or in OOC surrounded by spaces not filtering out server passwords like other login commands do

### 200807a (4.2.5-post3)
* Fixed /scream not showing default or custom shownames in IC for non-deaf players
* Reworded the /scream OOC notification so it is more in line with other OOC/IC notifications
* Deaf players now only see an IC notification for screams

### 201215a (4.2.5-post4)
* Fixed allowing zero-width characters in OOC names and shownames
* Fixed illegal OOC names being associated with clients, even after being notified they are invalid

### 201217a (4.2.5-post5)
* Backported 4.3.0 recognition of DRO 1.0.0 protocol and clearing of IC on area changes/blinding

### 210213a (4.2.5-post6)
* Enforced stricter file validation before attempting to open files
* Enforced file names not referencing current or parent directories in the name
* Improved error message if ban, IPID or HDID list JSON files are missing

### 210213b (4.2.5-post7)
* Fixed validation introduced in 4.2.5-post6 not working in Python 3.7

### 210213c (4.2.5-post8)
* Fixed regression where if ip_ids.json or hd_ids.json did not exist, the server would not launch

### 210325a (4.2.5-post9)
* Fixed server not recognizing the new DRO 1.0.0 colors
* Fixed server not accepting the SP packet
* Fixed server not accepting the new DRO splash buttons
* Fixed clients with letters included in their minor version throwing an error when joining a server
* Fixed server creating an ip_ids.json or hd_ids.json file with the wrong structure
* Fixed server accepting ip_ids.json or hd_ids.json files with wrong structure
* Fixed AO clients sending IC messages presenting with no evidence selected throwing an error

### 210621a (4.2.6)
* Community managers now have access to /area_list and /area_lists
* Added /ignore and /unignore to toggle ignoring IC messages from players
* Added /glock to lock the global and zone chats
* Moderators and community managers now see the IPID of players using /g or /zone_global
* Updated TsuserverDR so it uses travis-ci.com
* Fixed servers not accepting IC messages if they did not set some daily gmpasses
* Fixed some special characters not being accepted properly

### 210626a (4.2.6-post1)
* Fixed various commands not loading server YAML files with UTF-8 encoding

## 210929a (4.3.0)
* Tied in to Danganronpa Online v1.0.0, although support for the previous Danganronpa Online version will be kept for 4.3.0
* Explicitly allowed Python 3.9 support for server owners
* Added basic DR-style trials (confront readme for command instructions):
  - /trial
  - /trial_add <identifier>
  - /trial_end
  - /trial_focus <identifier> <value>
  - /trial_influence <identifier> <value>
  - /trial_info
  - /trial_join <trialname>
  - /trial_lead
  - /trial_leave
  - /trial_kick <identifier>
  - /trial_unlead
* Added basic DR-style nonstop debates that run within trials and can loop automatically until a player shoots an appropriate bullet (confront readme for command instructions):
  - /nsd <time>
  - /nsd_add <identifier>
  - /nsd_end
  - /nsd_join <nsdname>
  - /nsd_lead
  - /nsd_leave
  - /nsd_kick <identifier>
  - /nsd_unlead
  - /nsd_pause
  - /nsd_loop
  - /nsd_accept
  - /nsd_reject
  - /nsd_resume
* Added perjury bullet support: only the person using the perjury bullet and the NSD leaders (or GMs if not part of an NSD) receive the perjury animation, everyone else receives a counter animation.
* Added area lurk callouts to name players who have been idle some amount of time in an area via
  - /lurk <length>
  - /lurk_cancel (to cancel a lurk callout in an area)
* Players may now set and see custom status, which will send an IC notification to every player that subsequently sees them:
  - /status <id>
  - /status_set <new_status>
  - /status_set_other <id> <new_status> (GM+ command)
* Areas may now be marked as noteworthy, which will also trigger a similar IC notification on arrival or visibility change.
  - /noteworthy
* /look now shows a list of players in the area like /getarea, with the following additions
  - Players are listed by showname, if unavailable edited to character, and if unavailable character folder
  - Players in the same party now show a (P)
  - Players with a custom status now show a (!)
* Added /bilockh and /unilockh GM commands. They have the effect /bilock and /unilock formerly had of showing/hiding areas from the area list. /bilock and /unilock for all ranks now does not change passage visibility for all ranks.
  - Passage visibility changes are immediately reported in the affected players' area lists
* System blankposts are now sent on area change or when blinded to clear the last character on screen for compatible clients.
* Added support for new colors available in DRO as well as the set position SP packet
* Music playing notifications now show the server showname of the player in DRO if the player set a showname
* Last sender sprites no longer show in first person mode if the player with first person mode talks and the last sender
  - Disconnected
  - Is in a different area
  - Changed characters
  - Has sneaked, and it is not the case the player is sneaking and they are both in a party
* Added explicit 'forwards sprite mode' via /toggle_fs. When a player has forwards sprites disabled, all recipients of their IC message will not see the player's sprite, but the last one they saw (or blank if any of the conditions described for first person mode blanks applies). By default it is on.
* Day cycle clocks are now more linked with DRO 1.0.0 by supporting time of day periods. Players in the clock range playing with compatible clients will automatically change to their time of day's version of their theme when entering a custom period or unknown time:
  - /clock_period
  - /clock_unknown
* Day cycle clocks can now have their hour length and current hour be modified via /clock_set
* Day cycle clock unpauses now take place as soon as processed rather than at most 1 second after being processed
* Added /zone_mode to set up the gamemode of a zone. Players part of an area in that zone with compatible clients will automatically change to their gamemode's version of their theme.
* Players in a party that are sneaking may now see each other via /getarea and similar. Players in the party not sneaking, or players sneaking not part of the party may not see these players
* Non-GM players that are spectators may now follow players.
  - Players that were GM and not spectators who then logged out, or non-GMs who were spectators and switched to a character stop following whoever they were following.
* Changed wording of GM login notifications, /minimap, attempting to access a locked passage, talking in an area whose IC chat is locked, following and unfollowing
* Notifications are now sent if a mod via /switch forces a target off their character (e.g. mod using /switch) to the mod, the target, and other officers in the server
* Clients with compatible clients now no longer see auxiliary extra spaces in IC if deafened nor their own messages with global IC prefixes if they have them on
* Improved README description of /switch to account for GMs being able to switch to restricted characters, and mods being able to force a player off their character
* Added area parameter that allows only CMs and mods to send global messages in an area (by default false)
* Improved type checking of areas, background, config, music and character lists (they now hopefully fail earlier and more clearly if they have subtle errors)
* If a character list is changed via /refresh, all clients are switched to spectator and prompted to rejoin the server
* /banhdid now reports, if a player was already banned, what IPID was banned
* Judge buttons are now disallowed in lobby areas
* Removed support for AO1 style packets. The server will now respond only to DRO and AO2-style packets
* Server now logs 100 most recent sent and received packets in error logs
* Players that successfully call mod now receive an OOC notification acknowledging that
* Removed the limit on number of different judge buttons accepted
* Running /showname with no arguments with no showname set, or attempting to set the same showname as the one previously had, now returns an error instead of running successfully
* Added /dump to generate a server dump on request
* Added /slit, alias to /bloodtrail
* Clients sending syntactically correct but otherwise unidentifiable packets now silently log to console and server log rather than propagating an uncaught KeyError
* Allowed /cleargm to take a client ID to log out a particular client from their GM rank
* Improved output of /cleargm and /kickself for the user running the commands: they now see who they logged out or kicked respectively
* Added config/gimp.yaml so server owners can customize the output of gimped players
* Improved output of error messages if the port the server tries to use is already in use or that is beyond the range of available ports
* IC and OOC messages, as well as arguments to OOC commands, now have leading and trailing whitespace characters removed (except a chain of only spaces)
* The following server asset files may now be validated without launching a server by opening the appropriate file in server/validate, and dragging the file to check in there:
  - Areas
  - Backgrounds
  - Characters
  - Config
  - Gimp
  - Music
* /scream_set_range now allows <ALL> as an argument to indicate all areas should be able to receive a scream coming from the area the person running the command
* Added /iclock_bypass, allowing GM+ to let non-GMs in an area whose IC chat is locked to talk in IC. The effect disappears as soon as the target moves area or their area has their IC chat unlocked
* Improved output of /blind, /deafen, /gag if no arguments are passed
* Made /blind, /deafen, /gag, /bloodtrail echo the ID of the affected target as part of output message
* GMs are no longer subject to the server music flood guard
* Added /randommusic, which plays a randomly chosen track from the player's current music list
* Added /exit, which lets you exit the server from OOC
* Server initiated messages will now attempt to include desks wherever possible
* Added /zone_handicap and /zone_unhandicap. Players who enter an area part of a zone with a handicap will be subject to the imposed movement handicap automatically
    - Also added /zone_handicap_affect, which makes a player be subject to a zone handicap if their handicap was removed
* Running /sneak on an already sneaked player will now fail. Similarly, running /reveal on an already not sneaked player will now fail
* All commands that require a specific number of arguments now validate that the correct number of arguments was passed
* Zones that lose all their watchers but still have players in areas part of the zone will no longer be automatically deleted
* If an area is made part of a zone via /zone or /zone_add, all players are now notified about it. A similar behavior occurs now with /zone_remove
* All /showname_set notifications now include the old showname of the affected user if applicable
* Clients may now send empty sound effects
* Made /showname_history be available to all staff members (previously it was for moderators only)
* Added /charlog, which lists all character changes a player has gone through in a session (including character showname or iniswap changes)
* Made /whois identifiers follow the same identifier type lookup logic as other commands
* RP notifications that typically show player shownames will now try to use character shownames if available before defaulting to the character folder name
* Added /zone_tick and /zone_tick_remove to set the chat tick rate of a zone, so all players in an area part of the zone see messages with the same chat tick rate, or their own chat tick rate
* Made /switch indicate the target character, regardless of whether the switch was successful or not
* Made /zone_watch return a more specific error if the player is already watching the target zone
* Renamed certain commands that end certain features so they have a standard format:
  - /clock_cancel -> /clock_end
  - /party_disband -> /party_end
  - /timer_cancel -> /timer_end
  - /zone_delete -> /zone_end
* Added `background_tod` as an area parameter. Subparameters defined within it will indicate compatible clients to switch to a given background according to the current time of day present in the client's area
* Added /files_area (command alias /fa), which returns all visible players in the area who have set their files
* Added command alias /l for /look
* Made /whois also return the files the target player set for their character, if they set them
* Added support for incoming client packet "CharsCheck", which if received forwards the sender the list of characters their client is meant to see, so they can update their available characters list
* Added /zone_iclock, which applies the same lock/unlock status to all areas part of your zone
* Removed the AttributeError warning from console when a player inputs a command that does not exist
* Added the command name that was used whenever an "Invalid command" error message is triggered
* Made /sneak and /reveal (/unsneak) with no arguments affect the player using it rather than raising an error
* Added `source` optional parameter to music list files, which would indicate the source of the currently played music via /currentmusic
* Made /area with no parameters return an area list for non-staff players only if `announce_areas` was set to true in the server configuration
* Fixed scream_range in area list yaml files not supporting the keyword <ALL> to indicate all areas should be able to receive a scream coming from a particular area
* Fixed scream_range in area list yaml files not checking if the areas a scream can reach to from a particular area exist
* Fixed /scream, /whisper and /party_whisper raising errors if a message was sent to a deafened player with a bypass message starter. They now sent messages but filtered
* Fixed /scream bypassing moderation mutes or client mutes
* Fixed /scream bypassing IC chat locks, or being rendered in scream-reachable areas whose IC chats are locked
* Fixed /charselect sending the proper area background to blind clients
* Fixed blankposts or double empty spaces being filtered out for deafened players
* Fixed wrongly formatted OOC notifications being sent if a player moves to an area where there are players bleeding and sneaking, and players bleeding but not sneaking
* Fixed GMs blinding, deafening or gagging themselves receiving two notifications
* Fixed area lists containing <ALL> as an area name loading without raising errors
* Fixed /whisper, /blind, /deafen, /gag not showing client ID of target for GMs+
* Fixed /party_whisper not showing party ID of target for GMs+
* Fixed situation where if a player was in first person mode and was blinded, talked themselves but heard no one else talk, and after being unblinded started talking, they would see the sprite of the last person they last saw talked
* Fixed attempting to load non-YAML files or files with unusual encoding raising an uncaught UnicodeDecode error
* Fixed /refresh not undoing changes if either the background, character or music list raised errors when loading
* Fixed /sneak and /reveal not showing the client ID of target players to zone watchers
* Fixed /zone_add, /zone_lights, /zone_play, /zone_watch not showing the area ID of the command sender to zone watchers
* Fixed filtering out global IC prefixes if a prefix was set and a message that started with that prefix was sent while global IC was turned off
* Fixed players in first person mode not seeing the last sender' sprites if the last sender was a GM that was sneaking
* Fixed /scream going to screamable areas if area is marked as private
* Fixed the server not failing early if a server YAML file was empty
* Fixed /charselect (either as mod or not) not running all spectator actions, like restarting AFK kick timers, updating character folder or notifying zone watchers
* Fixed the server silently accepting a YAML mapping file (like an area list) with duplicate keys in an item. A helpful error message is now raised
* Fixed the server indicating the wrong directory for the configuration file if the passwords were incorrect (previously showed server/config.yaml, now shows 'configuration file')
* Fixed the server disallowing all IC messages if a daily password was deliberately left empty rather than removed from the configuration file
* Fixed /party_leave not having short documentation for /help party_leave
* Fixed the server attempting to send packets to clients without checking if the client is still online.
* Fixed /poison, /cure and notifications for effects kicking in not showing the target's ID to the command runner and zone watchers
* Fixed /charselect notifying of the wrong person running the command to officers
* Fixed output of /scream_range being formatted different from /minimap. It now lists areas in order by ID with the format number-name
* Fixed /scream, /whisper and /party_whisper not sending character folder information, which prevented rendering of showname images
* Fixed /play bypassing IC mutes, blockdj and the server music flood guard
* Fixed /showname_set stopping early if multiple targets needed to be updated but an early one failed
* Fixed the default config.yaml listing 'announce_areas' as an unused parameter (it is actively used)
* Fixed /showname_set being listed as a moderator only command in the README (it was always staff only)
* Removed deprecated AO commands, and deprecated packets opKICK and opBAN
* Dropped Python 3.6 support, and added indication of future Python 3.8 support drop

### 211006a (4.3.0-post1)
* Fixed issue preventing launching servers in Python 3.10
* Fixed issue where if a player was following another player who was part of a trial and that player left to an area not part of the trial, an error would be raised

### 211015a (4.3.0-post2)
* Fixed output of /look having extraneous spaces

### 211023a (4.3.0-post3)
* Removed leftover timer creation code
* Fixed passwords in `config.yaml` being erroneously casted to wrong types when possible