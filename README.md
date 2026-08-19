
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

## Disclaimer
KFO-Server codebase accepts the use of LLMs (Large Language Models such as Claude Code, ChatGPT, Deepseek etc.) and tool assistance in certain parts of development.

### What is acceptable use of AI for maintainers?

* Boilerplate code
* Code cleanup, bug fixing, debugging
* Syntax error fixes
* Minor LLM assistance to understanding the codebase (prefer asking active maintainers however)
* Technical documentation with human oversight
* First-pass automated tests and Tooling
* CI/CD

### What is NOT an acceptable use of AI for maintainers?

* Automated AI agents making pull requests without human oversight
* Automated AI Pull Request descriptions, discussions and comments unless explictly only used for language translation into English for non-native speakers
* Any form of Generative AI, included but not limited to Art, Music, Video, Logos
* User-facing documentation entirely copywritten by LLMs beyond the first draft
* Any API calls to cloud-based AI for any purpose, including but not limited to user-facing text generation (for example AI Dungeon)

By using automation in code you take full responsibility for the code written by your tooling assistants. The lead maintainers take full responsibility to review your code, if it does as advertiesed, and reserves the right to reject your contributions should it be determined you have no knowledge or understanding of how your code actually works, or if it works at all.

### What is my personal stance on AI?

While the world is being set on fire by atrocious business practices, idiotic investors throwing large sums of money into something they don't understand, and the general complete lack of profitability in the AI business world, I've come to see that Large Language Models themselves are at least a decent auto-correct tool that can be effective at saving time on tedious tasks. I am a staunch believer in local-first models that are capable of running on as little as 6 GB of VRAM and 16 GB of RAM and would generally prefer using them. I have not paid a single dime to use AI and will always prefer using only free tools for as long as they're available, and if not, local-first open source models that only utilize exactly the amount of hardware I give them and nothing else.

My stance on the coding assistants and LLMs is different from generative AIas automation in coding has always been a thing in the forms of programming languages, debuggers, autocomplete, etc. However you should also never let AI drive your creative deicisions in code and you should at least be the architect and understand what you're actually using these for.

LLMs will never achieve human-level intelligence, and I wish instead of trying to create "jack-of-all-trades" square peg into a round hole money-guzzling environmentaly disasterous torment nexus machines the corporations would instead prioritize on making user-accessible, local and offline models that can be used like you would use any other normal program.

When it comes to Generative AI, I believe it is a complete and utter waste of time. It fundamentally cannot be "creative", and it will never come close to what it means to have that human touch in art. Generative AI images, videos, deepfakes and music have all been absolute slop and garbage with no exceptions. Please, treat yourself with more self-respect than using the slop-generators that completely remove humanity from something that should fundamentally stay human.
