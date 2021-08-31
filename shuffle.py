#!/usr/bin/python3

import datetime
import discord
import discord.ext.commands
import glob
import json
import os
import random

CONFIG_FILE = 'shuffle.json'
READ_AUDIO_CHUNK_MS = 20

def file_stem(path):
    basename = os.path.basename(path)
    return basename.split('.')[0]

# Wrapper around FFmpegOpusAudio that counts the number of milliseconds
# streamed so far.
class ElapsedAudio(discord.FFmpegOpusAudio):
    def __init__(self, filename, elapsed_ms=0):
        # TODO: foward args if more sophisticated construction is needed.
        ss = datetime.timedelta(milliseconds=elapsed_ms)
        super().__init__(filename, options=f'-ss {str(ss)}')

        self._elapsed_ms = elapsed_ms

    def read(self):
        self._elapsed_ms += READ_AUDIO_CHUNK_MS
        return super().read()

    @property
    def elapsed_ms(self):
        return self._elapsed_ms

# Maintains a cursor in a list of music files and exposes an audio stream for
# the current file.
class Playlist:
    def __init__(self, name, fs):
        # Make copy.
        self._name = name
        self._fs = list(fs)

        # Populated in Restart.
        self._index = None
        self._cur_src = None

        # Start shuffled.
        self.Restart()

    # Clear current song and reshuffle playlist.
    def Restart(self):
        print(f'[INFO] Restarting playlist "{self._name}".')

        if self._cur_src:
            self._cur_src.cleanup()
        self._cur_src = None

        random.shuffle(self._fs)
        self._index = 0

    # Return the current audio source, or load it if it isn't initialised.
    async def CurrentStream(self):
        if self._index >= len(self._fs):
            return None

        if self._cur_src:
            print(f'[INFO] Resuming "{file_stem(self._fs[self._index])}".')
            self._cur_src.cleanup()
            self._cur_src = ElapsedAudio(self._fs[self._index], self._cur_src.elapsed_ms)
        else:
            print(f'[INFO] Starting "{file_stem(self._fs[self._index])}".')
            self._cur_src = ElapsedAudio(self._fs[self._index])

        return self._cur_src

    # Move to the next song, reshuffling and starting again if there isn't one.
    def Next():
        self._index += 1

        if self._index >= len(self._fs):
            self.Restart()
            return

        if self._cur_src:
            self._cur_src.clean_up()
        self._cur_src = None

    def CurrentIndex(self):
        print(self._fs[self._index])
        return self._index

# Read config.

config = json.loads(open(CONFIG_FILE, 'r').read())

playlists = {}
for name, globs in config['playlists'].items():
    playlists[name] = Playlist(name, sum([glob.glob(p) for p in globs], []))

# Define bot.

bot = discord.ext.commands.Bot(command_prefix='!')

# Returns true if the author can command the bot. That is, if the bot is in the
# same channel as the author.
def can_command(ctx):
    return ctx.author.voice and (not ctx.voice_client or
           ctx.author.voice.channel == ctx.voice_client.channel)

@bot.event
async def on_ready():
    print(f'[INFO] {bot.user.name} connected.')

@bot.command(name='start')
async def start(ctx):
    print(f'[INFO] Joining voice channel.')

    if not can_command(ctx):
        await ctx.send(f'You must connect yourself to the same channel as {bot.user.name}!')
        return

    dest = ctx.author.voice

    if not dest:
        await ctx.send('User not in voice channel!')
        return

    await dest.channel.connect()
    await ctx.send(f'Joined the voice channel {dest.channel.name}.')

@bot.command(name='play')
async def play(ctx, playlist):
    print(f'[INFO] Playback started.')

    if not can_command(ctx):
        await ctx.send(f'You must connect yourself to the same channel as {bot.user.name}!')
        return

    ctx.voice_client.stop()
    ctx.voice_client.play(await playlists[playlist].CurrentStream())

# Run bot.

bot.run(config['token'])
