# 🌌 INFINITUM — The Boundless Sandbox Universe

> **The most ambitious sandbox game ever conceived** — blending the best of Minecraft, Roblox, Garry's Mod, Steam Workshop, and People Playground, scaled to cosmic proportions.

---

## 🎮 Overview

**INFINITUM** is an open-ended sandbox game and platform where players can create, explore, and shape everything — from subatomic particles to entire galaxies. Every rule of physics, every law of nature, and every aspect of reality can be customized, scripted, and shared.

---

## 🏗️ Architecture

```
INFINITUM/
├── launcher/           # Cross-platform game launcher (Python/tkinter)
├── engine/
│   ├── voxel/          # Voxel world engine (multi-scale)
│   ├── procedural/     # Procedural world generation
│   ├── physics/        # Custom physics simulation
│   └── npc_ai/         # Neural network-driven NPC system
├── server/             # Multiplayer server infrastructure
├── client/             # Game client entry point
├── docs/               # Architecture & developer documentation
└── assets/             # Sprites, sounds, shaders
```

---

## ✨ Key Features

### 🌍 Infinite Procedural Worlds
- Multi-scale voxel worlds from **atomic (nanometers)** to **galactic (light-years)** scale
- Noise-based procedural terrain generation (Perlin + Simplex + Voronoi)
- Dynamic biome system with customizable physics per region
- Player-defined world laws (gravity, thermodynamics, electromagnetism)

### 🤖 AI-Driven NPCs
- Each NPC has an **individual neural network** (custom LSTM-based architecture)
- NPCs learn from player interactions and adapt their behaviour
- Social structures: NPCs form factions, build relationships, develop goals
- GPU-accelerated inference (CUDA/Metal)

### ⚙️ Physics Simulation
- Rigid body dynamics, fluid simulation, soft body physics
- Temperature, pressure, and material state changes
- Destruction simulation (Chaos-inspired)
- Customizable physics constants per world/region

### 🛠️ Content Workshop
- In-game scripting with **LuaScript** (Roblox-style) and **Python bindings**
- Asset marketplace: upload, sell, buy mods/objects/worlds
- Version-controlled content packages
- Hot-reload modding support

### 🌐 Multiplayer Infrastructure
- WebSocket-based real-time multiplayer
- Horizontal scaling with Redis pub/sub
- Region-sharded world servers
- Player-hosted private servers

### 🚀 Game Launcher
- Modern cross-platform launcher with game/mod management
- Automatic updates, server browser, workshop integration
- User account management and social features

---

## 🚀 Quick Start

### Prerequisites
```bash
pip install pygame numpy scipy noise pillow requests websockets
```

### Run the Launcher
```bash
python launcher/launcher.py
```

### Run the Game Directly
```bash
python client/main.py
```

### Run a Local Server
```bash
python server/server.py --port 8765 --world-seed 42
```

---

## 🔧 Development Stack

| Component | Technology |
|-----------|-----------|
| Game Engine | Python + Pygame (prototype) → UE5 (production) |
| Physics | Custom NumPy/SciPy + Bullet Physics |
| NPC AI | Custom LSTM Neural Networks (NumPy) |
| Procedural Gen | Perlin Noise + Voronoi + Fractal algorithms |
| Multiplayer | WebSockets (asyncio) + Redis |
| Launcher | Python + tkinter |
| Production Target | Unreal Engine 5 (Nanite + Lumen + Chaos) |

---

## 📁 Module Documentation

- [Engine Architecture](docs/engine.md)
- [NPC AI System](docs/npc_ai.md)
- [Procedural Generation](docs/procedural.md)
- [Physics System](docs/physics.md)
- [Multiplayer & Networking](docs/networking.md)
- [Content Workshop](docs/workshop.md)
- [Launcher](docs/launcher.md)

---

## 📜 License

MIT License — Build anything, share everything.