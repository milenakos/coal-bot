import asyncio
import os
import random
import time

import discord
import uvloop

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)


counter = random.randint(200, 1000)
contributors = {}
coal_msg = None
start = 0
last_update_time = 0


@bot.event
async def on_ready():
    print("online")

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
        await asyncio.sleep(random.randint(300, 600))
        await spawn_coal(coal_save)
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

async def spawn_coal(message):
    global counter, contributors, coal_msg, start, last_update_time
    start = time.time()
    counter = random.randint(500, 2000)
    contributors = {}
    last_update_time = time.time()
    coal_msg = await message.channel.send(f"<@&1294332417301286912> <:coal:1294300130014527498> A wild coal has appeared! Spam :pick: reaction to mine it! ({counter})")
    await coal_msg.add_reaction("⛏")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if message.author.id == 553093932012011520 and message.content == "coal":
        await spawn_coal(message)

bot.run(os.environ["COAL_TOKEN"])
