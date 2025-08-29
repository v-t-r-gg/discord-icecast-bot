import discord
from discord.ext import commands
import aiohttp
import asyncio
import time
from discord import Activity, ActivityType, Embed
from aiohttp import ClientTimeout, ClientPayloadError
from discord.ui import View, Button
import urllib.parse
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)
class StreamCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.metadata_task = None
        self.timeout_task = None
        self.current_title = ""
        self.song_history = []
        self.N = 50
        self.session = aiohttp.ClientSession(timeout=ClientTimeout(connect=10, sock_read=20))
    async def cog_unload(self):
        await self.session.close()
        if self.metadata_task:
            self.metadata_task.cancel()
        if self.timeout_task:
            self.timeout_task.cancel()
    async def update_metadata(self):
        url = 'YOUR_STREAM_URL_HERE'
        headers = {'Icy-MetaData': '1'}
        try:
            while True:
                try:
                    async with self.session.get(url, headers=headers) as response:
                        if 'icy-metaint' in response.headers:
                            metaint = int(response.headers['icy-metaint'])
                            while True:
                                try:
                                    audio_data = await response.content.readexactly(metaint)
                                    length_byte = await response.content.readexactly(1)
                                    length = length_byte[0] * 16
                                    if length > 0:
                                        metadata_bytes = await response.content.readexactly(length)
                                        metadata = metadata_bytes.decode('utf-8', errors='ignore').rstrip('\x00')
                                        if 'StreamTitle' in metadata:
                                            try:
                                                title = metadata.split("StreamTitle='")[1].split("';")[0].strip()
                                                if len(title) < 3 or title.isspace() or title.lower() in ['airtime', '']:
                                                    continue
                                                if title != self.current_title:
                                                    self.current_title = title
                                                    self.song_history.append(title)
                                                    if len(self.song_history) > self.N:
                                                        self.song_history.pop(0)
                                                    display = title
                                                    if ' - ' in title:
                                                        artist, track = title.split(' - ', 1)
                                                        display = f"{artist} – {track}"
                                                    await self.bot.change_presence(
                                                        activity=Activity(type=ActivityType.listening, name=display)
                                                    )
                                            except IndexError:
                                                pass
                                except (asyncio.IncompleteReadError, ClientPayloadError):
                                    break
                except Exception as e:
                    print(f"metadata error: {e}")
                    await asyncio.sleep(10)
        except asyncio.CancelledError:
            pass
    async def timeout_disconnect(self, vc):
        await asyncio.sleep(300)
        if vc.is_connected():
            non_bots = [m for m in vc.channel.members if not m.bot]
            if len(non_bots) == 0:
                await vc.disconnect()
                if self.metadata_task:
                    self.metadata_task.cancel()
                await self.bot.change_presence(activity=None)
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not self.bot.voice_clients:
            return
        vc = self.bot.voice_clients[0]
        if vc.channel != before.channel and vc.channel != after.channel:
            return
        non_bots = [m for m in vc.channel.members if not m.bot]
        if len(non_bots) == 0:
            if self.timeout_task is None or self.timeout_task.done():
                self.timeout_task = asyncio.create_task(self.timeout_disconnect(vc))
        else:
            if self.timeout_task and not self.timeout_task.done():
                self.timeout_task.cancel()
                self.timeout_task = None
    @commands.Cog.listener()
    async def on_disconnect(self):
        print("bot dc, reconnecting")
    @commands.command()
    async def play(self, ctx):
        if self.metadata_task:
            self.metadata_task.cancel()
        self.metadata_task = asyncio.create_task(self.update_metadata())
        if not ctx.author.voice:
            await ctx.send("join voice silly billy")
            return
        channel = ctx.author.voice.channel
        try:
            if ctx.voice_client is None:
                vc = await channel.connect()
            else:
                vc = ctx.voice_client
            non_bots = [m for m in vc.channel.members if not m.bot]
            if len(non_bots) == 0:
                if self.timeout_task is None or self.timeout_task.done():
                    self.timeout_task = asyncio.create_task(self.timeout_disconnect(vc))
            vc.play(discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(
                'YOUR_STREAM_URL_HERE',
                before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin',
                options='-vn'
            ), volume=0.5))
        except Exception as e:
            await ctx.send(f"Voice error: {e}")
    @commands.command()
    async def stop(self, ctx):
        if self.metadata_task:
            self.metadata_task.cancel()
        if self.timeout_task:
            self.timeout_task.cancel()
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
        await self.bot.change_presence(activity=None)
    @commands.command()
    async def history(self, ctx):
        if not self.song_history:
            await ctx.send("no songs yet.")
            return
        pages = []
        page_size = 10
        history_rev = list(reversed(self.song_history))
        for i in range(0, len(history_rev), page_size):
            embed = Embed(title="Song History")
            for j, song in enumerate(history_rev[i:i+page_size], i+1):
                embed.add_field(name=f"{j}.", value=song, inline=False)
            pages.append(embed)
        if len(pages) == 1:
            await ctx.send(embed=pages[0])
            return
        view = PaginatorView(pages)
        await view.send(ctx)
    @commands.command()
    async def song(self, ctx):
        if not self.current_title:
            await ctx.send("no current song.")
            return
        embed = Embed(title="Current Song", description=self.current_title)
        artist = track = None
        if ' - ' in self.current_title:
            artist, track = self.current_title.split(' - ', 1)
            embed.add_field(name="Artist", value=artist, inline=True)
            embed.add_field(name="Track", value=track, inline=True)
            search_query = urllib.parse.quote(f"{artist} {track}")
            genius_url = f"https://genius.com/search?q={search_query}"
            embed.add_field(name="Lyrics", value=f"[Search Genius]({genius_url})", inline=False)
        try:
            if artist and track:
                headers = {'User-Agent': 'YourBotName/1.0 (your.email@example.com)'}
                mb_url = f"https://musicbrainz.org/ws/2/recording/?query=artist:\"{artist}\"%5E2 AND recording:\"{track}\"&limit=5&fmt=json"
                async with self.session.get(mb_url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data['count'] > 0:
                            recording = None
                            for rec in data['recordings']:
                                if rec['title'].lower() == track.lower() and any(ac['artist']['name'].lower() == artist.lower() for ac in rec['artist-credit']):
                                    recording = rec
                                    break
                            if not recording and data['recordings']:
                                recording = data['recordings'][0]
                            recording_mbid = recording['id']
                            rec_url = f"https://musicbrainz.org/ws/2/recording/{recording_mbid}?inc=url-rels+releases+release-groups&fmt=json"
                            async with self.session.get(rec_url, headers=headers) as rec_resp:
                                if rec_resp.status == 200:
                                    rec_data = await rec_resp.json()
                                    if 'releases' in rec_data and rec_data['releases']:
                                        filtered_releases = [r for r in rec_data['releases'] if r.get('status') == 'Official' and r['release-group'].get('primary-type') not in ['Compilation', 'Live']]
                                        if filtered_releases:
                                            sorted_releases = sorted(filtered_releases, key=lambda r: r.get('date', '9999'))
                                            release = sorted_releases[0]
                                        else:
                                            release = rec_data['releases'][0]
                                        release_mbid = release['id']
                                        embed.url = f"https://musicbrainz.org/release/{release_mbid}"
                                        embed.add_field(name="Album", value=release.get('title', 'Unknown'), inline=True)
                                        caa_url = f"https://coverartarchive.org/release/{release_mbid}/front-500"
                                        embed.set_thumbnail(url=caa_url)
        except Exception as e:
            print(f"Song API error: {e}")
        await ctx.send(embed=embed)
    @commands.command()
    async def help(self, ctx):
        embed = Embed(title="Bot Commands")
        embed.add_field(name="!play", value="start stream", inline=False)
        embed.add_field(name="!stop", value="stop & dc", inline=False)
        embed.add_field(name="!history", value="last 10 tunes", inline=False)
        embed.add_field(name="!song", value="show album info", inline=False)
        embed.add_field(name="!help", value="this menu lol", inline=False)
        await ctx.send(embed=embed)
class PaginatorView(View):
    def __init__(self, embeds):
        super().__init__(timeout=300)
        self.embeds = embeds
        self.current_page = 0
        self.add_item(Button(label="<<", style=discord.ButtonStyle.primary, custom_id="first"))
        self.add_item(Button(label="<", style=discord.ButtonStyle.primary, custom_id="prev"))
        self.add_item(Button(label=">", style=discord.ButtonStyle.primary, custom_id="next"))
        self.add_item(Button(label=">>", style=discord.ButtonStyle.primary, custom_id="last"))
    async def send(self, ctx):
        await self.update_message()
        self.message = await ctx.send(embed=self.embeds[0], view=self)
    async def update_message(self):
        self.children[0].disabled = self.current_page == 0
        self.children[1].disabled = self.current_page == 0
        self.children[2].disabled = self.current_page == len(self.embeds) - 1
        self.children[3].disabled = self.current_page == len(self.embeds) - 1
        self.embeds[self.current_page].set_footer(text=f"Page {self.current_page + 1}/{len(self.embeds)}")
    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        await self.message.edit(view=self)
    async def interaction_check(self, interaction):
        if interaction.data['custom_id'] == 'first':
            self.current_page = 0
        elif interaction.data['custom_id'] == 'prev':
            self.current_page = max(0, self.current_page - 1)
        elif interaction.data['custom_id'] == 'next':
            self.current_page = min(len(self.embeds) - 1, self.current_page + 1)
        elif interaction.data['custom_id'] == 'last':
            self.current_page = len(self.embeds) - 1
        await self.update_message()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
        return True
async def main():
    bot.remove_command("help")
    await bot.add_cog(StreamCog(bot))
    await bot.start('YOUR_BOT_TOKEN_HERE')
asyncio.run(main())
