# discord-icecast-bot

A Discord bot that streams audio from an Icecast server, joins voice channels, and provides song info using MusicBrainz and Genius.

## Features
- Plays stream in voice channel with `!play`.
- Stops and disconnects with `!stop`.
- Shows current song info, album, lyrics search with `!song`.
- Displays song history with pagination via `!history`.
- Help menu with `!help`.

## Setup
1. Install dependencies: `pip install discord.py aiohttp`.
2. Replace `YOUR_STREAM_URL_HERE` with your Icecast stream URL.
3. Replace `YOUR_BOT_TOKEN_HERE` with your Discord bot token.
4. Run the script.

## Commands
- `!play`: Join voice and start streaming.
- `!stop`: Stop and disconnect.
- `!song`: Show current song details.
- `!history`: View recent songs.
- `!help`: List commands.

Update User-Agent in code with your info for MusicBrainz API compliance.
