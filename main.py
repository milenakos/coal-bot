import asyncio
import os
import random
import time

import discord
import uvloop

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

intents = discord.Intents.default()
bot = discord.Client(intents=intents)

counter = 0
contributors = {}
coal_msg = None
start = 0
last_update_time = 0


@bot.event
async def on_ready():
    print("online")
    await spawn_coal(bot.get_channel(1294299536184967209))

async def mine(user):
    global counter, contributors, coal_msg, start, last_update_time
    counter -= 1
    print(counter)
    contributors[user] = contributors.get(user, 0) + 1
    if counter <= 0:
        coal_save = coal_msg
        coal_msg = None
        contributors = "\n".join([f"<@{k}> - {v}" for k, v in sorted(contributors.items(), key=lambda item: item[1], reverse=True)])
        await coal_save.edit(content=f":pick: Coal mined successfully! It took {round(time.time() - start, 3)} seconds! These people helped:\n{contributors}")
        await asyncio.sleep(random.randint(600, 1200))
        await spawn_coal(coal_save.channel)
        return
    if last_update_time + 5 > time.time():
        return

    last_update_time = time.time()
    await coal_msg.edit(content=f"<:coal:1294300130014527498> A wild coal has appeared! Spam :pick: reaction to mine it! ({counter})")



@bot.event
async def on_raw_reaction_remove(payload):
    if coal_msg and payload.message_id == coal_msg.id and "⛏" in str(payload.emoji) and payload.user_id != bot.user.id:
        await mine(payload.user_id)


@bot.event
async def on_raw_reaction_add(payload):
    if coal_msg and payload.message_id == coal_msg.id and "⛏" in str(payload.emoji) and payload.user_id != bot.user.id:
        await mine(payload.user_id)


async def spawn_coal(channel):
    global counter, contributors, coal_msg, start, last_update_time
    start = time.time()
    counter = random.randint(250, 750)
    contributors = {}
    last_update_time = time.time()
    coal_msg = await channel.send(f"<@&1294332417301286912> <:coal:1294300130014527498> A wild coal has appeared! Spam :pick: reaction to mine it! ({counter})")
    await coal_msg.add_reaction("⛏")


bot.run(os.environ["COAL_TOKEN"])
