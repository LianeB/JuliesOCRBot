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

'''
    @commands.command()
    async def paginator(self, ctx, paginationList, loading_msg: discord.Message):
        current = 0
        await loading_msg.edit(
            content = '',
            embed = paginationList[current],
            components = [
                [
                    Button(
                        label = "Prev",
                        id = "back",
                        style = ButtonStyle.red
                    ),
                    Button(
                        label = f"Page {current + 1}/{len(paginationList)}",
                        id = "cur",
                        style = ButtonStyle.grey,
                        disabled = True
                    ),
                    Button(
                        label = "Next",
                        id = "front",
                        style = ButtonStyle.red
                    )
                ]
            ]
        )
'''

async def setup(client):
    await client.add_cog(Utils(client))
    print('Utils cog is loaded')


# IMPORTANT NOTE
# Pass 'self' in every function
# To get 'client', you must use self.client