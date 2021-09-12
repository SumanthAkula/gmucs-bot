from importlib import import_module
from os import environ as env
from discord import AutoShardedClient, AllowedMentions, Intents, Game
from config import WEBHOOKS, PREFIX # pylint: disable=E0611
from ..constants import TABLE_STRUCTURE, RELEASE, PLAYING_STATUS # pylint: disable=import-error, no-name-in-module
from . import Permissions # pylint: disable=import-error, no-name-in-module
from async_timeout import timeout
import functools
import traceback
import datetime
import logging
import aiohttp
import asyncio; loop = asyncio.get_event_loop()

try:
    from rethinkdb import RethinkDB; r = RethinkDB() # pylint: disable=no-name-in-module
except ImportError:
    import rethinkdb as r
finally:
    r.set_loop_type("asyncio")

LOG_LEVEL = env.get("LOG_LEVEL", "INFO").upper()
LABEL = env.get("LABEL", "Bloxlink")
SHARD_SLEEP_TIME = int(env.get("SHARD_SLEEP_TIME", "5"))

logger = logging.getLogger()


class BloxlinkStructure(AutoShardedClient):
    loaded_modules = {}

    def __init__(self, *args, **kwargs): # pylint: disable=W0235
        super().__init__(*args, **kwargs) # this seems useless, but it's very necessary.
        #loop.run_until_complete(self.get_session())
        loop.set_exception_handler(self._handle_async_error)

    async def get_session(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) # headers={"Connection": "close"}

    @staticmethod
    def log(*text, level=LOG_LEVEL):
        print(f"{LABEL} | {LOG_LEVEL} | {'| '.join(text)}", flush=True)

    def error(self, text, title=None):
        logger.exception(text)
        loop.create_task(self._error(str(text), title=title))

    async def _error (self, text, title=None):
        if (not text) or text == "Unclosed connection":
            return

        webhook_data = {
            "username": "Cluster Instance",

            "embeds": [{
                "timestamp": datetime.datetime.now().isoformat(),
                "fields": [
                    {"name": "Traceback", "value": f"```python\n{text[0:2000]}\n```"}
                ],
                "color": 13319470,
            }]
        }

        if title:
            webhook_data["embeds"][0]["title"] = title

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
                try:
                    await session.post(WEBHOOKS["ERRORS"], json=webhook_data)
                except Exception as e:
                    logger.exception(e)
                    pass

        except asyncio.TimeoutError:
            pass

    def _handle_async_error(self, loop, context):
        exception   = context.get("exception")
        future_info = context.get("future")
        title = None

        if exception:
            title = exception.__class__.__name__
            msg = "".join(traceback.format_exception(etype=type(exception), value=exception, tb=exception.__traceback__))
        else:
            msg = future_info and str(future_info) or str(context["message"])

        self.error(msg, title=title)

    @staticmethod
    def module(module):
        new_module = module()

        module_name = module.__name__.lower()
        module_dir = module.__module__.lower() # ".".join((module.__module__, module.__qualname__))

        if hasattr(new_module, "__setup__"):
            loop.create_task(new_module.__setup__())

        Bloxlink.log(f"Loaded {module_name}")

        if hasattr(new_module, "__loaded__"):
            loop.create_task(new_module.__loaded__())

        if BloxlinkStructure.loaded_modules.get(module_dir):
            BloxlinkStructure.loaded_modules[module_dir][module_name] = new_module
        else:
            BloxlinkStructure.loaded_modules[module_dir] = {module_name: new_module}

        return new_module

    @staticmethod
    def get_module(dir_name, *, name_override=None, name_override_pattern="", path="resources.modules", attrs=None):
        save_as  = f"{name_override_pattern.lower()}{(dir_name).lower()}"
        modules = BloxlinkStructure.loaded_modules.get(save_as)
        name_obj = (name_override or dir_name).lower()

        class_obj = None
        module = None

        if not modules:
            import_name = f"{path}.{dir_name}".replace("src/", "").replace("/",".").replace(".py","")

            try:
                module = import_module(import_name)
            except (ModuleNotFoundError, ImportError) as e:
                Bloxlink.log(f"ERROR | {e}")
                traceback_text = traceback.format_exc()
                traceback_text = len(traceback_text) < 500 and traceback_text or f"...{traceback_text[len(traceback_text)-500:]}"
                Bloxlink.error(traceback_text, title=f"{dir_name}.py")

            except Exception as e:
                Bloxlink.log(f"ERROR | Module {dir_name} failed to load: {e}")
                traceback_text = traceback.format_exc()
                traceback_text = len(traceback_text) < 500 and traceback_text or f"...{traceback_text[len(traceback_text)-500:]}"
                Bloxlink.error(traceback_text, title=f"{dir_name}.py")
            else:
                for attr_name in dir(module):
                    if attr_name.lower() == name_obj:
                        class_obj = getattr(module, attr_name)
                        break

        if not attrs:
            return module or class_obj

        if class_obj is None and module:
            for attr_name in dir(module):
                if attr_name.lower() == name_obj:
                    class_obj = getattr(module, attr_name)

                    break


        if class_obj is not None:
            if attrs:
                attrs_list = list()

                if not isinstance(attrs, list):
                    attrs = [attrs]

                for attr in attrs:
                    if hasattr(class_obj, attr):
                        attrs_list.append(getattr(class_obj, attr))

                if len(attrs_list) == 1:
                    return attrs_list[0]
                else:
                    if not attrs_list:
                        return None

                    return (*attrs_list,)
            else:
                return class_obj

        raise RuntimeError(f"Unable to find module {name_obj} from {dir_name}")

    @staticmethod
    def auto_reconnect(instance):
        if instance._instance is None or not instance._instance.is_open():
            loop.create_task(instance.reconnect())

    @staticmethod
    def command(*args, **kwargs):
        return Bloxlink.get_module("commands", attrs="new_command", name_override_pattern="Command_")(*args, **kwargs)

    @staticmethod
    def extension(*args, **kwargs):
        return Bloxlink.get_module("interactions", attrs="new_extension", name_override_pattern="Extension_")(*args, **kwargs)

    @staticmethod
    def subcommand(**kwargs):
        def decorator(f):
            f.__issubcommand__ = True
            f.__subcommandattrs__ = kwargs

            @functools.wraps(f)
            def wrapper(self, *args):
                return f(self, *args)

            return wrapper

        return decorator

    @staticmethod
    def flags(fn):
        fn.__flags__ = True
        return fn

    Permissions = Permissions.Permissions # pylint: disable=no-member

    def __repr__(self):
        return "< Bloxlink Client >"


intents = Intents.none()

intents.members = True # pylint: disable=assigning-non-slot
intents.guilds = True # pylint: disable=assigning-non-slot
intents.guild_reactions = True # pylint: disable=assigning-non-slot
intents.guild_messages = True # pylint: disable=assigning-non-slot
intents.dm_messages = True # pylint: disable=assigning-non-slot
intents.bans = True # pylint: disable=assigning-non-slot

if RELEASE == "PRO":
    intents.guild_typing = True # pylint: disable=assigning-non-slot


Bloxlink = BloxlinkStructure(
    chunk_guilds_at_startup=False,
    allowed_mentions=AllowedMentions(everyone=False, users=True, roles=False),
    intents=intents,
    activity=Game(PLAYING_STATUS.format(prefix=PREFIX))
)

class Module:
    client = Bloxlink
    session = aiohttp.ClientSession(loop=loop, timeout=aiohttp.ClientTimeout(total=20))
    loop = loop

Bloxlink.Module = Module
