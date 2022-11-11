import traceback

import discord
from cogs import itemlist

class completionView(discord.ui.View):
    def __init__(self, ctx, client, selects):
        super().__init__()
        self.client = client
        self.ctx = ctx
        for select in selects:
            self.add_item(select)


    # Grey out on timeout
    async def on_timeout(self) -> None:
        await self.disable_components()

    async def disable_components(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)


    @discord.ui.button(label='Complete', style=discord.ButtonStyle.green, row=4)
    async def completeButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            values = []
            for item in self.children:
                if isinstance(item, discord.ui.Select):
                    values += item.values
                    for select_str in item.values: # select_str of format "Reins of the Plagued Proto-Drake|Valen#0069"
                        item_name = select_str.split("|", 1)[0]
                        discord_tag = select_str.split("|", 1)[1]
                        await self.client.get_cog('Sales').remove_active_boost(self.ctx, discord_tag, item_name, "completed", withButton=True)

            all_values = "\n".join(values)
            await interaction.response.send_message(f'The following items have been completed:```{all_values}```')
            self.value = True
            self.stop()
            await self.disable_components()
        except:
            print(f'There was an error. Error log for Dev: ```{traceback.format_exc()}```')




class itemSelect(discord.ui.Select['itemSelect']):
    def __init__(self, options, placeholder):
        super().__init__(options=options, placeholder=placeholder, min_values=0, max_values=len(options))

    # This function is called whenever a select is done
    async def callback(self, interaction: discord.Interaction):
        try:
            # remove selected items from document
            await interaction.response.defer()
        except:
            await interaction.channel.send(f'There was an unexpected error. Error log for Dev: ```{traceback.format_exc()}```')

