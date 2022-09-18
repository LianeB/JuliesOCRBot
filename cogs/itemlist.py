import asyncio
import datetime
import json
import os
import re
import time
import traceback
import discord
import typing
from statistics import mean
from discord.ext import commands
import requests
from pymongo import MongoClient
from pytz import timezone
from views import dbView, confirmView
from cogs import utils
with open("./config.json") as f: configData = json.load(f)

# Development or Production
inDev = configData["inDev"]

class ItemList(commands.Cog, name='Item List'):

    # Description of this cog (cog.__doc__)
    """OCR cog description"""

    def __init__(self, client):
        self.client = client
        self.embed_dict = {}
        self.embed_average_dict = {}
        self.last_price_entry_items = {} # dict of {item : category}
        self.last_save = {} # dict of the format {server : "area52", item : category, item : category, ...}

        document = self.client.BMAH_coll.find_one({"name": "all_items"})

        for category, item_list in document.items():
            if category == "_id" or category == "name":
                continue
            elif category == "Mounts":
                items1 = ''
                items2 = ''
                split = len(item_list)//2
                counter = 0
                item_list.sort()
                for item in item_list:
                    if counter <= split:
                        items1 += f'‣ {item}\n'
                    else:
                        items2 += f'‣ {item}\n'
                    counter += 1
                embed = discord.Embed(title="Full BMAH item list", color=self.client.color)
                embed.add_field(name=category, value=items1, inline=True)
                embed.add_field(name="\u200b", value=items2, inline=True)
            else:
                items = ''
                item_list.sort()
                for item in item_list:
                    items += f'‣ {item}\n'
                embed = discord.Embed(title="Full BMAH item list", color=self.client.color, description=f'**{category}**\n{items}')

            self.embed_dict[f'{category}'] = embed

        self.reload_averages_dict()


    def reload_averages_dict(self):
        document = self.client.BMAH_coll.find_one({"name": "prices"})

        for category, item_obj in document.items():
            if category == "_id" or category == "name":
                continue
            else:
                item_obj = dict(sorted(item_obj.items()))  # sort dictionary alphabetically
                desc = ''
                for item, price_list in item_obj.items():
                    if price_list:
                        desc += f'‣ {item} ─ **{int(mean(price_list)):,}g**\n'
                    else:
                        desc += f'‣ {item} ─ **x**\n'
                embed = discord.Embed(title="Averages", color=self.client.color, description=desc)

                self.embed_average_dict[f'{category}'] = embed

    @commands.Cog.listener()
    async def on_ready(self):
        #DiscordComponents(self.client)
        print('Bot is online.')


    @commands.command()
    async def ping(self, ctx):
        # Description of command (command.help)
        """Responds with \"Pong!\""""
        await ctx.send('Pong!')


    @commands.command()
    async def ocr(self, ctx, input_url: typing.Optional[str]):
        """Translates Image to Text. Call this command with an attached image or with a URL to an image"""
        if input_url is None:
            if len(ctx.message.attachments) == 0:
                await ctx.send.edit("You didn't send any image")
                return
            url = ctx.message.attachments[0].url
        else:
            url = input_url
        scanning_msg = await ctx.send("Scanning...")
        result = ocr_space_url(url=url) #http://i.imgur.com/31d5L5y.jpg
        if result == '':
            await scanning_msg.edit(content=f'No text was found in the image')
        else:
            await scanning_msg.edit(content=f'```{result}```')


    @commands.command(aliases=['scan', 's'])
    async def save(self, ctx, *, server): #input_url: typing.Optional[str]
        """Will save the BMAH items of interest from photo to the Database. Call this command with an attached image or a URL to an image"""
        try:
            '''
            if input_url is None:
                if len(ctx.message.attachments) == 0:
                    await ctx.send("You didn't send any image")
                    return
                url = ctx.message.attachments[0].url
            else:
                url = input_url
            '''

            if len(ctx.message.attachments) == 0:
                await ctx.send("You didn't send any image")
                return

            url = ctx.message.attachments[0].url
            scanning_msg = await ctx.send("Scanning...")
            result = ocr_space_url(url=url)

            if "Timed out waiting for results" in result :
                await scanning_msg.edit(content="`The service is experiencing latency issues (slow). Please try again in a few minutes.`")
                return

            # enlève les sauts de ligne  The string '\n' represents newlines and \r represents carriage returns
            result = result.replace('\n', ' ').replace('\r', '')
            # removes whitespaces after a hyphen --> For "Proto- Drake" -> "Proto-Drake"
            result = re.sub(r"(?<=-)\s", "", result)

            scanned_items = ''
            scanned_items_dict = {}
            document = self.client.BMAH_coll.find_one({"name": "all_items"})
            for category, item_list in document.items():
                if category == "_id" or category == "name":
                    continue
                for item in item_list:
                    if item.lower() in result.lower():
                        scanned_items_dict[item] = category
                        scanned_items += f' ‣ {item}\n'
                        self.client.BMAH_coll.update_one({"name": "todays_items"}, {
                        "$inc": {f'{category}.{item}': 1},
                        }, upsert=True)
                        self.client.BMAH_coll.update_one({"name": "todays_items_servers"}, {
                        "$inc": {f'{server.lower()}.{item}': 1},
                        }, upsert=True)

            if scanned_items == '':
                await scanning_msg.edit(content=f'No items of interest were found in this image')
            else:
                await scanning_msg.edit(content=f'The following items were added to today\'s BMAH item list in the server **{server.title()}**:\n```{scanned_items}```')

            # Keep in memory the last items scanned
            self.last_save = {}
            self.last_save = scanned_items_dict
            self.last_save["server"] = server.lower()

        except:
            await ctx.send(f'There was an unexpected error. Error log for Dev: ```{traceback.format_exc()}```')



    @commands.command(aliases=['items'])
    async def list(self, ctx):
        """Shows the list of today's items that were scanned by the bot"""
        def date_suffix(myDate):
            date_suffix = ["th", "st", "nd", "rd"]

            if myDate % 10 in [1, 2, 3] and myDate not in [11, 12, 13]:
                return date_suffix[myDate % 10]
            else:
                return date_suffix[0]


        try:
            document = self.client.BMAH_coll.find_one({"name": "todays_items"})
            emoji_dict = self.client.BMAH_coll.find_one({"name": "emojis"})

            # check if there are items in today's items
            if len(document.keys()) == 3:
                embed = discord.Embed(description="There are no items in today's list", color=self.client.color)
                embed.set_author(name="Today's BMAH item list", icon_url=ctx.guild.icon.url)
                embed.timestamp = datetime.datetime.utcnow()
                await ctx.send(embed=embed)
                return

            now = datetime.datetime.now().strftime('%A, %B %d')
            date_suffix = date_suffix(int(datetime.datetime.now().strftime('%d')))
            embed = discord.Embed(description=f"The BMAH item list for **{now}{date_suffix}** is the following:", color=self.client.color) #title=f'{emoji} BMAH item list - {now}{date_suffix}')
            embed.set_author(name=f'BMAH item list', icon_url=ctx.guild.icon.url) #TODO: uncomment?
            embed.timestamp = datetime.datetime.now()
            embed.set_footer(text=ctx.guild.name)

            # get dict items
            item_list = [*document] # list of dict keys
            unwanted = {'Pets', 'Mounts', 'Misc', '_id', 'name', 'Toys'}
            item_list_sorted = sorted([item for item in item_list if item not in unwanted])
            wanted = {"Misc", "Pets", "Mounts", "Toys"}
            liste_a_part = [item for item in item_list if item in wanted]

            # order dict
            ordered_dict = {}
            for item_name in item_list_sorted:
                ordered_dict[f'{item_name}'] = document[f'{item_name}']

            # dict a part
            dict_a_part = {}
            for item_name in liste_a_part:
                dict_a_part[f'{item_name}'] = document[f'{item_name}']

            # create armor fields
            embed.add_field(name="\u200b", value="\u200b")
            embed.add_field(name="\u200b", value="\u200b")
            embed.add_field(name="\u200b", value="\u200b")
            if len(ordered_dict) == 0:
                embed.add_field(name="No armor items", value="\u200b", inline=True)
                embed.add_field(name="\u200b", value="\u200b")
                embed.add_field(name="\u200b", value="\u200b")


            for category, item_dict in ordered_dict.items():
                items = ''
                last_item = list(item_dict)[-1]
                for item, amount in item_dict.items():
                    items += f'{item} {"("+ str(amount) +")" if amount > 1 else ""}\n'
                    if item == last_item:
                        items += "\u200b"
                category_name = emoji_dict[f'{category}'] + " " + category
                embed.add_field(name=category_name, value=items, inline=True)

            # skip fields if fields not a multiple of 3
            if (len(ordered_dict)+1) % 3 == 0:
                # on finit avec 2 fields, donc en ajouter un vide
                embed.add_field(name="\u200b", value="\u200b")
            elif (len(ordered_dict)+2) % 3 == 0:
                # on finit avec 1 field, donc en ajouter 2 vides
                embed.add_field(name="\u200b", value="\u200b")
                embed.add_field(name="\u200b", value="\u200b")

            # Add Misc, Pets, Mounts
            if len(dict_a_part) == 0:
                embed.add_field(name="No Pets, Mounts or Misc items", value="\u200b", inline=True)
            else:
                for category, item_dict in dict_a_part.items():
                    items = ''
                    for item, amount in item_dict.items():
                        items += f'{item} {"("+ str(amount) +")" if amount > 1 else ""}\n'
                    category_name = emoji_dict[f'{category}'] + " " + category
                    embed.add_field(name=category_name, value=items, inline=True)

            # skip fields if fields not a multiple of 3
            if (len(dict_a_part)+1) % 3 == 0:
                # on finit avec 2 fields, donc en ajouter un vide
                embed.add_field(name="\u200b", value="\u200b")
            elif (len(dict_a_part)+2) % 3 == 0:
                # on finit avec 1 field, donc en ajouter 2 vides
                embed.add_field(name="\u200b", value="\u200b")
                embed.add_field(name="\u200b", value="\u200b")

            await ctx.message.delete()
            await ctx.send(embed=embed)
        except:
            await ctx.send(f'There was an error. Error log for Dev: ```{traceback.format_exc()}```')




    @commands.command(aliases=['server'])
    async def servers(self, ctx, *, item_given=None):
        """Shows the list of today's items that were scanned by the bot, classified by server"""
        try:
            document = self.client.BMAH_coll.find_one({"name": "todays_items_servers"})

            # check if there are items in today's items
            if len(document.keys()) == 2:
                embed = discord.Embed(description="There are no items in today's list", color=self.client.color)
                embed.set_author(name="Servers", icon_url=ctx.guild.icon.url)
                await ctx.send(embed=embed)
                return

            embed = discord.Embed(color=self.client.color) #title=f'{emoji} BMAH item list - {now}{date_suffix}')
            embed.set_author(name="Servers", icon_url=ctx.guild.icon.url)

            if item_given is None:
                # get dict items
                item_list = [*document] # list of dict keys
                unwanted = {'_id', 'name'}
                item_list_sorted = sorted([item for item in item_list if item not in unwanted])

                # order dict
                ordered_dict = {}
                for item_name in item_list_sorted:
                    ordered_dict[f'{item_name}'] = document[f'{item_name}']

                # create fields
                if len(ordered_dict) == 0:
                    embed.add_field(name="No items scanned", value="\u200b", inline=True)

                for server, item_dict in ordered_dict.items():
                    items = ''
                    last_item = list(item_dict)[-1]
                    for item, amount in item_dict.items():
                        items += f'{item} {"("+ str(amount) +")" if amount > 1 else ""}\n'
                        if item == last_item:
                            items += "\u200b"
                    embed.add_field(name=server.title(), value=items, inline=True)
                await ctx.send(embed=embed)

            else:
                servers = f''
                for server, item_list in document.items():
                    if server == "_id" or server == "name":
                        continue
                    for item in item_list:
                        if item.lower() in item_given.lower():
                            servers += f'\n{server.capitalize()}'

                if not servers:
                    servers = 'The item given is not in today\'s list. (or check for spelling errors)'
                else:
                    servers = f'**{item_given}** can be found in:' + servers

                await ctx.send(servers)
        except:
            await ctx.send(f'There was an error. Error log for Dev: ```{traceback.format_exc()}```')


    @commands.command()
    async def wipe(self, ctx):
        """Wipes today's list of items from the database"""
        document = self.client.BMAH_coll.find_one({"name": "todays_items"})
        document_servers = self.client.BMAH_coll.find_one({"name": "todays_items_servers"})

        for category, item_list in document.items():
            if category == "_id" or category == "name":
                continue
            self.client.BMAH_coll.update_one({"name": "todays_items"}, {'$unset': {f'{category}':1}})

        for server, item_list in document_servers.items():
            if server == "_id" or server == "name":
                continue
            self.client.BMAH_coll.update_one({"name": "todays_items_servers"}, {'$unset': {f'{server}':1}})

        # empty last save variable
        self.last_save = {}

        await ctx.send("The bot's current list of items has been successfully wiped.")


    @commands.command()
    async def add(self, ctx, server, *, item_name:str):
        """Manually add an item to today's item list. Use this if the bot didn't scan the words correctly."""

        document = self.client.BMAH_coll.find_one({"name": "all_items"})
        for category, item_list in document.items():
            if category == "_id" or category == "name":
                continue
            for item in item_list:
                if item.lower() in item_name.lower():
                    self.client.BMAH_coll.update_one({"name": "todays_items"}, {
                        "$inc": {f'{category}.{item}': 1},
                    }, upsert=True)
                    self.client.BMAH_coll.update_one({"name": "todays_items_servers"}, {
                        "$inc": {f'{server.lower()}.{item}': 1},
                    }, upsert=True)
                    await ctx.send(f'Added **{item}** to today\'s list in **{server.title()}**')
                    return

        await ctx.send(f'**{item_name}** does not exist in the database. Make sure your spelling is correct. You can see all items in the database with `{self.client.prefix}db`')


    @commands.command()
    async def remove(self, ctx, server, *, item_name):
        """Manually remove 1 of an item from today's item list."""
        document = self.client.BMAH_coll.find_one({"name": "all_items"})
        document_servers = self.client.BMAH_coll.find_one({"name": "todays_items_servers"})

        # verify server exists
        if server.lower()  not in document_servers:
            await ctx.send(f"The server **{server.title()}** does not have items today. You can see the list of today's servers with `{self.client.prefix}servers`")
            return

        # Document classified by item type
        for category, item_list in document.items():
            if category == "_id" or category == "name":
                continue
            for item in item_list:
                if item.lower() in item_name.lower():
                    # remove from the 2 databases
                    self.remove_everywhere(category, item, server)
                    await ctx.send(f'Removed one **{item}** from today\'s list from the server **{server.title()}**')
                    return

        # item not in database
        await ctx.send(f'**{item_name}** does not exist in the database. Make sure your spelling is correct. You can see all items in the database with `{self.client.prefix}db`')



    @commands.command(aliases=['removesave', 'rms'])
    async def removelastsave(self, ctx):
        """Deletes the last entry did with the save command"""

        # self.last_save dict of the format {server : "area52", item : category, item : category, ...}
        if not self.last_save:
            await ctx.send("The previous saved items have already been deleted (or list wiped, or bot rebooted)")
            return

        # Confirm we want to delete these items
        items_to_delete_str = ''
        server = ''
        for key, value in self.last_save.items():
            if key == "server":
                server = value
            else:
                items_to_delete_str += f" ‣ {key}\n"

        view = confirmView.ConfirmView()
        view.message = await ctx.send(f"This will delete the following items in **{server.title()}**:\n"
                                      f"```{items_to_delete_str}```"
                                      f"Proceed with the deletion?", view=view)
        await view.wait()
        if view.value is None:
            await ctx.send('Timed out. Please re-type the command to delete.')

        # Delete items from both databases
        elif view.value:
            for item, category in self.last_save.items():
                if item == "server":
                    continue
                else:
                    # delete from the 2 databases
                    self.remove_everywhere(category,item, server)

                    # Delete last save in memory
                    self.last_save = {}

            await ctx.send(f"✅ The items have been deleted")



    def remove_everywhere(self, category, item, server):
        """Remove an item from today's list. It will also delete the item from the "todays_items_servers" document"""
        # category : Capitalized
        # item : must be formatted as the same as DB
        # server : lowercase (like DB)

        # remove from "todays_items" database
        self.client.BMAH_coll.update_one({"name": "todays_items"}, {
            "$inc": {f'{category}.{item}': -1},
        }, upsert=True)

        # refresh document
        document_today = self.client.BMAH_coll.find_one({"name": "todays_items"})

        # if item count reaches 0, remove item from that category
        if document_today[f'{category}'][f'{item}'] == 0:
            self.client.BMAH_coll.update_one({"name": "todays_items"}, {'$unset': {f'{category}.{item}': 1}})

        # refresh document
        document_today = self.client.BMAH_coll.find_one({"name": "todays_items"})

        # if no more items in category
        if len(document_today[category]) == 0:
            self.client.BMAH_coll.update_one({"name": "todays_items"}, {'$unset': {f'{category}': 1}})


        # remove from "todays_items_servers" database
        self.client.BMAH_coll.update_one({"name": "todays_items_servers"}, {
            "$inc": {f'{server.lower()}.{item}': -1},
        }, upsert=True)

        # refresh document
        document_servers = self.client.BMAH_coll.find_one({"name": "todays_items_servers"})

        # if item count reaches 0, remove item from that server
        if document_servers[server.lower()][item] == 0:
            self.client.BMAH_coll.update_one({"name": "todays_items_servers"}, {'$unset': {f'{server.lower()}.{item}': 1}})

        # refresh document
        document_servers = self.client.BMAH_coll.find_one({"name": "todays_items_servers"})

        # if no more items in that server, delete the server
        if len(document_servers[server.lower()]) == 0:
            self.client.BMAH_coll.update_one({"name": "todays_items_servers"}, {'$unset': {f'{server.lower()}': 1}})



    @commands.command()
    async def db(self, ctx):
        """Shows all items in the database that are scanned for"""
        embed = discord.Embed(title="Full BMAH item list", color=self.client.color, description="Click on the category in which you want to see the items")
        view = dbView.dbView(self.embed_dict)
        view.message = await ctx.send(embed=embed, view=view)



    @commands.command()
    async def dbadd(self, ctx, category, *, item_name):
        """Adds an item to the database to be scanned for"""
        document = self.client.BMAH_coll.find_one({"name": "all_items"})
        del document["name"]
        del document["_id"]
        for category_name, item_list in document.items():
            if category.lower() in category_name.lower():
                for item in item_list:
                    if item_name.lower() in item.lower():
                        await ctx.send(f'The item **{item_name}** already exists in the database')
                        return
                # Get name in title case
                exceptions = ["and", "or", "the", "a", "of", "in"]
                lowercase_words = item_name.lower().split()
                lowercase_words[0] = lowercase_words[0].capitalize()
                capitalized_name = " ".join(w if w in exceptions else w.capitalize() for w in lowercase_words)

                # update DB
                self.client.BMAH_coll.update_one({"name": "all_items"}, {"$push": {f'{category_name}' : capitalized_name}})
                await ctx.send(f'Alright, the item **{capitalized_name}** was entered in the database under the **{category.capitalize()}** category')

                # reload the db command's embed for that category
                await self.reload_embed_dict(category_name)
                return

        await ctx.send(f'The category **{category}** does not exist in the database. Please chose another.')



    @commands.command()
    async def dbremove(self, ctx, *, item_name):
        """Removes an item from the database so it doesn't get scanned anymore."""
        document = self.client.BMAH_coll.find_one({"name": "all_items"})
        del document["name"]
        del document["_id"]
        for category_name, item_list in document.items():
            for item in item_list:
                if item_name.lower() in item.lower():
                    self.client.BMAH_coll.update_one({"name": "all_items"}, {"$pull": {f'{category_name}' : item}})
                    await ctx.send(f'Alright, the item **{item_name}** was removed from the database.')
                    # reload the db command's embed for that category
                    await self.reload_embed_dict(category_name)
                    return
        await ctx.send(f'The item **{item_name}** does not exist in the database.')


    async def reload_embed_dict(self, category_name):
        document = self.client.BMAH_coll.find_one({"name": "all_items"})
        item_list_refreshed = document[category_name]
        if category_name == "Mounts":
            items1 = ''
            items2 = ''
            split = len(item_list_refreshed)//2
            counter = 0
            item_list_refreshed.sort()
            for item in item_list_refreshed:
                if counter <= split:
                    items1 += f'‣ {item}\n'
                else:
                    items2 += f'‣ {item}\n'
                counter += 1
            embed = discord.Embed(title="Full BMAH item list", color=self.client.color)
            embed.add_field(name=category_name, value=items1, inline=True)
            embed.add_field(name="\u200b", value=items2, inline=True)
        else:
            items = ''
            item_list_refreshed.sort()
            for item in item_list_refreshed:
                items += f'‣ {item}\n'
            embed = discord.Embed(title="Full BMAH item list", color=self.client.color, description=f'**{category_name}**\n{items}')

        self.embed_dict[f'{category_name}'] = embed




    @commands.command(aliases=['enterprice', 'ep'])
    async def enterprices(self, ctx, *, inputted_server):
        """Enter the prices for the items of a server in today's list"""
        document = self.client.BMAH_coll.find_one({"name": "todays_items_servers"})

        # verify server is in today's list
        isPresent = False
        for server, item_list in document.items():
            if server.lower() in inputted_server.lower():
                isPresent = True
                break
        if not isPresent:
            await ctx.send(f"There are no items in today's list in **{inputted_server.title()}**, or there is a typo. Use `{self.client.prefix}servers` to see today's servers.")
            return

        # Get items from server
        item_list = document[inputted_server.lower()]
        scanned_items = ''
        for item in item_list:
            scanned_items += f' ‣ {item}\n'

        def check(m):
            return m.author == ctx.message.author

        # Receive user input
        await ctx.send(content=f'The items in **{inputted_server.title()}** are:\n```{scanned_items}```')
        price_list = {} # dict of {item : price}
        for item in item_list:
            await ctx.send(content=f"Enter price for **{item}**:")

            while True:
                try:
                    msg = await self.client.wait_for('message', check=check, timeout=120)
                    inputted_price = msg.content
                    if inputted_price.lower() == 'cancel':
                        await ctx.send("Cancelled the entry.")
                        return
                    if inputted_price.lower() == 'skip':
                        break
                    # convert K to 1000 or M to 1,000,000
                    translated_price = utils.translate_price(inputted_price)
                    price_list[item] = translated_price
                    break
                except asyncio.TimeoutError:
                    await ctx.send(f"{ctx.message.author.mention} You took too long to answer. Aborting the entry.")
                    return
                except:
                    await ctx.send(f'Incorrect number format. Please enter number again. Examples of what I accept : `200500` `200,500` `200.5k` `200,5k` `200k` `200K` (k or M)\n'
                                   f'You can also type `skip` to skip item or `cancel` to cancel.')


        # save all items and prices to db (in db: add to item array)
        all_items_document = self.client.BMAH_coll.find_one({"name": "all_items"})
        item_category_dict = {} # dict of {item : category}
        for item, price in price_list.items():
            # find category
            category = ''
            shouldBreak = False
            for _category, item_list in all_items_document.items():
                if _category == "_id" or _category == "name":
                    continue
                for _item in item_list:
                    if _item.lower() in item.lower():
                        category = _category
                        shouldBreak = True
                        item_category_dict[item] = category
                        break
                if shouldBreak : break
            # add to price db
            self.client.BMAH_coll.update_one({"name": "prices"}, {"$push": {f'{category}.{item}': price}})
            # remove from "todays_items" and "todays_items_servers"
            self.remove_everywhere(category, item, inputted_server.lower())

        # save item_list in a self.variable list to keep in memory last changes done. (Overwrite last one)
        self.last_price_entry_items = item_category_dict

        # Confirmation message
        lst = ''
        if not price_list:
            await ctx.send("No prices were registered.")
        else:
            for item, price in price_list.items():
                lst += f'\n ‣ {item} - {price:,}g'
            await ctx.send(f"✅ the following prices have been recorded, and these items are removed from today's list:```{lst}```")

        # Reload averages
        self.reload_averages_dict()



    @commands.command(aliases=['removeprices', 'rmp'])
    async def removelastprices(self, ctx):
        """In case of error when entering the prices with 'enterPrices', use this command to wipe the last set of prices entered."""

        # verify self.variable isn't empty (empty on reboot, or after a previous deletion)
        if not self.last_price_entry_items:
            await ctx.send("The previous list of items has already been deleted (or the bot has recently rebooted).") # or the bot has rebooted
            return

        # Confirm we want to delete these items
        document = self.client.BMAH_coll.find_one({"name": "prices"})
        items_to_delete_str = ''
        for item, category in self.last_price_entry_items.items():
            price_list = document[category][item]
            items_to_delete_str += f" ‣ {item} - {price_list[-1]:,}g\n"
        view = confirmView.ConfirmView()
        view.message = await ctx.send(f"This will delete the following item prices:\n"
                                      f"```{items_to_delete_str}```"
                                      f"Proceed with the deletion?", view=view)
        await view.wait()
        if view.value is None:
            await ctx.send('You took too long to answer. Please re-type the command to delete.')
        elif view.value:

            # Remove last price for each item
            for item, category in self.last_price_entry_items.items(): # dict of {item : category}
                self.client.BMAH_coll.update_one({"name": "prices"}, {"$pop": {f'{category}.{item}': 1 }}) # 1 : pop last element of array

            # empty self.variable
            self.last_price_entry_items = {}

            # Confirmation message
            await ctx.send(f"✅ the prices have been deleted")

            # Reload averages
            self.reload_averages_dict()



    @commands.command(aliases=['avg', 'average'])
    async def averages(self, ctx, *, item_name=None):
        """Shows the average price of items"""

        # If an item is specifed, print avg of just that item
        if item_name:
            #verify good item name
            document = self.client.BMAH_coll.find_one({"name": "prices"})
            del document["name"]
            del document["_id"]
            price_list = []
            formatted_item = ''
            found = False
            for category_name, items_obj in document.items():
                keysList = list(items_obj.keys())
                for item in keysList:
                    if item_name.lower() in item.lower():
                        price_list = document[category_name][item]
                        formatted_item = item
                        found = True
                        break
            if not found:
                await ctx.send(
                    f"**{item_name}** does not exist in the database. Make sure your spelling is correct. You can see all items in the database with `{self.client.prefix}db`")
                return
            # Create embed
            embed = discord.Embed(color=self.client.color)
            embed.set_author(name="Averages", icon_url=ctx.guild.icon.url)
            if price_list:
                desc = f"The average price for **{formatted_item}** is:\n\n**{int(mean(price_list)):,}g**"
            else:
                desc = f"The average price for **{formatted_item}** is:\n\n**No data**"
            embed.description = desc
            await ctx.send(embed=embed)

        # No item specified
        else:
            embed = discord.Embed(title="Averages", color=self.client.color, description="Click on the category in which you want to see the items")
            view = dbView.dbView(self.embed_average_dict)
            view.message = await ctx.send(embed=embed, view=view)



    @commands.command(aliases=['prices', 'p'])
    async def price(self, ctx, *, item_name):
        """Shows all the past prices an item had, as well as its average"""
        # verify item exists
        document = self.client.BMAH_coll.find_one({"name": "prices"})
        del document["name"]
        del document["_id"]
        price_list = []
        formatted_item = ''
        found=False
        for category_name, items_obj in document.items():
            keysList = list(items_obj.keys())
            for item in keysList:
                if item_name.lower() in item.lower():
                    price_list = document[category_name][item]
                    formatted_item = item
                    found=True
                    break
        if not found:
            await ctx.send(f"**{item_name}** does not exist in the database. Make sure your spelling is correct. You can see all items in the database with `{self.client.prefix}db`")
            return

        # Create embed
        embed = discord.Embed(color=self.client.color)
        embed.set_author(name="Prices", icon_url=ctx.guild.icon.url)
        if price_list:
            prices = ''
            for price in price_list:
                prices += f"{price:,}g\n"
            desc = f"The past prices for **{formatted_item}** are the following:\n\n" \
                   f"{prices}" \
                   f"\nAverage : **{int(mean(price_list)):,}g**"
        else:
            desc = f"The past prices for **{formatted_item}** are the following:\n\n" \
                   f"No data"
        embed.description = desc
        await ctx.send(embed=embed)



    @commands.command(aliases=['ap'])
    async def addprice(self, ctx):
        """Manually add a price for an item"""

        def check(m):
            return m.author == ctx.message.author

        # Prompt item name
        await ctx.send(content=f"Enter item name:")
        all_items_document = self.client.BMAH_coll.find_one({"name": "all_items"})
        category = ''
        item = ''
        item_category_dict = {}
        found = False

        while True:
            try:
                msg = await self.client.wait_for('message', check=check, timeout=120)
                inputted_item = msg.content
                if inputted_item.lower() == 'cancel':
                    await ctx.send("Cancelled the entry.")
                    return
                # verify item exists
                for _category, item_list in all_items_document.items():
                    if _category == "_id" or _category == "name":
                        continue
                    for _item in item_list:
                        if _item.lower() in inputted_item.lower():
                            category = _category
                            item = _item
                            found = True
                            item_category_dict[item] = category
                            break
                    if found : break
                if not found :
                    await ctx.send(f"**{inputted_item}** does not exist in the database. Make sure your spelling is correct. Please re-type it.")
                else:
                    break
            except asyncio.TimeoutError:
                await ctx.send("Timeout. Redo the command.")
                return

        # Prompt price
        await ctx.send(content=f"Enter price:")

        while True:
            try:
                msg = await self.client.wait_for('message', check=check, timeout=120)
                inputted_price = msg.content
                if inputted_price.lower() == 'cancel':
                    await ctx.send("Cancelled the entry.")
                    return
                # convert price
                translated_price = utils.translate_price(inputted_price)
                break
            except asyncio.TimeoutError:
                await ctx.send("You took too long to answer. Aborting the entry.")
                return
            except:
                await ctx.send(
                    f'Incorrect number format. Please enter number again. Examples of what I accept : `200500` `200,500` `200.5k` `200,5k` `200k` `200K` (k or M)\n'
                    f'You can also type `cancel` to cancel the entry.')

        # add to db
        self.client.BMAH_coll.update_one({"name": "prices"}, {"$push": {f'{category}.{item}': translated_price}})

        # Fill self.variable
        self.last_price_entry_items = item_category_dict

        # Confirmation
        lst = f' ‣ {item} - {translated_price:,}g'
        await ctx.send(f"✅ the following price has been recorded:```{lst}```")

        # Reload averages
        self.reload_averages_dict()



if inDev:
    with open("./auth.json") as f: authData = json.load(f)
    cluster = MongoClient(authData["MongoClient"]) # ------------------------------CHANGE HERE

else:
    cluster = MongoClient(str(os.environ.get("MONGOCLIENT")))

db = cluster["OCRBot"]
error_coll = db["errors"]


def ocr_space_url(url, overlay=False, api_key='7d59c9f1ee88957', language='eng'):
    """ OCR.space API request with remote file.
    :param url: Image url.
    :param overlay: Is OCR.space overlay required in your response.
                    Defaults to False.
    :param api_key: OCR.space API key.
                    Defaults to 'helloworld'.
    :param language: Language code to be used in OCR.
                    List of available language codes can be found on https://ocr.space/OCRAPI
                    Defaults to 'en'.
    :return: Result in JSON format.
    """

    payload = {'url': url,
               'isOverlayRequired': overlay,
               'apikey': api_key,
               'language': language,
               }
    time.sleep(0.01)
    r = requests.post('https://api.ocr.space/parse/image',
                      data=payload,
                      )

    # convert dictionary string to dictionary
    results_dict = json.loads(r.content.decode()) #r.content.decode() is a string of dict format

    try:
        result_string = results_dict["ParsedResults"][0]["ParsedText"] # result string
    except:
        print("Error in ParsedResults! Saved the dict to database.")
        print(f'results_dict:\n{results_dict}')
        results_dict["datetime"] = datetime.datetime.now()

        fmt = '%Y-%m-%d %H:%M:%S %Z%z'
        eastern = timezone('US/Eastern')
        date = datetime.datetime.now(eastern)
        results_dict["datetime"] = date.strftime(fmt)

        error_coll.insert_one(results_dict)

        error_msg = ''
        for msg in results_dict["ErrorMessage"]:
           error_msg += msg + "\n"
        return error_msg
    else:
        return result_string

async def setup(client):
    await client.add_cog(ItemList(client))
    print('Item List cog is loaded')


# IMPORTANT NOTE
# Pass 'self' in every function
# To get 'client', you must use self.client