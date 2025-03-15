from urllib import parse
import asyncio
import discord
import gspread
import aiohttp
import re
import ssl
from requests.exceptions import Timeout
from oauth2client.service_account import ServiceAccountCredentials
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound
from discord.ext import commands
from discord.utils import escape_markdown
from discord.errors import Forbidden, HTTPException



class Bridgebot(commands.Bot):
    """
    The AO2 Discord bridge bot.
    """

    def __init__(self, server, target_channel, hub_id, area_id):
        intents = discord.Intents.all()
        super().__init__(command_prefix="$", intents=intents)
        
        self.server = server
        self.pending_messages = []
        self.hub_id = hub_id
        self.area_id = area_id
        self.target_channel = target_channel

        # Google Sheets
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            "/home/ubuntu/servers/PoD/pod-bot-439920-7a593e38c2ca.json", scope
        )
        client = gspread.authorize(creds)
        self.sheet = client.open("PoD bridgebot database").sheet1

    async def init(self, token):
        """Starts the actual bot"""
        print("Trying to start the Discord Bridge bot...")
        try:
            await self.start(token)
        except Exception as e:
            print(e)

    def queue_message(self, name, message, charname, anim):
        base = None
        avatar_url = None
        anim_url = None
        embed_emotes = False
        if "base_url" in self.server.config["bridgebot"]:
            base = self.server.config["bridgebot"]["base_url"]
        if "embed_emotes" in self.server.config["bridgebot"]:
            embed_emotes = self.server.config["bridgebot"]["embed_emotes"]
        if base is not None:
            avatar_url = base + \
                parse.quote("characters/" + charname + "/char_icon.png")
            if embed_emotes:
                anim_url = base + parse.quote(
                    "characters/" + charname + "/" + anim + ".png"
                )
        self.pending_messages.append([name, message, avatar_url, anim_url])

    async def on_ready(self):
        print("Discord Bridge Successfully logged in.")
        print("Username -> " + self.user.name)
        print("ID -> " + str(self.user.id))
        self.guild = self.guilds[0]
        self.channel = discord.utils.get(
            self.guild.text_channels, name=self.target_channel
        )
        await self.wait_until_ready()

        while True:
            if len(self.pending_messages) > 0:
                await self.send_char_message(*self.pending_messages.pop())

            await asyncio.sleep(max(0.1, self.server.config["bridgebot"]["tickspeed"]))

    async def on_message(self, message):
        # Screw these loser bots
        if message.author.bot or message.webhook_id is not None:
            return

        if message.channel != self.channel:
            return

        if message.content.startswith("!clientcount"):
            number_players = int(self.server.player_count)
            await self.channel.send(f"There are {number_players}/300 clients in the AO Server!")
            return


        if message.content.startswith("!getareas") or message.content.startswith("!gas"):
            msg = ""
            number_players = int(self.server.player_count)
            msg += f"**Clients in Areas**\n"
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
                        msg += f" [LOCKED]"
                    elif area.muted:
                        msg += f" [SPECTATABLE]"
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
                msgchunks = [msg[i:i+2000] for i in range(0, len(msg), 2000)]
                for chunk in msgchunks:
                    await self.channel.send(chunk)
            else:
                await self.channel.send(msg)
            return
        
        if message.content.startswith("!g "):
            try:
                max_char = int(self.server.config["max_chars_ic"])
            except Exception:
                max_char = 256
            if len(message.clean_content) > max_char:
                await self.channel.send(
                    "Your message was too long - it was not received by the client. (The limit is 256 characters)"
                )
                return
            stripmsg = message.clean_content[3:]
            self.server.discord_global(message.author.name, stripmsg)
            await self.channel.send(f"$G[DISCORD]|{message.author.name}: {stripmsg}")
            return

        if message.content.startswith("!character-modify "):
            try:
                match = re.match(r'!character-modify "([^"]+)" (.+)', message.content)
                if match:
                    character = match.group(1)
                    emote = match.group(2)
                    discord_id = message.author.id
                    
                    
                    row = await self.find_row(discord_id)
                    if row is not None:
                        self.sheet.update_cell(row, 3, character)
                        self.sheet.update_cell(row, 4, emote)
                        await message.channel.send(f"Updated character to '{character}' and emote to '{emote}' for user {message.author.display_name}.")
                    else:
                        await message.channel.send("You don't have access to these perks.")
                else:
                    await message.channel.send("Invalid format. Use: `!character-modify \"[character]\" [emote]`.\nThe quotes are important.")

            except Exception as e:
                await message.channel.send(f"An error occurred: {e}")
            return

        
        if message.content.startswith("!showname "):
            try:
                _, showname = message.content.split(" ", 1)
                discord_id = message.author.id
                
                row = await self.find_row(discord_id)

                if row is not None:
                    self.sheet.update_cell(row, 2, showname)
                    await message.channel.send(f"Updated showname to '{showname}' for user {message.author.display_name}.")
                else:
                    await message.channel.send("You don't have access to these perks.")

            except ValueError:
                await message.channel.send("Invalid format. Use: `!showname [showname]`.")
            except Exception as e:
                await message.channel.send(f"An error occurred: {str(e)}")
            return

        if message.content.startswith("!profile"):
            discord_id = message.author.id
            row = await self.find_row(discord_id)
            if not row:
                await message.channel.send(f"No profile found for {message.author.display_name}.")
                return

            showname = self.sheet.cell(row, 2).value
            character = self.sheet.cell(row, 3).value
            emote = self.sheet.cell(row, 4).value

            base_url = "http://148.113.197.211/base/characters/"
            character_encoded = character.replace(" ", "%20")
            emote_encoded = emote.replace(" ", "%20")

            # Define base paths and extensions
            base_paths = [
                f"{base_url}{character_encoded}/{emote_encoded}",
                f"{base_url}{character_encoded}/(b)/{emote_encoded}",
                f"{base_url}{character_encoded}/(a)/{emote_encoded}"
            ]
            file_extensions = [".webp", ".apng", ".png", ".gif"]

            # Generate all possible URLs
            possible_urls = [f"{path}{ext}" for path in base_paths for ext in file_extensions]

            embed = discord.Embed(title="Profile Information", color=0x3498db)
            embed.add_field(name="Showname", value=showname, inline=True)
            embed.add_field(name="Character", value=character, inline=True)
            embed.add_field(name="Emote", value=emote, inline=True)

            image_url = None
            async with aiohttp.ClientSession() as session:
                for url in possible_urls:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            image_url = url
                            break

            if image_url:
                embed.set_image(url=image_url)
            else:
                await message.channel.send(embed=embed)
                await message.channel.send("Could not retrieve emote image.\nIf you are unsure about syntax, correct it. Otherwise refer this issue to Psyra.")
                return

            await message.channel.send(embed=embed)

        if message.content.startswith("!help"):
            embed = discord.Embed(title="Bridgebot Commands", color=0x3498db)

            commands_info = [
                ("!gas", "Get a list of all available users within the server and their location."),
                ("!g [message]", "Send a global message to PoD's AO server."),
                ("!showname [showname]", "Update your bridgebot's showname. __(<@&1296217970875437139> only)__"),
                ("!character-modify \"[character]\" [emote]", "Modify your bridgebot's character and emote. __(<@&1296217970875437139> only)__\nThis bot will only recognize characters from our [database](http://148.113.197.211/database/)."),
                ("!profile", "Get your personal bridgebot's profile information, namely showname, character, and emote. __(<@&1296217970875437139> only)__"),
                ("!clientcount", "Check the number of clients currently in the server."),
                ("!help", "Summon this list!"),
            ]

            for command, description in commands_info:
                embed.add_field(name=command, value=description, inline=False)

            embed.set_footer(text="Use the commands as specified above, don't be stinky.")

            await message.channel.send(embed=embed)


        if not message.content.startswith("!"):
            try:
                max_char = int(self.server.config["max_chars_ic"])
            except Exception:
                max_char = 256

            if len(message.clean_content) > max_char:
                await self.channel.send(
                    "Your message was too long - it was not received by the client. (The limit is 256 characters)"
                )
                return

            awesome_role_id = 1296217970875437139
            if any(role.id == awesome_role_id for role in message.author.roles):
                discord_id = message.author.id
                row = await self.find_row(discord_id)
                
                try:
                    if row:
                        dc_showname = self.sheet.cell(row, 2).value  # showname
                        dc_character = self.sheet.cell(row, 3).value # character
                        dc_emote = self.sheet.cell(row, 4).value     # emote

                        self.server.send_privileged_chat(
                            dc_showname,
                            dc_character,
                            dc_emote,
                            escape_markdown(message.clean_content),
                            self.hub_id,
                            self.area_id,
                        )
                    else:
                        self.server.send_discord_chat(
                            message.author.name,
                            escape_markdown(message.clean_content),
                            self.hub_id,
                            self.area_id,
                        )
                except Exception as e:
                    await message.channel.send(f"Your message could not be sent, an error occurred: ``{e}``")
            else:
                self.server.send_discord_chat(
                    message.author.name,
                    escape_markdown(message.clean_content),
                    self.hub_id,
                    self.area_id,
                )

    async def send_char_message(self, name, message, avatar=None, image=None):
        webhook = None
        embed = None
        try:
            webhooks = await self.channel.webhooks()
            for hook in webhooks:
                if hook.user == self.user or hook.name == "AO2_Bridgebot":
                    webhook = hook
                    break
            if webhook is None:
                webhook = await self.channel.create_webhook(name="AO2_Bridgebot")
            if image is not None:
                embed = discord.Embed()
                embed.set_image(url=image)
                print(avatar, image)
            await webhook.send(message, username=name, avatar_url=avatar, embed=embed)
            print(
                f'[DiscordBridge] Sending message from "{name}" to "{self.channel.name}"'
            )
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

    async def find_row(self, discord_id):
        try:
            cell = self.sheet.find(str(discord_id))
            return cell.row if cell else None
        except (Timeout, ssl.SSLError) as e:
            await self.channel.send(f"Network error while accessing Google Sheets: {e}")
            return None
        except Exception as e:
            await self.channel.send(f"An unexpected error occurred: {e}")
            return None