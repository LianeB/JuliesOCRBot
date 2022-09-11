import datetime
import json
import os
import re
import time
import traceback
import discord
import typing
from discord.ext import commands
import requests
#from discord_components import DiscordComponents, Button, ButtonStyle, InteractionType
from pymongo import MongoClient
from pytz import timezone
with open("./config.json") as f: configData = json.load(f)

# Development or Production
inDev = configData["inDev"]

class ItemList(commands.Cog, name='Item List'):

    # Description of this cog (cog.__doc__)
    """OCR cog description"""

    def __init__(self, client):
        self.client = client
        self.embed_dict = {}

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

    @commands.Cog.listener()
    async def on_ready(self):
        #DiscordComponents(self.client)
        print('Bot is online.')


    @commands.command()
    async def ping(self, ctx):
        # Description of command (command.help)
        """Responds with \"Pong!\""""
        await ctx.send('Pong!')

    async def get_name(self, ctx):
        if ctx.guild.id == 790974567865647116: # Liane's testing server
            name = "test_todays_items"
        else:
            name = "todays_items"
        return name

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
            await scanning_msg.edit(f'No text was found in the image')
        else:
            await scanning_msg.edit(f'```{result}```')


    @commands.command(aliases=['scan', 's'])
    async def save(self, ctx, input_url: typing.Optional[str]):
        """Will save the BMAH items of interest from photo to the Database. Call this command with an attached image or a URL to an image"""
        try:
            if input_url is None:
                if len(ctx.message.attachments) == 0:
                    await ctx.send("You didn't send any image")
                    return
                url = ctx.message.attachments[0].url
            else:
                url = input_url
            scanning_msg = await ctx.send("Scanning...")
            result = ocr_space_url(url=url)

            # enlève les sauts de ligne  The string '\n' represents newlines and \r represents carriage returns
            result = result.replace('\n', ' ').replace('\r', '')
            # removes whitespaces after a hyphen --> For "Proto- Drake" -> "Proto-Drake"
            result = re.sub(r"(?<=-)\s", "", result)

            scanned_items = ''
            document = self.client.BMAH_coll.find_one({"name": "all_items"})
            for category, item_list in document.items():
                if category == "_id" or category == "name":
                    continue
                for item in item_list:
                    if item.lower() in result.lower():
                        scanned_items += f' ‣ {item}\n'
                        name = await self.get_name(ctx)
                        self.client.BMAH_coll.update_one({"name": name}, {
                        "$inc": {f'{category}.{item}': 1},
                        }, upsert=True)

            if scanned_items == '':
                await scanning_msg.edit(content=f'No items of interest were found in this image')
            else:
                await scanning_msg.edit(content=f'The following items were added to today\'s BMAH item list:\n```{scanned_items}```')
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
            name = await self.get_name(ctx)
            document = self.client.BMAH_coll.find_one({"name": name})
            emoji_dict = self.client.BMAH_coll.find_one({"name": "emojis"})

            # check if there are items in today's items
            if len(document.keys()) == 3:
                embed = discord.Embed(description="There are no items in today's list", color=self.client.color)
                embed.set_author(name="Today's BMAH item list", icon_url=ctx.guild.icon_url)
                await ctx.send(embed=embed)
                return

            now = datetime.datetime.now().strftime('%A, %B %d')
            date_suffix = date_suffix(int(datetime.datetime.now().strftime('%d')))
            embed = discord.Embed(color=self.client.color) #title=f'{emoji} BMAH item list - {now}{date_suffix}')
            embed.set_author(name=f'BMAH item list - {now}{date_suffix}', icon_url=ctx.guild.icon_url) #TODO: uncomment?

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

            # create armor fields #TODO: uncomment?
            embed.add_field(name="\u200b", value="\u200b")
            #embed.add_field(name="\u200b", value="**ARMOR**\n\u200b", inline=True) #**🛡️
            embed.add_field(name="\u200b", value="\u200b")
            embed.add_field(name="\u200b", value="\u200b")
            if len(ordered_dict) == 0:
                embed.add_field(name="None", value="\u200b", inline=True)
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
            embed.add_field(name="\u200b", value="\u200b")
            #embed.add_field(name="\u200b", value="**MISC/MOUNTS/PETS**\n\u200b", inline=True) # 🐴
            embed.add_field(name="\u200b", value="\u200b")
            embed.add_field(name="\u200b", value="\u200b")
            if len(dict_a_part) == 0:
                embed.add_field(name="None", value="\u200b", inline=True)
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


    @commands.command()
    async def wipe(self, ctx):
        """Wipes today's list of items from the database"""
        name = await self.get_name(ctx)
        document = self.client.BMAH_coll.find_one({"name": name})

        for category, item_list in document.items():
            if category == "_id" or category == "name":
                continue
            self.client.BMAH_coll.update_one({"name": name}, {'$unset': {f'{category}':1}})

        await ctx.send("The bot's current list of items has been successfully wiped.")


    @commands.command()
    async def add(self, ctx, amount: typing.Optional[int] = 1, *, item_name:str):
        """Manually add an item to today's item list. Use this if the bot didn't scan the words correctly."""

        document = self.client.BMAH_coll.find_one({"name": "all_items"})
        for category, item_list in document.items():
            if category == "_id" or category == "name":
                continue
            for item in item_list:
                if item.lower() in item_name.lower():
                    name = await self.get_name(ctx)

                    self.client.BMAH_coll.update_one({"name": name}, {
                        "$inc": {f'{category}.{item}': amount},
                    }, upsert=True)
                    await ctx.send(f'Added {amount} **{item_name}** to today\'s list')
                    return

        await ctx.send(f'**{item_name}** does not exist in the database. Make sure your spelling is correct. You can see all items in the database with `{self.client.prefix}db`')

    @commands.command()
    async def remove(self, ctx, amount: typing.Optional[int] = None, *, item_name):
        """Manually remove an item from today's item list. If no quantity is specified, the bot will remove all items with that name"""
        name = await self.get_name(ctx)
        document = self.client.BMAH_coll.find_one({"name": "all_items"})
        for category, item_list in document.items():
            if category == "_id" or category == "name":
                continue
            for item in item_list:
                if item.lower() in item_name.lower():
                    if amount == None:
                        self.client.BMAH_coll.update_one({"name": name}, {'$unset': {f'{category}.{item}':1}})
                        document_today = self.client.BMAH_coll.find_one({"name": name})
                    else:
                        self.client.BMAH_coll.update_one({"name": name}, {
                            "$inc": {f'{category}.{item}': -amount},
                        }, upsert=True)
                        document_today = self.client.BMAH_coll.find_one({"name": name})
                        if document_today[f'{category}'][f'{item}'] == 0:
                            self.client.BMAH_coll.update_one({"name": name}, {'$unset': {f'{category}.{item}':1}})

                    if len(document_today[f'{category}']) == 0:
                        self.client.BMAH_coll.update_one({"name": name}, {'$unset': {f'{category}':1}})

                    await ctx.send(f'Removed {amount if amount else ""} **{item_name}** from today\'s list')
                    return

        await ctx.send(f'**{item_name}** does not exist in the database. Make sure your spelling is correct. You can see all items in the database with `{self.client.prefix}db`')

    '''
    @commands.command()
    async def db(self, ctx):
        """Shows all items in the database that are scanned for"""
        embed = discord.Embed(title="Full BMAH item list", color=self.client.color, description="Click on the category in which you want to see the items")

        categories = [*self.embed_dict] # list of dict keys
        nbCategories = len(categories)
        count = 0
        done = False
        buttons = []
        for i in range(5):
            buttons.append([])
            for j in range(5):
                btn = Button(label=categories[count])
                buttons[i].append(btn)

                count += 1
                if count == nbCategories:
                    done = True
                    break
            if done:
                break

        await ctx.send(embed=embed, components=buttons)
    '''

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

    '''
    @commands.Cog.listener()
    async def on_button_click(self, res):
        categories = [*self.embed_dict] # list of dict keys
        if res.component.label in categories:
            msg = await res.channel.fetch_message(res.message.id)
            await res.respond(type=6)
            await msg.edit(embed=self.embed_dict[res.component.label])
    '''

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