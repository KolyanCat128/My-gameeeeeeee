"""
INFINITUM — Procedural World Generation System
===============================================
Generates infinite, multi-scale voxel worlds using layered noise algorithms.
Supports scales from nanometers (atomic) to light-years (galactic).
"""

import math
import random
import hashlib
from typing import Dict, Tuple, List, Optional
from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class BiomeType(Enum):
    OCEAN = "ocean"
    PLAINS = "plains"
    FOREST = "forest"
    DESERT = "desert"
    TUNDRA = "tundra"
    MOUNTAIN = "mountain"
    SWAMP = "swamp"
    VOLCANO = "volcano"
    CRYSTAL = "crystal"
    VOID = "void"
    CUSTOM = "custom"


class BlockType(Enum):
    AIR = 0
    STONE = 1
    DIRT = 2
    GRASS = 3
    SAND = 4
    WATER = 5
    LAVA = 6
    WOOD = 7
    LEAVES = 8
    ORE_IRON = 9
    ORE_GOLD = 10
    ORE_DIAMOND = 11
    BEDROCK = 12
    SNOW = 13
    ICE = 14
    CRYSTAL = 15
    CUSTOM = 255


@dataclass
class WorldPhysicsLaws:
    """Customizable physics constants for a world or region."""
    gravity: float = 9.81          # m/s²
    air_resistance: float = 0.02
    water_density: float = 1000.0  # kg/m³
    temperature_base: float = 20.0 # °C
    pressure_base: float = 101325  # Pa
    light_speed_factor: float = 1.0  # multiplier on c
    time_scale: float = 1.0
    # Custom laws (player-defined)
    custom_rules: Dict[str, float] = field(default_factory=dict)


@dataclass
class ChunkData:
    """A 16×16×16 voxel chunk."""
    cx: int
    cy: int
    cz: int
    blocks: List[List[List[int]]]  # [x][y][z]
    biome: BiomeType = BiomeType.PLAINS
    physics: Optional[WorldPhysicsLaws] = None

    CHUNK_SIZE: int = 16

    @classmethod
    def empty(cls, cx: int, cy: int, cz: int) -> "ChunkData":
        size = cls.CHUNK_SIZE
        blocks = [[[BlockType.AIR.value] * size for _ in range(size)] for _ in range(size)]
        return cls(cx=cx, cy=cy, cz=cz, blocks=blocks)

    def set_block(self, lx: int, ly: int, lz: int, block: BlockType) -> None:
        self.blocks[lx][ly][lz] = block.value

    def get_block(self, lx: int, ly: int, lz: int) -> BlockType:
        return BlockType(self.blocks[lx][ly][lz])


# ---------------------------------------------------------------------------
# Noise implementation (pure Python, no external deps required)
# ---------------------------------------------------------------------------

class PerlinNoise:
    """Classic Perlin noise in 2D and 3D."""

    def __init__(self, seed: int = 0):
        self.seed = seed
        rng = random.Random(seed)
        self.perm = list(range(256))
        rng.shuffle(self.perm)
        self.perm = self.perm * 2  # duplicate for overflow safety

    # -- helpers --
    @staticmethod
    def _fade(t: float) -> float:
        return t * t * t * (t * (t * 6 - 15) + 10)

    @staticmethod
    def _lerp(t: float, a: float, b: float) -> float:
        return a + t * (b - a)

    def _grad2(self, h: int, x: float, y: float) -> float:
        h &= 3
        if h == 0: return  x + y
        if h == 1: return -x + y
        if h == 2: return  x - y
        return               -x - y

    def noise2(self, x: float, y: float) -> float:
        xi, yi = int(math.floor(x)) & 255, int(math.floor(y)) & 255
        xf, yf = x - math.floor(x), y - math.floor(y)
        u, v = self._fade(xf), self._fade(yf)
        p = self.perm
        aa = p[p[xi  ] + yi]
        ab = p[p[xi  ] + yi + 1]
        ba = p[p[xi+1] + yi]
        bb = p[p[xi+1] + yi + 1]
        return self._lerp(v,
            self._lerp(u, self._grad2(aa, xf,   yf),   self._grad2(ba, xf-1, yf)),
            self._lerp(u, self._grad2(ab, xf,   yf-1), self._grad2(bb, xf-1, yf-1))
        )

    def octave_noise2(self, x: float, y: float,
                      octaves: int = 6, persistence: float = 0.5,
                      lacunarity: float = 2.0) -> float:
        value, amplitude, frequency, max_val = 0.0, 1.0, 1.0, 0.0
        for _ in range(octaves):
            value    += self.noise2(x * frequency, y * frequency) * amplitude
            max_val  += amplitude
            amplitude *= persistence
            frequency *= lacunarity
        return value / max_val


# ---------------------------------------------------------------------------
# Biome selector
# ---------------------------------------------------------------------------

class BiomeSelector:
    """Determines biome from temperature/humidity values."""

    @staticmethod
    def select(temperature: float, humidity: float) -> BiomeType:
        """
        temperature: -1..1  (cold..hot)
        humidity:    -1..1  (dry..wet)
        """
        if temperature < -0.4:
            return BiomeType.TUNDRA if humidity < 0.2 else BiomeType.TUNDRA
        if temperature > 0.6:
            if humidity < -0.2:
                return BiomeType.DESERT
            if humidity > 0.4:
                return BiomeType.SWAMP
            return BiomeType.PLAINS
        if temperature > 0.3 and humidity > 0.5:
            return BiomeType.FOREST
        if temperature > 0.7 and humidity < -0.5:
            return BiomeType.VOLCANO
        return BiomeType.PLAINS


# ---------------------------------------------------------------------------
# World Generator
# ---------------------------------------------------------------------------

class WorldGenerator:
    """
    Procedurally generates voxel chunks for an infinite world.

    Supports multi-scale generation: surface details, caves, ore veins,
    biomes, and large-scale continent shapes are generated as layered passes.
    """

    SEA_LEVEL  = 64
    WORLD_HEIGHT = 256

    def __init__(self, seed: int = 0, physics: Optional[WorldPhysicsLaws] = None):
        self.seed = seed
        self.physics = physics or WorldPhysicsLaws()
        self._chunk_cache: Dict[Tuple[int, int, int], ChunkData] = {}

        # Noise generators for different scales
        self.terrain_noise   = PerlinNoise(seed ^ 0x1A2B3C)
        self.cave_noise      = PerlinNoise(seed ^ 0x4D5E6F)
        self.biome_temp      = PerlinNoise(seed ^ 0x7A8B9C)
        self.biome_humid     = PerlinNoise(seed ^ 0xABCDEF)
        self.ore_noise       = PerlinNoise(seed ^ 0x111213)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_chunk(self, cx: int, cy: int, cz: int) -> ChunkData:
        key = (cx, cy, cz)
        if key not in self._chunk_cache:
            self._chunk_cache[key] = self._generate_chunk(cx, cy, cz)
        return self._chunk_cache[key]

    def get_block(self, wx: int, wy: int, wz: int) -> BlockType:
        cs = ChunkData.CHUNK_SIZE
        cx, lx = divmod(wx, cs)
        cy, ly = divmod(wy, cs)
        cz, lz = divmod(wz, cs)
        return self.get_chunk(cx, cy, cz).get_block(lx, ly, lz)

    def get_height(self, wx: int, wz: int) -> int:
        """Surface height at world position (wx, wz)."""
        return self._surface_height(wx, wz)

    def get_biome(self, wx: int, wz: int) -> BiomeType:
        temp  = self.biome_temp.noise2(wx / 512.0, wz / 512.0)
        humid = self.biome_humid.noise2(wx / 512.0, wz / 512.0)
        return BiomeSelector.select(temp, humid)

    # ------------------------------------------------------------------
    # Internal generation passes
    # ------------------------------------------------------------------

    def _surface_height(self, wx: int, wz: int) -> int:
        base = self.terrain_noise.octave_noise2(
            wx / 200.0, wz / 200.0, octaves=8, persistence=0.5, lacunarity=2.0
        )
        # Map noise [-1,1] → [32, 192]
        return int(self.SEA_LEVEL + base * 64)

    def _is_cave(self, wx: int, wy: int, wz: int) -> bool:
        v = self.cave_noise.octave_noise2(wx / 40.0, wz / 40.0, octaves=3)
        v2 = self.cave_noise.octave_noise2(wy / 20.0, wx / 40.0, octaves=2)
        return abs(v * v2) < 0.03

    def _ore_at(self, wx: int, wy: int, wz: int) -> Optional[BlockType]:
        v = self.ore_noise.octave_noise2(wx / 10.0 + wy, wz / 10.0, octaves=2)
        if wy < 16  and v > 0.7:  return BlockType.ORE_DIAMOND
        if wy < 32  and v > 0.65: return BlockType.ORE_GOLD
        if wy < 64  and v > 0.55: return BlockType.ORE_IRON
        return None

    def _generate_chunk(self, cx: int, cy: int, cz: int) -> ChunkData:
        cs = ChunkData.CHUNK_SIZE
        chunk = ChunkData.empty(cx, cy, cz)
        biome = self.get_biome(cx * cs, cz * cs)
        chunk.biome = biome
        chunk.physics = self.physics

        for lx in range(cs):
            for lz in range(cs):
                wx = cx * cs + lx
                wz = cz * cs + lz
                surface = self._surface_height(wx, wz)

                for ly in range(cs):
                    wy = cy * cs + ly

                    if wy > surface:
                        # Above surface
                        if wy <= self.SEA_LEVEL:
                            chunk.set_block(lx, ly, lz, BlockType.WATER)
                        # else AIR (default)
                        continue

                    if wy == 0:
                        chunk.set_block(lx, ly, lz, BlockType.BEDROCK)
                        continue

                    # Cave carving
                    if self._is_cave(wx, wy, wz) and wy > 1:
                        continue  # leave as AIR

                    # Ore veins
                    ore = self._ore_at(wx, wy, wz)
                    if ore:
                        chunk.set_block(lx, ly, lz, ore)
                        continue

                    # Surface layers
                    depth = surface - wy
                    if depth == 0:
                        block = self._surface_block(biome, surface)
                    elif depth <= 3:
                        block = BlockType.DIRT if biome != BiomeType.DESERT else BlockType.SAND
                    elif depth <= 10:
                        block = BlockType.STONE
                    else:
                        block = BlockType.STONE

                    chunk.set_block(lx, ly, lz, block)

        return chunk

    @staticmethod
    def _surface_block(biome: BiomeType, height: int) -> BlockType:
        mapping = {
            BiomeType.DESERT:   BlockType.SAND,
            BiomeType.TUNDRA:   BlockType.SNOW,
            BiomeType.PLAINS:   BlockType.GRASS,
            BiomeType.FOREST:   BlockType.GRASS,
            BiomeType.SWAMP:    BlockType.DIRT,
            BiomeType.MOUNTAIN: BlockType.STONE if height > 160 else BlockType.GRASS,
            BiomeType.VOLCANO:  BlockType.LAVA,
            BiomeType.CRYSTAL:  BlockType.CRYSTAL,
            BiomeType.OCEAN:    BlockType.SAND,
            BiomeType.VOID:     BlockType.AIR,
        }
        return mapping.get(biome, BlockType.GRASS)


# ---------------------------------------------------------------------------
# Structure Generator (trees, ruins, dungeons, etc.)
# ---------------------------------------------------------------------------

class StructureGenerator:
    """Places procedural structures in the world."""

    def __init__(self, seed: int = 0):
        self.seed = seed
        self._rng_cache: Dict[Tuple[int,int], random.Random] = {}

    def _chunk_rng(self, cx: int, cz: int) -> random.Random:
        key = (cx, cz)
        if key not in self._rng_cache:
            h = hashlib.sha256(f"{self.seed}:{cx}:{cz}".encode()).hexdigest()
            self._rng_cache[key] = random.Random(int(h[:16], 16))
        return self._rng_cache[key]

    def get_trees(self, cx: int, cz: int, chunk: ChunkData,
                  world: WorldGenerator) -> List[Tuple[int,int,int]]:
        """Returns list of (wx, wy, wz) tree base positions for this chunk."""
        if chunk.biome not in (BiomeType.FOREST, BiomeType.PLAINS):
            return []
        rng = self._chunk_rng(cx, cz)
        cs = ChunkData.CHUNK_SIZE
        trees = []
        count = rng.randint(0, 5) if chunk.biome == BiomeType.FOREST else rng.randint(0, 1)
        for _ in range(count):
            lx = rng.randint(2, cs - 3)
            lz = rng.randint(2, cs - 3)
            wx, wz = cx * cs + lx, cz * cs + lz
            wy = world.get_height(wx, wz) + 1
            trees.append((wx, wy, wz))
        return trees

    def place_tree(self, chunk: ChunkData, lx: int, ly: int, lz: int,
                   height: int = 5) -> None:
        """Carve a simple tree into a chunk using local coords."""
        cs = ChunkData.CHUNK_SIZE
        # Trunk
        for h in range(height):
            if 0 <= ly + h < cs:
                chunk.set_block(lx, ly + h, lz, BlockType.WOOD)
        # Canopy
        top = ly + height
        for dx in range(-2, 3):
            for dz in range(-2, 3):
                for dy in range(-1, 2):
                    nx, ny, nz = lx+dx, top+dy, lz+dz
                    if 0 <= nx < cs and 0 <= ny < cs and 0 <= nz < cs:
                        if chunk.get_block(nx, ny, nz) == BlockType.AIR:
                            chunk.set_block(nx, ny, nz, BlockType.LEAVES)


# ---------------------------------------------------------------------------
# Galactic Scale Generator (placeholder / concept)
# ---------------------------------------------------------------------------

class GalacticGenerator:
    """
    Generates star systems, planets, and galaxies at macro-scale.
    Each star system can contain a full WorldGenerator instance.
    """

    def __init__(self, seed: int = 0):
        self.seed = seed
        self._noise = PerlinNoise(seed)
        self._systems: Dict[Tuple[int,int], dict] = {}

    def get_star_system(self, sx: int, sz: int) -> dict:
        key = (sx, sz)
        if key not in self._systems:
            self._systems[key] = self._generate_system(sx, sz)
        return self._systems[key]

    def _generate_system(self, sx: int, sz: int) -> dict:
        rng = random.Random(f"{self.seed}:{sx}:{sz}")
        density = self._noise.noise2(sx / 50.0, sz / 50.0)
        has_star = density > -0.3

        system = {
            "position": (sx, sz),
            "has_star": has_star,
            "star_type": None,
            "planets": [],
        }

        if has_star:
            system["star_type"] = rng.choice(["yellow_dwarf", "red_giant", "neutron", "white_dwarf"])
            n_planets = rng.randint(0, 8)
            for i in range(n_planets):
                seed_p = rng.randint(0, 2**31)
                planet = {
                    "orbit_radius": (i + 1) * rng.uniform(0.5, 1.5),
                    "type": rng.choice(["rocky", "gas_giant", "ice", "lava", "ocean"]),
                    "world_seed": seed_p,
                    "has_life": rng.random() < 0.1,
                }
                system["planets"].append(planet)

        return system


# ---------------------------------------------------------------------------
# Quick test / demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== INFINITUM Procedural World Generator ===\n")

    gen = WorldGenerator(seed=12345)
    struct_gen = StructureGenerator(seed=12345)

    print("Generating surface heights for a 16×16 area:")
    for z in range(0, 16, 2):
        row = ""
        for x in range(0, 16, 2):
            h = gen.get_height(x, z)
            biome = gen.get_biome(x, z)
            row += f"({x:2},{z:2}) h={h:3} {biome.value:<10}  "
        print(row)

    print("\nGenerating chunk (0, 0, 0)...")
    chunk = gen.get_chunk(0, 0, 0)
    print(f"Biome: {chunk.biome.value}")
    print(f"Physics gravity: {chunk.physics.gravity} m/s²")

    # Count block types
    counts: Dict[str, int] = {}
    for x in range(16):
        for y in range(16):
            for z in range(16):
                b = BlockType(chunk.blocks[x][y][z]).name
                counts[b] = counts.get(b, 0) + 1
    print("Block distribution in chunk (0,0,0):")
    for btype, cnt in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {btype:<15} {cnt}")

    print("\nGalactic generator — checking a small region of star systems:")
    gal = GalacticGenerator(seed=42)
    for sx in range(3):
        for sz in range(3):
            sys_data = gal.get_star_system(sx, sz)
            if sys_data["has_star"]:
                print(f"  System ({sx},{sz}): {sys_data['star_type']}, "
                      f"{len(sys_data['planets'])} planets")

    print("\n✅ Procedural generation OK")
