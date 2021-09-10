from os import listdir
from re import compile
from ..structures import Bloxlink # pylint: disable=import-error, no-name-in-module, no-name-in-module
from ..exceptions import RobloxAPIError, RobloxDown, RobloxNotFound, CancelCommand # pylint: disable=import-error, no-name-in-module, no-name-in-module
from ..constants import RELEASE, HTTP_RETRY_LIMIT # pylint: disable=import-error, no-name-in-module, no-name-in-module
from discord.errors import NotFound, Forbidden
from discord import Embed
from requests.utils import requote_uri
from async_timeout import timeout as a_timeout
from aiohttp.client_exceptions import ClientOSError, ServerDisconnectedError
import asyncio
import aiohttp
import json as json_

get_guild_value = Bloxlink.get_module("cache", attrs=["get_guild_value"])

@Bloxlink.module
class Utils(Bloxlink.Module):
    def __init__(self):
        self.option_regex = compile("(.+):(.+)")
        self.timeout = aiohttp.ClientTimeout(total=20)

    @staticmethod
    def get_files(directory):
        return [name for name in listdir(directory) if name[:1] != "." and name[:2] != "__" and name != "_DS_Store"]

    @staticmethod
    async def suppress_timeout_errors(awaitable):
        try:
            return await awaitable
        except asyncio.TimeoutError:
            pass

    async def post_event(self, guild, guild_data, event_name, text, color=None):
        if guild_data:
            log_channels = guild_data.get("logChannels")
        else:
            log_channels = await get_guild_value(guild, "logChannels")

        log_channels = log_channels or {}
        log_channel  = log_channels.get(event_name) or log_channels.get("all")

        if log_channel:
            text_channel = guild.get_channel(int(log_channel))

            if text_channel:
                embed = Embed(title=f"{event_name.title()} Event", description=text)
                embed.colour = color

                try:
                    await text_channel.send(embed=embed)
                except (Forbidden, NotFound):
                    pass

    async def fetch(self, url, method="GET", params=None, headers=None, json=None, text=True, bytes=False, raise_on_failure=True, retry=HTTP_RETRY_LIMIT, timeout=20):
        params  = params or {}
        headers = headers or {}

        url = requote_uri(url)

        if RELEASE == "LOCAL":
            Bloxlink.log(f"Making HTTP request: {url}")

        for k, v in params.items():
            if isinstance(v, bool):
                params[k] = "true" if v else "false"

        try:
            async with a_timeout(timeout): # I noticed sometimes the aiohttp timeout parameter doesn't work. This is added as a backup.
                async with self.session.request(method, url, json=json, params=params, headers=headers, timeout=timeout) as response:
                    if text:
                        text = await response.text()

                    if text == "The service is unavailable." or response.status == 503:
                        raise RobloxDown

                    if raise_on_failure:
                        if response.status >= 500:
                            if retry != 0:
                                retry -= 1
                                await asyncio.sleep(1.0)

                                return await self.fetch(url, raise_on_failure=raise_on_failure, bytes=bytes, text=text, params=params, headers=headers, retry=retry, timeout=timeout)

                            raise RobloxAPIError

                        elif response.status == 400:
                            raise RobloxAPIError
                        elif response.status == 404:
                            raise RobloxNotFound

                    if bytes:
                        return await response.read(), response
                    elif text:
                        return text, response
                    else:
                        return response

        except ServerDisconnectedError:
            if retry != 0:
                return await self.fetch(url, raise_on_failure=raise_on_failure, retry=retry-1, timeout=timeout)
            else:
                raise ServerDisconnectedError

        except ClientOSError:
            # TODO: raise HttpError with non-roblox URLs
            raise RobloxAPIError

        except asyncio.TimeoutError:
            raise RobloxDown