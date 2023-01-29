import discord
import json
from discord.ext import commands


def has_wowhoes_role():
    def predicate(ctx):

        # must be in guild
        if ctx.channel.type == discord.ChannelType.private:
            raise commands.NoPrivateMessage()
        wowhoes_role = discord.utils.get(ctx.guild.roles, id=1019350994867470336) # id for "Wow hoes" role
        common_ids = set([role.id for role in ctx.author.roles]) & {wowhoes_role.id}

        if len(common_ids) == 0:
            raise commands.MissingAnyRole([wowhoes_role.id])
        else:
            return True
    return commands.check(predicate)