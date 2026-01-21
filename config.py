# config.py
import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env para o ambiente
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OAUTH2_CLIENT_ID = os.getenv("OAUTH2_CLIENT_ID")
OAUTH2_CLIENT_SECRET = os.getenv("OAUTH2_CLIENT_SECRET")
BOT_PREFIX = "!"
SERVER_IP = os.getenv("SERVER_IP", "127.0.0.1") # Usa 127.0.0.1 como padrão se não for definido
