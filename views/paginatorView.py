import discord


class paginatorView(discord.ui.View):
    def __init__(self, embed_list):
        super().__init__()
        self.embed_list = embed_list
        self.current = 0
        self.add_item(previousBtn())
        self.add_item(currentPageBtn(label="Page 1"))
        self.add_item(nextBtn())

    # Grey out on timeout
    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)




class previousBtn(discord.ui.Button['previousBtn']):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.blurple, emoji=discord.PartialEmoji(name='◀')) #'⏪'))

    # This function is called whenever this particular button is pressed
    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        index = self.view.current
        index -= 1
        # If its out of index, go to end
        if index < 0:
            index = len(self.view.embed_list) - 1
        self.view.current = index
        # children[1] = 2nd button = the current page button
        self.view.children[1].label = f"Page {index+1}"  # +1 because idx starts at 0
        await interaction.response.edit_message(embed=self.view.embed_list[index], view=self.view)




class currentPageBtn(discord.ui.Button['currentPageBtn']):
    def __init__(self, label):
        super().__init__(style=discord.ButtonStyle.grey, label=label, disabled=True)




class nextBtn(discord.ui.Button['nextBtn']):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.blurple, emoji=discord.PartialEmoji(name='▶')) #'⏩'))

    # This function is called whenever this particular button is pressed
    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        index = self.view.current
        index += 1
        # If its out of index, go back to start
        if index == len(self.view.embed_list):
            index = 0
        self.view.current = index

        # children[1] = 2nd button = the current page button
        self.view.children[1].label = f"Page {index+1}"  # +1 because idx starts at 0
        await interaction.response.edit_message(embed=self.view.embed_list[index], view=self.view)

