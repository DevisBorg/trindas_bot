# main.py
import asyncio, uvicorn, os, json
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from contextlib import asynccontextmanager
from requests_oauthlib import OAuth2Session
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel

from discord_bot import bot
from music_cog import MusicCog
from help_cog import HelpCog
from config import DISCORD_TOKEN, OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET, SERVER_IP

API_BASE_URL = 'https://discord.com/api/v10'
AUTHORIZATION_BASE_URL = 'https://discord.com/api/oauth2/authorize'
TOKEN_URL = 'https://discord.com/api/oauth2/token'
REDIRECT_URI = f'http://{SERVER_IP}:8000/callback' 

class ConnectionManager:
    def __init__(self): self.active_connections: dict[int, set[WebSocket]] = {}
    async def connect(self, websocket: WebSocket, guild_id: int): await websocket.accept(); self.active_connections.setdefault(guild_id, set()).add(websocket)
    def disconnect(self, websocket: WebSocket, guild_id: int):
        if guild_id in self.active_connections: self.active_connections[guild_id].remove(websocket)
    async def broadcast(self, guild_id: int, message: dict):
        if guild_id in self.active_connections:
            for connection in self.active_connections[guild_id]: await connection.send_json(message)

manager = ConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Carregando Cogs e iniciando o bot..."); bot.manager = manager
    await bot.add_cog(MusicCog(bot)); await bot.add_cog(HelpCog(bot))
    asyncio.create_task(bot.start(DISCORD_TOKEN))
    yield
    print("Desligando..."); await bot.close()

app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=os.urandom(24), max_age=2592000)
app.mount("/static", StaticFiles(directory="static"), name="static")

class PlayPayload(BaseModel): query: str
class MoveSongPayload(BaseModel): old_index: int; new_index: int
class IndexPayload(BaseModel): index: int
class VolumePayload(BaseModel): volume: int

@app.get("/login")
async def login():
    scope = ["identify", "guilds"]; discord_session = OAuth2Session(OAUTH2_CLIENT_ID, redirect_uri=REDIRECT_URI, scope=scope)
    authorization_url, state = discord_session.authorization_url(AUTHORIZATION_BASE_URL)
    return RedirectResponse(authorization_url)

@app.get("/callback")
async def callback(request: Request):
    try:
        discord_session = OAuth2Session(OAUTH2_CLIENT_ID, redirect_uri=REDIRECT_URI)
        loop = asyncio.get_event_loop()
        token = await loop.run_in_executor(None, lambda: discord_session.fetch_token(TOKEN_URL, authorization_response=str(request.url), client_secret=OAUTH2_CLIENT_SECRET))
        request.session['oauth2_token'] = token
        user_response = discord_session.get(f'{API_BASE_URL}/users/@me')
        if user_response.ok: request.session['user_id'] = user_response.json()['id']
        return RedirectResponse("/")
    except Exception as e: print(f"ERRO CALLBACK: {e}"); raise HTTPException(status_code=500, detail="Erro na autenticação.")

async def get_validated_member(request: Request, guild_id: int, check_voice=True):
    token = request.session.get('oauth2_token')
    if not token: raise HTTPException(status_code=401, detail="Não autenticado")
    user_id = request.session.get('user_id')
    if not user_id: raise HTTPException(status_code=403, detail="Sessão de usuário inválida.")
    guild = bot.get_guild(guild_id)
    if not guild: raise HTTPException(status_code=404, detail="Bot não está neste servidor.")
    member = guild.get_member(int(user_id))
    if check_voice and (not member or not member.voice or not member.voice.channel):
        raise HTTPException(status_code=403, detail="Você não está conectado a um canal de voz.")
    return member

@app.get("/api/me")
async def get_current_user(request: Request):
    token = request.session.get('oauth2_token')
    if not token: raise HTTPException(status_code=401, detail="Não autenticado")
    discord_session = OAuth2Session(OAUTH2_CLIENT_ID, token=token)
    user_data = discord_session.get(f'{API_BASE_URL}/users/@me').json()
    guilds_data = discord_session.get(f'{API_BASE_URL}/users/@me/guilds').json()
    bot_guild_ids = {g.id for g in bot.guilds}
    admin_guilds = [{"id": str(g['id']), "name": g['name']} for g in guilds_data if (int(g['permissions']) & 0x8) == 0x8 and int(g['id']) in bot_guild_ids]
    return {"user": user_data, "guilds": admin_guilds}

@app.get("/api/guilds/{guild_id}/queue")
async def get_guild_queue(guild_id: int):
    music_cog = bot.get_cog("Música");
    if not music_cog: raise HTTPException(status_code=500, detail="Music Cog não carregado.")
    return music_cog.get_queue_data(guild_id)

@app.post("/api/guilds/{guild_id}/control/{action}")
async def player_control(request: Request, guild_id: int, action: str):
    await get_validated_member(request, guild_id)
    music_cog = bot.get_cog("Música")
    actions = { "pause-resume": music_cog.pause_resume_from_web, "skip": music_cog.skip_from_web, "previous": music_cog.previous_from_web, "shuffle": music_cog.shuffle_from_web, "toggle-loop": music_cog.toggle_loop_from_web, "leave": music_cog.cleanup }
    if action not in actions: raise HTTPException(status_code=400, detail="Ação inválida")
    result = await actions[action](bot.get_guild(guild_id)) if action == "leave" else await actions[action](guild_id)
    return {"status": "success", "action": action, "result": result}

@app.post("/api/guilds/{guild_id}/play")
async def play_song(request: Request, guild_id: int, payload: PlayPayload):
    member = await get_validated_member(request, guild_id)
    music_cog = bot.get_cog("Música")
    await music_cog.play_from_web(guild=bot.get_guild(guild_id), member=member, query=payload.query)
    return {"status": "success", "action": "play_request_sent"}

@app.post("/api/guilds/{guild_id}/volume")
async def set_volume(request: Request, guild_id: int, payload: VolumePayload):
    await get_validated_member(request, guild_id); music_cog = bot.get_cog("Música")
    await music_cog.set_volume_from_web(guild_id, payload.volume)
    return {"status": "success", "action": "volume_set"}

@app.post("/api/guilds/{guild_id}/queue/move")
async def move_song_in_queue(request: Request, guild_id: int, payload: MoveSongPayload):
    await get_validated_member(request, guild_id, check_voice=False)
    music_cog = bot.get_cog("Música")
    if not await music_cog.move_song(guild_id, payload.old_index, payload.new_index):
        raise HTTPException(status_code=400, detail="Índices inválidos.")
    return {"status": "success", "action": "move"}

@app.post("/api/guilds/{guild_id}/skipto")
async def skipto_song(request: Request, guild_id: int, payload: IndexPayload):
    await get_validated_member(request, guild_id)
    music_cog = bot.get_cog("Música"); await music_cog.skipto_from_web(guild_id, payload.index)
    return {"status": "success", "action": "skipto"}

@app.post("/api/guilds/{guild_id}/remove")
async def remove_song(request: Request, guild_id: int, payload: IndexPayload):
    await get_validated_member(request, guild_id, check_voice=False) 
    music_cog = bot.get_cog("Música"); await music_cog.remove_from_web(guild_id, payload.index)
    return {"status": "success", "action": "remove"}

@app.websocket("/ws/{guild_id}")
async def websocket_endpoint(websocket: WebSocket, guild_id: int):
    await manager.connect(websocket, guild_id)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect: manager.disconnect(websocket, guild_id)

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)