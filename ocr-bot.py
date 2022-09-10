import os
import time

from discord.ext import commands
import json
from pymongo import MongoClient


with open("./info.json") as f:
    info = json.load(f)

inDev = info["inDev"]

if inDev:
    with open("./config.json") as f:
        configData = json.load(f)
    token = configData["Token"]
    cluster = MongoClient(configData["MongoClient"])

else:
    token = str(os.environ.get("DISCORD_TOKEN"))
    cluster = MongoClient(str(os.environ.get("MONGOCLIENT")))



client = commands.Bot(command_prefix = ';')
client.remove_command("help")

db = cluster["OCRBot"]
client.BMAH_coll = db["BMAH_items"]
client.error_coll = db["errors"]
client.active_boosts_coll = db["active_boosts"]
client.archives_coll = db["archives"]
client.prefix = ';'

# changer l'order pcq utils doit être loadé en premier
list = []
for filename in os.listdir('./cogs'):
    if filename.endswith('.py'):
        list.append(filename)

#myorder = [3, 0, 1, 2] #utils (3), boosts(0), help(1), itemlist(2)
#mylist = [list[i] for i in myorder]



@client.command()
async def load(ctx, extension):
    client.load_extension(f'cogs.{extension}')
    await ctx.send(f'Loaded **{extension}**!')

@client.command()
async def unload(ctx, extension):
    client.unload_extension(f'cogs.{extension}')
    await ctx.send(f'Unloaded **{extension}**!')

@client.command()
async def reload(ctx, extension=None):
    if extension is None:
        for filename in mylist:
            client.unload_extension(f'cogs.{filename[:-3]}')
            client.load_extension(f'cogs.{filename[:-3]}')
            await ctx.send(f'Reloaded **{filename[:-3]}**!')
    else:
        client.unload_extension(f'cogs.{extension}')
        client.load_extension(f'cogs.{extension}')
        await ctx.send(f'Reloaded **{extension}**!')



for filename in list:
    client.load_extension(f'cogs.{filename[:-3]}')


client.run(token)
