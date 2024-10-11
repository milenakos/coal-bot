import asyncio
import os
import random
import time
from typing import Optional

import discord
from discord.ext import commands

from database import Channel, Profile, db

if os.name != "nt":
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


class CleanupClient(commands.AutoShardedBot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def close(self):
        for i in coal_msg.values():
            if i:
                await finish_mining(i.channel.id)

        await super().close()


intents = discord.Intents.default()
bot = CleanupClient(command_prefix="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    intents=intents,
                    member_cache_flags=discord.MemberCacheFlags.none(),
                    help_command=None,
                    chunk_guilds_at_startup=False)

counter = {}
contributors = {}
coal_msg = {}
start = {}
last_update_time = {}


async def spawn_coal(channel):
    global counter, contributors, coal_msg, start, last_update_time
    if coal_msg.get(channel.id, None):
        return
    ch = Channel.get(channel.id)
    ch.yet_to_spawn = 0
    ch.save()
    start[channel.id] = time.time()
    counter[channel.id] = random.randint(250, 750)
    contributors[channel.id] = {}
    last_update_time[channel.id] = time.time()
    coal_msg[channel.id] = await channel.send(f"<@&1294332417301286912> <:coal:1294300130014527498> A wild coal has appeared! Spam :pick: reaction to mine it! ({counter[channel.id]})")
    await coal_msg[channel.id].add_reaction("⛏")


async def finish_mining(channel_id):
    global coal_msg
    coal_save = coal_msg[channel_id]
    if not isinstance(coal_save, discord.Message):
        return
    coal_msg[channel_id] = None

    to_save = []

    for user_id, amount in contributors[channel_id].items():
        user, _ = Profile.get_or_create(guild_id=coal_save.guild.id, user_id=user_id)
        user.contributions += 1
        user.clicks += amount
        user.tokens += amount
        to_save.append(user)

    with db.atomic():
        Profile.bulk_update(to_save, fields=[Profile.contributions, Profile.clicks, Profile.tokens], batch_size=50)

    contributors_list = "\n".join([f"<@{k}> - {v}" for k, v in sorted(contributors[channel_id].items(), key=lambda item: item[1], reverse=True)])
    await coal_save.edit(content=f":pick: Coal mined successfully! It took {round(time.time() - start[channel_id])} seconds! These people helped:\n{contributors_list}")
    return coal_save.channel


async def mine(payload):
    global counter, contributors, coal_msg, start, last_update_time
    counter[payload.channel_id] -= 1
    contributors[payload.channel_id][payload.user_id] = contributors[payload.channel_id].get(payload.user_id, 0) + 1
    if counter[payload.channel_id] <= 0:
        channel = await finish_mining(payload.channel_id)
        ch = Channel.get(channel.id)
        decided_time = random.randint(ch.spawn_times_min, ch.spawn_times_max)
        ch.yet_to_spawn = int(time.time()) + decided_time
        ch.save()
        await asyncio.sleep(decided_time)
        await spawn_coal(channel)
        return
    if last_update_time.get(payload.channel_id, 0) + 5 > time.time():
        return

    last_update_time[payload.channel_id] = time.time()
    await coal_msg[payload.channel_id].edit(content=f"<:coal:1294300130014527498> A wild coal has appeared! Spam :pick: reaction to mine it! ({counter[payload.channel_id]})")


@bot.tree.command(description="(ADMIN) Setup a mine channel")
@discord.app_commands.default_permissions(manage_guild=True)
async def setup(message):
    if Channel.get_or_none(channel_id=message.channel.id):
        await message.response.send_message("bruh you already setup a mine here are you dumb")
        return

    Channel.create(channel_id=message.channel.id)
    await message.response.send_message(f"ok, now i will also send coals in <#{message.channel.id}>")
    await spawn_coal(message.channel)


@bot.tree.command(description="(ADMIN) Forcespawn a coal")
@discord.app_commands.default_permissions(manage_guild=True)
async def forcespawn(message):
    if coal_msg.get(message.channel.id, None):
        await message.response.send_message("bruh you already setup a coal here are you dumb")
        return

    await message.response.send_message("ok, spawned.")
    await spawn_coal(message.channel)


@bot.tree.command(description="View a profile!")
async def profile(message, user: Optional[discord.User]):
    if not user:
        user = message.user

    profile, _ = Profile.get_or_create(guild_id=message.guild.id, user_id=user.id)
    embed = discord.Embed(
        title=f"{user}'s Profile",
        description=f"Total clicks:{profile.clicks}\nTotal contributions:{profile.contributions}"
    ).add_field(
        name="Tokens",
        value=profile.tokens
    ).add_field(
        name="Pickaxe",
        value=profile.pickaxe
    )

    await message.response.send_message(embed=embed)


async def wait_and_spawn(channel):
    time_left = channel.yet_to_spawn - time.time()
    if time_left > 0:
        await asyncio.sleep(time_left)
    await spawn_coal(bot.get_channel(channel.channel_id))


@bot.event
async def on_ready():
    print("online")
    await bot.tree.sync()
    for channel in Channel.select():
        bot.loop.create_task(wait_and_spawn(channel))


@bot.event
async def on_raw_reaction_remove(payload):
    if coal_msg.get(payload.channel_id, False) and payload.message_id == coal_msg[payload.channel_id].id and str(payload.emoji) == "⛏" and payload.user_id != bot.user.id:
        await mine(payload)


@bot.event
async def on_raw_reaction_add(payload):
    if coal_msg.get(payload.channel_id, False) and payload.message_id == coal_msg[payload.channel_id].id and payload.user_id != bot.user.id:
        if str(payload.emoji) == "⛏":
            await mine(payload)
        else:
            channel = bot.get_channel(payload.channel_id)
            if not isinstance(channel, discord.TextChannel):
                return
            message = await channel.fetch_message(payload.message_id)

            await message.clear_reaction(payload.emoji)


db.connect()
if not db.get_tables():
    db.create_tables([Profile, Channel])

try:
    bot.run(os.environ["COAL_TOKEN"])
finally:
    db.close()
