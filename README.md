# tsuserver3.DR

A Python-based server for Danganronpa Online. It is a direct branch from tsuserver3, which is targeted towards Attorney Online.

Requires Python 3.6+ and PyYAML.

## How to use

### Installing

* Install the latest version of Python. **Python 2 will not work**, as tsuserver3 depends on async/await, which can only be found on Python 3.5 and newer.
  - If your system supports it, it is recommended that you use a separate virtual environment, such as [Anaconda](https://www.continuum.io/downloads) for Windows, or [virtualenv](https://virtualenv.pypa.io/en/stable/) for everyone else (it runs itself using Python).
* Open Command Prompt or your terminal, and change to the directory where you downloaded tsuserver3 to. You can do this in two ways:
  - Go up one folder above the tsuserver3 folder, Shift + right click the tsuserver3 folder, and click `Open command window here`. This is the easiest method.
  - Copy the path of the tsuserver3 folder, open the terminal, and type in `cd "[paste here]"`, excluding the brackes, but including the quotation marks if the path contains spaces.
* To install PyYAML and dependencies, type in the following:
  ```bash
  python -m pip install --user -r requirements.txt
  ```
  If you are using Windows and have both Python 2 and 3 installed, you may do the following:
  ```batch
  py -3 -m pip install --user -r requirements.txt
  ```
  This operation should not require administrator privileges, unless you decide to remove the `--user` option.
* Rename `config_sample` to `config` and edit the values to your liking. Be sure to check your YAML file for syntax errors. *Use spaces only; do not use tabs.*

### Running

* Run by either double-clicking `start_server.py` or typing in cmd or your terminal `python start_server.py`, or `py -3 start_server.py` if you use both Python 2 and 3. If everything was set up correctly, you will see something like this appear:  
[2019-07-02T17:33:30]: Starting...  
[2019-07-02T17:33:30]: Launching tsuserver3.DR.190702b...  
[2019-07-02T17:33:30]: Loading server configurations...  
[2019-07-02T17:33:31]: Server started successfully!

* To stop the server, press Ctrl+C once from your terminal. This will initiate a shutdown process and notify you when it is done.  
[2019-07-03T14:23:04]: You have initiated a server shut down.  
[2019-07-03T14:23:04]: Kicking 12 remaining clients.  
[2019-07-03T14:23:04]: Server has successfully shut down.

  - If you do not see said messages after a few seconds, you can try spamming Ctrl+C to try and force a shutdown or directly close out your terminal. This is not recommended due to the cleanup process not finishing correctly but it is doable.

* To restart a server, you can follow the steps outlined above to shut down and then start the server again.
  
* In the unlikely event that there is an error during runtime, the server will do its best to print out to your terminal a complete traceback of the error with some additional information to help with debugging. Depending on the nature of the error, the server may or may not be able to continue execution normally.
 
### Updating

* If you already have a version of tsuserver installed and wish to update to a new version, you can download the new version and then overwrite your previously existing files. Do note that you do not need to shut down your server before overwriting the files, but you must restart it from console in order for changes to take effect.

  - This process will not overwrite your server configurations inside the "config" folder, your existing logs inside the "logs" folder, or the user information inside the "storage" folder. However, it will overwrite other files including the Python files inside the "server" folder. Therefore, make sure to save backups of those files before overwriting in case you have modified them and wish to keep an archive of your changes.
 
## Commands

### User Commands

* **help**
    - Links to this readme
* **area** "area number" 
    - Displays all areas when blank, swaps to area with number
* **bg** "background" 
    - Changes the current background
* **charselect** 
    - Puts you back to char select screen
* **cleardoc** 
    - Clears the doc url
* **coinflip**
    - Flips a coin
* **currentmusic** 
    - Displays the current music
* **discord**
    - Displays the invite link of the server's Discord server.
* **doc** "url" 
    - Gives the doc url if blank, updates the doc url otherwise
* **g** "message" 
    - Sends a serverwide message
* **getarea** 
    - Shows the current characters in your area
* **getareas** 
    - Shows all characters in all areas
* **kickself**
    - Removes all of of the user's clients except the one that used the command.
* **lock**
    - Locks your area.
* **pm** "target" "Message" 
    - PMs the target, can either be character name or OOC name
* **pmmute**
    - Disables all incoming PMs
* **pos** "position" 
    - Changes your position in the court
    - Positions: 'def', 'pro', 'hld', 'hlp', 'jud', 'wit'
* **randomchar** 
    - Randomly chooses a character
* **reload** 
    - Reloads your character ini
* **roll** "max, number of dice" 
    - Rolls a 1D6 if blank
* **roll** "max, number of dice" 
    - Same as above but unseen by other clients
* **switch** "character" 
    - Quick switch to a character
* **time**
    - Displays the time according to the local timezone of whoever is running the server.
* **toggleglobal** 
    - Toggles global on and off
* **unlock**
    - Unlocks your area.
* **8ball**
    - Gain insight from the magic 8 ball.
	
### GM Commands
* **loginrp** "Password"
    - Makes you a GM.
    - GMs can: 
      - Bypass Locks.
      - See all areas even in RP mode.
      - Use GM commands.
* **area_kick** "ID"
    - Kicks target and all his(same for all genders) multi-accs from your area and remove him from invite-list.
* **follow** "ID"
    - Moves user clients to target client's area.
* **gmlock**
    - Locks your area. Prevents other GMs from entering.
* **invite** "ID"
    - Adds target in invite list of your area.
* **play** "song.mp3" 
    - Plays a song
* **rpmode** "on, off"
    - Toggles RP mode.
* **unfollow** "ID"
    - Undo previous command.

### Community Manager Commands

* **logincm**
    - Makes you a Community Manager.
* **blockdj** "target"
    - Mutes the target from changing music. 
* **kick** "IPID" 
    - Kicks the targets with this IPID.
* **mute** "Target" 
    - Mutes the target from all IC actions, can be IP or Character name
* **unblockdj** "target"
    - Allows the target to change music again.
* **ooc_mute** "Target" 
    - Mutes the target from all OOC actions via OOC-name.
* **ooc_unmute** "Target" 
    - Unmutes the target.
* **unmute** "Target","all" 
    - Unmutes the target, "all" will unmute all muted clients

### Moderator Commands

* **login** "Password"
    - Makes you a Moderator.
* **allow_iniswap**
    - Toggle allow_iniswap var in this area. 
    - Even if iniswap at all is forbidden you can configure all-time allowed iniswaps in *iniswaps.yaml*
* **announce** "Message" 
    - Sends a serverwide announcement
* **ban** "IPID"/"IP" 
    - Bans the IPID/IP (hdid is linked to ipid so all bans happens in a same time).
* **bglock** 
    - Toggles the background lock in the current area
* **charselect** "ID"
    - Kicks a player back to the character select screen. If no ID was entered then target yourself.
* **disemvowel/disemconsonant/remove_h** "Target"
    - Removes the respective letters from everything said by the target
* **gm** "Message" 
    - Sends a serverwide message with mod tag
* **lm** "Message" 
    - Sends an area OOC message with mod tag
* **modlock**
    - Locks your area. Prevents other mods from entering.
* **unban** "IPID" 
    - Unbans the specified IPID .
* **undisemvowel/undisemconsonant/unremove_h** "Target"
    - Undo correlating command.

## License

This server is licensed under the AGPLv3 license. In short, if you use a modified version of tsuserver3, you *must* distribute its source licensed under the AGPLv3 as well, and notify your users where the modified source may be found. The main difference between the AGPL and the GPL is that for the AGPL, network use counts as distribution. If you do not accept these terms, you should use [serverD](https://github.com/Attorney-Online-Engineering-Task-Force/serverD), which uses GPL rather than AGPL.

See the [LICENSE](LICENSE.md) file for more information.
