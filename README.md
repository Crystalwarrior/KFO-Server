[![Build Status](https://travis-ci.org/Chrezm/TsuserverDR.svg?branch=master)](https://travis-ci.org/Chrezm/TsuserverDR)
# TsuserverDR

A Python-based server for Danganronpa Online. It is a fork from [tsuserver3](https://github.com/AttorneyOnline/tsuserver3) which is targeted towards Attorney Online.

Requires Python 3.6-3.8 and PyYAML (follow instructions below to install).

## How to use

### Installing

It is highly recommended you read through all the installation steps first before going through them.

* Install the latest version of Python. **Python 2 will not work**.
  - You can download Python from its official website [here](https://www.python.org/downloads/). If you already have Python installed, check that your Python version satisfies the version requirement listed above.
  - If prompted during the installation to add `python` as a PATH environment variable, accept this option. You may see this option appear on the very first screen during the installation process.
  - If you know what a virtual environment is and your system supports it, it is recommended that you use one, such as [Anaconda](https://www.continuum.io/downloads) for Windows, or [virtualenv](https://virtualenv.pypa.io/en/stable/) for everyone else (it runs itself using Python). If you do not know what a virtual environment is, you may skip this point.
  - If you have Python 3.5 or earlier, you must update to a working version to run TsuserverDR. Follow instructions on updating Python further down in this readme.
  - If you have Python 3.6, you will be prompted on server launch to update to a newer version of Python. That is because an upcoming major release will require Python 3.7 or higher. Follow instructions on updating Python further down in this readme.
* Open PowerShell, Command Prompt or your preferred terminal, and change to the directory where you downloaded TsuserverDR to. You can do this in two ways:
  - Go up one folder above the TsuserverDR folder, Shift + right click the TsuserverDR folder, and click `Open PowerShell window here`. This is the easiest method.
  - Copy the path of the TsuserverDR folder, open the terminal, and type in `cd "[paste here]"`, excluding the brackets, but including the quotation marks if the path contains spaces.
* Install PyYAML and dependencies by typing in the following in the terminal you just opened:
  ```
  python -m pip install --user -r requirements.txt
  ```

  If you are using Windows and have both Python 2 and 3 installed, you may do the following:
  ```
  py -3 -m pip install --user -r requirements.txt
  ```

  This operation should not require administrator privileges, unless you decide to remove the `--user` option.
* Rename the folder `config_sample` to `config` and edit the values in the provided YAML files to your liking. Be sure to check the YAML files for syntax errors after you are done. *Use spaces only; do not use tabs.*

### Running

* To launch a server, you may either 
  - Double-click `start_server.py` in your TsuserverDR folder.
  - In PowerShell, Command Prompt or your preferred terminal, change directory to your TsuserverDR folder and type `python start_server.py`, or `py -3 start_server.py` if you use both Python 2 and 3. For instructions on how to launch any of the above programs or change directory, refer to the second point in the Installing section.
  
* If everything was set up correctly, you will see something like this appear:

\[2020-07-31T10:20:20\]: Starting...  
\[2020-07-31T10:20:20\]: Launching TsuserverDR 4.2.5 (200731a)...  
\[2020-07-31T10:20:20\]: Loading server configurations...  
\[2020-07-31T10:20:20\]: Server configurations loaded successfully!  
\[2020-07-31T10:20:20\]: Starting a nonlocal server...  
\[2020-07-31T10:20:20\]: Server started successfully!  
\[2020-07-31T10:20:21\]: Server should be now accessible from 192.0.2.0:50000:My First DR Server  

* If you are listing your server in the Attorney Online master server, make sure its details are set up correctly. In particular, make sure that your server name and description are correct, as that is how players will find your server. If everything was set up correctly, you will see something like this appear:

\[2020-07-31T10:20:21\]: Attempting to connect to the master server at master.aceattorneyonline.com:27016 with the following details:  
\[2020-07-31T10:20:21\]: *Server name: My First DR Server  
\[2020-07-31T10:20:21\]: *Server description: This is my flashy new DR server  
\[2020-07-31T10:20:22\]: Connected to the master server.  

  - The server will make a single ping to [ipify](https://api.ipify.org) in order to obtain its public IP address. If it fails to do that, it will let you know that, as it means there is probably something wrong with your internet connection and that other players may not be able to connect to your server.
  - Successful connection or getting a spot in the master server list does not imply that your server will be accessible to other players. In particular, you must make sure that your external port in `config\config.yaml` is open and accepting connections, which usually involves a combination of router and firewall settings. In case of doubt, you can use websites such as [Can You See Me](https://canyouseeme.org) to check if your port is visible.

* To stop the server, press Ctrl+C once from your terminal. This will initiate a shutdown sequence and notify you when it is done. If the shutdown finished successfully, you will see something like this appear:

\[2020-07-31T22:23:04\]: You have initiated a server shut down.  
\[2020-07-31T22:23:04\]: Kicking 12 remaining clients.  
\[2020-07-31T22:23:04\]: Server has successfully shut down.  

* If you do not see anything after a few seconds of starting a shutdown, you can try spamming Ctrl+C to try and force a shutdown or directly close out your terminal. This is not recommended due to the cleanup process not finishing correctly but it is doable.

* To restart a server, you can follow the steps outlined above to shut down and then start the server again.

* In the unlikely event that there is an error during runtime, the server will do its best to print out to your terminal a complete traceback of the error with some additional information, as well as a more complete log file in the `logs` folder with the error timestamp, to help with debugging. Depending on the nature of the error, the server may or may not be able to continue execution normally after such an error happens.

### Updating

* If you already have a version of TsuserverDR or tsuserver3 installed and wish to update to a new version, you can download the new version and then overwrite your previously existing files. Do note that you do not need to shut down your server before overwriting the files, but you must restart it from console in order for changes to take effect.

  - This process will not overwrite your server configurations inside the `config` folder, your existing logs inside the `logs` folder, or the user information inside the `storage` folder. However, it will overwrite other files including the Python files inside the `server` folder. Therefore, make sure to save backups of those files before overwriting in case you have modified them and wish to keep an archive of your changes.

* If you want to update **Python** itself, you can get the latest Python download [from their website here](https://www.python.org/downloads/) and then follow the instructions under the Installing section in this readme. To check your current version of Python, you can run ``python`` on its own and look at the first line. The latest stable major Python release is *Python 3.8* as of October 31, 2019.

  - Please follow the installation instructions again even if you had successfully ran a server before, because your new Python installation may be missing libraries that TsuserverDR expects there to exist. You should not need to change any server configuration files though.
  - In general, updating to a Python version beyond what is specified as supported may lead to unstable behavior, so for active servers try to keep your Python version among the ones specifically labeled as supported.

## Commands
Additional notes are listed at the end of the command list. Unless otherwise specified, all command arguments have a character limit of 1024 characters, beyond which they will be cut off.

### User Commands

* **help** "command name"
    - Displays help for a command, or links to the server repository if not given an argument.
* **area** "area number"
    - Moves you to an area by its numerical ID if it is reachable from your own, or displays all areas if not given a number.
* **autopass**
    - Toggles enter/leave messages being sent automatically or not to users in the current area, including original/target areas.
    - Messages will not be sent if sneaking. Altered messages will be sent if the area's lights are turned off.
* **bg** "background"
    - Changes the current background.
* **bilock** "area number/name"
    - Changes the passage status (locked/unlocked) between the current area and the given area.
* **bloodtrail_clean**
    - Cleans the bloodtrail in the current area.
    - If someone is bleeding in the current area, the cleaning process will fail.
* **bloodtrail_smear**
    - Smears the bloodtrail in the current area.
* **charselect**
    - Puts you back to the character select screen.
* **chars_restricted**
    - Lists all characters that are restricted in the current area.
* **cleardoc**
    - Clears the doc url of the current area.
* **cid** "ID/char name/edited-to character/showname/OOC name"
    - Gives you the client ID of the target, or your own client ID if not given an argument.
* **coinflip** "call"
    - Flips a coin and returns its result, as well as whatever it is called with (e.g. a prediction, consequences for heads/tails, etc.) if given.
* **currentmusic**
    - Displays the current music and who played it.
* **discord**
    - Displays the invite link of the server's Discord server.
* **doc** "url"
    - Gives the doc url if blank, updates the doc url otherwise.
* **files** "ID/char name/edited-to character/showname/OOC name"
    - Gives a download link set by the target that links to their files, or gives your own download link if not given an argument.
* **files_set** "url"
    - Sets a download link for the user's files, or clears it if not given an argument.
* **g** "message"
    - Sends a serverwide message.
* **getarea**
    - Shows the current characters in your area.
* **getareas**
    - Shows all characters in all areas reachable from your own.
* **invite** "ID/char name/edited-to character/showname/OOC name"
    - Adds target to the invite list of your locked area so they may join.
* **kickself**
    - Removes all of of the user's clients except the one that used the command.
* **knock** "area"
    - Knocks on a reachable area's door, sending an OOC notification to that area. Can be either area ID or name.
* **lights** "on/off"
    - Changes the light status in the area to on or off.
    - Areas with lights off will have a dark background, and they disable /getarea(s) and alter /autopass, bleeding, /look and sneaking notifications.
* **lock**
    - Locks your area. Prevents normal users from entering.
    - People in the area, including yourself, at the time the area is locked are free to come and go regardless of their status.
* **login** "password"
    - Makes you a Moderator.
* **logincm** "password"
    - Makes you a Community Manager.
* **loginrp** "password"
    - Makes you a GM.
* **logout**
    - Logs you out of the rank you have, if any.
* **look**
    - Obtains the description of the current area.
* **minimap**
    - Lists all areas reachable from the current one.
* **motd**
    - Returns the server's Message of the Day.
* **music_list** "music list name"
    - Sets your music list to the given one, or restores the original one if not given any.
* **music_lists**
    - Lists all available music lists as established in `config/music_lists.yaml`.
* **online**
    - Returns how many players are online.
* **party**
    - Creates a party and makes you its leader.
* **party_disband**
    - Disbands your party.
* **party_id**
    - Returns your party ID.
* **party_invite** "ID/char name/edited-to character/showname/OOC name"
    - Invites a player in the same area to your party.
* **party_join** "party ID"
    - Makes you join a party you were invited to.
* **party_kick** "ID/char name/edited-to character/showname/OOC name"
    - Kicks a player off your party.
* **party_lead**
    - Makes you a leader of your party.
* **party_members**
    - Lists the leaders and regular members of your party.
* **party_uninvite** "ID/char name/edited-to character/showname/OOC name"
    - Revokes an invitation sent to a player to join your player.
* **party_unlead**
    - Removes your party leader role.
* **party_whisper** "message"
    - Sends an IC private message to everyone in the party.
    - Other people in the area are warned that a whisper has taken place (but not the message content). However, staff members do get message contents, so this command should only be used in RP settings.
	- Messages are limited to 256 characters.
* **ping**
    - Returns "Pong", used to check for server connection.
* **play** "song.mp3"
    - Plays a song, provided the area you are in allows non-staff members to run this command.
* **pm** "ID/char name/edited-to character/showname/OOC name" "message"
    - PMs the target.
* **pos** "position"
    - Changes your position in the court.
    - Positions: 'def', 'pro', 'hld', 'hlp', 'jud', 'wit'
* **randomchar**
    - Changes your character to a randomly chosen one.
* **reload**
    - Reloads your character ini file.
* **roll** "number of dice"d"number of faces" "modifiers"
    - Rolls as many dice as given with the given number of faces, and applies modifiers if given. If no arguments are given, rolls one d6.
* **rollp** "number of dice"d"number of faces" "modifiers"
    - Same as roll but other non-staff members in the area only are notified that someone rolled.
* **scream** "message"
    - Sends an IC message visible to all players in the areas that are set to be able to listen to screams from the current area.
	- Messages are limited to 256 characters.
* **showname** "showname"
    - Sets your showname to be the given one, or clears it if not given one.
* **showname_area**
    - Similar to /getarea, but lists shownames along with character names.
* **showname_areas**
    - Similar to /getareas, but lists shownames along with character names.
* **spectate**
    - Switches you to a SPECTATOR character.
* **switch** "character name"
    - Switches you to the given character.
* **time**
    - Displays the server's local time.
* **time12**
    - Displays the server's local time in 12 hour format.
* **timer** "length" "timer name" "public"
    - Starts a timer of the given length in seconds, which will send a notification to people in the area once it expires.
    - If given a timer name, it will override the default timer name (OOCNameTimer).
    - If public is set to any of the following: "False, false, 0, No, no", the timer details will be hidden from non-staff players.
* **timer_cancel** "timer name"
    - Cancels the timer by name, provided it is yours.
* **timer_get** "timer name"
    - Obtains the remaining time of the given timer by name, provided it is public, or list all remaining times in all public timers if not given a name.
* **ToD**
    - Chooses "Truth" or "Dare" for Truth or Dare minigames.
* **toggle_fp**
    - Changes your setting to be in first person mode (your character does not appear to you when you send IC messages) or normal mode (your character does appear). By default it is in normal mode.
* **toggle_global**
    - Changes your setting to receive global messages. By default it is on.
* **toggle_pm**
    - Changes your setting to receive PMs. By default it is on.
* **toggle_shownames**
    - Changes your setting to have the IC messages you receive to include the sender's custom showname. By default it is on.
* **unilock** "area number/name"
    - Changes the passage status (locked/unlocked) from the current area to the given one.
* **uninvite** "ID/char name/edited-to character/showname/OOC name"
    - Removes a target from your locked area's invite list, so that if they leave, they will not be allowed back until the area is unlocked.
* **unlock**
    - Unlocks your area, provided the lock came as a result of /lock.
* **version**
    - Obtains the current version of the server software.
* **whisper** "ID/char name/edited-to character/showname/OOC name" "message"
    - Sends an IC private message to the target, provided they are in the area.
    - Other people in the area are warned that a whisper has taken place (but not the message content). However, staff members do get message contents, so this command should only be used in RP settings.
	- Messages are limited to 256 characters.
* **zone_global**
    - Sends a message to all players in the zone you are in.
* **8ball** "question"
    - Gains insight from the magic 8 ball in response to a question if given one.

### GM Commands

GMs can:
  - Bypass area passages and locks.
  - Receive special RP notifications.
  - Use GM commands.
* **area_kick** "ID" "area number"
    - Kicks target from your area to the intended area and remove them from its invite-list.
    - If not given a target area, it will use the server's default area (usually area 0).
* **bilock** "area 1", "area 2"
    - Changes the passage status (locked/unlocked) between two areas.
* **blind** "ID"
    - Changes the blind status of a target.
    - Blind players will receive no character sprites nor background with IC messages and cannot use "visual" commands such as /look, /getarea, etc.
* **bloodtrail** "ID"
    - Changes the bleeding status of a target.
    - If bleeding, they will leave 'blood' in all areas they pass through, and send OOC notifications to players in the area and those who join indicating their status. Sneaking and bleeding players send altered notifications.
* **bloodtrail_clean** "area 1", "area 2", ...
    - Cleans the blood trails in the given areas (or the current one if not given any areas).
    - If someone is bleeding in any of the given areas, the cleaning process will fail.
* **bloodtrail_list**
    - Lists all areas that have bloodtrails in them, and where they lead to if appropiate.
* **bloodtrail_set** "area 1", "area 2", ...
    - Sets the current area to have bloodtrails leading to the listed areas. If no areas are given, the area is set to have an unconnected pool of blood.
* **bloodtrail_smear** "area 1", "area 2", ...
    - Smears the blood trails in the given areas (or the current one if not given any areas).
* **can_passagelock**
    - Changes the current area's setting to allow non-staff members to change passages starting in the area with /bilock or /unilock. By default area setting is indicated in the server's area list.
* **can_rollp**
    - Changes the current area's setting to allow non-staff members to do /rollp. By default area setting is indicated in the server's area list.
* **can_rpgetarea**
    - Changes the current area's setting to allow RP users to use /getarea. By default area setting is indicated in the server's area list.
* **can_rpgetareas**
    - Changes the current area's setting to allow RP users to use /getareas. By default area setting is indicated in the server's area list.
* **char_restrict** "character name"
    - Changes the restricted status of a character in the current area.
    - If a character is restricted, only GMs and above can use the character in the current area.
* **clock** "area range start" "area range end" "hour length" "hour start"
    - Sets up a day cycle that, starting from the given hour, will tick one hour every given number of seconds and provide a time announcement to a given range of areas.
* **clock_cancel** "ID"
    - Cancels the day cycle initiated by the target or yourself if not given a target.
* **clock_pause** "ID"
    - Pauses the day cycle initiated by the target or yourself if not given a target.
* **clock_unpause** "ID"
    - Unpauses the day cycle initiated by the target or yourself if not given a target.
* **cure** "ID" "initials of effects"
    - Clears the given effects from the target, as well as any poison that would have inflicted those effects.
* **deafen** "ID"
    - Changes the deafened status of a target.
    - Deafened players will be unable to read IC messages properly or receive other audio cues from commands such as /knock, /scream, etc.
* **dicelog** "ID"
    - Obtains the last 20 rolls from a target, or your last 20 rolls if not given a target.
* **dicelog_area** "area"
    - Obtains the last 20 rolls from an area by ID or name, or the last 20 rolls of your area if not given one.
* **follow** "ID"
    - Starts following a target. If the target changes areas, you will automatically follow them there.
* **gag** "ID"
    - Changes the gagged status of a target.
    - Gagged players will be unable to talk IC properly or use other talking features such as /scream.
* **getarea** "area"
    - Shows the current characters in the given area, or your area if not given any.
* **globalic** "area range start", "area range end"
    - Sends subsequence IC messages to the area range described above. Can take either area IDs or area names.
* **globalic_pre** "prefix"
    - Ensures only IC messages that start with the prefix are sent to the preestablished area range through /globalic (otherwise, just to the current area), or removes the need for a prefix if not given one.
* **gmlock**
    - Locks your area. Prevents CMs and normal users from entering. WARNING: Pending deprecation.
* **gmself**
    - Logs all opened multiclients as GM.
* **guide** "ID/char name/edited-to character/showname/OOC name" "message"
    - Sends an IC private 'guiding' message to the target.
    - Unlike /whisper, other people in the area are not warned that a whisper has taken place. However, staff members do get message contents, so this command should only be used in RP settings.
	- Messages are limited to 256 characters.
* **handicap** "ID" "length" "name" "announce if over"
    - Sets a movement handicap on a client by ID so that they need to wait a set amount of time in seconds between changing areas.
    - If name is given, the handicap announcement will use it as the name of the handicap.
    - If announce if over is set to any of "False, false, 0, No, no", no announcements will be sent to the player indicating that they may now move areas.
* **iclock**
    - Changes the IC lock status of the current area.
    - If the area has an IC lock, only GMs and above will be able to send IC messages.
* **judgelog** "area"
    - Lists the last 20 judge actions performed in the given area (or current area if not given).
    - Each entry includes the time of execution, client ID, character name, client IPID and the judge action performed.
* **look_clean** "area 1", "area 2", ...
    - Restores the default area descriptions of the given areas by ID or name, or the current area if not given any.
* **look_list**
    - Lists all areas that have custom descriptions.
* **look_set** "description"
    - Sets the area's description to the given one, or restores the default one if not given.
* **make_gm** "ID"
    - Makes the target a GM, provided the target is a multiclient of the player.
* **multiclients** "ID"
    - Lists all the clients opened by a target and the areas they are in.
* **party_disband** "party ID"
    - Disbands a party.
* **party_join** "party ID"
    - Makes you join a party, even if you were not invited to it.
* **party_list**
    - Lists all active parties in the server, as well as some of their details.
* **passage_clear** "area range start", "area range end"
    - Clears passage locks that start in the areas in the given area range, or just the ones in the current area if not given a range.
* **passage_restore** "area range start", "area range end"
    - Restores passage locks that start in the areas in the given area range to their original status, or just the ones in the current area if not given a range.
* **play** "song.mp3"
    - Plays a song, even if not in the server music list.
* **poison** "ID" "initials of effects" "length"
    - Applies a poison to the target that will inflict them in the given length of time in seconds the given effects.
* **reveal** "ID"
    - Reveals a target if they were previously sneaking.
    - Also restores their formerly assigned handicap if they had one that was shorter than the server's automatic sneaking handicap.
* **rplay** "song.mp3"
    - Plays a song in all areas reachable from the current one.
* **rpmode** "on/off"
    - Toggles RP mode.
* **scream_range**
    - Returns the areas that can listen to screams sent from the current area.
* **scream_set** "area"
    - Changes the reachable status from screams sent from the current area to the given area.
* **scream_set_range** "area 1", "area 2", ...
    - Sets the current area's scream range to be the areas listed.
* **shoutlog** "area"
    - Lists the last 20 shouts sent in the given area, or from the current area if not given.
    - Each entry includes the time of execution, client ID, character name, client IPID, the shout ID and the IC message sent alongside.
* **showname_area** "area"
    - Similar to /getarea, but lists shownames along with character names.
* **sneak** "ID"
    - Sets a target to be sneaking if they were visible.
    - If the target was subject to a handicap shorter than the server's automatic sneak handicap length, they will be imposed this handicap.
* **st** "message"
    - Sends a message to all active staff members.
* **toggle_allpasses**
	- Changes your ability to receive autopass notifications from players that do not have autopass on. By default it is off.
* **toggle_allrolls**
    - Changes your ability to receive /roll and /rollp results from other areas. By default it is off.
* **transient** "ID"
    - Changes a player's ability to ignore passage locks and thus access all areas from any given area. By default it is off.
* **unfollow**
    - Stops following whoever you were following.
* **unglobalic**
    - Stops sending subsequent IC messages to the area range specified in a previous /globalic command.
* **unhandicap** "ID"
    - Removes movement handicaps on a target.
* **unilock** "area 1", "area 2"
    - Changes the passage status (locked/unlocked) from area 1 to area 2.
* **uninvite** "ID/char name/edited-to character/showname/OOC name"
    - Removes a target from your locked area's invite list, so that if they leave, they will not be allowed back until the area is unlocked.
* **unlock**
    - Unlocks an area, provided the lock came as a result of /gmlock or /lock.
* **whereis** "ID"
    - Obtains the area a target is.
* **whois** "ID/char name/showname/OOC name"
    - Obtains a lot of properties of the target.
* **zone** "area range start", "area range end"
    - Creates a zone involving the area range given above, just the given area if given one parameter, or just the current area if not given a parameter.
    - You are automatically set to watch the zones you create like this.
* **zone_add** "area"
    - Adds an area by name or ID to the zone you are watching.
* **zone_delete**
    - Deletes the zone you are watching.
* **zone_info**
    - Lists brief description of the zone you are watching, as well as lists all players in areas part of the zone.
* **zone_lights** "on/off"
    - Changes the light status of every area in a zone you are watching to on or off.
* **zone_list**
    - Lists all active zones in the server, as well as some of their details.
* **zone_play**
    - Plays a track in all areas in the zone you are watching.
* **zone_remove** "area"
    - Removes an area by name or ID from the zone you are watching.
* **zone_unwatch**
    - Makes you stop watching the zone you were watching.
* **zone_watch** "zone"
    - Makes you start watching a zone by its ID.

### Community Manager Commands

* **area_kick** "ID/IPID" "area number"
    - Kicks target from your area to the intended area and remove them from its invite-list.
    - If not given a target area, it will use the server's default area (usually area 0).
* **blockdj** "ID/IPID"
    - Mutes the target from changing music.
* **cleargm**
    - Logs out all GMs in the server and puts them in RP mode if needed.
* **getarea**
    - Shows the current characters in your area as well as their IPIDs.
* **getareas**
    - Shows all characters in all areas of the server as well as their IPIDs.
* **handicap** "ID/IPID" "length" "name" "announce if over"
    - Sets a movement handicap on a client by ID or IPID so that they need to wait a set amount of time in seconds between changing areas.
    - If name is given, the handicap announcement will use it as the name of the handicap.
    - If announce if over is set to any of "False, false, 0, No, no", no announcements will be sent to the player indicating that they may now move areas.
* **invite** "ID/IPID/char name/edited-to character/showname/OOC name"
    - Adds target to the invite list of your area.
* **kick** "ID/IPID"
    - Kicks the target from the server.
* **make_gm** "ID"
    - Makes the target a GM.
* **multiclients** "ID/IPID"
    - Lists all the clients opened by a target and the areas they are in.
* **mute** "ID/IPID"
    - Mutes the target from all IC actions.
* **ooc_mute** "OOC name"
    - Mutes the target from all OOC actions.
* **ooc_unmute** "OOC name"
    - Unmutes the target.
* **reveal** "ID/IPID"
    - Reveals a target if they were previously sneaking.
    - Also restores their formerly assigned handicap if they had one that was shorter than the server's automatic sneaking handicap.
* **showname_area**
    - Similar to /getarea, but lists shownames along with character names as well as their IPIDs.
* **showname_areas**
    - Similar to /getareas, but lists shownames along with character names as well as their IPIDs.
* **sneak** "ID/IPID"
    - Sets a target to be sneaking if they were visible.
    - If the target was subject to a handicap shorter than the server's automatic sneak handicap length, they will be imposed this handicap.
* **transient** "ID/IPID"
    - Changes a player's ability to ignore passage locks and thus access all areas from any given area. By default it is off.
* **unblockdj** "ID/IPID"
    - Allows the target to change music again.
* **unhandicap** "ID/IPID"
    - Removes movement handicaps on a target.
* **uninvite** "ID/IPID/char name/edited-to character/showname/OOC name"
    - Removes a target from your locked area's invite list, so that if they leave, they will not be allowed back until the area is unlocked.
* **unmute** "ID/IPID"
    - Unmutes the target from the IC chat.
* **whereis** "ID/IPID"
    - Obtains the area a target is.
* **whois** "ID/IPID/char name/showname/OOC name"
    - Obtains a lot of properties of the target, including HDID and IPID.
* **zone_delete** "zone"
    - Deletes a zone by its ID, or the zone you are watching if not given a zone.

### Moderator Commands

* **announce** "message"
    - Sends a serverwide announcement
* **area_list** "area list"
    - Sets the server's current area list.
    - If not given an area list, it will restore the original area list as it was on server bootup.
* **area_lists**
    - Lists all available area lists as established in `config/area_lists.yaml`.
* **ban** "IPID"/"IP"
    - Bans the specified IPID/IP (hdid is linked to ipid so all bans happen at the same time).
* **banhdid** "HDID"
    - Bans the specified HDID (hdid is linked to ipid so all bans happen at the same time).
* **bglock**
    - Toggles the background lock in the current area.
* **can_iniswap**
    - Changes the iniswap status in the current area.
    - Even if iniswap at all is forbidden you can configure all-time allowed iniswaps in *iniswaps.yaml*
* **charselect** "ID"
    - Kicks a player back to the character select screen. If no ID was entered then target yourself.
* **defaultarea** "area number"
    - Sets the given area to be the area all future players join when they connect to the server.
* **disemvowel/disemconsonant/remove_h** "ID/IPID"
    - Removes the respective letters from everything said by the target
* **gimp** "ID/IPID"
    - Gimps a target so that all their IC messages are replaced with a selection of preset messages.
* **gm** "message"
    - Sends a serverwide message with mod tag.
* **lm** "message"
    - Sends an area OOC message with mod tag.
* **modlock**
    - Locks your area. Prevents GMs, CMs and normal users from entering.
* **refresh**
    - Reloads the server's default character, music and background lists.
* **showname_freeze**
    - Changes the ability of non-staff members of being able to change or remove their own shownames.
* **showname_history** "ID/IPID"
    - Lists all shownames a target has gone through since connecting, including the time they were changed.
* **showname_nuke**
    - Clears all shownames from non-staff members.
* **showname_set** "ID/IPID" "showname"
    - Sets a target's showname to be the given one, or clears it if not given one.
* **unban** "IPID/IP"
    - Unbans the specified IPID/IP.
* **unbanhdid** "HDID"
    - Unbans the specified HDID.
* **undisemvowel/undisemconsonant/ungimp/unremove_h** "ID/IPID"
    - Undo correlating command.
* **unlock**
    - Unlocks an area, provided the lock came as a result of /gmlock, /lock or /modlock.

### Debug commands

* **exec** "command"
    - (DEBUG) Executes the given command as a Python instruction. Requires turning on in `server/commands.py` before using.
* **lasterror**
    - (DEBUG) Obtains the latest uncaught error as a result of a client packet. This message emulates what is output on the server console.
* **reload_commands**
    - (DEBUG) Reloads the `server/commands.py` file.

### Deprecated commands and aliases
Commands marked with (D) are marked as deprecated. They will continue to serve their original purpose as usual for three months after the stated date. If an alternative command name is given to a deprecated command, please try and use that command instead.

Commands without (D) are aliases to commands and can be freely used (subject to the parent command's conditions).

#### Everyone

* **mutepm** (D: Aug.19.19): Same as /toggle_pm.
* **toggleglobal** (D: Jul.15.19): Same as /toggle_global.
* **huddle**: Same as /party_whisper.
* **pw**: Same as /party_whisper.
* **sa**: Same as /showname_area.
* **sas**: Same as /showname_areas.
* **shout**: Same as /scream.
* **showname_list**: Same as /showname_areas.
* **unsneak**: Same as /reveal.
* **yell**: Same as /scream.
* **zi**: Same as /zone_info.
* **zg**: Same as /zone_global.

#### GM+

* **delete_areareachlock** (D: Jul.15.19): Same as /passage_clear.
* **restore_areareachlock** (D: Jul.15.19): Same as /passage_restore.
* **toggle_areareachlock** (D: Jul.15.19): Same as /can_passagelock.
* **toggle_rollp** (D: Jul.15.19): Same as /can_rollp.
* **toggle_rpgetarea** (D: Jul.15.19): Same as /can_rpgetarea.
* **toggle_rpgetareas** (D: Jul.15.19): Same as /can_rpgetareas.
* **logingm**: Same as /loginrp.

#### Mod+

* **allow_iniswap** (D: Jul.15.19): Same as /can_iniswap.

### Notes

* **Note 1**: the commands may refer to the following identifiers for a player:
    - **Character Name**: the folder name of the character the player is using, also the name that appears in /getarea.
    - **HDID**: the hard drive ID of the player, accessible through /whois (requires community manager rank).
    - **ID**: number in brackets [] in /getarea.
    - **IPID**: number in parentheses () in /getarea (requires community manager rank).
    - **IP**: the IP address of the player.
    - **OOC Name**: the username of the player in the OOC chat.
* **Note 2**: some commands include commas (,) between the parameters. If that is the case, the command expects you to actually use the commas between the parameters. If for whatever reason your parameter also has a comma followed by a space, you can include it by using ,\ (so 'Hello, world' becomes 'Hello,\ world').
* **Note 3**: additional documentation for the commands can be found in `config\commands.py` and consulting the docstrings. For example, to get additional information for /help, you would look for `ooc_cmd_help` and look for the associated text.

## License

This server is licensed under the AGPLv3 license. In short, if you use a modified version of TsuserverDR, you *must* distribute its source licensed under the AGPLv3 as well, and notify your users where the modified source may be found. The main difference between the AGPL and the GPL is that for the AGPL, network use counts as distribution. If you do not accept these terms, you should use [serverD](https://github.com/Attorney-Online-Engineering-Task-Force/serverD), which uses GPL rather than AGPL.

See the [LICENSE](LICENSE.md) file for more information.
