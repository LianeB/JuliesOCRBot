import discord
from discord.ext import commands
#from discord_components import DiscordComponents, Button, ButtonStyle, InteractionType


class Utils(commands.Cog, name='Utils'):

    # Description of this cog (cog.__doc__)
    """Example cog description"""

    def __init__(self, client):
        self.client = client


    @commands.Cog.listener()
    async def on_ready(self):
        pass


def translate_price(price):
    '''translate k or M to int. Throws error if incorrect format'''
    if price.endswith('k') or price.endswith('K'):
        price = price[:-1]  # remove last char (the k)
        price = float(price.replace(',', '.')) * 1000
    elif price.endswith('m') or price.endswith('M'):
        price = price[:-1]  # remove last char (the M)
        price = float(price.replace(',', '.')) * 1000000
    else:
        price = float(price.replace(',', ''))
    price = int(price)
    return price


async def setup(client):
    await client.add_cog(Utils(client))
    print('Utils cog is loaded')


# IMPORTANT NOTE
# Pass 'self' in every function
# To get 'client', you must use self.client