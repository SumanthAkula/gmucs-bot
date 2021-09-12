import re
import traceback
import asyncio
from concurrent.futures._base import CancelledError
from discord.errors import Forbidden, NotFound, HTTPException
from discord import User
from ..exceptions import PermissionError, CancelledPrompt, Message, CancelCommand, RobloxAPIError, RobloxDown, Error # pylint: disable=redefined-builtin, import-error
from ..structures import Bloxlink, Args, Command, Arguments, Response # pylint: disable=import-error, no-name-in-module
from ..constants import DEFAULTS, RELEASE # pylint: disable=import-error, no-name-in-module
from ..secrets import TOKEN # pylint: disable=import-error, no-name-in-module
from config import BOTS # pylint: disable=import-error, no-name-in-module, no-name-in-module

fetch = Bloxlink.get_module("utils", attrs=["fetch"])
get_guild_value = Bloxlink.get_module("cache", attrs=["get_guild_value"])


BOT_ID = BOTS[RELEASE]
COMMANDS_URL = f"https://discord.com/api/v8/applications/{BOT_ID}/commands" if RELEASE != "LOCAL" else f"https://discord.com/api/v8/applications/{BOT_ID}/guilds/842537684785823755/commands"
PREFIX = DEFAULTS["prefix"]

@Bloxlink.module
class Commands(Bloxlink.Module):
    def __init__(self):
        self.commands = {}

    async def __loaded__(self):
        """sync the slash commands"""

        slash_commands = [self.slash_command_to_json(c) for c in self.commands.values() if c.slash_enabled]
        text, response = await fetch(COMMANDS_URL, "PUT", json=slash_commands, headers={"Authorization": f"Bot {TOKEN}"}, raise_on_failure=False)

        if response.status == 200:
            Bloxlink.log("Successfully synced Slash Commands")
        else:
            print(slash_commands, flush=True)
            print(response.status, text, flush=True)

    async def redirect_command(self, command_name, ):
        pass

    async def command_checks(self, command, response, guild_data, author, channel, CommandArgs, message=None, guild=None, subcommand_attrs=None, slash_command=False):
        channel_id = str(channel.id) if channel else None
        dm = not bool(guild)
        subcommand_attrs = subcommand_attrs or {}

        if guild:
            if not command.bypass_channel_perms:
                ignored_channels = guild_data.get("ignoredChannels", {})
                disabled_commands = guild_data.get("disabledCommands", {})

                author_perms = author.guild_permissions

                if guild.owner_id != author.id and not (author_perms.manage_guild or author_perms.administrator):
                    if ignored_channels.get(channel_id) or (channel.category and ignored_channels.get(str(channel.category.id))):
                        await response.send(f"The server admins have **disabled** all commands in channel {channel.mention}.", dm=True, hidden=True, strict_post=True, no_dm_post=True)

                        if message:
                            try:
                                await message.delete()
                            except (Forbidden, NotFound):
                                pass

                        raise CancelCommand

                    if command.name in disabled_commands.get("global", []):
                        await response.send(f"The server admins have **disabled** the command `{command.name}` globally.", dm=True, hidden=True, strict_post=True, no_dm_post=True)

                        if message:
                            try:
                                await message.delete()
                            except (Forbidden, NotFound):
                                pass

                        raise CancelCommand

                    elif disabled_commands.get("channels", {}).get(channel_id, {}).get(command.name):
                        await response.send(f"The server admins have **disabled** the command `{command.name}` in channel {channel.mention}.", dm=True, hidden=True, strict_post=True, no_dm_post=True)

                        if message:
                            try:
                                await message.delete()
                            except (Forbidden, NotFound):
                                pass

                        raise CancelCommand

        if not (command.dm_allowed or guild):
            await response.send("This command does not support DM; please run it in a server.", hidden=True)
            raise CancelCommand

        try:
            await command.check_permissions(author, guild, dm=dm, **subcommand_attrs)
        except PermissionError as e:
            if subcommand_attrs.get("allow_bypass"):
                CommandArgs.has_permission = False
            elif command.permissions.allow_bypass:
                CommandArgs.has_permission = False
            else:
                await response.error(e, hidden=True)
                raise CancelCommand

        except Message as e:
            message_type = "send" if e.type == "info" else e.type
            response_fn = getattr(response, message_type, response.send)

            if e.message:
                await response_fn(e, hidden=True)

            if subcommand_attrs.get("allow_bypass"):
                CommandArgs.has_permission = False
            elif command.permissions.allow_bypass:
                CommandArgs.has_permission = False
            else:
                raise CancelCommand

        else:
            CommandArgs.has_permission = True


    async def execute_command(self, command, fn, response, CommandArgs, author, channel, arguments, guild_data=None, guild=None, message=None, after_text=None, slash_command=False):
        my_permissions = guild and guild.me.guild_permissions

        try:
            await arguments.initial_command_args(after_text)

            CommandArgs.add(prompt=arguments.prompt)
            response.prompt = arguments.prompt # pylint: disable=no-member

            await fn(CommandArgs)
        except PermissionError as e:
            if e.message:
                await response.error(e)
            else:
                await response.error("I'm missing permissions for this command. Please give me the appropriate permissions.")
        except Forbidden as e:
            if e.args:
                await response.error(e)
            else:
                await response.error("I'm missing permissions for this command. Please give me the appropriate permissions.")
        except CancelledPrompt as e:
            arguments.cancelled = True

            if e.message:
                text = f"**Cancelled prompt**: {e}"
            else:
                text = f"**Cancelled prompt.**"

            if ((e.type == "delete" and not e.dm) and guild_data.get("promptDelete", DEFAULTS.get("promptDelete"))):
                if my_permissions and my_permissions.manage_messages:
                    if message:
                        try:
                            await message.delete()
                        except (Forbidden, NotFound):
                            pass

                    if slash_command and response.first_slash_command:
                        await response.first_slash_command.delete()
                else:
                    await response.send(text, dm=e.dm, no_dm_post=True)
            else:
                if my_permissions and my_permissions.manage_messages:
                    if slash_command and response.first_slash_command:
                        await response.first_slash_command.edit(content="**_Command finished._**", view=None, embed=None)

                await response.send(text, dm=e.dm, no_dm_post=True)

        except Message as e:
            message_type = "send" if e.type == "send" else e.type
            response_fn = getattr(response, message_type, response.send)

            if e.message:
                await response_fn(e, hidden=e.hidden)
            else:
                await response_fn("This command closed unexpectedly.")
        except Error as e:
            if e.message:
                await response.error(e, hidden=e.hidden)
            else:
                await response.error("This command has unexpectedly errored.")
        except CancelCommand as e:
            if e.message:
                await response.send(e, mention_author=True)
        except NotImplementedError:
            await response.error("The option you specified is currently not implemented, but will be coming soon!")
        except CancelledError:
            pass
        except Exception as e:
            """
            error_id = Bloxlink.error(e, command=command_name, user=(author.id, str(author)), guild=guild and f"id:{guild.id}")

            if error_id:
                await response.error("We've experienced an unexpected error. You may report this "
                                        f"error with ID `{error_id}` in our support server: {SERVER_INVITE}.")
            else:
                await response.error("An unexpected error occured.")
            """

            await response.error("This command has unexpectedly errored.")
            Bloxlink.error(traceback.format_exc(), title=f"Error source: {command.name}.py\n{f'Guild ID: {guild.id}' if guild else ''}")

        finally:
            delete_messages = response.delete_message_queue
            prompt_messages = arguments.messages
            bot_responses   = response.bot_responses

            if arguments.dm_post and not response.webhook_only:
                if arguments.cancelled:
                    content = f"{author.mention}, **this DM prompt has been cancelled.**"
                else:
                    content = f"{author.mention}, **this DM prompt has finished.**"

                try:
                    await arguments.dm_post.edit(content=content)
                except NotFound:
                    pass

            if my_permissions and my_permissions.manage_messages:
                delete_options = await get_guild_value(guild, ["promptDelete", DEFAULTS.get("promptDelete")], ["deleteCommands", DEFAULTS.get("deleteCommands")])

                delete_commands_after = delete_options["deleteCommands"]
                prompt_delete         = delete_options["promptDelete"]

                if prompt_delete:
                    if prompt_messages:
                        delete_messages += prompt_messages
                else:
                    delete_messages = [] # we'll populate this with the command information

                if delete_commands_after:
                    if message:
                        delete_messages.append(message.id)

                    delete_messages += bot_responses

                    await asyncio.sleep(delete_commands_after)

                if delete_messages:
                    if slash_command and response.first_slash_command and not arguments.cancelled:
                        await response.first_slash_command.edit(content="_**Command finished.**_", embed=None, view=None)

                    try:
                        await channel.purge(limit=100, check=lambda m: (m.id in delete_messages) or (delete_commands_after and re.search(f"^[</{command.name}:{slash_command}>]", m.content)))
                    except (Forbidden, HTTPException):
                        pass


    async def parse_message(self, message, guild_data=None):
        guild = message.guild
        content = message.content
        author = message.author
        channel = message.channel

        guild_id   = guild and str(guild.id)

        client_match = re.search(f"^(<@!?{self.client.user.id}>)", content)
        check = (content[:len(PREFIX)].lower() == PREFIX.lower() and PREFIX) or client_match and client_match.group(0)

        if check:
            after = content[len(check):].strip()
            args = after.split(" ")
            command_name = args[0] and args[0].lower()
            del args[0]

            if command_name:
                for index, command in self.commands.items():
                    if index == command_name or command_name in command.aliases:
                        if guild:
                            if isinstance(author, User):
                                try:
                                    author = await guild.fetch_member(author.id)
                                except NotFound:
                                    raise CancelCommand

                        # guild_data = guild_data or (guild and (await self.r.table("guilds").get(guild_id).run() or {"id": guild_id})) or {}
                        guild_data = {"id": guild_id}

                        fn = command.fn
                        subcommand_attrs = {}
                        subcommand = False

                        if args:
                            # subcommand checking
                            subcommand = command.subcommands.get(args[0])
                            if subcommand:
                                fn = subcommand
                                subcommand_attrs = getattr(fn, "__subcommandattrs__", None)
                                del args[0]

                        after = args and " ".join(args) or ""

                        CommandArgs = Args(
                            command_name = index,
                            real_command_name = command_name,
                            message = message,
                            channel = message.channel,
                            author  = message.author,
                            guild = message.guild,
                            guild_data = guild_data,
                            flags = {},
                            has_permission = False,
                            command = command,
                            slash_command = False
                        )

                        if getattr(fn, "__flags__", False):
                            flags, flags_str = command.parse_flags(after)
                            content = content.replace(flags_str, "")
                            message.content = content
                            after = after.replace(flags_str, "")
                            CommandArgs.flags = flags

                        response = Response(CommandArgs, author, channel, guild, message, slash_command=False)

                        CommandArgs.add(response=response)

                        await self.command_checks(command, response, guild_data, author, channel, CommandArgs, message, guild, subcommand_attrs, slash_command=False)

                        arguments = Arguments(CommandArgs, author, channel, command, guild, message, subcommand=(subcommand, subcommand_attrs) if subcommand else None, slash_command=False)

                        await self.execute_command(command, fn, response, CommandArgs, author, channel, arguments, guild_data, guild, message, after, False)

                        break


    def slash_command_to_json(self, command):
        type_enums = {
            "string":  3,
            "number":  4,
            "boolean": 5,
            "user":    6,
            "channel": 7,
            "role":    8
        }

        def prompts_to_json(prompts):
            def single_prompt(prompt):
                option = {
                    "name": prompt["name"],
                    "type": type_enums.get(prompt.get("type", "string"), type_enums.get("string")),
                    "description": prompt.get("slash_desc", prompt["prompt"]),
                    "required": not (prompt.get("optional") or prompt.get("slash_optional")),
                    "choices": [{
                        "name": choice,
                        "value": choice

                    } for choice in prompt.get("choices", []) if len(prompt.get("choices", [])) <= 25 ]
                }

                return option

            if isinstance(prompts, dict):
                return single_prompt(prompts)
            else:
                options = []

                for prompt in prompts:
                    options.append(single_prompt(prompt))

                return options

        if command.slash_enabled:
            json = {
                "name": command.name,
                "description": command.description,
                "options": []
            }

            if command.subcommands:
                for subcommand_name, subcommand_fn in command.subcommands.items():
                    subcommand_attrs = getattr(subcommand_fn, "__subcommandattrs__")
                    subcommand_options = subcommand_attrs.get("slash_args") or subcommand_attrs.get("arguments")

                    json["options"].append({
                        "name": subcommand_name,
                        "type": 1,
                        "description": subcommand_attrs.get("slash_desc", subcommand_fn.__doc__),
                        "options": prompts_to_json(subcommand_options) if subcommand_options else None,
                    })

            elif command.slash_args or command.arguments:
                json["options"] += prompts_to_json(command.slash_args or command.arguments)


            return json


    def new_command(self, command_structure, addon=None):
        c = command_structure()
        command = Command(c)

        Bloxlink.log(f"Adding command {command.name}")

        if hasattr(c, "__setup__"):
            self.loop.create_task(c.__setup__())

        for attr_name in dir(command_structure):
            attr = getattr(c, attr_name)

            if callable(attr) and hasattr(attr, "__issubcommand__"):
                command.subcommands[attr_name] = attr

        self.commands[command.name] = command
        command.addon = addon

        self.loop.create_task(self.inject_command(command))

        return command_structure


    async def inject_command(self, command):
        subcommands = []

        if command.subcommands:
            for subcommand_name, subcommand in command.subcommands.items():
                subcommand_description = subcommand.__doc__ or "N/A"
                subcommands.append({"id": subcommand_name, "description": subcommand_description})
