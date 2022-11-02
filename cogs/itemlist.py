import asyncio
import datetime
import json
import os
import re
import time
import traceback
import aiocron as aiocron
import discord
import typing
from statistics import mean, median
import pytz
from discord.ext import commands
import requests
from pymongo import MongoClient
from pytz import timezone
from views import dbView, confirmView, categoryView
from cogs import utils
with open("./config.json") as f: configData = json.load(f)

# Development or Production
inDev = configData["inDev"]

class ItemList(commands.Cog, name='Item List'):
    # Description of this cog (cog.__doc__)
    """OCR cog description"""

    def __init__(self, client):
        self.client = client
        eastern = pytz.timezone('America/Toronto')
        # (*minute, *hour_of_day, *day_of_month, *month, *day_of_week)
        # example : ('2 4 * * mon,fri')  # 04:02 on every Monday and Friday
        @aiocron.crontab("30 1 * * *", tz=eastern)
        @asyncio.coroutine
        def at_one_thirty():
            yield from self.auto_wipe()

        self.embed_dict = {}
        self.embed_average_dict = {}
        self.embed_median_dict = {}
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

        self.reload_averages_medians_dict()


    # Event: Auto-wipe at 1:30 AM
    @asyncio.coroutine
    async def auto_wipe(self):
        channel = await self.client.fetch_channel(784660945758584853) # bot-commands channel
        msg = f'⏰‼ ***It is 1:30AM!*** ‼⏰'
        await channel.send(msg)
        await self.wipe_func(channel)



    def reload_averages_medians_dict(self):
        document = self.client.BMAH_coll.find_one({"name": "prices"})

        for category, item_obj in document.items():
            if category == "_id" or category == "name":
                continue
            else:
                item_obj = dict(sorted(item_obj.items()))  # sort dictionary alphabetically
                desc_avg = ''
                desc_med = ''
                all_averages = []
                all_medians = []
                for item, price_list in item_obj.items():
                    if price_list:
                        desc_avg += f'‣ {item} ─ **{int(mean(self.get_price(price_list))):,}g**\n'
                        desc_med += f'‣ {item} ─ **{int(median(self.get_price(price_list))):,}g**\n'
                        all_averages.append(int(mean(self.get_price(price_list))))
                        all_medians.append(int(median(self.get_price(price_list))))
                    else:
                        desc_avg += f'‣ {item} ─ **x**\n'
                        desc_med += f'‣ {item} ─ **x**\n'
                if category == 'Mage' or category == 'Priest' or category == 'Hunter' or category == 'Warlock' or category == 'Shaman' or category == 'Warrior' or category == 'Rogue' or category == 'Druid' or category == 'Paladin':
                    desc_avg += f'\n**FULL SET:** {sum(all_averages):,}g\n'
                    desc_med += f'\n**FULL SET:** {sum(all_medians):,}g\n'
                embed_avg = discord.Embed(title=f"{category} Averages", color=self.client.color, description=desc_avg)
                embed_med = discord.Embed(title=f"{category} Medians", color=self.client.color, description=desc_med)

                self.embed_average_dict[f'{category}'] = embed_avg
                self.embed_median_dict[f'{category}'] = embed_med

    @commands.Cog.listener()
    async def on_ready(self):
        print('Bot is online.')


    @commands.command()
    async def ping(self, ctx):
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
        """Will save the BMAH items of interest from photo to the Database. Call this command with an attached image"""
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

            # enlève les sauts de ligne et espaces.  The string '\n' represents newlines and \r represents carriage returns
            result = result.replace('\n', ' ').replace('\r', '').replace(' ', '').replace('•', '-')
            # removes whitespaces after a hyphen --> For "Proto- Drake" -> "Proto-Drake"
            result = re.sub(r"(?<=-)\s", "", result)

            scanned_items = 'diff\n'
            scanned_items_dict = {}
            document = self.client.BMAH_coll.find_one({"name": "all_items"})
            for category, item_list in document.items():
                if category == "_id" or category == "name":
                    continue
                for item in item_list:
                    # Hardcoded for certain items
                    if item.lower().replace(' ', '') in result.lower() or \
                            (item == "Kor'kron Shaman's Treasure" and "korikronshamanis" in result.lower()) or \
                            (item == "Valarjar Stormwing" and "valariar" in result.lower()) or \
                            (item == "Clutch of Ji-Kun" and "clutchof" in result.lower()) or \
                            (item == "Reins of the Green Proto-Drake" and "reinsofthegreen" in result.lower()) or \
                            (item == "Deathcharger's Reins" and "deathchargerisreins" in result.lower()) or \
                            (item == "Reins of the Jade Primordial Direhorn" and "reinsoftheladeprimordialdirehorn" in result.lower()) or \
                            (item == "X-51 Nether-Rocket X-TREME" and "x-51" in result.lower()) or \
                            (item == "Reins of the Drake of the North Wind" and "northwind" in result.lower()) or \
                            (item == "Reins of the Blazing Drake" and "reinsoftheblazing" in result.lower()) or \
                            (item == "Illusion: Winter's Grasp" and "winterisgrasp" in result.lower()) or \
                            (item == "Shackled Ur'zul" and "shackledurizul" in result.lower()) or \
                            (item == "Ashes of Al'ar" and "ashesofaliar" in result.lower()) or \
                            (item == "Kor'kron Juggernaut" and "korikronjuggernaut" in result.lower()) or \
                            (item == "Experiment 12-B" and "experiment12" in result.lower()) :
                            # item_split = item.lower().split()
                    # if all(x in result.lower() for x in item_split):
                    # ---> Code for if all the words in item name are present in result
                    # --- possible issue: "Leggings of Faith" "Frostfire Robe" --> Would register also "Frostfire Leggings" and "Robe of Faith"
                        scanned_items_dict[item] = category
                        self.client.BMAH_coll.update_one({"name": "todays_items"}, {
                        "$inc": {f'{category}.{item}': 1},
                        }, upsert=True)
                        self.client.BMAH_coll.update_one({"name": "todays_items_servers"}, {
                        "$inc": {f'{server.lower()}.{item}': 1},
                        }, upsert=True)

                        # Highlight item in green if there's a current sale for it
                        sales_doc = self.client.BMAH_coll.find_one({"name": "sales"})
                        has_sale = False
                        for item_name, sales_list in sales_doc["Sales"].items():
                            if item_name.lower() in item.lower():
                                scanned_items += f'+‣ {item} (Requested by {sales_list[0]["discordTag"]})\n'
                                has_sale=True
                                break
                        if not has_sale:
                            scanned_items += f' ‣ {item}\n'



            if scanned_items == 'diff\n':
                await scanning_msg.edit(content=f'No items of interest were found in this image')
            else:
                await scanning_msg.edit(content=f'The following items were added to today\'s BMAH item list in the server **{server.title()}**:\n```{scanned_items}```')

            # Keep in memory the last items scanned
            self.last_save = {}
            self.last_save = scanned_items_dict
            self.last_save["server"] = server.lower()

        except:
            await ctx.send(f'There was an unexpected error. Error log for Dev: ```{traceback.format_exc()}```')


    @commands.command(aliases=['listservers'])
    async def serverlist(self, ctx):
        """Shows the list of today's items with the server associated"""
        document = self.client.BMAH_coll.find_one({"name": "todays_items"})
        serverDocument = self.client.BMAH_coll.find_one({"name": "todays_items_servers"})
        await self.list_fct(ctx.guild, ctx.channel, calledWithWithout=False, document=document, client=self.client, withServers=True, serverDocument=serverDocument)


    @commands.command(aliases=['items'])
    async def list(self, ctx, without=None):
        """Shows the list of today's items that were scanned by the bot"""
        # content is a separate function because it is called with the selects
        try:
            document = self.client.BMAH_coll.find_one({"name": "todays_items"})
            if without is None:
                await self.list_fct(ctx.guild, ctx.channel, calledWithWithout=False, document=document, client=self.client)
            elif without.lower() == "without":
                view = categoryView.categoryView(document=document, client=self.client)
                view.message = await ctx.send("This will show today's list without a set of items you select.\nWhat categories are the items from?", view=view)
        except:
            await ctx.send(f'There was an error. Error log for Dev: ```{traceback.format_exc()}```')


    async def list_fct(self, guild, channel, calledWithWithout, document, client, withServers=False, serverDocument=None):
        def date_suffix(myDate):
            date_suffix = ["th", "st", "nd", "rd"]

            if myDate % 10 in [1, 2, 3] and myDate not in [11, 12, 13]:
                return date_suffix[myDate % 10]
            else:
                return date_suffix[0]


        try:
            #document = self.client.BMAH_coll.find_one({"name": "todays_items"})
            emoji_dict = client.BMAH_coll.find_one({"name": "emojis"})

            # check if there are items in today's items
            if not calledWithWithout and len(document.keys()) == 3:
                embed = discord.Embed(description="There are no items in today's list", color=client.color)
                embed.set_author(name="Today's BMAH item list", icon_url=guild.icon.url)
                embed.timestamp = datetime.datetime.utcnow()
                await channel.send(embed=embed)
                return

            # if ;serverlist, fix serverDocument
            if withServers:
                del serverDocument["name"]
                del serverDocument["_id"]

            # Create embed
            now = datetime.datetime.now().strftime('%A, %B %d')
            date_suffix = date_suffix(int(datetime.datetime.now().strftime('%d')))
            embed = discord.Embed(description=f"The BMAH item list for **{now}{date_suffix}** is the following:", color=client.color) #title=f'{emoji} BMAH item list - {now}{date_suffix}')
            embed.set_author(name=f'BMAH item list', icon_url=guild.icon.url) #TODO: uncomment?
            embed.timestamp = datetime.datetime.now()
            embed.set_footer(text=guild.name)

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

            # Create T3 (Armor) fields
            for category, item_dict in ordered_dict.items():
                items = ''
                last_item = list(item_dict)[-1]
                for item, amount in item_dict.items():
                    # if ;listservers
                    if withServers:
                        for server, item_list in serverDocument.items():
                            for item_fromServerDoc in item_list:
                                if item.lower() in item_fromServerDoc.lower():
                                    items += f'{item} ─ {server.capitalize()}\n'
                    else:
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
                        # if ;listservers
                        if withServers:
                            for server, item_list in serverDocument.items():
                                for item_fromServerDoc in item_list:
                                    if item.lower() in item_fromServerDoc.lower():
                                        items += f'{item} ─ {server.capitalize()}\n'
                        else:
                            items += f'{item} {"(" + str(amount) + ")" if amount > 1 else ""}\n'
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

            #await ctx.message.delete()
            await channel.send(embed=embed)
        except:
            await channel.send(f'There was an error. Error log for Dev: ```{traceback.format_exc()}```')




    @commands.command(aliases=['server', 'realms'])
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

                async def add_fields(embed, dict):
                    for server, item_dict in dict.items():
                        items = ''
                        last_item = list(item_dict)[-1]
                        for item, amount in item_dict.items():
                            items += f'{item} {"("+ str(amount) +")" if amount > 1 else ""}\n'
                            if item == last_item:
                                items += "\u200b"
                        embed.add_field(name=server.title(), value=items, inline=True)
                    await ctx.send(embed=embed)

                if len(ordered_dict) > 25:
                    await add_fields(embed, dict(list(ordered_dict.items())[:25]))
                    await add_fields(discord.Embed(color=self.client.color), dict(list(ordered_dict.items())[25:]))
                else:
                    await add_fields(embed, ordered_dict)


            else:
                servers = f''
                for server, item_list in document.items():
                    if server == "_id" or server == "name":
                        continue
                    for item in item_list:
                        if item_given.lower() in item.lower():
                            servers += f'\n ‣ {server.capitalize()}'

                if not servers:
                    servers = f'**{item_given.title()}** is not in today\'s list, or there is a spelling mistake.'
                else:
                    servers = f'**{item_given.title()}** can be found in:' + f"```{servers}```"

                await ctx.send(servers)
        except:
            await ctx.send(f'There was an error. Error log for Dev: ```{traceback.format_exc()}```')


    @commands.command()
    async def wipe(self, ctx):
        """Wipes today's list of items from the database"""
        await self.wipe_func(ctx.channel)


    async def wipe_func(self, channel):
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

        await channel.send("The bot's current list of items has been successfully wiped.")


    @commands.command()
    async def add(self, ctx, server, *, item_name:str):
        """Manually add an item to today's item list. Use this if the bot didn't scan the words correctly."""

        document = self.client.BMAH_coll.find_one({"name": "all_items"})
        for category, item_list in document.items():
            if category == "_id" or category == "name":
                continue
            for item in item_list:
                if item_name.lower() in item.lower():
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
                if item_name.lower() in item.lower():
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
                self.client.BMAH_coll.update_one({"name": "prices"}, {"$set": {f'{category_name}.{capitalized_name}': []}})
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

        # NOTE: Did not code the removal of the item in the 'prices' database in case we want to keep the historical data.


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
    async def enterprices(self, ctx, *, inputted_server=None):
        """Enter the prices for the items of a server in today's list"""
        document = self.client.BMAH_coll.find_one({"name": "todays_items_servers"})

        # verify inputted_server argument is present
        if inputted_server is None:
            await ctx.send(f"You forgot to add the server name!")
            return

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
                    elif inputted_price.lower() == 'skip':
                        break
                    elif (inputted_price.lower() == 'miss') or (inputted_price.lower() == 'missed'):
                        price_list[item] = 0 # Put 0 to indicate that item is missed (should be deleted without entering the price)
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
                        if price > 0 : item_category_dict[item] = category
                        break
                if shouldBreak : break
            if price > 0:
                # add to price db
                self.client.BMAH_coll.update_one({"name": "prices"}, {"$push": {f'{category}.{item}': f'{price}-{inputted_server.title()}'}})
            # remove from "todays_items" and "todays_items_servers"
            self.remove_everywhere(category, item, inputted_server.lower())

        # save item_list in a self.variable list to keep in memory last changes done. (Overwrite last one)
        self.last_price_entry_items = item_category_dict

        # Remove missed items (where price = 0) to avoid it showing in confirmation message
        price_list = {key: val for key, val in price_list.items() if val != 0}

        # Confirmation message
        lst = ''
        if not price_list:
            await ctx.send("No prices were registered.")
        else:
            for item, price in price_list.items():
                lst += f'\n ‣ {item} - {price:,}g - {inputted_server.title()}'
            await ctx.send(f"✅ the following prices have been recorded, and these items are removed from today's list:```{lst}```")

        # Reload averages
        self.reload_averages_medians_dict()



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
            items_to_delete_str += f" ‣ {item} - {self.get_price(price_list[-1]):,}g - {self.get_server(price_list[-1])}\n"
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
            self.reload_averages_medians_dict()



    @commands.command(aliases=['avg', 'average'])
    async def averages(self, ctx, *, item_name=None):
        """Shows the average price of items"""
        await self.avg_or_med_command(ctx, item_name, "Averages")


    @commands.command(aliases=['median', 'med'])
    async def medians(self, ctx, *, item_name=None):
        """Shows the median price of items"""
        await self.avg_or_med_command(ctx, item_name, "Medians")


    async def avg_or_med_command(self, ctx, item_name, avg_or_med):
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
            embed.set_author(name=avg_or_med, icon_url=ctx.guild.icon.url)
            if price_list:
                desc = f"The {'average' if avg_or_med == 'Averages' else 'median'} price for **{formatted_item}** is:\n\n**{(int(mean(self.get_price(price_list))) if avg_or_med == 'Averages' else int(median(self.get_price(price_list)))):,}g**"
            else:
                desc = f"The {'average' if avg_or_med == 'Averages' else 'median'} price for **{formatted_item}** is:\n\n**No data**"
            embed.description = desc
            await ctx.send(embed=embed)

        # No item specified
        else:
            embed = discord.Embed(title=avg_or_med, color=self.client.color, description="Click on the category in which you want to see the items")
            view = dbView.dbView(self.embed_average_dict if avg_or_med == 'Averages' else self.embed_median_dict)
            view.message = await ctx.send(embed=embed, view=view)



    @commands.command(aliases=['prices', 'p'])
    async def price(self, ctx, *, item_name=None):
        """Shows all the past prices an item had, as well as its average and median"""

        # verify item_name is present
        if item_name is None:
            await ctx.send("You forgot to add the item name!")
            return

        try:
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
            # if price exists in db for this item
            if price_list:
                # List is strings of price and server, or simply the price ["442500-Yseras", "316000-Deathwing", "22000"]
                prices_servers_str = ''
                for price_server in price_list:
                    prices_servers_str += f"{self.get_price(price_server):,}g ─ *{self.get_server(price_server)}*\n"
                desc = f"The past prices for **{formatted_item}** are the following:\n\n" \
                       f"{prices_servers_str}" \
                       f"\nAverage : **{int(mean(self.get_price(price_list))):,}g**" \
                       f"\nMedian : **{int(median(self.get_price(price_list))):,}g**"
            else:
                desc = f"The past prices for **{formatted_item}** are the following:\n\n" \
                       f"No data"
            embed.description = desc
            await ctx.send(embed=embed)
        except:
            await ctx.send(f'There was an unexpected error. Error log for Dev: ```{traceback.format_exc()}```')


    def get_price(self, price_string):
        """Get price out of the prices database. Format is "442500-Yseras" or 442500. Shoots only the price in int format."""
        if type(price_string) is int:
            return price_string
        elif type(price_string) is str:
            # string format of type "442500-Yseras"
            price_int = int(price_string.split('-')[0])
            return price_int
        # if list of prices
        elif type(price_string) is list:
            return [self.get_price(x) for x in price_string]


    def get_server(self, price_string):
        """Get server out of the prices database. Format is "442500-Yseras" or 442500. Shoots only the server, or "x" if none set."""
        if type(price_string) is int:
            return "x"
        else:
            # string format of type "442500-Yseras"
            server_name = price_string.split('-')[1]
            return server_name



    @commands.command(aliases=['ap'])
    async def addprice(self, ctx):
        """Manually add a price for an item"""

        def check(m):
            return m.author == ctx.message.author


        # Prompt server
        await ctx.send(content=f"Enter server:")
        all_items_document = self.client.BMAH_coll.find_one({"name": "all_items"})
        category = ''
        item = ''
        item_category_dict = {}
        found = False

        try:
            msg = await self.client.wait_for('message', check=check, timeout=120)
            inputted_server = msg.content
            if inputted_server.lower() == 'cancel':
                await ctx.send("Cancelled the entry.")
                return
        except asyncio.TimeoutError:
            await ctx.send("You took too long to answer. Aborting the entry.")
            return


        # Prompt item name
        await ctx.send(content=f"Enter item name:")

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
        self.client.BMAH_coll.update_one({"name": "prices"}, {"$push": {f'{category}.{item}': f'{translated_price}-{inputted_server.title()}'}})

        # Fill self.variable
        self.last_price_entry_items = item_category_dict

        # Confirmation
        lst = f' ‣ {item} - {translated_price:,}g - {inputted_server.title()}'
        await ctx.send(f"✅ the following price has been recorded:```{lst}```")

        # Reload averages
        self.reload_averages_medians_dict()


    @commands.command(aliases=['sp', 'realmprices'])
    async def serverprices(self, ctx, *, server):
        """Lists all items and their prices that were recorded for a server"""
        # Create embed
        embed = discord.Embed(title=server.title(), color=self.client.color)
        embed.set_author(name="Server Prices", icon_url=ctx.guild.icon.url)

        # Get prices
        document = self.client.BMAH_coll.find_one({"name": "prices"})
        del document["name"]
        del document["_id"]
        outer_desc = ''
        for category_name, items_obj in document.items():
            inner_desc = ''
            for item_name, price_list in items_obj.items():
                for price_str in price_list:
                    if server.lower() in self.get_server(price_str).lower():
                        inner_desc += f"{item_name} - {self.get_price(price_str):,}g\n"
            if inner_desc:
                outer_desc += f"**__{category_name}__**\n{inner_desc}\n"
        embed.description = outer_desc
        await ctx.send(embed=embed)




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
        print("Error in ParsedResults... results_dict value:")
        print(f'results_dict:\n{results_dict}')
        results_dict["datetime"] = datetime.datetime.now()

        fmt = '%Y-%m-%d %H:%M:%S %Z%z'
        eastern = timezone('US/Eastern')
        date = datetime.datetime.now(eastern)
        results_dict["datetime"] = date.strftime(fmt)

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