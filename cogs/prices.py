from datetime import datetime
import io
import json
import discord
from discord.ext import commands
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


with open("./config.json") as f: configData = json.load(f)

# Development or Production
inDev = configData["inDev"]

class Prices(commands.Cog, name='Prices'):

    # Description of this cog (cog.__doc__)
    """OCR cog description"""

    def __init__(self, client):
        self.client = client

    @commands.command()
    async def plot(self, ctx, days=30):
        '''
        Get the OSRS GE price for an item.
        Argument "days" is optional, default is 30.
        '''

        embed = discord.Embed(title="Prices", color=self.client.color, description="Blabla")


        #datetimes = [datetime(2020, 5, 17), datetime(2020, 5, 24), datetime(2020, 6, 1), datetime(2020, 6, 19),
        #             datetime(2020, 6, 30), datetime(2020, 7, 24), datetime(2020, 8, 1), datetime(2020, 8, 17)]
        prices = [100000, 200000, 150000, 125000, 110000, 400000, 222000, 119000]

        '''
        if days <= 60:
            loc = mdates.WeekdayLocator()
        else:
            loc = mdates.MonthLocator()

        formatter = mdates.DateFormatter('%d %b')

        plt.style.use('dark_background')

        fig, ax = plt.subplots()

        dates = mdates.date2num(datetimes)
        plt.plot_date(dates, prices, color='#47a0ff', linestyle='-', ydate=False, xdate=True)

        ax.xaxis.set_major_locator(loc)
        ax.xaxis.set_major_formatter(formatter)

        ax.yaxis.grid()

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)

        locs, _ = plt.yticks()
        ylabels = []
        for l in locs:
            lab = str(int(l)).replace('000000000', '000M').replace('00000000', '00M').replace('0000000', '0M').replace(
                '000000', 'M').replace('00000', '00K').replace('0000', '0K').replace('000', 'K')
            if not ('K' in lab or 'M' in lab):
                lab = "{:,}".format(int(lab))
            ylabels.append(lab)
        plt.yticks(locs, ylabels)
        '''

        plt.style.use('dark_background')
        fig, ax = plt.subplots()
        plt.figure()
        a = [1, 2, 5, 6, 9, 11, 15, 17, 18]
        plt.hlines(1, 1, 20)  # Draw a horizontal line
        plt.xlim(0, 21)
        plt.ylim(0.5, 1.5)
        plt.eventplot(a, orientation='horizontal', colors='#47a0ff', linelengths=0.05)
        plt.axis('off')


        #plt.tight_layout()
        #plt.show()
        plt.savefig('./images/graph.png', transparent=True, bbox_inches='tight', pad_inches=None)
        plt.close(fig)

        image = discord.File('./images/graph.png', filename='graph.png')
        embed.set_image(url=f'attachment://graph.png')

        await ctx.send(file=image, embed=embed)


async def setup(client):
    await client.add_cog(Prices(client))
    print('Prices cog is loaded')