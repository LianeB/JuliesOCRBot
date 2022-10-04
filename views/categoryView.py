import discord
from views import itemSelectView
import traceback

class categoryView(discord.ui.View):
    def __init__(self, document, client):
        super().__init__()
        del document['_id']
        del document['name']
        self.document = document
        self.client = client
        categories = [*document]  # list of dict keys
        select_options = []
        for category in categories:
            select_options.append(discord.SelectOption(label=category))
        self.add_item(categorySelect(options=select_options))


    # Grey out on timeout
    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)



class categorySelect(discord.ui.Select['categorySelect']):
    def __init__(self, options):
        super().__init__(options=options, placeholder="Select categories", min_values=1, max_values=5)

    # This function is called whenever a select is done
    async def callback(self, interaction: discord.Interaction):
        try:
            item_list = []
            for category in self.values:
                item_object = self.view.document[category]
                item_list.extend([*item_object]) # list of dict keys
            sorted_list = sorted(item_list)

            itemView = itemSelectView.itemSelectView(options=sorted_list, document=self.view.document, client=self.view.client)
            itemView.message = await interaction.response.send_message("What item(s) do you want to make invisible?", view=itemView)
        except:
            await interaction.channel.send(f'There was an unexpected error. Error log for Dev: ```{traceback.format_exc()}```')





