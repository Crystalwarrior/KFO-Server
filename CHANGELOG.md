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

## (4.2-In progress)
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
 - Players in the zone disconnecting
 - Players in the zone changing character
 - Players in the zone changing showname
* Improved password-less process of GM logins:
 - Added /make_gm so CMs and mods can log in other players as GMs
 - Added /gmself so GMs can log in all other clients they opened as GMs
* Custom shownames now appear if set in server notifications instead of character folders
* Improved /help
 - It can now take a command name and it will show a brief description and expected syntax, as well as the 
 minimum required rank if the player is not authorized to use it
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
* Fixed clients with same HDID but different IPID not being recognized as multiclients. This fixes the following: 
 - Players getting a new IP can now kick ghosting clients under their old IP with /kickself
 - Staff can now recognize such situations with /whois or /multiclients
* Fixed /play and /rplay not looping music tracks that appear in the server music list
* Fixed daily GM passwords switching at 3 pm incorrectly, they now switch correctly and at midnight
* Fixed day cycles not canceling on area list reload
* Fixed single space messages sent by gagged players not blankposting but being converted to jumbled text
* Explicitly allowed Python 3.8 support for server owners
 