from discord import Embed
import discord
from ..structures.Bloxlink import Bloxlink # pylint: disable=import-error, no-name-in-module
from ..exceptions import CancelledPrompt # pylint: disable=import-error, no-name-in-module
from ..constants import RED_COLOR, INVISIBLE_COLOR # pylint: disable=import-error, no-name-in-module
from ..constants import IS_DOCKER, PROMPT # pylint: disable=import-error, no-name-in-module
import asyncio

get_resolver = Bloxlink.get_module("resolver", attrs="get_resolver")
suppress_timeout_errors = Bloxlink.get_module("utils", attrs="suppress_timeout_errors")

prompts = {}


class Arguments:
    def __init__(self, CommandArgs, author, channel, command, guild=None, message=None, subcommand=None, slash_command=None):
        self.channel = channel
        self.author  = author
        self.message = message
        self.guild   = guild

        self.command    = command
        self.subcommand = subcommand

        self.command_args = CommandArgs
        self.response     = CommandArgs.response

        self.messages  = []
        self.dm_post   = None
        self.cancelled = False
        self.dm_false_override = False
        self.first_slash = True
        self.skipped_args = []

        self.slash_command = slash_command

        self.parsed_args = {}

    async def initial_command_args(self, text_after=None):
        if self.subcommand:
            prompts = self.subcommand[1].get("arguments")
        else:
            prompts = self.command.arguments

        if self.slash_command:
            if not isinstance(self.slash_command, bool):
                self.skipped_args = [x[1] for x in self.slash_command]

            self.parsed_args = await self.prompt(prompts, slash_command=True) if prompts else {}
            self.command_args.add(parsed_args=self.parsed_args, string_args=[])

            return

        arg_len = len(prompts) if prompts else 0
        skipped_args = []
        split = text_after.split(" ")
        temp = []

        for arg in split:
            if arg:
                if arg.startswith('"') and arg.endswith('"'):
                    arg = arg.replace('"', "")

                if len(skipped_args) + 1 == arg_len:
                    t = text_after.replace('"', "")
                    toremove = " ".join(skipped_args)

                    if t.startswith(toremove):
                        t = t[len(toremove):]

                    t = t.strip()

                    skipped_args.append(t)

                    break

                if arg.startswith('"') or (temp and not arg.endswith('"')):
                    temp.append(arg.replace('"', ""))

                elif arg.endswith('"'):
                    temp.append(arg.replace('"', ""))
                    skipped_args.append(" ".join(temp))
                    temp.clear()

                else:
                    skipped_args.append(arg)

        if len(skipped_args) > 1:
            self.skipped_args = skipped_args
        else:
            if text_after:
                self.skipped_args = [text_after]
            else:
                self.skipped_args = []

        if prompts:
            self.parsed_args = await self.prompt(prompts)

        self.command_args.add(parsed_args=self.parsed_args, string_args=text_after and text_after.split(" ") or [])


    async def say(self, text, type=None, footer=None, embed_title=None, is_prompt=True, embed_color=INVISIBLE_COLOR, embed=True, dm=False, components=None):
        embed_color = embed_color or INVISIBLE_COLOR
        view = discord.ui.View(timeout=PROMPT["PROMPT_TIMEOUT"])

        if components:
            for component in components:
                if isinstance(component, discord.ui.Button):
                    component.custom_id = component.label

                view.add_item(item=component)

        if type != "error":
            view.add_item(item=discord.ui.Button(style=discord.ButtonStyle.secondary, label="Cancel", custom_id="cancel"))

        if self.dm_false_override:
            dm = False

        if footer:
            footer = f"{footer}\n"
        else:
            footer = ""

        if not embed:
            if is_prompt:
                text = f"{text}\n\n{footer}\nThis prompt will automatically cancel in {PROMPT['PROMPT_TIMEOUT']} seconds."

            return await self.response.send(text, dm=dm, no_dm_post=True, strict_post=True, view=view)

        description = f"{text}\n\n{footer}"

        if type == "error":
            new_embed = Embed(title=embed_title or "Prompt Error")
            new_embed.colour = RED_COLOR
        else:
            new_embed = Embed(title=embed_title or "Prompt")
            new_embed.colour = embed_color

        new_embed.description = description

        new_embed.set_footer(text=f"This prompt will automatically cancel in {PROMPT['PROMPT_TIMEOUT']} seconds.")

        msg = await self.response.send(embed=new_embed, dm=dm, no_dm_post=True, strict_post=True, ignore_errors=True, view=view)

        if not msg:
            if is_prompt:
                text = f"{text}\n\nSay **cancel** to cancel.\n\nThis prompt will automatically cancel in {PROMPT['PROMPT_TIMEOUT']} seconds."

            return await self.response.send(text, dm=dm, no_dm_post=True, strict_post=True, view=view)

        if msg and not dm:
            if self.slash_command and self.first_slash:
                self.first_slash = False
                return msg

            self.messages.append(msg.id)

        return msg


    @staticmethod
    def in_prompt(author):
        return prompts.get(author.id)

    async def prompt(self, arguments, error=False, embed=True, dm=False, no_dm_post=False, last=False, slash_command=False):
        prompts[self.author.id] = True

        checked_args = 0
        err_count = 0
        resolved_args = {}
        had_args = {x:True for x, _ in enumerate(self.skipped_args)}
        last_prompt = None

        if dm:
            if IS_DOCKER:
                try:
                    m = await self.author.send("Loading setup...")
                except discord.errors.Forbidden:
                    dm = False
                else:
                    try:
                        await m.delete()
                    except discord.errors.NotFound:
                        pass

                    if not no_dm_post:
                        self.dm_post = await self.response.send(f"{self.author.mention}, **please check your DMs to continue.**", ignore_errors=True, strict_post=True)
            else:
                dm = False

        try:
            if slash_command:
                prompt_groups = {}

                for i, prompt in enumerate(arguments): # to make easy O(1) lookup to get the position to append the arg in
                    prompt_groups[prompt["name"]] = i

                for slash_command_arg in self.slash_command:
                    arg_pos = prompt_groups.get(slash_command_arg[0])
                    if arg_pos:
                        self.skipped_args.insert(arg_pos, slash_command_arg[1])

            print(self.skipped_args)


            while checked_args != len(arguments):
                if err_count == PROMPT["PROMPT_ERROR_COUNT"]:
                    raise CancelledPrompt("Too many failed attempts.", type="delete")

                if last and checked_args +1 == len(arguments):
                    self.skipped_args = [" ".join(self.skipped_args)]

                prompt_ = arguments[checked_args]

                skipped_arg = str(self.skipped_args[0]) if self.skipped_args else ""

                message     = None
                interaction = None
                select_values = []

                custom_id = None

                if ((prompt_.get("optional") or (slash_command and prompt_.get("slash_optional"))) and not had_args.get(checked_args)) or (prompt_.get("show_if") and last_prompt and prompt_["name"] != last_prompt["name"] and not prompt_["show_if"](resolved_args)):
                    if self.skipped_args:
                        self.skipped_args.pop(0)

                    resolved_args[prompt_["name"]] = None
                    checked_args += 1
                    last_prompt = prompt_

                    continue

                formatting = prompt_.get("formatting", True)
                prompt_text = prompt_["prompt"]

                if not skipped_arg:
                    try:
                        if formatting:
                            prompt_text = prompt_text.format(**resolved_args, prefix=self.prefix)

                        bot_prompt = await self.say(prompt_text, embed_title=prompt_.get("embed_title"), embed_color=prompt_.get("embed_color"), footer=prompt_.get("footer"), type=error and "error", embed=embed, dm=dm, components=prompt_.get("components", []))

                        task_1 = asyncio.create_task(suppress_timeout_errors(Bloxlink.wait_for("message", check=self._check_prompt(dm), timeout=PROMPT["PROMPT_TIMEOUT"])))
                        task_2 = asyncio.create_task(suppress_timeout_errors(Bloxlink.wait_for("interaction", check=self._check_interaction(), timeout=PROMPT["PROMPT_TIMEOUT"])))

                        result_set, pending = await asyncio.wait({task_1, task_2}, return_when=asyncio.FIRST_COMPLETED, timeout=PROMPT["PROMPT_TIMEOUT"])

                        if not result_set:
                            raise CancelledPrompt(f"timeout ({PROMPT['PROMPT_TIMEOUT']}s)", dm=dm)

                        result = next(iter(result_set)).result()

                        if isinstance(result, discord.Interaction):
                            interaction = result
                            message = None
                            custom_id = interaction.data["custom_id"]

                            if interaction.data["component_type"] == 3:
                                select_values = interaction.data["values"]
                        else:
                            interaction = None
                            message = result

                        if message:
                            skipped_arg = message.content

                            if prompt_.get("delete_original", True):
                                self.messages.append(message.id)
                        else:
                            skipped_arg = custom_id

                        skipped_arg_lower = skipped_arg.lower() if skipped_arg else None

                        if bot_prompt and bot_prompt.components:
                            disabled_view = discord.ui.View.from_message(bot_prompt)

                            for child in disabled_view.children:
                                if hasattr(child, "disabled"):
                                    child.disabled = True

                            try:
                                await bot_prompt.edit(view=disabled_view)
                            except discord.errors.NotFound:
                                pass

                        if custom_id == "cancel":
                            raise CancelledPrompt(type="delete")
                        elif skipped_arg_lower == "cancel":
                            raise CancelledPrompt(type="delete", dm=dm)
                        elif skipped_arg_lower == "cancel (timeout)":
                            raise CancelledPrompt(f"timeout ({PROMPT['PROMPT_TIMEOUT']}s)", dm=dm)

                    except asyncio.TimeoutError:
                        raise CancelledPrompt(f"timeout ({PROMPT['PROMPT_TIMEOUT']}s)", dm=dm)

                skipped_arg_lower = str(skipped_arg).lower()

                if skipped_arg_lower in prompt_.get("exceptions", []):
                    if self.skipped_args:
                        self.skipped_args.pop(0)
                        had_args[checked_args] = True

                    checked_args += 1
                    resolved_args[prompt_["name"]] = skipped_arg_lower

                    last_prompt = prompt_

                    continue

                resolver_types = prompt_.get("type", "string")

                if not isinstance(resolver_types, list):
                    resolver_types = [resolver_types]

                resolve_errors = []
                resolved = False
                error_message = None

                for resolver_type in resolver_types:
                    resolver = get_resolver(resolver_type)
                    resolved, error_message = await resolver(prompt_, content=skipped_arg, guild=self.guild, message=message or self.message, select_options=select_values)

                    if resolved:
                        if prompt_.get("validation"):
                            res = [await prompt_["validation"](content=skipped_arg, message=not dm and message, prompt=self.prompt, guild=self.guild)]

                            if isinstance(res[0], tuple):
                                if not res[0][0]:
                                    error_message = res[0][1]
                                    resolved = False

                            else:
                                if not res[0]:
                                    error_message = "Prompt failed validation. Please try again."
                                    resolved = False

                            if resolved:
                                resolved = res[0]
                    else:
                        error_message = f"Invalid {resolver_type} argument: `{error_message}`"

                    if error_message:
                        resolve_errors.append(error_message)
                    else:
                        break

                if resolved:
                    checked_args += 1
                    resolved_args[prompt_["name"]] = resolved
                else:
                    await self.say("\n".join(resolve_errors), type="error", embed=embed, dm=dm)

                    if self.skipped_args:
                        self.skipped_args.pop(0)
                        had_args[checked_args] = True

                    err_count += 1

                if self.skipped_args:
                    self.skipped_args.pop(0)

                last_prompt = prompt_

            return resolved_args

        finally:
            prompts.pop(self.author.id, None)


    def _check_prompt(self, dm=False):
        def wrapper(message):
            if message.author.id  == self.author.id:
                if dm:
                    return not message.guild
                else:
                    return message.channel.id == self.channel.id
            else:
                return False

        return wrapper

    def _check_interaction(self):
        def wrapper(interaction):
            if interaction.user.id == self.author.id and interaction.data.get("custom_id"):
                return True

        return wrapper
