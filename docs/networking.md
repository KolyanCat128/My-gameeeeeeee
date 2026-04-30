# Networking & Multiplayer

## Protocol

INFINITUM uses **WebSockets** (JSON messages) for real-time communication.

### Message Types (Client → Server)

| Type | Fields | Description |
|------|--------|-------------|
| `register` | username, password | Create account |
| `login` | username, password | Authenticate |
| `move` | x, y, z | Update player position |
| `place_block` | wx, wy, wz, block | Place a block |
| `chat` | text | Send chat message |
| `request_chunk` | cx, cz | Request chunk data |
| `ping` | — | Keep-alive |
| `server_info` | — | Query server status |

### Message Types (Server → Client)

| Type | Description |
|------|-------------|
| `registered` | Account created, returns token |
| `logged_in` | Authenticated, returns player_id + token |
| `world_state` | Current world snapshot for new players |
| `player_joined` | Another player joined |
| `player_left` | Player disconnected |
| `player_moved` | Player position update |
| `block_update` | A block was placed/removed |
| `chat` | Chat message broadcast |
| `chunk_data` | Chunk block data |
| `pong` | Ping response with server time |
| `error` | Error message |

## Starting a Server

```bash
python server/server.py --host 0.0.0.0 --port 8765 --world-seed 42
```

## Scaling Architecture (Production)

```
                    ┌─────────────┐
                    │  Load       │
                    │  Balancer   │
                    └──────┬──────┘
            ┌──────────────┼──────────────┐
            │              │              │
     ┌──────▼──────┐ ┌─────▼─────┐ ┌─────▼─────┐
     │  Game Shard │ │ Game Shard│ │ Game Shard│
     │  (Region A) │ │ (Region B)│ │ (Region C)│
     └──────┬──────┘ └─────┬─────┘ └─────┬─────┘
            └──────────────┼──────────────┘
                    ┌──────▼──────┐
                    │    Redis    │
                    │  Pub/Sub    │
                    │  (Events)   │
                    └──────┬──────┘
                    ┌──────▼──────┐
                    │  Database   │
                    │  (Players,  │
                    │   Worlds)   │
                    └─────────────┘
```

- Each **Game Shard** handles one world region (e.g., 4096×4096 blocks)
- Cross-shard events are routed via **Redis Pub/Sub**
- Player positions near shard boundaries trigger seamless handoff
- World data is persisted to a distributed key-value store (RocksDB cluster)
- Target: **10,000+ concurrent players per shard**, millions globally

## Authentication

Token-based auth (HMAC-SHA256). Tokens expire after 24 hours.
Two-factor authentication available for accounts with purchases.

## Anti-Cheat

- All authoritative calculations run **server-side**
- Client sends intents (move direction, block placement) — server validates
- Position is checked against physics simulation on the server
- Rate limiting prevents block-spam attacks
