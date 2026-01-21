# help_cog.py
import discord
from discord.ext import commands

class HelpCog(commands.Cog, name="Ajuda"):
    """Mostra informações sobre os comandos."""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='help', aliases=['ajuda', 'comandos'])
    async def help(self, ctx, *, command_name: str = None):
        """Mostra a lista de comandos ou detalhes de um comando específico."""
        prefix = ctx.prefix
        if command_name is None:
            embed = discord.Embed(
                title="🤖 Central de Ajuda do Bot 🤖",
                description=f"Use `{prefix}help <comando>` para ver mais detalhes.",
                color=discord.Color.blue()
            )
            for cog_name, cog in self.bot.cogs.items():
                commands_list = [f"`{c.name}`" for c in cog.get_commands() if not c.hidden]
                if commands_list:
                    embed.add_field(name=f"Categoria: {cog_name}", value=", ".join(commands_list), inline=False)
            await ctx.send(embed=embed)
        else:
            command = self.bot.get_command(command_name.lower())
            if command is None or command.hidden:
                return await ctx.send(f"Comando `{command_name}` não encontrado.")
            
            embed = discord.Embed(title=f"Ajuda: `{command.name}`", description=command.help or "Sem descrição disponível.", color=discord.Color.green())
            if command.aliases: embed.add_field(name="Apelidos", value=", ".join(f"`{a}`" for a in command.aliases), inline=False)
            signature = f"{prefix}{command.name} {command.signature}"
            embed.add_field(name="Como Usar", value=f"`{signature}`", inline=False)
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))