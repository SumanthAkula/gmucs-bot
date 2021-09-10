from ..structures import Bloxlink # pylint: disable=import-error, no-name-in-module, no-name-in-module
from benedict import benedict


@Bloxlink.module
class Cache(Bloxlink.Module):
    def __init__(self):
        self._cache = benedict(keypath_separator=":")
        self.get_options = self.get_board = None

    async def __setup__(self):
        pass

    async def get(self, k, primitives=False, redis_hash=False, redis_hash_exists=False):
        return self._cache.get(k)


    async def set(self, k, v, check_primitives=True):
        self._cache[k] = v

    async def pop(self, k, primitives=False):
        self._cache.pop(k, None)


    async def clear(self, *exceptions):
        if exceptions:
            cache = benedict(keypath_separator=":")

            for exception in exceptions:
                cache_find = self._cache.get(exception)

                if cache_find:
                    cache[exception] = cache_find

            self._cache = cache
        else:
            self._cache = benedict(keypath_separator=":")


    async def get_guild_value(self, guild, *items, return_guild_data=False):
        item_values = {}
        guild_data = await self.get(f"guild_data:{guild.id}")

        if guild_data is None:
            guild_data = await self.r.table("guilds").get(str(guild.id)).run() or {"id": str(guild.id)}

            await self.set(f"guild_data:{guild.id}", guild_data, check_primitives=False)

        for item_name in items:
            item_default = None

            if isinstance(item_name, list):
                item_default = item_name[1]
                item_name = item_name[0]

            data = await self.get(f"guild_data:{guild.id}:{item_name}", primitives=False)

            if data is not None:
                item_values[item_name] = data

                continue

            item = guild_data.get(item_name, item_default)

            await self.set_guild_value(guild, item_name, item)

            item_values[item_name] = item

        if len(items) == 1:
            if return_guild_data:
                return item_values[item_name], guild_data
            else:
                return item_values[item_name]
        else:
            if return_guild_data:
                return item_values, guild_data
            else:
                return item_values


    async def set_guild_value(self, guild, item_name, value, guild_data=None):
        if guild_data:
            await self.set(f"guild_data:{guild.id}", guild_data, check_primitives=False)

        await self.set(f"guild_data:{guild.id}:{item_name}", value, check_primitives=False)


    async def clear_guild_data(self, guild):
        await self.pop(f"guild_data:{guild.id}", primitives=False)
