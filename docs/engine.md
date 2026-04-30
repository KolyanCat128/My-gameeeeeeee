# Engine Architecture

## Overview

The INFINITUM engine is composed of four independently-testable subsystems
that work together to deliver a seamless infinite sandbox experience.

```
┌─────────────────────────────────────────────────────────────────┐
│                        INFINITUM ENGINE                         │
│                                                                 │
│  ┌───────────────────┐    ┌────────────────────────────────┐   │
│  │  Procedural World │    │       Physics World            │   │
│  │  Generator        │    │                                │   │
│  │  - PerlinNoise    │    │  - Rigid Body Dynamics         │   │
│  │  - BiomeSelector  │    │  - Fluid Simulation (SPH)      │   │
│  │  - ChunkData      │    │  - Thermal Propagation         │   │
│  │  - GalacticGen    │    │  - Destruction System          │   │
│  └────────┬──────────┘    └────────────┬───────────────────┘   │
│           │                             │                        │
│  ┌────────▼──────────────────────────  ▼───────────────────┐   │
│  │               Voxel World State                          │   │
│  │  - Modified blocks cache                                 │   │
│  │  - Time of day                                           │   │
│  │  - Active physics bodies                                 │   │
│  └────────────────────────┬─────────────────────────────── ┘   │
│                            │                                     │
│  ┌─────────────────────────▼──────────────────────────────┐    │
│  │               NPC Society                               │    │
│  │  - Individual LSTM brain per NPC                        │    │
│  │  - Episodic memory                                      │    │
│  │  - Faction & social graph                               │    │
│  │  - Online learning (policy gradient)                    │    │
│  └─────────────────────────────────────────────────────── ┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Chunk System

The world is divided into **16×16×16 voxel chunks**.
Chunks are generated on demand and cached in memory.

```python
chunk = world_gen.get_chunk(cx, cy, cz)   # returns ChunkData
block = chunk.get_block(lx, ly, lz)       # BlockType enum
```

## Multi-Scale Architecture

| Scale | System | Details |
|-------|--------|---------|
| Nanometers | Custom physics | Quantum simulation (placeholder) |
| Millimeters–meters | Voxel engine | 16×16×16 chunks |
| Kilometers | World generator | Continent-level noise |
| Planetary | Biome system | Climate model |
| Solar system | GalacticGenerator | Star + planet generation |
| Galactic | GalacticGenerator | Star density maps |

## Physics Constants

Each world or region carries a `WorldPhysicsLaws` object that overrides
the default constants:

```python
laws = WorldPhysicsLaws(
    gravity=1.62,        # Moon gravity
    air_resistance=0.0,  # Vacuum
    time_scale=0.5,      # Slow motion
)
gen = WorldGenerator(seed=42, physics=laws)
```

## Performance Notes

- Chunks are lazily generated and cached (LRU in production builds)
- Physics uses fixed timestep (0.05s) with a max of 20 bodies per frame
  for the Python prototype (production: GPU-accelerated via UE5 Chaos)
- NPC brains are batched on GPU (CUDA) in production mode
