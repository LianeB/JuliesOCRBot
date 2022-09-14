from discord.ext import commands

import discord

# Define a simple View that gives us a confirmation menu
class ConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None
        self.timeout = 60


    # Grey out on timeout
    async def on_timeout(self) -> None:
        await self.disable_buttons()


    async def disable_buttons(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)


    # When the confirm button is pressed, set the inner value to `True` and
    # stop the View from listening to more input.
    # We also send the user an ephemeral message that we're confirming their choice.
    @discord.ui.button(label='Delete', style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message('Deleting...')
        self.value = True
        self.stop()
        await self.disable_buttons()

    # This one is similar to the confirmation button except sets the inner value to `False`
    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message('Operation cancelled.')
        self.value = False
        self.stop()
        await self.disable_buttons()