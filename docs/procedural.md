# Procedural Generation

## Overview

INFINITUM uses a multi-layer noise stack to generate infinite, deterministic worlds.
The same seed always produces the same terrain, ensuring world sharing works correctly.

## Noise Stack

```
Layer 1: Continental shape     (lacunarity=2.0, 3 octaves, scale=1000)
Layer 2: Regional terrain      (lacunarity=2.0, 6 octaves, scale=200)
Layer 3: Detail bumps          (lacunarity=2.0, 4 octaves, scale=40)
Layer 4: Cave mask             (3D noise, scale=40)
Layer 5: Ore veins             (2D noise per ore type, scale=10)
Layer 6: Biome temperature     (smooth noise, scale=512)
Layer 7: Biome humidity        (smooth noise, scale=512)
```

## Biome Matrix

|            | Dry       | Normal     | Wet      |
|------------|-----------|------------|----------|
| **Cold**   | Tundra    | Tundra     | Tundra   |
| **Mild**   | Plains    | Plains     | Forest   |
| **Warm**   | Desert    | Plains     | Swamp    |
| **Hot**    | Desert    | Volcano    | Swamp    |

## World Height Mapping

```
surface_height = SEA_LEVEL + octave_noise(x/200, z/200) * 64
```

Where `SEA_LEVEL = 64` and `WORLD_HEIGHT = 256`.

## Underground

| Depth | Contents |
|-------|---------|
| Surface | Biome-appropriate surface block |
| 1–3 below | Dirt / Sand |
| 3–10 below | Stone |
| 10–32 below | Stone + Iron ore veins |
| 32–64 below | Stone + Gold ore veins |
| 64–256 below | Stone + Diamond ore veins |
| y=0 | Bedrock |
| y>surface, y≤sea | Water |

## Structure Generation

Structures are placed deterministically per chunk using a seeded RNG derived
from the world seed + chunk coordinates. This ensures structures never move
between sessions.

## Galactic Scale

The `GalacticGenerator` places star systems on a 2D galactic grid:
- Star density follows a Perlin noise function (centre of galaxy is denser)
- Each inhabited system has 0–8 planets with randomised types
- Planets with `has_life=True` get a fully-functional WorldGenerator instance
- Travel between systems is handled by a separate warp/portal system
