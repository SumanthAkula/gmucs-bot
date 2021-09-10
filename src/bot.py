from os import environ
import asyncio
import logging
import signal
import os
from resources.constants import MODULE_DIR # pylint: disable=import-error, no-name-in-module
from resources.structures.Bloxlink import Bloxlink # pylint: disable=import-error, no-name-in-module
from resources.secrets import TOKEN # , SENTRY_URL, VALID_SECRETS # pylint: disable=import-error, no-name-in-module

logger = logging.getLogger()
logging.basicConfig(level=getattr("logging", environ.get("DEBUG_MODE", "WARNING"), "WARNING"))


loop = asyncio.get_event_loop()


async def register_modules():
    get_files = Bloxlink.get_module("utils", attrs="get_files")

    for directory in MODULE_DIR: # pylint: disable=E1101
        files = get_files(directory)

        for filename in [f.replace(".py", "") for f in files]:
            Bloxlink.get_module(path=directory, dir_name=filename)

async def handle_signal(sig):
    """handle the Unix SIGINT and SIGTERM signals.
       `SystemExit`s are incorrectly caught, so we have to use
       os._exit until this is fixed"""

    Bloxlink.log(f"Handling signal {sig}")

    await Bloxlink.close_db()
    await Bloxlink.close()

    loop.stop()

    for task in asyncio.all_tasks():
        task.cancel()

    os._exit(0)

async def signals_handler():
    loop = asyncio.get_event_loop()

    for signame in ("SIGINT", "SIGTERM"):
        loop.add_signal_handler(getattr(signal, signame),
                                lambda: asyncio.ensure_future(handle_signal(signame), loop=loop))

async def main():
    await signals_handler()
    await register_modules()



if __name__ == "__main__":
    loop.create_task(main())

    Bloxlink.run(TOKEN)
