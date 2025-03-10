"""
MIT License

Copyright (c) 2020-2021 phenom4n4n

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import logging

import akinator
import discord
from akinator.async_aki import Akinator
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config
from redbot.vendored.discord.ext import menus

log = logging.getLogger("red.phenom4n4n.aki")

NSFW_WORDS = ["porn", "sex"]


def channel_is_nsfw(channel) -> bool:
    return getattr(channel, "nsfw", False)


class AkiMenu(menus.Menu):
    def __init__(self, game: Akinator, color: discord.Color):
        self.aki = game
        self.color = color
        self.num = 1
        self.message = None
        super().__init__(timeout=60, delete_message_after=False, clear_reactions_after=True)

    async def send_initial_message(self, ctx: commands.Context, channel: discord.TextChannel):
        return await channel.send(embed=self.current_question_embed())

    @menus.button("✅")
    async def yes(self, payload: discord.RawReactionActionEvent):
        self.num += 1
        await self.answer("yes")
        await self.send_current_question()

    @menus.button("❎")
    async def no(self, payload: discord.RawReactionActionEvent):
        self.num += 1
        await self.answer("no")
        await self.send_current_question()

    @menus.button("❔")
    async def idk(self, payload: discord.RawReactionActionEvent):
        self.num += 1
        await self.answer("idk")
        await self.send_current_question()

    @menus.button("📉")
    async def probably(self, payload: discord.RawReactionActionEvent):
        self.num += 1
        await self.answer("probably")
        await self.send_current_question()

    @menus.button("📈")
    async def probably_not(self, payload: discord.RawReactionActionEvent):
        self.num += 1
        await self.answer("probably not")
        await self.send_current_question()

    @menus.button("🔙")
    async def back(self, payload: discord.RawReactionActionEvent):
        try:
            await self.aki.back()
        except akinator.CantGoBackAnyFurther:
            await self.ctx.send(
                "You can't go back on the first question, try a different option instead.",
                delete_after=10,
            )
        else:
            self.num -= 1
            await self.send_current_question()

    @menus.button("🏆")
    async def react_win(self, payload: discord.RawReactionActionEvent):
        await self.win()

    @menus.button("🗑️")
    async def end(self, payload: discord.RawReactionActionEvent):
        await self.cancel()

    def current_question_embed(self):
        e = discord.Embed(
            color=self.color,
            title=f"Question #{self.num}",
            description=self.aki.question,
        )
        if self.aki.progression > 0:
            e.set_footer(text=f"{round(self.aki.progression, 2)}% guessed")
        return e

    def get_winner_embed(self, winner: dict) -> discord.Embed:
        win_embed = discord.Embed(
            color=self.color,
            title=f"I'm {round(float(winner['proba']) * 100)}% sure it's {winner['name']}!",
            description=winner["description"],
        )
        win_embed.set_image(url=winner["absolute_picture_path"])
        return win_embed

    def get_nsfw_embed(self):
        embed = discord.Embed(
            color=self.color,
            title="I guessed it, but this result is inappropriate.",
            description="Try again in a NSFW channel.",
        )
        return embed

    def text_is_nsfw(self, text: str) -> bool:
        text = text.lower()
        for word in NSFW_WORDS:
            if word in text:
                return True
        return False

    async def win(self):
        winner = await self.aki.win()
        description = winner["description"]
        if not channel_is_nsfw(self.message.channel) and self.text_is_nsfw(description):
            embed = self.get_nsfw_embed()
        else:
            embed = self.get_winner_embed(winner)
        await self.edit_or_send(embed=embed)
        self.stop()
        # TODO allow for continuation of game

    async def send_current_question(self):
        if self.aki.progression < 80:
            try:
                await self.message.edit(embed=self.current_question_embed())
            except discord.HTTPException:
                await self.cancel()
        else:
            await self.win()

    async def finalize(self, timed_out: bool):
        if timed_out:
            await self.edit_or_send(content="Akinator game timed out.", embed=None)

    async def cancel(self, message: str = "Akinator game cancelled."):
        await self.edit_or_send(content=message, embed=None)
        self.stop()

    async def edit_or_send(self, **kwargs):
        try:
            await self.message.edit(**kwargs)
        except discord.NotFound:
            await self.ctx.send(**kwargs)
        except discord.Forbidden:
            pass

    async def answer(self, message: str):
        try:
            await self.aki.answer(message)
        except akinator.AkiNoQuestions:
            await self.win()
        except akinator.AkiTimedOut:
            await self.cancel("The connection to the Akinator servers was lost.")
        except Exception as error:
            log.exception(
                f"Encountered an exception while answering with {message} during Akinator session",
                exc_info=True,
            )
            await self.edit_or_send(content=f"Akinator game errored out:\n`{error}`", embed=None)
            self.stop()


class Aki(commands.Cog):
    """
    Play Akinator in Discord!
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=8237578807127857,
            force_registration=True,
        )

    __version__ = "1.0.2"

    def format_help_for_context(self, ctx):
        pre_processed = super().format_help_for_context(ctx)
        n = "\n" if "\n\n" not in pre_processed else ""
        return f"{pre_processed}{n}\nCog Version: {self.__version__}"

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        return

    @commands.max_concurrency(1, commands.BucketType.channel)
    @commands.bot_has_permissions(embed_links=True, add_reactions=True)
    @commands.command(aliases=["akinator"])
    async def aki(self, ctx: commands.Context, *, language: str.lower = "en"):
        """
        Start a game of Akinator!

        Controls:
        > ✅ : yes
        > ❎ : no
        > ❔ : i don't know
        > 📉 : probably
        > 📈 : probably not
        > 🔙 : back
        > 🏆 : win
        > 🗑️ : cancel
        """
        await ctx.trigger_typing()
        aki = Akinator()
        child_mode = not channel_is_nsfw(ctx.channel)
        try:
            await aki.start_game(language=language.replace(" ", "_"), child_mode=child_mode)
        except akinator.InvalidLanguageError:
            await ctx.send(
                "Invalid language. Refer here to view valid languages.\n<https://github.com/NinjaSnail1080/akinator.py#functions>"
            )
        except Exception:
            await ctx.send("I encountered an error while connecting to the Akinator servers.")
        else:
            aki_color = discord.Color(0xE8BC90)
            menu = AkiMenu(aki, aki_color)
            await menu.start(ctx)
