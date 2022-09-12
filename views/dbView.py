from discord.ext import commands
import discord


class dbView(discord.ui.View):
    def __init__(self, embed_dict):
        super().__init__()
        categories = [*embed_dict]  # list of dict keys
        for category in categories:
            self.add_item(dbButton(embed=embed_dict[category] ,label=category))

    # Grey out on timeout
    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)




class dbButton(discord.ui.Button['dbButton']):
    def __init__(self, embed, label):
        super().__init__(style=discord.ButtonStyle.secondary, label=label)
        self.embed = embed

    # This function is called whenever this particular button is pressed
    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        await interaction.response.edit_message(embed=self.embed, view=self.view)