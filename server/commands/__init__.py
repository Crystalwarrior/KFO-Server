def call(client, cmd, arg):
    import sys

    me = sys.modules[__name__]
    called_function = f"ooc_cmd_{cmd}"
    if len(client.server.command_aliases) > 0 and not hasattr(me, called_function):
        if cmd in client.server.command_aliases:
            called_function = f"ooc_cmd_{client.server.command_aliases[cmd]}"
    if not hasattr(me, called_function):
        client.send_ooc(
            f"Invalid command: {cmd}. Use /help to find up-to-date commands."
        )
        return
    getattr(me, called_function)(client, arg)


def submodules():
    """Get all command-related submodules."""
    import sys
    import inspect

    me = sys.modules[__name__]
    for _, v in inspect.getmembers(me):
        if inspect.ismodule(v):
            yield v


def reload():
    """Reload all submodules."""
    import sys
    import importlib

    me = sys.modules[__name__]
    for module in submodules():
        m = importlib.reload(module)
        for f in m.__all__:
            me.__dict__[f] = m.__dict__[f]


def help(command):
    import sys
    import inspect

    try:
        doc = inspect.getdoc(getattr(sys.modules[__name__], command))
    except AttributeError:
        raise
    return doc


def list_submodules():
    """
    Lists all known submodules.
    """
    subm = ""
    for module in submodules():
        # Only return the name of the module and not the whole hierarchy
        name = module.__name__.split(".")[-1]
        subm += f"{name}\n"
    return subm


def list_commands(submodule=""):
    """
    Lists all known commands.
    :param submodule: Which submodule to search. Lists all commands if blank. Raises attribute error if submodule not found.
    """
    import inspect

    cmds = ""
    modules = [
        a
        for a in submodules()
        if submodule == "" or a.__name__.split(".")[-1] == submodule
    ]
    if len(modules) == 0:
        raise AttributeError
    for module in modules:
        for func in module.__all__:
            doc = inspect.getdoc(module.__dict__[func])
            if doc is None:
                doc = "(no docs)"
            else:
                # Find the first sentence (assuming it ends in a period).
                doc = doc[: doc.find(".") + 1]
            prefix = "ooc_cmd_"
            if func.startswith(prefix):
                func = func[len(prefix):]
            cmds += f"{func} - {doc}\n"
    return cmds


def mod_only(area_owners=False, hub_owners=False):
    import functools
    from ..exceptions import ClientError

    def decorator(func):
        @functools.wraps(func)
        def wrapper_mod_only(client, arg, *args, **kwargs):
            if (
                not client.is_mod
                and (not area_owners or client not in client.area.owners)
                and (not hub_owners or client not in client.area.area_manager.owners)
            ):
                raise ClientError("You must be authorized to do that.")
            func(client, arg, *args, **kwargs)

        return wrapper_mod_only

    return decorator


# Note that only the members of __all__ in each module will be imported.
# There must be an __all__ in each module in order for reloading
# to work properly.
from .admin import *
from .area_access import *
from .areas import *
from .casing import *
from .character import *
from .fun import *
from .hubs import *
from .messaging import *
from .music import *
from .roleplay import *
