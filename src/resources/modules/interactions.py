from ..structures import Bloxlink, Application, Args, Arguments, Response # pylint: disable=import-error, no-name-in-module
from ..constants import RELEASE # pylint: disable=import-error, no-name-in-module
from config import BOTS # pylint: disable=import-error, no-name-in-module
from ..exceptions import CancelCommand # pylint: disable=redefined-builtin, import-error
from ..secrets import TOKEN # pylint: disable=import-error, no-name-in-module
import discord

BOT_ID = BOTS[RELEASE]
COMMANDS_URL = f"https://discord.com/api/v8/applications/{BOT_ID}/commands"

fetch = Bloxlink.get_module("utils", attrs=["fetch"])
command_checks, execute_command = Bloxlink.get_module("commands", attrs=["command_checks", "execute_command"])


@Bloxlink.module
class Interactions(Bloxlink.Module):
    """slash commands and context menus"""

    def __init__(self):
        self.extensions = {}
        self.commands   = Bloxlink.get_module("commands", attrs=["commands"])


    async def __loaded__(self):
        #text, response = await fetch(COMMANDS_URL, "GET", headers={"Authorization": f"Bot {TOKEN}"}, raise_on_failure=False)
        #print(text, flush=True)

        return

        #applications = [self.app_command_to_json(a) for a in self.apps.values()]
        text, response = await fetch(COMMANDS_URL, "PUT", body=[], headers={"Authorization": f"Bot {TOKEN}"}, raise_on_failure=False)

        if response.status == 200:
            Bloxlink.log("Successfully synced the Applications")
        else:
            #print(applications, flush=True)
            print(response.status, text, flush=True)


    def app_command_to_json(self, application):
        return {
            "name": application.name,
            "type": application.type
        }

    def new_extension(self, application_structure):
        a = application_structure()
        app = Application(a)

        Bloxlink.log(f"Adding application {app.name}")

        if hasattr(a, "__setup__"):
            self.loop.create_task(a.__setup__())

        self.extensions[app.name] = app

        self.loop.create_task(self.inject_extension(app))

        return application_structure

    async def inject_extension(self, app):

        app_json = self.app_command_to_json(app)
        text, response = await fetch(COMMANDS_URL, "POST", body=app_json, headers={"Authorization": f"Bot {TOKEN}"}, raise_on_failure=False)

        if response.status not in (200, 201):
            Bloxlink.log(f"Extension {app.name} could not be added.")
            print(app, flush=True)
            print(response.status, text, flush=True)


    async def execute_interaction_command(self, typex, command_name, command_id, guild, channel, user, first_response, followups, interaction, resolved=None, subcommand=None, arguments=None):
        command = getattr(self, typex).get(command_name)

        if command:
            subcommand_attrs = {}
            guild_data = {}

            if subcommand and command.subcommands.get(subcommand):
                fn = command.subcommands[subcommand]
                subcommand_attrs = getattr(fn, "__subcommandattrs__", None)
            else:
                fn = command.fn

            CommandArgs = Args(
                command_name = command_name,
                real_command_name = command_name,
                message = None,
                guild_data = guild_data,
                flags = {},
                prefix = "/",
                has_permission = False,
                command = command,
                guild = guild,
                channel = channel,
                author = user,
                first_response = first_response,
                followups = followups,
                interaction = interaction,
                slash_command = True,
                resolved = resolved
            )

            CommandArgs.flags = {} if getattr(fn, "__flags__", False) else None # unsupported by slash commands

            response = Response(CommandArgs, user, channel, guild, None, slash_command=(first_response, followups, interaction))

            if Arguments.in_prompt(user):
                await response.send("You are currently in a prompt! Please complete it or say `cancel` to cancel.", hidden=True)
                raise CancelCommand

            CommandArgs.add(response=response)

            await command_checks(command, response, guild_data, user, channel, CommandArgs, None, guild, subcommand_attrs, slash_command=True)

            if command.slash_defer:
                try:
                    await response.slash_defer(command.slash_ephemeral)
                except discord.NotFound:
                    raise CancelCommand

            arguments = Arguments(CommandArgs, user, channel, command, guild, None, subcommand=(subcommand, subcommand_attrs) if subcommand else None, slash_command=arguments or True)

            await execute_command(command, fn, response, CommandArgs, user, channel, arguments, guild_data, guild, slash_command=command_id)
