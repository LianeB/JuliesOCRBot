import datetime
import re
import traceback
import discord
from discord.ext import commands
import json
from views import paginatorView, completionView
from cogs import utils
import math

with open("./config.json") as f: configData = json.load(f)


class Boosts(commands.Cog, name='Sales'):
    """Has related commands to save, track and complete paid boosts"""

    def __init__(self, client):
        self.client = client
        #self.utils = self.client.get_cog('Utils')
        self.embed_list = []



    #TODO: if sales in ;boosts by item need to be in order, add a datetime field in Sales
    @commands.command(aliases=['b'])
    async def buyer(self, ctx, buyer, price, *, inputted_item):
        """Saves the boost to the list of active boosts"""

        #get buyer user object
        user = None
        try:
            user = await commands.UserConverter().convert(ctx, buyer)
        except:
            pass

        #translate k to int
        try:
            formatted_price = utils.translate_price(price)
        except:
            await ctx.send(f'Incorrect number format. Examples of what I accept : `200500` `200,500` `200.5k` `200,5k` `200k` `200K` (k or M)')
            return

        def check(m):
            return m.user == ctx.message.author

        try:
            # Ask for booster
            select = discord.ui.Select(custom_id='boosterSelect', placeholder="Select a user", options=[discord.SelectOption(label="Xjd"), discord.SelectOption(label="Gunner")])
            view = discord.ui.View()
            view.add_item(select)
            msg = await ctx.send(content=f"Who did the sale?", view=view)
            interaction = await self.client.wait_for('interaction', check=check, timeout=60)
            await interaction.response.defer()
            booster = interaction.data['values'][0] #interaction.data = {'values': ['Xjd'], 'custom_id': 'boosterSelect', 'component_type': 3}

            # Ask if paid
            button_yes = discord.ui.Button(custom_id='Yes', style=discord.ButtonStyle.green, label="Yes")
            button_no = discord.ui.Button(custom_id='No', style=discord.ButtonStyle.red, label="No")
            view = discord.ui.View()
            view.add_item(button_yes)
            view.add_item(button_no)
            await ctx.send(content=f"Is the item paid?", view=view)
            interaction = await self.client.wait_for('interaction', check=check, timeout=5)
            for item in view.children:
                item.disabled = True
            await interaction.response.edit_message(view=view)
            isPaid = True if interaction.data['custom_id'] == 'Yes' else False
        except:
            await ctx.send(f"{ctx.author.mention} You took too long to enter the sale. Entry aborted.")
            return

        # check for keywords
        words = inputted_item.split()
        if words[0].lower() == "t3":
            classes = ["mage", "warrior", "warlock", "priest", "druid", "paladin", "hunter", "shaman", "rogue"]
            _class = words[1]
            if _class.lower() in classes:
                # prend en compte les mots partiels (sans s)
                keywords = { "Head" : ["head", "helm", "helmet", "circlet", "headpiece"],
                             "Chest": ["chest", "robe", "tunic", "breastplate"],
                             "Shoulder" : ["shoulders", "shoulderpads", "spaulders", "pauldrons"],
                             "Gloves" : ["gloves", "hand", "gauntlets", "handguards"],
                             "Legging" : ["leg", "pants", "leggings", "legguards", "legplates"],
                             "Belt" : ["belt", "waist", "girdle", "waistguard"],
                             "Boots" : ["boots", "feet", "sandals", "sabatons"],
                             "Wrist" : ["wrist", "bracers", "bindings", "wristguards"]
                             }
                inputted_items_list = words[2:]
                count = 1
                inputted_items_official_names_list = []
                # Find official item names from DB
                all_items_document = self.client.BMAH_coll.find_one({"name": "all_items"})
                fullset_list = all_items_document[_class.capitalize()]
                for inputted_item in inputted_items_list:
                    # fullset
                    if inputted_item.lower() == "fullset":
                        for item_full_name in fullset_list:
                            inputted_items_official_names_list.append(item_full_name)
                            #todo: uncomment
                            self.client.BMAH_coll.update_one({"name": "sales"}, { "$push": {f'Sales.{item_full_name}': {"buyerid": user.id if user else "", "discordTag": str(user) if user else buyer, "Price": formatted_price, "Multiple": f'{count}/{len(fullset_list)}', "Booster": booster, "isPaid": isPaid}}}, upsert=True)
                            count += 1
                    else:
                        canBreak = False
                        for item_type, synonym_list in keywords.items():
                            for keyword in synonym_list:
                                if inputted_item.lower() in keyword:
                                    #find offical item name
                                    for official_item_name in fullset_list:
                                        if any(keyword in official_item_name.lower() for keyword in synonym_list):
                                            inputted_items_official_names_list.append(official_item_name)
                                            #TODO: UNCOMMENT
                                            self.client.BMAH_coll.update_one({"name": "sales"}, { "$push": {f'Sales.{official_item_name}': {"buyerid": user.id if user else "", "discordTag": str(user) if user else buyer, "Price": formatted_price, "Multiple": f'{count}/{len(inputted_items_list)}', "Booster": booster, "isPaid": isPaid}}}, upsert=True)
                                            canBreak = True
                                            count += 1
                                        if canBreak: break
                                if canBreak: break
                            if canBreak: break
                        if not canBreak:
                            await ctx.send(f"Did not find match for **{inputted_item}**")
                items_formatted = ''
                count = 1
                for item_name in inputted_items_official_names_list:
                    items_formatted += f" ‣ {item_name} ({count}/{len(inputted_items_official_names_list)})\n"
                    count += 1
                await ctx.send(f'💰 Added a sale of **{formatted_price:,}g** ({"paid" if isPaid else "unpaid"}) for buyer {user.mention if user else ""}(**{str(user) if user else buyer}**), by {booster}, for the item(s) ```{items_formatted}```')
                return

        # only 1 item inputted
        else:
            # Verify if item exists
            document = self.client.BMAH_coll.find_one({"name": "all_items"})
            for category, item_list in document.items():
                if category == "_id" or category == "name":
                    continue
                for item in item_list:
                    if inputted_item.lower() in item.lower():
                        # item exists, add to sales DB
                        #TODO: UNCOMMENT
                        self.client.BMAH_coll.update_one({"name": "sales"}, { "$push": {f'Sales.{item}': {"buyerid": user.id if user else "", "discordTag": str(user) if user else buyer, "Price": formatted_price, "Multiple": "", "Booster": booster, "isPaid": isPaid}}}, upsert=True)
                        await ctx.send(f'💰 Added a sale of **{formatted_price:,}g** ({"paid" if isPaid else "unpaid"}) for buyer {user.mention if user else ""}(**{str(user) if user else buyer}**), by {booster}, for the item ``` ‣ {item}```')
                        return

            # Did not find item
            await ctx.send(f'**{inputted_item.title()}** does not exist in the database. Make sure your spelling is correct. You can see all items in the database with `{self.client.prefix}db`')



    @commands.command(aliases=['rs'])
    async def removesale(self, ctx, buyer, *, item_identifier):
        """Use this command if a mistake was made in paid. It will remove a sale from the list of paid boosts"""
        #convert buyer to discord Tag if user object
        if isinstance(buyer, discord.User):
            buyer = str(buyer)

        await self.remove_active_boost(ctx, buyer, item_identifier, "removed")

    '''
    @commands.command(aliases=['done'])
    async def complete(self, ctx, buyer, *, item_identifier):
        """Completes a boost. (removes the sale from the list)"""
        # buyer is either User object or discord Tag string

        #convert buyer to discord Tag if user object
        try:
            user = await commands.UserConverter().convert(ctx, buyer)
            buyer = str(user)
        except:
            pass

        # if item_identifier is only numbers
        if all(word.isdigit() or word.isspace() for word in item_identifier):
            item_names = await self.remove_active_boost(ctx, buyer, item_identifier.split(), "completed")
        # if item_identifier is the item name
        else:
            item_names = await self.remove_active_boost(ctx, buyer, item_identifier, "completed")
    '''

    @commands.command(aliases=['comp'])
    async def complete(self, ctx):
        document = self.client.BMAH_coll.find_one({"name": "sales"})

        count_items = 0
        select_options = []
        selects = []
        page = 1
        for item_name, sales_list in document["Sales"].items():
            for object_sale in sales_list:
                select_options.append(discord.SelectOption(label=item_name, description=object_sale["discordTag"], value=f'{item_name}|{object_sale["discordTag"]}'))
            count_items += 1

            if count_items % 8 == 0:
                selects.append(completionView.itemSelect(select_options, f'Page {page}'))
                select_options = []
                page += 1
            elif count_items >= len(document["Sales"].keys()):
                selects.append(completionView.itemSelect(select_options, f'Page {page}'))

        view = completionView.completionView(ctx, self.client, selects)
        view.message = await ctx.send("Select the items to complete", view=view)



    async def remove_active_boost(self, ctx, buyer, item_identifier, removed_or_completed, withButton=False):
        """Removes specified item (or index) from active boosts"""

        """
        :buyer: discord tag
        
        :item_identifier: 
           is either 
            - list (list of # to complete)
            - str : item name 
        
        :removed_or_completed: string "removed" or "completed" for confirmation message at the end
        
        returns all full item names that have been completed
        """
        index = None
        input_item_name = None
        items_to_delete = None
        if isinstance(item_identifier, list):
            items_to_delete = []
        else:
            try:
                index = int(item_identifier) -1
            except:
                input_item_name = item_identifier


        document = self.client.BMAH_coll.find_one({"name": "sales"})

        playeritems_dict = {} # discordTag : [item1, item2], ...
        item_set = set() # tous les objets dans les current boost
        for item_name, sales_list in document["Sales"].items():
            for object_sale in sales_list:
                playeritems_dict.setdefault(object_sale["discordTag"],[]).append(item_name) # if key doesnt exist, add [] and append, else append
                item_set.add(item_name)

        if buyer not in playeritems_dict.keys():
            await ctx.send(f'The player **{buyer}** does not have any active boosts')
            return None

        correct_item_names = [] #used to have item name to delete Array at the end of function

        # if wants to complete multiple numbers
        if isinstance(item_identifier, list):
            for number in item_identifier:
                number = int(number)
                if number > len(playeritems_dict[buyer]) or number < 1:
                    await ctx.send(f'The number {number} is incorrect. This player does not have that many active boosts')
                    return None
                items_to_delete.append(playeritems_dict[buyer][number-1]) #number-1 to get index
            for item in items_to_delete:
                self.client.BMAH_coll.update_one({"name": "sales"}, {"$pull": {f'Sales.{item}' : {"discordTag": buyer}}})
                correct_item_names.append(item)


        # complete according to item name
        elif input_item_name is not None:
            found=False
            for official_item_name in item_set:
                if input_item_name.lower() in official_item_name.lower():
                    self.client.BMAH_coll.update_one({"name": "sales"},{"$pull": {f'Sales.{official_item_name}': {"discordTag": buyer}}})
                    correct_item_names.append(official_item_name)
                    found=True
                    break
            if not found:
                await ctx.send(f'User **{buyer}** has no sale for item **{input_item_name}**, or item has a typo.')
                return None


        # if list is empty, delete field
        document = self.client.BMAH_coll.find_one({"name": "sales"})
        for correct_item_name in correct_item_names:
            if correct_item_name in document["Sales"]:
                if len(document["Sales"][correct_item_name]) == 0:
                    self.client.BMAH_coll.update_one({"name": "sales"}, {'$unset': {f'Sales.{correct_item_name}':1}})

        if not withButton:
            if isinstance(item_identifier, list):
                await ctx.send(f'✅ Boost(s) **{", ".join(name for name in correct_item_names)}** for buyer **{buyer}** have been successfully {removed_or_completed}')
            else:
                await ctx.send(f'✅ Boost **{item_identifier}** for buyer **{buyer}** has been successfully {removed_or_completed}')
            return correct_item_names


    @commands.command()
    async def paid(self, ctx, buyer, *, item_name):
        """Change the status of a sale from 'not paid' to 'paid' """

        # Get discord Tag depending if player is str or User object
        try:
            user = await commands.UserConverter().convert(ctx, str(buyer))
            discordTag = str(user)
        except:
            discordTag = buyer

        # update DB
        document = self.client.BMAH_coll.find_one({"name": "sales"})
        found=False
        for item_full_name, sale_list in document["Sales"].items():
            if item_name.lower() in item_full_name.lower():
                idx = 0
                for sale_object in sale_list:
                    if discordTag.lower() in sale_object["discordTag"].lower():
                        self.client.BMAH_coll.update_one({"name": "sales"}, {"$set": {f'Sales.{item_full_name}.{idx}.isPaid': True}}, upsert=True)
                        await ctx.send(f'✅ **{item_full_name}** sale for **{discordTag}** is now paid')
                        found=True
                        break
                    idx += 1
        if not found:
            await ctx.send(f'❌ **{item_name.title()}** sale for **{discordTag}** was not found. Make sure there are no spelling mistakes. You may see all current sales with `;boosts`')


    @commands.command(aliases=["lb", "buyerslist", "listbuyers", "buyers", "orders"])
    async def boosts(self, ctx, by="by", categorize_by="item", player=None):
        """Lists the active boosts. Can list by item or by player (default is by item). Type literally `;boosts by player` or `;boosts by item`"""

        # Get discord Tag depending if player is str or User object
        user = None
        if isinstance(player, discord.User):
            user = player
            discordTag = str(user)
        else:
            discordTag = player

        document = self.client.BMAH_coll.find_one({"name": "sales"})

        if document is None:
            embed = discord.Embed(title=":star2: Active Boosts", color=self.client.color)
            embed.add_field(name="\u200b", value="There are currently no active boosts")
            await ctx.send(embed=embed)
            return

        if len(document["Sales"]) == 0:
            embed = discord.Embed(title=":star2: Active Boosts", color=self.client.color)
            embed.add_field(name="\u200b", value="There are currently no active boosts")
            await ctx.send(embed=embed)
            return

        loading_msg = await ctx.send("Loading...")
        if ("player" in categorize_by.lower() or "user" in categorize_by.lower() or "buyer" in categorize_by.lower()):
            embed = discord.Embed(title=":star2: Paid Boosts by Player", color=self.client.color)
            playeritems_dict = {}
            gold_dict = {}
            userid_dict = {}
            multiple_dict = {}
            isPaid_dict = {}
            booster_dict = {}
            count_fields = 0
            self.embed_list = []
            qty_per_page = 8
            page = 1
            count_players = 0

            try:
                for item_name, sales_list in document["Sales"].items():
                    for object_sale in sales_list:
                        playeritems_dict.setdefault(object_sale["discordTag"],[]).append(item_name) # if key doesnt exist, add [] and append, else append
                        gold_dict.setdefault(object_sale["discordTag"],[]).append(object_sale["Price"])
                        userid_dict.setdefault(object_sale["discordTag"], []).append(object_sale["buyerid"])
                        multiple_dict.setdefault(object_sale["discordTag"], []).append(object_sale["Multiple"])
                        isPaid_dict.setdefault(object_sale["discordTag"], []).append(object_sale["isPaid"])
                        booster_dict.setdefault(object_sale["discordTag"], []).append(object_sale["Booster"])

                for db_discordTag, list_items in playeritems_dict.items():
                    if player is not None:
                        if db_discordTag == discordTag:
                            pass # continue this loop
                        else:
                            continue # next loop
                    item_count = 1
                    last_item_number = len(list_items)
                    try:
                        # if buyerid exists, can convert to user
                        user = await commands.UserConverter().convert(ctx, str(userid_dict[db_discordTag][0]))
                        item_info = f'{user.mention}\n'
                    except:
                        # buyerid doesnt exist, use just discord tag
                        item_info = f'**{db_discordTag}**\n'


                    for item in list_items:
                        isPaid = isPaid_dict[db_discordTag][item_count - 1]
                        item_info += f'{item_count}. **{item.title()}** {multiple_dict[db_discordTag][item_count-1]}- '
                        item_info += f'{gold_dict[db_discordTag][item_count-1]:,}g ' #price
                        item_info += f'{"✅ paid" if isPaid else "❌ not paid"} - '  # isPaid
                        item_info += f'{booster_dict[db_discordTag][item_count-1]}\n'  # booster
                        item_count += 1
                    if item_count == last_item_number:
                        item_info += "\u200b"
                    embed.add_field(name="\u200b", value=item_info, inline = False)
                    count_fields += 1
                    count_players += 1

                    # create pages (embeds) for paginator
                    if count_fields >= len(playeritems_dict):
                        embed.set_footer(text=f'Viewing {(page-1)*qty_per_page+1}-{count_players} of {len(playeritems_dict)} players | page {page}/{math.ceil((len(playeritems_dict) / qty_per_page))}')
                        self.embed_list.append(embed)
                        page += 1
                    elif count_fields % 8 == 0:
                        embed.set_footer(text=f'Viewing {(page-1)*qty_per_page+1}-{count_players} of {len(playeritems_dict)} players | page {page}/{math.ceil((len(playeritems_dict) / qty_per_page))}')
                        self.embed_list.append(embed)
                        embed = discord.Embed(title=":star2: Paid Boosts by Player", color=self.client.color)
                        page += 1

                # if it is "boosts by player @" or embed_list of length 1
                if len(self.embed_list) <= 1:
                    await loading_msg.edit(content='', embed=embed)
                # else we need a paginator
                else:
                    view = paginatorView.paginatorView(self.embed_list)
                    view.message = await loading_msg.edit(content='', embed=self.embed_list[0], view=view)
            except Exception as e:
                await ctx.send(f'There was an unexpected error. Error log for Dev: ```{traceback.format_exc()}```')



        elif ("item" in categorize_by.lower() or "mount" in categorize_by.lower()):
            embed = discord.Embed(title=":star2: Paid Boosts by Item", color=self.client.color, description="\u200b")
            count_fields = 0
            self.embed_list = []
            qty_per_page = 8
            page = 1
            count_items = 0

            for item_name, sales_list in document["Sales"].items():
                count_buyers = 1
                info = ''
                last_buyer_number = len(sales_list)
                for object_sale in sales_list:
                    try:
                        user = await commands.UserConverter().convert(ctx, str(object_sale["buyerid"]))
                        info += f'{count_buyers}. {user.mention} - '
                    except:
                        info += f'{count_buyers}. **{object_sale["discordTag"]}** - '
                    isPaid = object_sale["isPaid"]
                    info += f'{object_sale["Price"]:,}g {"✅ paid" if isPaid else "❌ not paid"} - {object_sale["Booster"]}\n'

                    if count_buyers == last_buyer_number:
                        info += "\u200b"
                    count_buyers += 1
                embed.add_field(name=item_name.title(), value=info, inline=False)
                count_fields += 1
                count_items += 1

                # create pages (embeds) for paginator
                if count_fields >= len(document["Sales"]):
                    embed.set_footer(text=f'Viewing {(page-1)*qty_per_page+1}-{count_items} of {len(document["Sales"])} items | page {page}/{math.ceil(len(document["Sales"]) / qty_per_page)}')
                    self.embed_list.append(embed)
                    page += 1
                elif count_fields % 8 == 0:
                    embed.set_footer(text=f'Viewing {(page-1)*qty_per_page+1}-{count_items} of {len(document["Sales"])} items | page {page}/{math.ceil(len(document["Sales"]) / qty_per_page)}')
                    self.embed_list.append(embed)
                    embed = discord.Embed(title=":star2: Paid Boosts by Item", color=self.client.color, description="\u200b")
                    page += 1

            if len(self.embed_list) == 1:
                await loading_msg.edit(content='', embed=self.embed_list[0])
            # else we need a paginator
            else:
                view = paginatorView.paginatorView(self.embed_list)
                view.message = await loading_msg.edit(content='', embed=self.embed_list[0], view=view)



        else:
            await loading_msg.edit(content=f'**{categorize_by}** is an invalid type of categorization. You can categorize by ***player*** or by ***item***')





async def setup(client):
    await client.add_cog(Boosts(client))
    print('Boost cog is loaded')
