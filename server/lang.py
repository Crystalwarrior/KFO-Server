import inspect
import sys
import yaml

try:
    with open("config/config.yaml", "r", encoding="utf-8") as cfg:
        config = yaml.safe_load(cfg)
except OSError:
    print("error: config/config.yaml wasn't found.")
    print("You are either running from the wrong directory, or")
    print("you forgot to rename config_sample (read the instructions).")
    sys.exit(1)

supported_languages = ["eng", "it"]
if "language" not in config or config["language"] not in supported_languages:
    config["language"] = "eng"

if config["language"] != "eng":
    try:
        with open(
            f"translations/{config['language']}.yaml", "r", encoding="latin-1"
        ) as translation:
            server_translation = yaml.safe_load(translation)
    except OSError:
        print(f"error: translation wasn't found.")
        print("You are either running from the wrong directory")
        sys.exit(1)

else:
    server_translation = None


def tr(string):
    if server_translation is None:
        return string
    filename = inspect.stack()[1][1].split("\\")[-1]
    function_name = inspect.stack()[1][3]
    if (
        filename in server_translation
        and function_name in server_translation[filename]
        and string in server_translation[filename][function_name]
    ):
        return server_translation[filename][function_name][string]
    else:
        return string
