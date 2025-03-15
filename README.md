
# KFO-Server

KFO-Server is the official Python-based server for Attorney Online, forked from tsuserver3.

## Server setup

In order to set up the server, you must follow these instructions. This assumes you are familiar with using a terminal.

### Install Python

* Install the [latest version of Python](https://www.python.org/downloads/). You will need Python 3.11 or newer.
* If you run Windows, make sure to check the "Add Python to PATH" and install pip checkboxes in the installer
* If you run anything other than Windows, you should read "Advanced setup instructions" below.

### Download server software

We recommend [Git](https://git-scm.com/downloads/guis) for downloading the server software.
This makes it easier to update the server later. In order to use Git, just clone the respository.

If you don't want to use Git, you can download the latest zip of KFO-Server [here](https://github.com/Crystalwarrior/KFO-Server/archive/refs/heads/master.zip). Extract it and put it wherever you want.

### Install dependencies

In order to install dependencies, you will need to open a terminal.

On Windows, you can do this by pressing Win+R, typing in `cmd`, and pressing Enter.
On Linux, you can do this by pressing Ctrl+Alt+T.

You should then navigate to the folder where the server is located.

Take note that depending on your operating system, the command for python may be python3 or python.
You should also verify the version by running `python --version` or `python3 --version`.

First, we need to create the virtual environment. This can be done by running the following command:

```bash
python -m venv venv
```

Then, we need to activate the virtual environment.
If you're on a unix system (bash or similar), you can run the following command:

```bash
./venv/bin/pip install -r requirements.txt
```

If you're on Windows (cmd), you may have to do this instead:

```batch
venv\Scripts\pip install -r requirements.txt
```

### Configure tsuserver

* Copy `config_sample` to `config`
* Edit the values in the `.yaml` files to your liking.
* Be sure to check your YAML file for syntax errors. Use this website: <http://www.yamllint.com/>
  * *Use spaces only; do not use tabs.*
* You don't need to copy characters into the `characters` folder *unless* you specifically chose to disable iniswapping in an area (in `areas.yaml`). In this case, all tsuserver needs to know is the `char.ini` of each character. It doesn't need sprites.

### Run

You can run the server using one of the helper scripts `start-unix.sh` or `start-windows.bat`.
They run the server using the local environment.

To stop the server, press Ctrl+C in the terminal.

## Using Docker

You can also use docker to run KFO-server. First you need to install [Docker](https://get.docker.com/) and [Docker Compose](https://docs.docker.com/compose/install/).

Once you have everything configured, do `docker-compose up`. It will build the image and start tsuserver up for you. If you accidentally restart the server, the container will automatically start back up. If you're not understanding why it's starting, try starting it up manually:

## Pro Tips

* To keep the server running even if your login shell is closed, use a multiplexer, such as screen or tmux.
* For more info about available command, see [Commands](https://github.com/Crystalwarrior/KFO-Server/blob/master/docs/commands.md). You may also use the /help command on the server.
* For more info about Python virtual environments, refer to ["Creating Virtual Environments"](https://docs.python.org/3/library/venv.html#creating-virtual-environments)
* In order to join your server, it has to be accessible to the public internet. You might need to forward the ports in config.yaml to make this work.
* If you can't portforward, you may want to check out [ngrok](https://ngrok.com/). It's a service that allows you to expose your local server to the internet. It's free, but you can also pay for a subscription to get more features.

## License

This server is licensed under the AGPLv3 license. In short, if you use a modified version of tsuserver3, you *must* distribute its source licensed under the AGPLv3 as well, and notify your users where the modified source may be found. The main difference between the AGPL and the GPL is that for the AGPL, network use counts as distribution. If you do not accept these terms, you should use [serverD](https://github.com/Attorney-Online-Engineering-Task-Force/serverD), which uses GPL rather than AGPL.

See the [LICENSE](LICENSE.md) file for more information.
