import os
import asyncio
from discord.ext import commands
import discord
import json
from pymongo import MongoClient
with open("./config.json") as f: configData = json.load(f)

# Development or Production
inDev = configData["inDev"]

# Get environment variables
if inDev:
    with open("./auth.json") as f: authData = json.load(f)
    token = authData["Token"]
    cluster = MongoClient(authData["MongoClient"])
    bmah_items_collection = "dev_BMAH_items"

else:
    token = str(os.environ.get("DISCORD_TOKEN"))
    cluster = MongoClient(str(os.environ.get("MONGOCLIENT")))
    bmah_items_collection = "BMAH_items"


# Setup client
intents=discord.Intents.all()
client = commands.Bot(command_prefix = configData["prefix"], intents = intents, case_insensitive=True, help_command=None)
db = cluster["JulieOCRBot"]

#Set variables accessible in all cogs
client.BMAH_coll = db[bmah_items_collection] # either BMAH_items or dev_BMAH_items
client.error_coll = db["errors"]
client.color = 0x68bd0e #0x74d40c
client.prefix = configData["prefix"]



@client.command()
async def reload(ctx, extension=None):
    if extension is None:
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await client.unload_extension(f'cogs.{filename[:-3]}')
                await client.load_extension(f'cogs.{filename[:-3]}')
                await ctx.send(f'Reloaded **{filename[:-3]}**!')
    else:
        await client.unload_extension(f'cogs.{extension}')
        await client.load_extension(f'cogs.{extension}')
        await ctx.send(f'Reloaded **{extension}**!')


async def load():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            await client.load_extension(f'cogs.{filename[:-3]}')

async def main():
    await load()
    await  client.start(token)


asyncio.run(main())