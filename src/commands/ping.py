from resources.structures.Bloxlink import Bloxlink # pylint: disable=import-error
from resources.exceptions import PermissionError # pylint: disable=import-error
from discord.errors import NotFound, Forbidden
import time


@Bloxlink.command
class PingCommand(Bloxlink.Module):
    """measure the latency between the bot and Discord"""

    def __init__(self):
        self.dm_allowed    = True
        self.slash_enabled = True

    async def __main__(self, CommandArgs):
        channel  = CommandArgs.channel
        response = CommandArgs.response

        t_1 = time.perf_counter()

        try:
            await channel.trigger_typing()
        except (NotFound, Forbidden):
            pass

        t_2 = time.perf_counter()
        time_delta = round((t_2-t_1)*1000)

        await response.send(f"Pong! `{time_delta}ms`", hidden=True)
