import asyncio
import os
import random
import time
import json
from typing import Optional, Literal

import discord
from discord import ButtonStyle
from discord.ext import commands
from discord.ui import Button, View

from database import Channel, Profile, db

if os.name != "nt":
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

while True:
    print("1")

class CleanupClient(commands.AutoShardedBot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def close(self):
        for i in coal_msg.values():
            try:
                if i:
                    # i hate how nested this is but i dont think i can do anything about it
                    await finish_mining(i.channel.id)
            except Exception:
                pass

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
coal_types = {}
start = {}
last_update_time = {}


with open("minerals.json", "r") as f:
    minerals = json.load(f)

coal_options = []
for k, v in minerals.items():
    coal_options.extend([k] * v["chance"])


with open("pickaxes.json", "r") as f:
    pickaxes = json.load(f)


on_ready_debounce = False
last_loop_time = time.time()

async def spawn_coal(channel):
    global counter, contributors, coal_msg, start, last_update_time, coal_types
    if not channel or coal_msg.get(channel.id, None):
        return
    ch = Channel.get(channel.id)
    ch.yet_to_spawn = 0
    ch.save()
    coal_type = random.choice(coal_options)
    start[channel.id] = time.time()
    counter[channel.id] = round(random.randint(250, 750) * ch.hardness_multipler * minerals[coal_type]["hp"])
    contributors[channel.id] = {}
    coal_types[channel.id] = coal_type
    last_update_time[channel.id] = time.time()
    try:
        coal_msg[channel.id] = await channel.send(f"<@&1294332417301286912> <:coal:1294300130014527498> A wild {coal_type} has appeared! Spam :pick: reaction to mine it! ({counter[channel.id]})")
    except Exception:
        # fuck you
        ch.delete_instance()
    await coal_msg[channel.id].add_reaction("⛏")


async def finish_mining(channel_id):
    global coal_msg, coal_types
    coal_save = coal_msg[channel_id]
    if not isinstance(coal_save, discord.Message):
        return
    coal_msg[channel_id] = None
    multiplier = minerals[coal_types[channel_id]]["value"]

    to_save = []

    for user_id, amount in contributors[channel_id].items():
        user, _ = Profile.get_or_create(guild_id=coal_save.guild.id, user_id=user_id)
        user.contributions += 1
        user.clicks += amount
        user.tokens += round(amount * multiplier)
        to_save.append(user)

    with db.atomic():
        Profile.bulk_update(to_save, fields=[Profile.contributions, Profile.clicks, Profile.tokens], batch_size=50)

    contributors_list = "\n".join([f"<@{k}> - {v} clicks, {round(v * multiplier)} tokens" for k, v in sorted(contributors[channel_id].items(), key=lambda item: item[1], reverse=True)])
    try:
        await coal_save.edit(content=f":pick: {coal_types[channel_id]} mined successfully! It took {round(time.time() - start[channel_id])} seconds! These people helped:\n{contributors_list}")
    except Exception:
        # yk i hate you
        pass
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
    await coal_msg[payload.channel_id].edit(content=f"<:coal:1294300130014527498> A wild {coal_types[payload.channel_id]} has appeared! Spam :pick: reaction to mine it! ({counter[payload.channel_id]})")


@bot.tree.command(description="(ADMIN) Setup a mine channel")
@discord.app_commands.default_permissions(manage_guild=True)
async def setup(message):
    if Channel.get_or_none(channel_id=message.channel.id):
        await message.response.send_message("bruh you already setup a mine here are you dumb")
        return

    Channel.create(channel_id=message.channel.id)
    await message.response.send_message(f"ok, now i will also send coals in <#{message.channel.id}>")
    await spawn_coal(message.channel)


@bot.tree.command(description="(ADMIN) Undo the setup")
@discord.app_commands.default_permissions(manage_guild=True)
async def forget(message: discord.Interaction):
    if channel := Channel.get_or_none(channel_id=message.channel.id):
        channel.delete_instance()
        coal_msg.pop(channel.channel_id, None)
        start.pop(channel.channel_id, None)
        counter.pop(channel.channel_id, None)
        contributors.pop(channel.channel_id, None)
        last_update_time.pop(channel.channel_id, None)
        coal_types.pop(channel.channel_id, None)
        await message.response.send_message(f"ok, now <#{message.channel.id}> is no longer a mine")
    else:
        await message.response.send_message("your an idiot there is literally no mine setupped in this channel you stupid")


@bot.tree.command(description="(ADMIN) Forcespawn a coal")
@discord.app_commands.default_permissions(manage_guild=True)
async def forcespawn(message):
    if coal_msg.get(message.channel.id, None):
        await message.response.send_message("bruh you already setup a coal here are you dumb")
        return

    if not Channel.get_or_none(channel_id=message.channel.id):
        await message.response.send_message("bruh this isnt a mine are you dumb")
        return

    await message.response.send_message("ok, spawned.")
    await spawn_coal(message.channel)


@bot.tree.command(description="(ADMIN) changes some server settings (everything is optional)")
@discord.app_commands.default_permissions(manage_guild=True)
async def changesettings(message, minimum_time: int, maximum_time: int, toughness_multiplier: float):
    if not Channel.get_or_none(channel_id=message.channel.id):
        await message.response.send_message("bruh this isnt a mine are you dumb")
        return

    ch = Channel.get(message.channel.id)
    if minimum_time and minimum_time >= 20:
        ch.spawn_times_min = minimum_time
    if maximum_time and maximum_time >= ch.spawn_times_min:
        ch.spawn_times_max = maximum_time
    if toughness_multiplier and toughness_multiplier >= 0:
        ch.hardness_multipler = toughness_multiplier
    ch.save()

    await message.response.send_message("ok, settings saved.")


@bot.tree.command(description="Eat a coal token.")
async def eat(message):
    profile, _ = Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    profile.tokens -= 1
    profile.save()
    await message.response.send_message(f"You eat a coal token. Yum!\nYou now have {profile.tokens} tokens remaining.")


@bot.tree.command(description="View an inventory!")
async def inventory(message, user: Optional[discord.User]):
    if not user:
        user = message.user

    profile, _ = Profile.get_or_create(guild_id=message.guild.id, user_id=user.id)
    embed = discord.Embed(
        title=f"{profile.tokens} tokens",
        description=f"Total clicks: {profile.clicks}\nTotal contributions: {profile.contributions}",
        color=0x4C88BB
    ).set_author(
        name=str(user),
        icon_url=user.avatar.url
    )

    if profile.pickaxe == "Normal":
        embed.add_field(name="⛏️ Normal (Selected)", value="Infinite durability left\nNo extra stats.", inline=True)
    else:
        picked = profile.inventory[profile.pickaxe]
        pickaxe = pickaxes[picked["id"]]
        embed.add_field(name=f"{pickaxe['name']} (Selected)", value=f"{picked['durability']} durability left\n{pickaxe['desc']}", inline=True)

    for k, v in enumerate(profile.inventory):
        if k == profile.pickaxe:
            continue
        pickaxe = pickaxes[v["id"]]
        embed.add_field(name=pickaxe['name'], value=f"{v['durability']} durability left\n{pickaxe['desc']}", inline=True)

    if profile.pickaxe != "Normal":
        embed.add_field(name="⛏️ Normal", value="Infinite durability left\nNo extra stats.", inline=True)

    await message.response.send_message(embed=embed)


@bot.tree.command(description="View the pickaxe shop")
async def shop(message):
    embed = discord.Embed(
        title="Shop",
        description="Click on the items to buy them!",
        color=0x4C88BB
    )

    async def pickaxe_handler(interaction):
        if interaction.user != message.user:
            await interaction.response.send_message("Visit the shop on your own!", ephemeral=True)
            return

        profile, _ = Profile.get_or_create(guild_id=message.guild.id, user_id=interaction.user.id)

        pickaxe = pickaxes[interaction.data["custom_id"]]

        if pickaxe["cost"] > profile.tokens:
            await interaction.response.send_message("You dont have enough tokens to buy this pickaxe!", ephemeral=True)
            return

        if len(profile.inventory) >= 23:
            await interaction.response.send_message("You cant buy any more pickaxes!", ephemeral=True)
            return

        profile.tokens -= pickaxe["cost"]
        h = profile.inventory
        h.append({"id": interaction.data["custom_id"], "durability": pickaxe["durability"]})
        profile.inventory = h
        profile.save()

        await interaction.response.send_message(f"You have bought the {pickaxe['name']} pickaxe!", ephemeral=True)

    view = View()

    for k, v in pickaxes.items():
        if v["cost"] <= 0:
            continue
        embed.add_field(name=v['name'], value=f"{v['durability']} durability\n{v['desc']}\n**{v['cost']} tokens**", inline=True)
        emoji, name = v['name'].split(" ")
        b = Button(label=name, emoji=emoji, style=ButtonStyle.blurple, custom_id=k)
        b.callback = pickaxe_handler
        view.add_item(b)

    await message.response.send_message(embed=embed, view=view)


@bot.tree.command(description="View the leaderboards")
@discord.app_commands.rename(leaderboard_type="type")
@discord.app_commands.describe(leaderboard_type="The leaderboard type to view!")
async def leaderboards(message: discord.Interaction, leaderboard_type: Optional[Literal["Tokens", "Clicks", "Contributions"]]):
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
        elif type == "Clicks":
            unit = "clicks"
            # run the query
            result = (Profile
                .select(Profile.user_id, Profile.clicks.alias("final_value"))
                .where(Profile.guild_id == message.guild.id)
                .group_by(Profile.user_id, Profile.clicks)
                .order_by(Profile.clicks.desc())
            ).execute()
        elif type == "Contributions":
            unit = "contributions"
            # run the query
            result = (Profile
                .select(Profile.user_id, Profile.contributions.alias("final_value"))
                .where(Profile.guild_id == message.guild.id)
                .group_by(Profile.user_id, Profile.contributions)
                .order_by(Profile.contributions.desc())
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

        if type == "Clicks":
            button2 = Button(label="Refresh", style=ButtonStyle.green)
        else:
            button2 = Button(label="Clicks", style=ButtonStyle.blurple)

        if type == "Contributions":
            button3 = Button(label="Refresh", style=ButtonStyle.green)
        else:
            button3 = Button(label="Contributions", style=ButtonStyle.blurple)

        button1.callback = tokenlb
        button2.callback = clickslb
        button3.callback = contributionslb

        myview = View(timeout=3600)
        myview.add_item(button1)
        myview.add_item(button2)
        myview.add_item(button3)

        # just send if first time, otherwise edit existing
        try:
            if not do_edit:
                raise Exception
            await interaction.edit_original_response(embed=embedVar, view=myview)
        except Exception:
            await interaction.followup.send(embed=embedVar, view=myview)

    async def tokenlb(interaction):
        await lb_handler(interaction, "Tokens")

    async def clickslb(interaction):
        await lb_handler(interaction, "Clicks")

    async def contributionslb(interaction):
        await lb_handler(interaction, "Contributions")

    await lb_handler(message, leaderboard_type, False)


async def wait_and_spawn(channel):
    time_left = channel.yet_to_spawn - time.time()
    if time_left > 0:
        await asyncio.sleep(time_left)
    await spawn_coal(bot.get_channel(channel.channel_id))


async def maintaince_loop():
    global last_loop_time
    last_loop_time = time.time()
    await bot.change_presence(
        activity=discord.CustomActivity(name=f"Abusing miners in {len(bot.guilds):,} servers")
    )

    for channel in Channel.select().where(0 < Channel.yet_to_spawn < time.time()):
        await spawn_coal(bot.get_channel(channel.channel_id))
        await asyncio.sleep(0.1)

@bot.event
async def on_ready():
    global on_ready_debounce
    print("online")
    if on_ready_debounce:
        return
    on_ready_debounce = True

    await bot.change_presence(
        activity=discord.CustomActivity(name=f"Just restarted! Abusing miners in {len(bot.guilds):,} servers")
    )

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
        await mine(payload)


@bot.event
async def on_message(message):
    if last_loop_time + 300 < time.time():
        await maintaince_loop()
    if message.author.id == 553093932012011520 and "coal!eval" in message.content:
        silly_billy = message.content.split("coal!eval")[1]

        spaced = ""
        for i in silly_billy.split("\n"):
            spaced += "  " + i + "\n"

        intro = "async def go(message, bot):\n try:\n"
        ending = "\n except Exception:\n  await message.reply(traceback.format_exc())\nbot.loop.create_task(go(message, bot))"

        exec(intro + spaced + ending)


db.connect()
if not db.get_tables():
    db.create_tables([Profile, Channel])

try:
    bot.run(os.environ["COAL_TOKEN"])
finally:
    db.close()
