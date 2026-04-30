# Content Workshop

## Overview

The INFINITUM Workshop lets players create, share, and monetise content.
All content is version-controlled and hot-reloadable.

## Content Types

| Type | Description |
|------|-------------|
| **World** | A saved world with seed + all modifications |
| **Mod** | Python/Lua scripts that extend game behaviour |
| **Block Pack** | Custom block types with textures + physics properties |
| **NPC Pack** | Pre-trained NPC brain + visual appearance |
| **Biome Pack** | New biome definitions with noise parameters |
| **Physics Mod** | Custom WorldPhysicsLaws presets |
| **Scenario** | Pre-built world + NPC + quest combination |

## Creating a Mod

```python
# mods/my_mod.py
from engine.procedural.world_generator import BlockType, WorldPhysicsLaws

class MyMod:
    name = "Anti-Gravity World"
    version = "1.0.0"
    author = "YourName"

    def on_world_create(self, world):
        world.physics.gravity = -5.0   # objects fall upward!
        return world

    def on_player_join(self, player, world):
        player.health = 200.0          # double health
```

## Mod API

- `on_world_create(world)` — called when a world is first created
- `on_player_join(player, world)` — player enters the world
- `on_block_place(player, wx, wy, wz, block)` — block placed
- `on_npc_spawn(npc, world)` — NPC spawned
- `on_tick(world, dt)` — every game tick (use sparingly)

## Marketplace

- Workshop items are listed with a price (free or paid)
- Revenue split: 70% creator / 30% platform
- Items are reviewed for malware before listing
- Rating system (1–5 stars) and comment threads

## Installing Mods

Via the launcher:
1. Open **Workshop** tab
2. Browse / search
3. Click **Install**
4. Restart the game or hot-reload (if supported)

Via CLI:
```bash
python launcher/launcher.py --install <mod_id>
```
