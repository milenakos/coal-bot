import asyncio
import os
import random
import time
from typing import Optional, Literal

import discord
import peewee
from discord import ButtonStyle
from discord.ext import commands
from discord.ui import Button, View

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
counter_spawn = {}
contributors = {}
coal_msg = {}
start = {}
last_update_time = {}


async def spawn_coal(channel):
    global counter, counter_spawn, contributors, coal_msg, start, last_update_time
    if coal_msg.get(channel.id, None):
        return
    ch = Channel.get(channel.id)
    ch.yet_to_spawn = 0
    ch.save()
    start[channel.id] = time.time()
    counter_spawn[channel.id] = random.randint(250, 750)
    counter[channel.id] = counter_spawn[channel.id]
    contributors[channel.id] = {}
    last_update_time[channel.id] = time.time()
    coal_msg[channel.id] = await channel.send(f"<@&1294332417301286912> <:coal:1294300130014527498> A wild coal has appeared! Spam :pick: reaction to mine it! ({counter[channel.id]})")
    await coal_msg[channel.id].add_reaction("⛏")


async def finish_mining(channel_id):
    global coal_msg, counter_spawn
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
    await coal_save.edit(content=f":pick: Coal mined successfully! It took {counter_spawn[channel.id]} pickaxe hits in {round(time.time() - start[channel_id])} seconds! These people helped:\n{contributors_list}")
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
        title=f"{profile.tokens} tokens",
        description=f"**Pickaxe**: {profile.pickaxe}\n\nTotal clicks: {profile.clicks}\nTotal contributions: {profile.contributions}",
        color=0x4C88BB
    ).set_author(
        name=str(user),
        icon_url=user.avatar.url
    )

    await message.response.send_message(embed=embed)


@bot.tree.command(description="View the leaderboards")
@discord.app_commands.rename(leaderboard_type="type")
@discord.app_commands.describe(leaderboard_type="The leaderboard type to view!")
async def leaderboards(message: discord.Interaction, leaderboard_type: Optional[Literal["Tokens"]]):
    if not leaderboard_type:
        leaderboard_type = "Tokens"

    # this fat function handles a single page
    async def lb_handler(interaction, type, do_edit=None):
        nonlocal message
        if do_edit is None:
            do_edit = True
        await interaction.response.defer()

        messager = None
        interactor = None
        string = ""
        if type == "Tokens":
            unit = "tokens"
            # run the query
            result = (Profile
                .select(Profile.user_id, Profile.tokens.alias("final_value"))
                .where(Profile.guild_id == message.guild.id)
                .group_by(Profile.user_id, Profile.tokens)
                .order_by(Profile.tokens.desc())
            ).execute()
        else:
            # qhar
            return

        # find the placement of the person who ran the command and optionally the person who pressed the button
        interactor_placement = 0
        messager_placement = 0
        for index, position in enumerate(result):
            if position.user_id == interaction.user.id:
                interactor_placement = index
                interactor = position.final_value
            if interaction.user != message.user and position.user_id == message.user.id:
                messager_placement = index
                messager = position.final_value

        # dont show placements if they arent defined
        if interactor:
            if interactor <= 0:
                interactor_placement = 0
            interactor = round(interactor)

        if messager:
            if messager <= 0:
                messager_placement = 0
            messager = round(messager)

        # the little place counter
        current = 1
        for i in result[:15]:
            num = i.final_value
            if num <= 0:
                break
            string = string + f"{current}. {num:,} {unit}: <@{i.user_id}>\n"
            current += 1

        # add the messager and interactor
        # todo: refactor this
        if messager_placement > 15 or interactor_placement > 15:
            string = string + "...\n"
            # sort them correctly!
            if messager_placement > interactor_placement:
                # interactor should go first
                if interactor_placement > 15 and str(interaction.user.id) not in string:
                    string = string + f"{interactor_placement}\\. {interactor:,} {unit}: <@{interaction.user.id}>\n"
                if messager_placement > 15 and str(message.user.id) not in string:
                    string = string + f"{messager_placement}\\. {messager:,} {unit}: <@{message.user.id}>\n"
            else:
                # messager should go first
                if messager_placement > 15 and str(message.user.id) not in string:
                    string = string + f"{messager_placement}\\. {messager:,} {unit}: <@{message.user.id}>\n"
                if interactor_placement > 15 and str(interaction.user.id) not in string:
                    string = string + f"{interactor_placement}\\. {interactor:,} {unit}: <@{interaction.user.id}>\n"

        embedVar = discord.Embed(
                title=f"{type} Leaderboards:", description=string.rstrip(), color=0x4C88BB
        )

        # handle funny buttons
        if type == "Tokens":
            button1 = Button(label="Refresh", style=ButtonStyle.green)
        else:
            button1 = Button(label="Tokens", style=ButtonStyle.blurple)

        button1.callback = tokenlb

        myview = View(timeout=3600)
        myview.add_item(button1)

        # just send if first time, otherwise edit existing
        try:
            if not do_edit:
                raise Exception
            await interaction.edit_original_response(embed=embedVar, view=myview)
        except Exception:
            await interaction.followup.send(embed=embedVar, view=myview)

    async def tokenlb(interaction):
        await lb_handler(interaction, "Tokens")

    await lb_handler(message, leaderboard_type, False)


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
