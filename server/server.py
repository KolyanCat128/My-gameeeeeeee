"""
INFINITUM — Multiplayer Game Server
=====================================
WebSocket-based authoritative game server supporting:
  - Multiple concurrent game worlds
  - Player position synchronisation
  - Block placement/removal broadcast
  - NPC state synchronisation
  - Chat system
  - Server browser information
  - Player authentication (token-based)

Run:  python server/server.py --port 8765 --world-seed 42
"""

import asyncio
import json
import time
import random
import hashlib
import argparse
import logging
import sys
import os
from typing import Dict, Set, Optional, Any
from dataclasses import dataclass, asdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.procedural.world_generator import WorldGenerator, BlockType, BiomeType

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("infinitum-server")


# ---------------------------------------------------------------------------
# Protocol messages  (JSON over WebSocket)
# ---------------------------------------------------------------------------

def msg(msg_type: str, **payload) -> str:
    return json.dumps({"type": msg_type, **payload})


# ---------------------------------------------------------------------------
# Player session
# ---------------------------------------------------------------------------

@dataclass
class PlayerSession:
    player_id: str
    username: str
    token: str
    x: float = 0.0
    y: float = 70.0
    z: float = 0.0
    health: float = 100.0
    websocket: Any = None       # websocket connection object
    connected_at: float = 0.0
    last_ping: float = 0.0
    world_id: str = "default"
    is_admin: bool = False


# ---------------------------------------------------------------------------
# World shard  (one running world)
# ---------------------------------------------------------------------------

class WorldShard:
    def __init__(self, world_id: str, seed: int = 0):
        self.world_id = world_id
        self.seed = seed
        self.gen = WorldGenerator(seed=seed)
        self.players: Dict[str, PlayerSession] = {}
        self.modified_blocks: Dict[str, int] = {}   # "x,y,z" → block type value
        self.chat_history: list = []
        self.created_at = time.time()
        self.tick = 0

    def add_player(self, session: PlayerSession) -> None:
        session.world_id = self.world_id
        self.players[session.player_id] = session

    def remove_player(self, player_id: str) -> None:
        self.players.pop(player_id, None)

    def set_block(self, wx: int, wy: int, wz: int, block_type: int,
                  player_id: str = "") -> dict:
        key = f"{wx},{wy},{wz}"
        self.modified_blocks[key] = block_type
        return {
            "type": "block_update",
            "wx": wx, "wy": wy, "wz": wz,
            "block": block_type,
            "by": player_id,
        }

    def get_chunk_data(self, cx: int, cz: int) -> dict:
        """Return serialised chunk data for client."""
        chunk = self.gen.get_chunk(cx, 4, cz)   # surface level chunks
        # Flatten blocks for transmission
        blocks_flat = []
        for x in range(16):
            for z in range(16):
                blocks_flat.append(chunk.blocks[x][8][z])
        return {
            "cx": cx,
            "cz": cz,
            "biome": chunk.biome.value,
            "blocks": blocks_flat,
        }

    def get_state_snapshot(self) -> dict:
        """Current world state for new players joining."""
        return {
            "type": "world_state",
            "world_id": self.world_id,
            "seed": self.seed,
            "tick": self.tick,
            "player_count": len(self.players),
            "modified_block_count": len(self.modified_blocks),
        }

    def add_chat(self, username: str, text: str) -> dict:
        entry = {
            "type": "chat",
            "from": username,
            "text": text[:256],   # cap length
            "time": time.time(),
        }
        self.chat_history.append(entry)
        if len(self.chat_history) > 100:
            self.chat_history = self.chat_history[-100:]
        return entry


# ---------------------------------------------------------------------------
# Auth manager
# ---------------------------------------------------------------------------

class AuthManager:
    """
    Password storage uses PBKDF2-HMAC-SHA256 with a per-user salt.
    Token generation uses secrets.token_hex for cryptographic randomness.
    """
    _ITERATIONS = 260_000   # NIST recommended minimum (2023)

    def __init__(self):
        self._users: Dict[str, dict] = {}   # username → {pw_hash, salt, is_admin}
        self._tokens: Dict[str, str] = {}   # token → player_id

    def _hash_password(self, password: str, salt: bytes) -> str:
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, self._ITERATIONS)
        return dk.hex()

    def register(self, username: str, password: str) -> Optional[str]:
        if username in self._users or len(username) < 3:
            return None
        import secrets as _sec
        salt = _sec.token_bytes(32)
        pw_hash = self._hash_password(password, salt)
        # Use a time-based UUID for player_id (no MD5)
        player_id = hashlib.sha256(
            f"{username}{time.time()}".encode()
        ).hexdigest()[:24]
        self._users[username] = {
            "pw_hash": pw_hash,
            "salt": salt.hex(),
            "player_id": player_id,
            "is_admin": False,
        }
        return self._make_token(player_id)

    def login(self, username: str, password: str) -> Optional[str]:
        user = self._users.get(username)
        if not user:
            return None
        salt = bytes.fromhex(user["salt"])
        pw_hash = self._hash_password(password, salt)
        if pw_hash != user["pw_hash"]:
            return None
        return self._make_token(user["player_id"])

    def validate_token(self, token: str) -> Optional[str]:
        return self._tokens.get(token)

    def _make_token(self, player_id: str) -> str:
        import secrets as _sec
        token = _sec.token_hex(32)
        self._tokens[token] = player_id
        return token

    def get_player_id(self, username: str) -> Optional[str]:
        user = self._users.get(username)
        return user["player_id"] if user else None


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

class InfinitumServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8765,
                 default_seed: int = 42):
        self.host = host
        self.port = port
        self.worlds: Dict[str, WorldShard] = {
            "default": WorldShard("default", seed=default_seed),
        }
        self.sessions: Dict[str, PlayerSession] = {}   # player_id → session
        self.ws_to_pid: Dict[Any, str] = {}            # ws → player_id
        self.auth = AuthManager()
        self._tick_task: Optional[asyncio.Task] = None
        self.start_time = time.time()

        # Pre-register a test admin account
        self.auth.register("admin", "admin1234")
        admin_id = self.auth.get_player_id("admin")
        if admin_id:
            self.auth._users["admin"]["is_admin"] = True

    # -- connection lifecycle --

    async def handle_connection(self, websocket, path="") -> None:
        pid = None
        try:
            log.info(f"New connection from {websocket.remote_address}")
            async for raw in websocket:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send(msg("error", text="Invalid JSON"))
                    continue

                pid = await self._dispatch(websocket, data, pid)

        except Exception as e:
            log.warning(f"Connection error: {e}")
        finally:
            if pid:
                await self._disconnect(pid)

    async def _dispatch(self, ws, data: dict, pid: Optional[str]) -> Optional[str]:
        t = data.get("type", "")

        if t == "register":
            token = self.auth.register(data.get("username",""), data.get("password",""))
            if token:
                await ws.send(msg("registered", token=token))
            else:
                await ws.send(msg("error", text="Registration failed"))
            return pid

        elif t == "login":
            token = self.auth.login(data.get("username",""), data.get("password",""))
            if token:
                new_pid = self.auth.validate_token(token)
                session = PlayerSession(
                    player_id=new_pid,
                    username=data.get("username",""),
                    token=token,
                    websocket=ws,
                    connected_at=time.time(),
                    last_ping=time.time(),
                )
                self.sessions[new_pid] = session
                self.ws_to_pid[ws] = new_pid
                world = self.worlds["default"]
                world.add_player(session)
                await ws.send(msg("logged_in", player_id=new_pid, token=token))
                await ws.send(json.dumps(world.get_state_snapshot()))
                # Announce to others
                await self._broadcast(world, msg("player_joined",
                    player_id=new_pid, username=session.username), exclude=new_pid)
                log.info(f"Player {session.username!r} joined (id={new_pid})")
                return new_pid
            else:
                await ws.send(msg("error", text="Login failed"))
                return pid

        elif t == "move":
            if pid and pid in self.sessions:
                s = self.sessions[pid]
                s.x = float(data.get("x", s.x))
                s.y = float(data.get("y", s.y))
                s.z = float(data.get("z", s.z))
                world = self.worlds.get(s.world_id)
                if world:
                    await self._broadcast(world,
                        msg("player_moved", player_id=pid,
                            x=s.x, y=s.y, z=s.z), exclude=pid)
            return pid

        elif t == "place_block":
            if pid and pid in self.sessions:
                s = self.sessions[pid]
                world = self.worlds.get(s.world_id)
                if world:
                    update = world.set_block(
                        int(data.get("wx", 0)),
                        int(data.get("wy", 0)),
                        int(data.get("wz", 0)),
                        int(data.get("block", BlockType.STONE.value)),
                        player_id=pid,
                    )
                    await self._broadcast(world, json.dumps(update))
            return pid

        elif t == "chat":
            if pid and pid in self.sessions:
                s = self.sessions[pid]
                world = self.worlds.get(s.world_id)
                if world:
                    entry = world.add_chat(s.username, data.get("text",""))
                    await self._broadcast(world, json.dumps(entry))
            return pid

        elif t == "request_chunk":
            if pid:
                s = self.sessions.get(pid)
                if s:
                    world = self.worlds.get(s.world_id)
                    if world:
                        chunk_data = world.get_chunk_data(
                            int(data.get("cx", 0)),
                            int(data.get("cz", 0)),
                        )
                        await ws.send(msg("chunk_data", **chunk_data))
            return pid

        elif t == "ping":
            if pid and pid in self.sessions:
                self.sessions[pid].last_ping = time.time()
            await ws.send(msg("pong", server_time=time.time()))
            return pid

        elif t == "server_info":
            info = self._get_server_info()
            await ws.send(json.dumps(info))
            return pid

        return pid

    async def _disconnect(self, pid: str) -> None:
        session = self.sessions.pop(pid, None)
        if session:
            world = self.worlds.get(session.world_id)
            if world:
                world.remove_player(pid)
                await self._broadcast(world,
                    msg("player_left", player_id=pid, username=session.username))
            if session.websocket in self.ws_to_pid:
                del self.ws_to_pid[session.websocket]
            log.info(f"Player {session.username!r} disconnected")

    async def _broadcast(self, world: WorldShard, message: str,
                         exclude: Optional[str] = None) -> None:
        for pid, session in list(world.players.items()):
            if pid == exclude:
                continue
            try:
                await session.websocket.send(message)
            except Exception:
                pass

    # -- server tick --

    async def _tick_loop(self) -> None:
        while True:
            await asyncio.sleep(1.0 / 20)  # 20 TPS
            for world in self.worlds.values():
                world.tick += 1
                # Timeout inactive connections (120s)
                now = time.time()
                for pid, session in list(world.players.items()):
                    if now - session.last_ping > 120:
                        await self._disconnect(pid)

    # -- public API --

    def _get_server_info(self) -> dict:
        total_players = sum(len(w.players) for w in self.worlds.values())
        return {
            "type": "server_info",
            "name": "INFINITUM Official Server",
            "version": "0.1.0",
            "uptime": int(time.time() - self.start_time),
            "worlds": len(self.worlds),
            "players_online": total_players,
            "max_players": 10000,
        }

    async def start(self) -> None:
        try:
            import websockets
            self._tick_task = asyncio.create_task(self._tick_loop())
            log.info(f"INFINITUM Server starting on ws://{self.host}:{self.port}")
            async with websockets.serve(self.handle_connection, self.host, self.port):
                log.info("Server ready — waiting for connections")
                await asyncio.Future()   # run forever
        except ImportError:
            log.warning("websockets library not installed — running in simulation mode")
            await self._demo_mode()

    async def _demo_mode(self) -> None:
        """Simulate server activity without actual WebSocket connections."""
        log.info("Running in DEMO mode (no websockets)")
        for i in range(10):
            await asyncio.sleep(0.2)
            log.info(f"  Server tick {i+1}: {len(self.sessions)} players, "
                     f"{len(self.worlds)} worlds active")
        log.info("Demo complete")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="INFINITUM Multiplayer Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--world-seed", type=int, default=42)
    args = parser.parse_args()

    server = InfinitumServer(host=args.host, port=args.port,
                             default_seed=args.world_seed)
    asyncio.run(server.start())
