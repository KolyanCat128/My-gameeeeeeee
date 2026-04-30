"""
INFINITUM — Game Client (Main Entry Point)
==========================================
Pygame-based game prototype demonstrating:
  - Procedural voxel world rendering (2D top-down view)
  - NPC AI agents moving in the world
  - Physics interaction
  - HUD with player stats and world info
  - Basic crafting / building system
  - Creative and survival modes

Controls:
  WASD / Arrow Keys — Move
  E                 — Interact / open inventory
  F                 — Toggle flight
  B                 — Build mode
  T                 — Talk to nearby NPC
  ESC               — Menu
  Mouse click       — Place / remove blocks
  Scroll wheel      — Block selector
"""

import sys
import os
import math
import random
import time
from typing import Tuple

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import pygame
    from pygame import Surface, Rect
    _HAS_PYGAME = True
except ImportError:
    _HAS_PYGAME = False
    print("[WARNING] pygame not installed — running in headless/demo mode")

from engine.procedural.world_generator import (
    WorldGenerator, WorldPhysicsLaws, BlockType, BiomeType, ChunkData
)
from engine.npc_ai.npc_brain import NPCSociety, NPCAction
from engine.physics.physics_world import PhysicsWorld, Vec3


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCREEN_W, SCREEN_H = 1280, 720
TILE_SIZE = 32          # pixels per block (top-down view)
VIEW_RANGE_X = SCREEN_W // TILE_SIZE + 2
VIEW_RANGE_Z = SCREEN_H // TILE_SIZE + 2
FPS_TARGET = 60

GAME_TITLE = "INFINITUM — The Boundless Sandbox Universe"

# Colour palette
COLOURS = {
    BlockType.AIR:         (135, 206, 235),   # sky blue
    BlockType.STONE:       ( 80,  80,  80),
    BlockType.DIRT:        (101,  67,  33),
    BlockType.GRASS:       ( 34, 139,  34),
    BlockType.SAND:        (210, 180, 140),
    BlockType.WATER:       ( 64, 164, 223),
    BlockType.LAVA:        (207,  60,   0),
    BlockType.WOOD:        (139,  90,  43),
    BlockType.LEAVES:      ( 0,  100,   0),
    BlockType.ORE_IRON:    (160, 100,  80),
    BlockType.ORE_GOLD:    (255, 215,   0),
    BlockType.ORE_DIAMOND: ( 70, 210, 215),
    BlockType.BEDROCK:     ( 30,  30,  30),
    BlockType.SNOW:        (240, 248, 255),
    BlockType.ICE:         (176, 224, 230),
    BlockType.CRYSTAL:     (180, 130, 255),
}


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------

class Player:
    SPEED = 5.0
    FLY_SPEED = 10.0

    def __init__(self, x: float = 0.0, z: float = 0.0):
        self.x = x
        self.z = z
        self.y = 70.0       # height
        self.vy = 0.0       # vertical velocity
        self.health = 100.0
        self.max_health = 100.0
        self.hunger = 0.0
        self.stamina = 100.0
        self.flying = False
        self.inventory: dict = {}    # block_type → count
        self.selected_block = BlockType.STONE
        self.mode = "survival"       # "survival" | "creative"
        self.xp = 0
        self.name = "Player"

    def move(self, dx: float, dz: float) -> None:
        speed = self.FLY_SPEED if self.flying else self.SPEED
        self.x += dx * speed
        self.z += dz * speed

    def pick_block(self, block: BlockType, count: int = 1) -> None:
        self.inventory[block] = self.inventory.get(block, 0) + count

    def use_block(self, block: BlockType) -> bool:
        if self.mode == "creative":
            return True
        if self.inventory.get(block, 0) > 0:
            self.inventory[block] -= 1
            if self.inventory[block] == 0:
                del self.inventory[block]
            return True
        return False

    def add_xp(self, amount: int) -> None:
        self.xp += amount


# ---------------------------------------------------------------------------
# World state (combines all engine subsystems)
# ---------------------------------------------------------------------------

class GameWorld:
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.world_gen = WorldGenerator(seed=seed)
        self.physics = PhysicsWorld(gravity=Vec3(0, -9.81, 0))
        self.society = NPCSociety(world_seed=seed)
        self._modified_blocks: dict = {}   # (wx, wy, wz) → BlockType
        self.time_of_day = 0.3             # 0=midnight, 0.5=noon, 1=midnight
        self.tick_count = 0

        # Spawn some NPCs near the origin
        for i in range(8):
            pos = (random.uniform(-30, 30), 0, random.uniform(-30, 30))
            faction = "villagers" if i < 5 else "bandits"
            self.society.spawn_npc(pos, faction=faction)

    def get_surface_block(self, wx: int, wz: int) -> BlockType:
        """Return the top-most non-air block at (wx, wz)."""
        key = (wx, 0, wz)
        if key in self._modified_blocks:
            return self._modified_blocks[key]
        h = self.world_gen.get_height(wx, wz)
        biome = self.world_gen.get_biome(wx, wz)
        return WorldGenerator._surface_block(biome, h)

    def set_block(self, wx: int, wy: int, wz: int, block: BlockType) -> None:
        self.modified_blocks[(wx, wy, wz)] = block

    @property
    def modified_blocks(self):
        return self._modified_blocks

    def tick(self, player_x: float, player_z: float) -> None:
        self.tick_count += 1
        # Advance time of day
        self.time_of_day = (self.time_of_day + 1 / (20 * 60 * 24)) % 1.0
        # Update NPC society
        if self.tick_count % 5 == 0:
            world_state = {
                "time_of_day": self.time_of_day,
                "danger_level": 0.3,
                "food_availability": 0.7,
            }
            self.society.tick((player_x, 0, player_z), world_state)
        # Periodically train NPC brains
        if self.tick_count % 300 == 0:
            self.society.learn_all()


# ---------------------------------------------------------------------------
# HUD Renderer
# ---------------------------------------------------------------------------

def draw_hud(screen: "Surface", player: Player, world: GameWorld, font_small, font_large) -> None:
    sw, sh = SCREEN_W, SCREEN_H

    # Health bar
    bar_w = 200
    pygame.draw.rect(screen, (60, 0, 0),   (20, sh - 50, bar_w, 18))
    filled = int(bar_w * player.health / player.max_health)
    pygame.draw.rect(screen, (220, 40, 40), (20, sh - 50, filled, 18))
    pygame.draw.rect(screen, (255, 255, 255), (20, sh - 50, bar_w, 18), 1)
    txt = font_small.render(f"♥ {int(player.health)}/{int(player.max_health)}", True, (255,255,255))
    screen.blit(txt, (28, sh - 48))

    # Hunger bar
    pygame.draw.rect(screen, (50, 30, 0),  (20, sh - 28, bar_w, 14))
    filled_h = int(bar_w * (100 - player.hunger) / 100)
    pygame.draw.rect(screen, (200, 120, 0), (20, sh - 28, filled_h, 14))
    pygame.draw.rect(screen, (200, 200, 200), (20, sh - 28, bar_w, 14), 1)
    txt = font_small.render(f"🍖 {int(100 - player.hunger)}%", True, (200,200,200))
    screen.blit(txt, (28, sh - 27))

    # XP
    xp_txt = font_small.render(f"XP: {player.xp}", True, (100, 255, 100))
    screen.blit(xp_txt, (sw - 130, sh - 50))

    # Mode badge
    mode_color = (0, 180, 255) if player.mode == "creative" else (255, 140, 0)
    mode_txt = font_small.render(f"[{player.mode.upper()}]", True, mode_color)
    screen.blit(mode_txt, (sw - 130, sh - 28))

    # Flying indicator
    if player.flying:
        fly_txt = font_small.render("✈ FLYING", True, (150, 220, 255))
        screen.blit(fly_txt, (sw // 2 - 40, 12))

    # Selected block
    sel_surf = pygame.Surface((40, 40))
    sel_surf.fill(COLOURS.get(player.selected_block, (128, 128, 128)))
    pygame.draw.rect(sel_surf, (255, 255, 255), (0, 0, 40, 40), 2)
    screen.blit(sel_surf, (sw // 2 - 20, sh - 55))
    sel_txt = font_small.render(player.selected_block.name, True, (255, 255, 255))
    screen.blit(sel_txt, (sw // 2 - sel_txt.get_width() // 2, sh - 12))

    # World info (top-left)
    biome = world.world_gen.get_biome(int(player.x), int(player.z))
    h = world.world_gen.get_height(int(player.x), int(player.z))
    hour = int(world.time_of_day * 24)
    minute = int((world.time_of_day * 24 - hour) * 60)
    info_lines = [
        f"Pos: ({player.x:.1f}, {player.y:.1f}, {player.z:.1f})",
        f"Biome: {biome.value}",
        f"Height: {h}",
        f"Time: {hour:02d}:{minute:02d}",
        f"Seed: {world.seed}",
        f"NPCs: {len(world.society.npcs)}",
        f"Tick: {world.tick_count}",
    ]
    for i, line in enumerate(info_lines):
        t = font_small.render(line, True, (220, 220, 220))
        screen.blit(t, (8, 8 + i * 18))

    # Crosshair
    cx, cy = sw // 2, sh // 2
    pygame.draw.line(screen, (255,255,255), (cx-12, cy), (cx+12, cy), 1)
    pygame.draw.line(screen, (255,255,255), (cx, cy-12), (cx, cy+12), 1)


# ---------------------------------------------------------------------------
# Sky / ambient colour
# ---------------------------------------------------------------------------

def get_sky_colour(time_of_day: float) -> Tuple:
    """Return sky colour based on time of day."""
    from pygame import Color
    if time_of_day < 0.25:   # night → dawn
        t = time_of_day / 0.25
        r = int(10  + t * 100)
        g = int(10  + t * 50)
        b = int(30  + t * 100)
    elif time_of_day < 0.5:  # dawn → noon
        t = (time_of_day - 0.25) / 0.25
        r = int(110 + t * 25)
        g = int(60  + t * 146)
        b = int(130 + t * 95)
    elif time_of_day < 0.75: # noon → dusk
        t = (time_of_day - 0.5) / 0.25
        r = int(135 + t * 60)
        g = int(206 - t * 100)
        b = int(225 - t * 100)
    else:                    # dusk → night
        t = (time_of_day - 0.75) / 0.25
        r = int(195 - t * 185)
        g = int(106 - t * 96)
        b = int(125 - t * 95)
    return (max(0,min(255,r)), max(0,min(255,g)), max(0,min(255,b)))


# ---------------------------------------------------------------------------
# World renderer (2D top-down)
# ---------------------------------------------------------------------------

def render_world(screen: "Surface", world: GameWorld, player: Player) -> None:
    px, pz = int(player.x), int(player.z)
    half_x = VIEW_RANGE_X // 2
    half_z = VIEW_RANGE_Z // 2

    for screen_z in range(VIEW_RANGE_Z):
        for screen_x in range(VIEW_RANGE_X):
            wx = px - half_x + screen_x
            wz = pz - half_z + screen_z

            block = world.get_surface_block(wx, wz)
            colour = COLOURS.get(block, (128, 0, 128))

            # Simple height-based shading
            h = world.world_gen.get_height(wx, wz)
            shade = max(0, min(1.0, (h - 40) / 100.0))
            colour = tuple(int(c * (0.5 + 0.5 * shade)) for c in colour)

            rect = pygame.Rect(
                screen_x * TILE_SIZE,
                screen_z * TILE_SIZE,
                TILE_SIZE, TILE_SIZE,
            )
            pygame.draw.rect(screen, colour, rect)

    # Draw NPCs
    for npc in world.society.npcs.values():
        sx = int((npc.position[0] - px + half_x) * TILE_SIZE + TILE_SIZE // 2)
        sz = int((npc.position[2] - pz + half_z) * TILE_SIZE + TILE_SIZE // 2)
        if 0 <= sx < SCREEN_W and 0 <= sz < SCREEN_H:
            colour = (255, 50, 50) if npc.faction == "bandits" else (50, 200, 50)
            pygame.draw.circle(screen, colour, (sx, sz), 6)
            pygame.draw.circle(screen, (255,255,255), (sx, sz), 6, 1)

    # Draw player (centre of screen)
    cx = (VIEW_RANGE_X // 2) * TILE_SIZE + TILE_SIZE // 2
    cz = (VIEW_RANGE_Z // 2) * TILE_SIZE + TILE_SIZE // 2
    pygame.draw.circle(screen, (0, 120, 255), (cx, cz), 8)
    pygame.draw.circle(screen, (255, 255, 255), (cx, cz), 8, 2)


# ---------------------------------------------------------------------------
# Main game loop
# ---------------------------------------------------------------------------

def run_game(seed: int = 42, headless: bool = False) -> None:
    if not _HAS_PYGAME or headless:
        print("[HEADLESS] Running game simulation without display...")
        _headless_simulation(seed)
        return

    pygame.init()
    pygame.display.set_caption(GAME_TITLE)
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock = pygame.time.Clock()
    font_small = pygame.font.SysFont("monospace", 14)
    font_large = pygame.font.SysFont("monospace", 28, bold=True)

    world = GameWorld(seed=seed)
    player = Player(x=0.0, z=0.0)
    player.y = float(world.world_gen.get_height(0, 0) + 2)

    # Selectable blocks
    placeable_blocks = [
        BlockType.STONE, BlockType.DIRT, BlockType.GRASS, BlockType.SAND,
        BlockType.WOOD, BlockType.LEAVES, BlockType.WATER, BlockType.LAVA,
        BlockType.ICE, BlockType.CRYSTAL,
    ]
    selected_idx = 0
    player.selected_block = placeable_blocks[selected_idx]

    running = True
    show_menu = False
    last_time = time.time()

    while running:
        now = time.time()
        dt = now - last_time
        last_time = now

        # --- Events ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    show_menu = not show_menu
                elif event.key == pygame.K_f:
                    player.flying = not player.flying
                elif event.key == pygame.K_m:
                    player.mode = "creative" if player.mode == "survival" else "survival"
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 4:  # scroll up
                    selected_idx = (selected_idx - 1) % len(placeable_blocks)
                    player.selected_block = placeable_blocks[selected_idx]
                elif event.button == 5:  # scroll down
                    selected_idx = (selected_idx + 1) % len(placeable_blocks)
                    player.selected_block = placeable_blocks[selected_idx]
                elif event.button == 1:  # left click — place block
                    mx, my = pygame.mouse.get_pos()
                    wx = int(player.x) + (mx - SCREEN_W // 2) // TILE_SIZE
                    wz = int(player.z) + (my - SCREEN_H // 2) // TILE_SIZE
                    if player.use_block(player.selected_block):
                        world._modified_blocks[(wx, 0, wz)] = player.selected_block
                elif event.button == 3:  # right click — remove block
                    mx, my = pygame.mouse.get_pos()
                    wx = int(player.x) + (mx - SCREEN_W // 2) // TILE_SIZE
                    wz = int(player.z) + (my - SCREEN_H // 2) // TILE_SIZE
                    old = world.get_surface_block(wx, wz)
                    world._modified_blocks[(wx, 0, wz)] = BlockType.AIR
                    if old not in (BlockType.AIR, BlockType.WATER, BlockType.LAVA):
                        player.pick_block(old)
                        player.add_xp(1)

        # --- Movement ---
        keys = pygame.key.get_pressed()
        dx = dz = 0.0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  dx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx += 1
        if keys[pygame.K_w] or keys[pygame.K_UP]:    dz -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  dz += 1
        if dx != 0 or dz != 0:
            length = math.sqrt(dx*dx + dz*dz)
            player.move(dx / length * dt, dz / length * dt)

        # --- World tick ---
        world.tick(player.x, player.z)

        # --- Render ---
        sky = get_sky_colour(world.time_of_day)
        screen.fill(sky)
        render_world(screen, world, player)
        draw_hud(screen, player, world, font_small, font_large)

        # --- Menu overlay ---
        if show_menu:
            _draw_menu(screen, font_large, font_small)

        pygame.display.flip()
        clock.tick(FPS_TARGET)

    pygame.quit()


def _draw_menu(screen: "Surface", font_large, font_small) -> None:
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    screen.blit(overlay, (0, 0))

    lines = [
        ("INFINITUM", font_large, (100, 220, 255)),
        ("", font_small, (200, 200, 200)),
        ("WASD / Arrows  — Move", font_small, (200, 200, 200)),
        ("F              — Toggle flight", font_small, (200, 200, 200)),
        ("M              — Toggle mode", font_small, (200, 200, 200)),
        ("Left click     — Place block", font_small, (200, 200, 200)),
        ("Right click    — Remove block", font_small, (200, 200, 200)),
        ("Scroll wheel   — Select block", font_small, (200, 200, 200)),
        ("ESC            — Open/close menu", font_small, (200, 200, 200)),
    ]
    y = SCREEN_H // 2 - len(lines) * 20
    for text, fnt, colour in lines:
        surf = fnt.render(text, True, colour)
        screen.blit(surf, (SCREEN_W // 2 - surf.get_width() // 2, y))
        y += surf.get_height() + 6


def _headless_simulation(seed: int = 42) -> None:
    """Run a non-display simulation for testing / CI environments."""
    print(f"  Initialising world (seed={seed})...")
    world = GameWorld(seed=seed)
    player_x, player_z = 0.0, 0.0

    print("  Running 120 simulation ticks...")
    for t in range(120):
        player_x += 0.5
        player_z += 0.1
        world.tick(player_x, player_z)

    print(f"  Time of day: {world.time_of_day:.3f}")
    print(f"  NPCs alive:  {len(world.society.npcs)}")
    print(f"  Ticks run:   {world.tick_count}")

    faction_stats = world.society.get_faction_stats()
    for faction, stats in faction_stats.items():
        print(f"  Faction '{faction}': {stats['count']} members, "
              f"avg health={stats['avg_health']:.1f}")

    print("\n  World height samples:")
    for x in range(0, 50, 10):
        h = world.world_gen.get_height(x, x)
        b = world.world_gen.get_biome(x, x)
        print(f"    ({x},{x}): height={h}, biome={b.value}")

    print("\n✅ Headless game simulation complete")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="INFINITUM Game Client")
    parser.add_argument("--seed", type=int, default=42, help="World seed")
    parser.add_argument("--headless", action="store_true", help="Run without display")
    args = parser.parse_args()
    run_game(seed=args.seed, headless=args.headless)
