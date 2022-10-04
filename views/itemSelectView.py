import traceback

import discord
from cogs import itemlist

class itemSelectView(discord.ui.View):
    def __init__(self, options, document, client):
        super().__init__()
        self.document = document
        self.client = client
        select_options = []
        for option in options:
            select_options.append(discord.SelectOption(label=option))
        self.add_item(itemSelect(options=select_options))


    # Grey out on timeout
    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)



class itemSelect(discord.ui.Select['itemSelect']):
    def __init__(self, options):
        super().__init__(options=options, placeholder="Select item(s)", min_values=1, max_values=len(options))

    # This function is called whenever a select is done
    async def callback(self, interaction: discord.Interaction):
        try:
            # remove selected items from document
            doc_without_items = self.view.document
            for category, items_object in doc_without_items.copy().items():
                for item, qty in items_object.copy().items():
                    if item in self.values:
                        del items_object[item]
                        if self.view.document[category] == {}:
                            del doc_without_items[category]
            print(doc_without_items)
            await itemlist.ItemList.list_fct(self.view.client.get_cog("Item list"), interaction.guild, interaction.channel, calledWithWithout=True, document=doc_without_items, client=self.view.client)
            await interaction.response.defer()
        except:
            await interaction.channel.send(f'There was an unexpected error. Error log for Dev: ```{traceback.format_exc()}```')

