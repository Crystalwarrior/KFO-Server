import asyncio
from urllib import parse

import discord
from discord.errors import Forbidden, HTTPException
from discord.ext import commands
from discord.utils import escape_markdown
from typing import TYPE_CHECKING, Any, List, Optional, Tuple

if TYPE_CHECKING:  # Avoid circular imports at runtime
    from server.tsuserver import TsuServer


class Bridgebot(commands.Bot):
    """
    The AO2 Discord bridge self.
    """

    def __init__(self, server: "TsuServer", target_chanel: str, hub_id: int, area_id: int) -> None:
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)
        self.server: TsuServer = server  # type: ignore[name-defined]
        self.pending_messages: List[Tuple[str, str, Optional[str], Optional[str]]] = []
        self.hub_id: int = hub_id
        self.area_id: int = area_id
        self.target_channel: str = target_chanel
        # Will be set in on_ready
        self.guild: Optional[discord.Guild] = None
        self.channel: Optional[discord.TextChannel] = None
        # Announcement configuration (types depend on config; keep broad where uncertain)
        self.announce_channel: str = server.config["bridgebot"]["announce_channel"]
        self.announce_title: str = server.config["bridgebot"]["announce_title"]
        self.announce_image: str = server.config["bridgebot"]["announce_image"]
        self.announce_color: Any = server.config["bridgebot"]["announce_color"]
        self.announce_description: str = server.config["bridgebot"]["announce_description"]
        self.announce_ping: bool = server.config["bridgebot"]["announce_ping"]
        self.announce_role: Any = server.config["bridgebot"]["announce_role"]

    async def init(self, token: str) -> None:
        """Starts the actual bot"""
        print("Trying to start the Discord Bridge bot...")
        try:
            await self.start(token)
        except Exception as e:
            print(e)

    def add_commands(self) -> None:
        @self.command()
        async def announcing(
            ctx: commands.Context,
            name: Optional[str] = None,
            description: Optional[str] = None,
            url: Optional[str] = None,
            additional: Optional[str] = None,
            when: Optional[str] = None,
            where: Optional[str] = None,
        ) -> None:
            desc = f"{ctx.author}" + " " + self.announce_description
            embed = discord.Embed(title=self.announce_title, description=desc, color=self.announce_color)
            if name is not None:
                embed.add_field(name="Announce Name:", value=name, inline=False)
            else:
                self.channel.send("Arguments error!\n!announcing name description url additional when where")
                return
            if description is not None:
                embed.add_field(name="Description:", value=description, inline=False)
            else:
                self.channel.send("Arguments error!\n!announcing name description url additional when where")
                return
            embed.set_thumbnail(url=self.announce_image)
            if url is not None:
                embed.add_field(name="Document Link:", value=url, inline=False)
            if additional is not None:
                embed.add_field(name="Additional Note:", value=additional, inline=False)
            if when is not None:
                embed.add_field(name="When:", value=when, inline=True)
            if where is not None:
                embed.add_field(name="Where:", value=where, inline=True)
            channel = discord.utils.get(self.guild.text_channels, name=self.announce_channel)  # type: ignore[union-attr]
            if self.announce_ping:
                await channel.send(f"<@&{self.announce_role}>", embed=embed)
            else:
                await channel.send(embed=embed)

        @self.tree.command()
        async def gethubs(interaction: discord.Interaction) -> None:
            msg = ""
            number_players = int(self.server.player_count)
            msg += "**Clients in Areas**\n"
            for hub in self.server.hub_manager.hubs:
                if len(hub.clients) == 0:
                    continue
                if not hub.can_getareas or hub.hide_clients:
                    continue
                msg += f"**[={hub.name}=]**\n"
                for area in hub.areas:
                    if area.hidden:
                        continue
                    if len(area.clients) == 0:
                        continue
                    msg += f"\t**[{area.id}] {area.name} (users: {len(area.clients)}) [{area.status}]"
                    if area.locked:
                        msg += " [LOCKED]"
                    elif area.muted:
                        msg += " [SPECTATABLE]"
                    if area.get_owners() != "":
                        msg += f" [CM(s): {area.get_owners()}]"
                    msg += "**\n"
                    for client in area.clients:
                        if client.hidden:
                            continue
                        msg += "\t  ◾ "
                        if client in area.afkers:
                            msg += "[AFK] "
                        if client.is_mod:
                            msg += "[M] "
                        elif client in area.area_manager.owners:
                            msg += "[GM] "
                        elif client in area._owners:
                            msg += "[CM] "
                        if client.showname != client.char_name:
                            msg += f'[{client.id}] "{client.showname}" ({client.char_name})'
                        else:
                            msg += f"[{client.id}] {client.showname}"
                        if client.pos != "":
                            msg += f" <{client.pos}>"
                        msg += "\n"
                msg += "\n"
            msg += f"Current online: {number_players} clients\n"
            if len(msg) > 2000:
                msgchunks = [msg[i : i + 2000] for i in range(0, len(msg), 2000)]
                for chunk in msgchunks:
                    await interaction.response.send_message(chunk)
            else:
                await interaction.response.send_message(msg)

        @self.event
        async def on_message(message: discord.Message) -> None:
            # Screw these loser bots
            if message.author.bot or message.webhook_id is not None:
                return

            if message.channel != self.channel:
                if message.content.startswith("!"):
                    await self.process_commands(message)
                    await message.delete()
                return

            if not message.content.startswith("!"):
                try:
                    max_char = int(self.server.config["max_chars_ic"])
                except Exception:
                    max_char = 256
                if len(message.clean_content) > max_char:
                    await self.channel.send("Your message was too long - it was not received by the client. (The limit is 256 characters)")
                    return
                self.server.send_discord_chat(
                    message.author.name,
                    escape_markdown(message.clean_content),
                    self.hub_id,
                    self.area_id,
                )

    def queue_message(self, name: str, message: str, charname: str, anim: str) -> None:
        base = None
        avatar_url = None
        anim_url = None
        embed_emotes = False
        if "base_url" in self.server.config["bridgebot"]:
            base = self.server.config["bridgebot"]["base_url"]
        if "embed_emotes" in self.server.config["bridgebot"]:
            embed_emotes = self.server.config["bridgebot"]["embed_emotes"]
        if base is not None:
            avatar_url = base + parse.quote("characters/" + charname + "/char_icon.png")
            if embed_emotes:
                anim_url = base + parse.quote("characters/" + charname + "/" + anim + ".png")
        self.pending_messages.append([name, message, avatar_url, anim_url])

    async def on_ready(self) -> None:
        print("Discord Bridge Successfully logged in.")
        print("Username -> " + self.user.name)
        print("ID -> " + str(self.user.id))
        try:
            await self.tree.sync()
            print("Synced commands!")
        except Exception as e:
            print(e)
        self.guild = self.guilds[0]
        self.channel = discord.utils.get(self.guild.text_channels, name=self.target_channel)  # type: ignore[assignment]
        await self.wait_until_ready()

        while True:
            if len(self.pending_messages) > 0:
                await self.send_char_message(*self.pending_messages.pop())

            await asyncio.sleep(max(0.1, self.server.config["bridgebot"]["tickspeed"]))

    async def send_char_message(
        self,
        name: str,
        message: str,
        avatar: Optional[str] = None,
        image: Optional[str] = None,
    ) -> None:
        webhook: Optional[discord.Webhook] = None
        embed: Optional[discord.Embed] = None
        try:
            webhooks = await self.channel.webhooks()  # type: ignore[union-attr]
            for hook in webhooks:
                if hook.user == self.user or hook.name == "AO2_Bridgebot":
                    webhook = hook
                    break
            if webhook is None:
                webhook = await self.channel.create_webhook(name="AO2_Bridgebot")  # type: ignore[union-attr]
            if image is not None:
                embed = discord.Embed()
                embed.set_image(url=image)
                print(avatar, image)
            await webhook.send(message, username=name, avatar_url=avatar, embed=embed)
            print(f'[DiscordBridge] Sending message from "{name}" to "{self.channel.name}"')
        except Forbidden:
            print(
                f'[DiscordBridge] Insufficient permissions - couldnt send char message "{name}: {message}" with avatar "{avatar}" to "{self.channel.name}"'
            )
        except HTTPException:
            print(
                f'[DiscordBridge] HTTP Failure - couldnt send char message "{name}: {message}" with avatar "{avatar}" to "{self.channel.name}"'
            )
        except Exception as ex:
            # This is a workaround to a problem - [Errno 104] Connection reset by peer occurs due to too many calls for this func.
            # Simple solution is to increase the tickspeed config so it waits longer between messages sent.
            print(f"[DiscordBridge] Exception - {ex}")
