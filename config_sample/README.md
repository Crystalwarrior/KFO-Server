# Server configuration files

## Before you get started...
With your copy of this software, you should check that you have the following files in `\config_sample\`:

* `config.yaml`  
* `area_lists.yaml`  
* `area_templates.yaml`  
* `areas.yaml`  
* `backgrounds.yaml`  
* `iniswaps.yaml`  
* `music.yaml`  
* `music_lists.yaml`  

As well as two folders:

* `area_lists`  
* `music_lists`  

Make sure you have all of the above inside this folder (otherwise, the server may hang or crash while starting).

In order to customize your server, you would be modifying the files in this configuration folder. You should be able to edit these files with any text editor, including Notepad, Notepad++, Nano, Vim, etc. 

### YAML

* The configuration files follow YAML syntax. YAML is a human-readable markup language, so you should be able to pick up the syntax rather quickly. However, if you feel like a short tutorial could come handy, the guide from [Rollout](https://rollout.io/blog/yaml-tutorial-everything-you-need-get-started/) is a great starting point. You can also use external YAML linters such as the one [here](https://codebeautify.org/yaml-validator) in order to check if your YAML syntax is valid. 
* By convention, TsuserverDR uses two spaces to indent (not tabulations).
* **As long as some configuration files have invalid YAML syntax or attributes TsuserverDR does not like, your server will very likely not start.** The server will try its best to let you know what is wrong, but this is not guaranteed.

## Files

Each file contains an example configuration. Further instructions should be located in each file as comments at the beginning.

* **config.yaml**
    - Contains server configuration attributes such as server name, player limit, the port it should use to listen to  connections, whether it should be advertised in the AO master server list, etc.

* **area_lists.yaml**
    - Lists the area lists the server supports. 
    - This is the list that is returned when moderators use `/area_lists`. No validation is performed to check if some area list is in this list of area lists.

* **area_templates.yaml**
    - Lists the area templates area lists can use to generate areas. **Currently unused.**

* **areas.yaml**
    - Contains the default server area list.
    - This is the area list that is loaded when the server starts, as well as the area list the server falls back to when moderators use `/area_list` on its own.
    
* **backgrounds.yaml**
    - Lists the background names the server supports.
    - This is the list that is used to validate attempts from regular players to change the background with `/bg`.

* **iniswaps.yaml**
    - Lists the allowed iniswapping combinations.
    - This is the list the server uses to check in areas that prevent iniswapping to check if they should allow a particular iniswap to exist.

* **music.yaml**
    - Contains the default server music list.
    - This is the music list that is loaded when the server starts, as well as the music list the server sends to a client that uses `/music_list` on its own.

* **music_lists.yaml**
    - Lists the music lists the server supports.
    - This is the list that is returned when players use `/music_lists`. No validation is performed to check if some music list is in this list of music lists.
