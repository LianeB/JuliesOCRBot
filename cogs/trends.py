import datetime
import io
import json
import traceback
import discord
import matplotlib.pyplot as plt
from statistics import mean, median
from discord.ext import commands
from views import dbView, confirmView, categoryView
from cogs import utils
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.colors import ListedColormap, BoundaryNorm
with open("./config.json") as f: configData = json.load(f)



class TrendsCog(commands.Cog, name='Trends Cog'):
    # Description of this cog (cog.__doc__)
    """OCR cog description"""

    def __init__(self, client):
        self.client = client


    @commands.command(aliases=['trend'])
    async def trends(self, ctx, server):
        """Test plotting of trends"""

        document = self.client.BMAH_coll.find_one({"name": "prices"})
        del document["name"]
        del document["_id"]

        # Create embed
        embed = discord.Embed(title=server.title(), color=self.client.color)
        embed.set_author(name="Trends", icon_url=ctx.guild.icon.url)

        # Create dict with all median prices -- {Mage : {Frostfire Circlet: 12555, Frostfire Shoulderpads: 17800, ...}, ...}
        median_prices = {}
        for category_name, items_obj in document.items():
            median_prices[category_name] = {}
            for item_name, price_list in items_obj.items():
                if price_list:
                    median_prices[category_name][item_name] = int(median(self.get_price(price_list)))

        # Get prices
        dict_of_under = {} # Format : {1: 100, 2: 50, 3: 66, 4: 75...} --> {counter (total) : ratio}
        total_items = 0
        qty_under = 0 #qty of items that were under the median
        for category_name, items_obj in document.items():
            for item_name, price_list in items_obj.items():
                for price_str in price_list:
                    if server.lower() in self.get_server(price_str).lower():
                        total_items += 1
                        price = self.get_price(price_str)
                        if price <= median_prices[category_name][item_name]:
                            qty_under += 1
                        dict_of_under[total_items] = round(qty_under / total_items * 100, 1)

        dataX = list(dict_of_under.keys())[3:]
        dataY = list(dict_of_under.values())[3:]



        file = self.create_plot(dataX, dataY)
        # image = discord.File('./images/graph.png', filename='graph.png')
        embed.set_image(url=f'attachment://graph.png')
        await ctx.send(file=file, embed=embed)



    def create_plot(self, dataX, dataY):
        # PLOTTING ----------------------------------------
        plt.style.use('dark_background')

        # Size/ratio of plot
        fig, ax = plt.subplots()#figsize=(1, 1), dpi=500)

        # Draw horizontal line
        plt.axhline(y=50, color='#4d5657', linewidth=0.4, linestyle='--', label='50%')  # [y, xmin, xmax]

        # Set limits
        #plt.xlim(min(data)-1000, max(data)+1000)
        plt.ylim(0, 100)

        # Set labels
        plt.xlabel("Records")
        plt.ylabel("% Under")

        # Colors
        # select how to color
        cmap = ListedColormap(['blue', 'lawngreen'])
        norm = BoundaryNorm([0, 50, 100], cmap.N)

        # get segments
        xy = np.array([dataX, dataY]).T.reshape(-1, 1, 2)
        segments = np.hstack([xy[:-1], xy[1:]])

        # make line collection
        lc = LineCollection(segments, cmap=cmap, norm=norm)
        lc.set_array(dataY)
        ax.add_collection(lc)

        # Create plot
        plt.plot(dataX, dataY)

        # Show legend
        plt.legend(frameon=False)

        # Save figure
        arr = io.BytesIO()
        plt.savefig(arr, transparent=True, bbox_inches='tight', pad_inches=None)
        plt.close(fig)

        # Create discord File
        arr.seek(0)
        file = discord.File(arr, filename='graph.png')

        return file





    @commands.command()
    async def listtest(self, ctx, without=None):
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




    # Code changes
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
            categories = ''
            items = ''
            servers = ''
            count = 0
            last_category = list(ordered_dict)[-1]
            for category, item_dict in ordered_dict.items():
                category_name = emoji_dict[f'{category}'] + " " + category
                categories += f'{category_name}\n'
                last_item = list(item_dict)[-1]
                for item, amount in item_dict.items():
                    # if ;listservers
                    if withServers:
                        for server, item_list in serverDocument.items():
                            for item_fromServerDoc in item_list:
                                if item.lower() in item_fromServerDoc.lower():
                                    items += f'🡢 {item} __*({server.capitalize()})*__\n'
                    else:
                        items += f'{item} {"("+ str(amount) +")" if amount > 1 else ""}\n'
                        categories += '\u200b\n'
                    if item == last_item:
                        items += "\u200b"

                if count % 3 == 0:
                    categories = ''
                    items = ''
                    servers = ''
                    print(categories)
                    print(items)
                    embed.add_field(name='Category', value=categories, inline=True)
                    embed.add_field(name='Items', value=items, inline=True)
                    embed.add_field(name="\u200b", value="\u200b")
                elif category == last_category:
                    embed.add_field(name='Category', value=categories, inline=True)
                    embed.add_field(name='Items', value=items, inline=True)
                    embed.add_field(name="\u200b", value="\u200b")
                count += 1

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
                categories = ''
                items = ''
                servers = ''
                count = 0
                last_category = list(ordered_dict)[-1]
                for category, item_dict in dict_a_part.items():
                    for item, amount in item_dict.items():
                        # if ;listservers
                        if withServers:
                            for server, item_list in serverDocument.items():
                                for item_fromServerDoc in item_list:
                                    if item.lower() in item_fromServerDoc.lower():
                                        items += f'🡢 {item} __*({server.capitalize()})*__\n'
                        else:
                            items += f'{item} {"(" + str(amount) + ")" if amount > 1 else ""}\n'
                            categories += '\u200b\n'

                    if count % 3 == 0:
                        categories = ''
                        items = ''
                        servers = ''
                        embed.add_field(name='Category', value=categories, inline=True)
                        embed.add_field(name='Items', value=items, inline=True)
                        embed.add_field(name="\u200b", value="\u200b")
                    elif category == last_category:
                        embed.add_field(name='Category', value=categories, inline=True)
                        embed.add_field(name='Items', value=items, inline=True)
                        embed.add_field(name="\u200b", value="\u200b")
                    count += 1

            # skip fields if fields not a multiple of 3
            #if (len(dict_a_part)+1) % 3 == 0:
            #    # on finit avec 2 fields, donc en ajouter un vide
            #    embed.add_field(name="\u200b", value="\u200b")
            #elif (len(dict_a_part)+2) % 3 == 0:
            #    # on finit avec 1 field, donc en ajouter 2 vides
            #    embed.add_field(name="\u200b", value="\u200b")
            #    embed.add_field(name="\u200b", value="\u200b")

            #await ctx.message.delete()
            await channel.send(embed=embed)
        except:
            await channel.send(f'There was an error. Error log for Dev: ```{traceback.format_exc()}```')


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


async def setup(client):
    await client.add_cog(TrendsCog(client))
    print('Trends cog is loaded')

