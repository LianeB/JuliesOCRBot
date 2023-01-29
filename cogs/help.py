import discord
from discord.ext import commands

class HelpCog(commands.Cog, name='Help'):

    # Description of this cog (cog.__doc__)
    """Help formatter"""

    def __init__(self, client):
        self.client = client


    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        try:
            # Verifies if the command already has an error message to it (in that case it will not run through this)
            if hasattr(ctx.command, 'on_error'):
                return
            elif isinstance(error, commands.MissingAnyRole):
                # await ctx.send(f'{ctx.author.mention} you don\'t have the role to run this command.')
                return
            else:
                embed = discord.Embed(title=f'Error in {ctx.command}',
                                      description=f'`{self.client.prefix}{ctx.command.qualified_name} {ctx.command.signature}` \n{error}',
                                      color=self.client.color) # can also be discord.Colour.magenta()
        except:
            embed = discord.Embed(title=f'Error',
                                  description=f'`{error}`',
                                  color=self.client.color)
        await ctx.send(embed=embed)

    @commands.command()
    async def help(self, ctx, arg=None):

        # Description of command (command.help)
        """Shows command definition and syntax for commands"""

        # if just the basic help command (with no args)
        if arg is None:
            embed = discord.Embed(color=self.client.color, title="Help")
            scog_info = 'Here are all the possible commands:\n\n'
            for c in self.client.cogs:
                cog = self.client.get_cog(c)
                if cog.qualified_name == 'Help' or cog.qualified_name == 'Utils':
                    continue
                scog_info += f'__**{cog.qualified_name} Module Commands**__\n'
                cog_commands = cog.get_commands()
                for c in cog_commands:
                    if not c.hidden:
                        scog_info += f'**{c.name}** - {c.help}\n'
                scog_info += '\n'
            footer_text = f'\n You can also type {self.client.prefix}help <command name> for info on a specific command\nExample: {self.client.prefix}help save'
            embed.set_footer(text=footer_text)
            embed.description = scog_info

            await ctx.send(embed=embed)

        # Arg present (cog or command)
        else:

            # arg is a cog
            if arg in self.client.cogs:
                embed = discord.Embed(color=self.client.color) # green
                cog = self.client.get_cog(arg)
                scog_info = ''
                cog_commands = cog.get_commands()
                for c in cog_commands:
                    if not c.hidden:
                        scog_info += f'**{c.name}** - {c.help}\n'
                embed.add_field(name=f'__{cog.qualified_name} Module__', value=f'{cog.__doc__}\n\n__**Commands**__\n' + scog_info)

            # arg is a command
            elif self.client.get_command(arg) is not None:
                embed = discord.Embed(color=self.client.color)
                command = self.client.get_command(arg)
                info = f'{command.help}\n\n**Proper Syntax:**\n`{self.client.prefix}{command.qualified_name} {command.signature}`\n'
                for alias in command.aliases:
                    info += f'`{self.client.prefix}{alias} {command.signature}`\n'
                info += '\n'

                embed.add_field(name=f'**{command.name} command**'.upper(),
                                value=info)

            else:
                embed = discord.Embed(color=0x43780) # blue for error
                embed.add_field(name='Error',
                                value=f'{arg} is not a valid cog or command.')

            await ctx.send(embed=embed)


async def setup(client):
    await client.add_cog(HelpCog(client))
    print('Help cog is loaded')