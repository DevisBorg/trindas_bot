# discord_bot.py
import discord
from discord.ext import commands
import logging
import os 
from config import BOT_PREFIX

LOG_DIR = 'data'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# --- CONFIGURAÇÃO DO LOGGING ---
handler = logging.FileHandler(filename=os.path.join(LOG_DIR, 'discord.log'), encoding='utf-8', mode='w')
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')
handler.setFormatter(formatter)
logging.getLogger('discord').setLevel(logging.INFO)
logging.getLogger('discord').addHandler(handler)

#addição mais agressiva pra logs
# import sys

# # Limpa configurações anteriores
# for handler in logging.root.handlers[:]:
#     logging.root.removeHandler(handler)

# # Configuração que obriga a saída para o terminal (stdout)
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s:%(levelname)s:%(name)s: %(message)s',
#     handlers=[
#         logging.StreamHandler(sys.stdout), # Garante que vai para o journalctl
#         logging.FileHandler(os.path.join(LOG_DIR, 'discord.log'), encoding='utf-8', mode='w')
#     ]
# )

# Debug específico para rastrear o aperto de mão (handshake) da voz
logging.getLogger('discord').setLevel(logging.INFO)
logging.getLogger('discord.voice_client').setLevel(logging.DEBUG)
logging.getLogger('discord.gateway').setLevel(logging.DEBUG)

# --- CONFIGURAÇÃO DO BOT ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents, help_command=None)

# --- EVENTOS E COMANDOS GERAIS DO BOT ---
@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
    logging.getLogger('discord').info(f'Bot conectado como {bot.user}')
    await bot.change_presence(activity=discord.Game(name=f"{BOT_PREFIX}help"))

@bot.command(name='stopbot', hidden=True)
@commands.is_owner()
async def stop_bot(ctx):
    """Para o bot completamente (apenas o dono)."""
    await ctx.send("Ok, desligando...")
    logging.getLogger('discord').info(f"Comando de desligamento executado por {ctx.author}.")
    await bot.close()
