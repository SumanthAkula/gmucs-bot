from ..structures.Bloxlink import Bloxlink # pylint: disable=import-error, no-name-in-module
from ..exceptions import CancelCommand # pylint: disable=import-error, no-name-in-module
from discord import User, Message


execute_interaction_command = Bloxlink.get_module("interactions", attrs=["execute_interaction_command"])


@Bloxlink.event
async def on_interaction(interaction):
    data = interaction.data
    command_name = interaction.data.get("name")
    command_id   = interaction.data.get("id")
    command_args = []

    first_response = interaction.response
    followups      = interaction.followup

    guild   = interaction.guild
    channel = interaction.channel
    user    = interaction.user

    if data.get("target_id"):
        resolved = None

        if data.get("resolved"):
            if data["resolved"].get("users"):
                resolved = User(state=interaction._state, data=list(data["resolved"]["users"].values())[0])
            else:
                resolved = Message(state=interaction._state, channel=channel, data=list(data["resolved"]["messages"].values())[0])

        try:
            await execute_interaction_command("extensions", command_name, command_id, guild=guild, channel=channel, user=user,
                                              first_response=first_response, interaction=interaction, followups=followups,
                                              resolved=resolved
                                              )
        except CancelCommand:
            pass
    else:
        if not command_name:
            return

        subcommand = None

        if data.get("options"):
            for arg in data["options"]:
                if arg.get("options"):
                    subcommand = arg["name"]

                    for arg2 in arg["options"]:
                        command_args.append([arg2["name"], arg2["value"]])
                else:
                    if arg.get("value") is not None:
                        command_args.append([arg["name"], arg["value"]])
                    else:
                        subcommand = arg["name"]

        if not guild:
            return

        try:
            await execute_interaction_command("commands", command_name, guild=guild, channel=channel,
                                                user=user, first_response=first_response,
                                                interaction=interaction,
                                                followups=followups, command_id=command_id,
                                                subcommand=subcommand, arguments=command_args)
        except CancelCommand:
            pass
