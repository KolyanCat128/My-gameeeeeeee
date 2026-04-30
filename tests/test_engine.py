"""
INFINITUM — Test Suite
========================
Tests all core engine subsystems without requiring pygame or a GPU.
Run: python -m pytest tests/ -v
  or: python tests/test_engine.py
"""

import sys
import os
import math
import unittest

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.procedural.world_generator import (
    WorldGenerator, WorldPhysicsLaws, BlockType, BiomeType,
    ChunkData, PerlinNoise, BiomeSelector, GalacticGenerator,
    StructureGenerator,
)
from engine.physics.physics_world import (
    PhysicsWorld, Vec3, AABB, RigidBody, Material, MATERIALS,
    CollisionDetector, CollisionResolver, FluidSimulator,
    ThermalSimulator, DestructionSystem,
)
from engine.npc_ai.npc_brain import (
    NPCBrain, NPC, NPCSociety, NPCAction, LSTMCell,
    sigmoid, tanh_act, softmax,
)


# ===========================================================================
# Procedural Generation Tests
# ===========================================================================

class TestPerlinNoise(unittest.TestCase):

    def setUp(self):
        self.noise = PerlinNoise(seed=42)

    def test_noise_in_range(self):
        """Noise values should be between -1 and 1."""
        for x in range(0, 100, 10):
            for z in range(0, 100, 10):
                v = self.noise.noise2(x / 20.0, z / 20.0)
                self.assertGreaterEqual(v, -1.0)
                self.assertLessEqual(v, 1.0)

    def test_octave_noise_deterministic(self):
        """Same seed + coords should produce the same value."""
        n1 = PerlinNoise(seed=99)
        n2 = PerlinNoise(seed=99)
        v1 = n1.octave_noise2(1.23, 4.56)
        v2 = n2.octave_noise2(1.23, 4.56)
        self.assertAlmostEqual(v1, v2, places=6)

    def test_different_seeds_differ(self):
        n1 = PerlinNoise(seed=1)
        n2 = PerlinNoise(seed=2)
        # Accumulate several sample points; with different seeds the totals must differ
        coords = [(0.3, 0.7), (1.1, 2.3), (5.5, 8.9), (0.9, 0.1)]
        s1 = sum(n1.noise2(x, y) for x, y in coords)
        s2 = sum(n2.noise2(x, y) for x, y in coords)
        self.assertNotAlmostEqual(s1, s2, places=2)


class TestBiomeSelector(unittest.TestCase):

    def test_desert_hot_dry(self):
        self.assertEqual(BiomeSelector.select(0.8, -0.5), BiomeType.DESERT)

    def test_tundra_cold(self):
        self.assertEqual(BiomeSelector.select(-0.7, 0.0), BiomeType.TUNDRA)

    def test_plains_default(self):
        result = BiomeSelector.select(0.4, 0.0)
        self.assertIn(result, (BiomeType.PLAINS, BiomeType.FOREST, BiomeType.SWAMP))


class TestWorldGenerator(unittest.TestCase):

    def setUp(self):
        self.gen = WorldGenerator(seed=12345)

    def test_surface_height_in_range(self):
        for x in range(-50, 50, 10):
            for z in range(-50, 50, 10):
                h = self.gen.get_height(x, z)
                self.assertGreater(h, 0)
                self.assertLess(h, WorldGenerator.WORLD_HEIGHT)

    def test_chunk_correct_size(self):
        chunk = self.gen.get_chunk(0, 0, 0)
        self.assertEqual(len(chunk.blocks), ChunkData.CHUNK_SIZE)
        self.assertEqual(len(chunk.blocks[0]), ChunkData.CHUNK_SIZE)
        self.assertEqual(len(chunk.blocks[0][0]), ChunkData.CHUNK_SIZE)

    def test_chunk_has_biome(self):
        chunk = self.gen.get_chunk(0, 0, 0)
        self.assertIsInstance(chunk.biome, BiomeType)

    def test_chunk_cached(self):
        c1 = self.gen.get_chunk(5, 0, 3)
        c2 = self.gen.get_chunk(5, 0, 3)
        self.assertIs(c1, c2)

    def test_bedrock_at_bottom(self):
        # In chunk (0, 0, 0), y=0 should have bedrock somewhere
        chunk = self.gen.get_chunk(0, 0, 0)
        found_bedrock = any(
            chunk.blocks[x][0][z] == BlockType.BEDROCK.value
            for x in range(16)
            for z in range(16)
        )
        self.assertTrue(found_bedrock)

    def test_block_types_valid(self):
        chunk = self.gen.get_chunk(0, 0, 0)
        valid_values = {b.value for b in BlockType}
        for x in range(16):
            for y in range(16):
                for z in range(16):
                    self.assertIn(chunk.blocks[x][y][z], valid_values)

    def test_get_biome_returns_biome_type(self):
        b = self.gen.get_biome(10, 20)
        self.assertIsInstance(b, BiomeType)

    def test_different_seeds_produce_different_terrain(self):
        gen2 = WorldGenerator(seed=99999)
        heights1 = [self.gen.get_height(x, 0) for x in range(10)]
        heights2 = [gen2.get_height(x, 0) for x in range(10)]
        self.assertNotEqual(heights1, heights2)

    def test_physics_laws_attached(self):
        chunk = self.gen.get_chunk(0, 0, 0)
        self.assertIsNotNone(chunk.physics)
        self.assertIsInstance(chunk.physics.gravity, float)

    def test_custom_physics(self):
        custom = WorldPhysicsLaws(gravity=1.62, air_resistance=0.01)  # moon-like
        gen = WorldGenerator(seed=1, physics=custom)
        chunk = gen.get_chunk(0, 0, 0)
        self.assertAlmostEqual(chunk.physics.gravity, 1.62)


class TestGalacticGenerator(unittest.TestCase):

    def setUp(self):
        self.gal = GalacticGenerator(seed=42)

    def test_system_has_expected_keys(self):
        sys_data = self.gal.get_star_system(0, 0)
        self.assertIn("has_star", sys_data)
        self.assertIn("planets", sys_data)
        self.assertIn("position", sys_data)

    def test_planet_count_in_range(self):
        for sx in range(5):
            for sz in range(5):
                sys_data = self.gal.get_star_system(sx, sz)
                if sys_data["has_star"]:
                    self.assertLessEqual(len(sys_data["planets"]), 8)
                    self.assertGreaterEqual(len(sys_data["planets"]), 0)

    def test_cached(self):
        s1 = self.gal.get_star_system(3, 7)
        s2 = self.gal.get_star_system(3, 7)
        self.assertEqual(s1["has_star"], s2["has_star"])
        self.assertEqual(len(s1["planets"]), len(s2["planets"]))


# ===========================================================================
# Physics Tests
# ===========================================================================

class TestVec3(unittest.TestCase):

    def test_add(self):
        v = Vec3(1, 2, 3) + Vec3(4, 5, 6)
        self.assertEqual((v.x, v.y, v.z), (5, 7, 9))

    def test_sub(self):
        v = Vec3(4, 5, 6) - Vec3(1, 2, 3)
        self.assertEqual((v.x, v.y, v.z), (3, 3, 3))

    def test_scale(self):
        v = Vec3(1, 2, 3) * 2
        self.assertEqual((v.x, v.y, v.z), (2, 4, 6))

    def test_length(self):
        v = Vec3(3, 4, 0)
        self.assertAlmostEqual(v.length(), 5.0)

    def test_normalize(self):
        v = Vec3(3, 4, 0).normalize()
        self.assertAlmostEqual(v.length(), 1.0, places=6)

    def test_normalize_zero(self):
        v = Vec3(0, 0, 0).normalize()
        self.assertEqual(v.length(), 0.0)

    def test_dot(self):
        v1, v2 = Vec3(1, 0, 0), Vec3(0, 1, 0)
        self.assertAlmostEqual(v1.dot(v2), 0.0)
        self.assertAlmostEqual(v1.dot(v1), 1.0)

    def test_cross(self):
        v = Vec3(1, 0, 0).cross(Vec3(0, 1, 0))
        self.assertAlmostEqual(v.x, 0)
        self.assertAlmostEqual(v.y, 0)
        self.assertAlmostEqual(v.z, 1)


class TestAABB(unittest.TestCase):

    def test_overlap(self):
        a = AABB(Vec3(0, 0, 0), Vec3(2, 2, 2))
        b = AABB(Vec3(1, 1, 1), Vec3(3, 3, 3))
        self.assertTrue(a.overlaps(b))

    def test_no_overlap(self):
        a = AABB(Vec3(0, 0, 0), Vec3(1, 1, 1))
        b = AABB(Vec3(2, 2, 2), Vec3(3, 3, 3))
        self.assertFalse(a.overlaps(b))

    def test_contains(self):
        box = AABB(Vec3(0, 0, 0), Vec3(4, 4, 4))
        self.assertTrue(box.contains(Vec3(2, 2, 2)))
        self.assertFalse(box.contains(Vec3(5, 2, 2)))


class TestPhysicsWorld(unittest.TestCase):

    def setUp(self):
        self.world = PhysicsWorld(gravity=Vec3(0, -9.81, 0), floor_y=0.0)

    def test_body_falls_under_gravity(self):
        body = self.world.add_body(Vec3(0, 20, 0), mass=1.0)
        for _ in range(100):
            self.world.step(0.05)
        # Should have fallen from y=20
        self.assertLess(body.position.y, 20.0)

    def test_body_lands_on_floor(self):
        body = self.world.add_body(Vec3(0, 5, 0), mass=1.0)
        for _ in range(200):
            self.world.step(0.05)
        # Should be near the floor
        self.assertAlmostEqual(body.position.y, 0.5, delta=1.0)

    def test_static_body_doesnt_move(self):
        body = self.world.add_body(Vec3(0, 5, 0), mass=10.0, is_static=True)
        orig_y = body.position.y
        for _ in range(50):
            self.world.step(0.05)
        self.assertAlmostEqual(body.position.y, orig_y)

    def test_apply_force(self):
        body = self.world.add_body(Vec3(0, 100, 0), mass=1.0)
        body.apply_force(Vec3(10, 0, 0))
        self.world.step(0.1)
        self.assertGreater(body.position.x, 0)

    def test_explosion_moves_bodies(self):
        bodies = []
        for i in range(4):
            b = self.world.add_body(Vec3(float(i * 2), 5, 0), mass=1.0)
            bodies.append(b)
        self.world.apply_explosion(Vec3(4, 5, 0), radius=8.0, force=50.0)
        # At least some bodies should have been pushed away
        moved = sum(1 for b in bodies if abs(b.velocity.x) > 0.1 or abs(b.velocity.y) > 0.1)
        self.assertGreater(moved, 0)

    def test_body_count_after_destruction(self):
        body = self.world.add_body(Vec3(0, 10, 0), mass=5.0, health=20.0,
                                   material="stone")
        frags = DestructionSystem.apply_damage(body, 999, Vec3(0, 10, 0))
        self.assertGreater(len(frags), 0)
        self.assertLessEqual(body.health, 0)

    def test_multiple_bodies(self):
        for i in range(10):
            self.world.add_body(Vec3(float(i), 10, 0), mass=1.0)
        for _ in range(20):
            self.world.step(0.05)
        self.assertEqual(len(self.world.bodies), 10)


class TestFluidSimulator(unittest.TestCase):

    def test_fluid_flows_down(self):
        sim = FluidSimulator(10, 10, gravity=9.81, viscosity=0.5)
        sim.add_fluid(5, 9, density=3.0)
        # Step many times
        for _ in range(30):
            sim.step(0.05)
        # Fluid should have flowed; density at original cell should be lower or spread
        total = sum(sim.get_density(x, y) for x in range(10) for y in range(10))
        self.assertGreater(total, 0)

    def test_solid_blocks_flow(self):
        sim = FluidSimulator(5, 5)
        sim.set_solid(2, 2)
        sim.add_fluid(2, 4, density=1.0)
        for _ in range(10):
            sim.step(0.1)
        # Solid cell should have zero density
        self.assertAlmostEqual(sim.get_density(2, 2), 0.0)


class TestThermalSimulator(unittest.TestCase):

    def test_heat_transfer(self):
        thermal = ThermalSimulator()
        bodies = [
            RigidBody(0, Vec3(0, 0, 0), mass=1.0, material="iron", temperature=200.0),
            RigidBody(1, Vec3(0.5, 0, 0), mass=1.0, material="stone", temperature=20.0),
        ]
        initial_hot = bodies[0].temperature
        initial_cold = bodies[1].temperature
        for _ in range(10):
            thermal.propagate(bodies, 0.1)
        # Hot body should cool, cold body should warm
        self.assertLess(bodies[0].temperature, initial_hot)
        self.assertGreater(bodies[1].temperature, initial_cold)


# ===========================================================================
# NPC AI Tests
# ===========================================================================

class TestActivationFunctions(unittest.TestCase):

    def test_sigmoid_range(self):
        import numpy as np
        x = np.array([-10, -1, 0, 1, 10], dtype=np.float32)
        s = sigmoid(x)
        self.assertTrue((s >= 0).all())
        self.assertTrue((s <= 1).all())

    def test_sigmoid_midpoint(self):
        import numpy as np
        v = sigmoid(np.float32(0))
        self.assertAlmostEqual(float(v), 0.5, places=4)

    def test_softmax_sums_to_one(self):
        import numpy as np
        x = np.array([1.0, 2.0, 3.0, 0.5], dtype=np.float32)
        s = softmax(x)
        self.assertAlmostEqual(float(s.sum()), 1.0, places=5)

    def test_softmax_all_positive(self):
        import numpy as np
        x = np.array([-2.0, 0.0, 2.0], dtype=np.float32)
        s = softmax(x)
        self.assertTrue((s > 0).all())


class TestLSTMCell(unittest.TestCase):

    def setUp(self):
        import numpy as np
        self.cell = LSTMCell(input_size=8, hidden_size=16, seed=42)
        self.x = np.zeros(8, dtype=np.float32)
        self.x[0] = 1.0

    def test_forward_output_shape(self):
        h = self.cell.forward(self.x)
        self.assertEqual(h.shape, (16,))

    def test_forward_changes_state(self):
        import numpy as np
        initial_h = self.cell.h.copy()
        self.cell.forward(self.x)
        self.assertFalse(np.allclose(self.cell.h, initial_h))

    def test_reset_state(self):
        import numpy as np
        self.cell.forward(self.x)
        self.cell.reset_state()
        self.assertTrue(np.allclose(self.cell.h, np.zeros(16)))
        self.assertTrue(np.allclose(self.cell.c, np.zeros(16)))

    def test_backward_returns_correct_shape(self):
        import numpy as np
        self.cell.forward(self.x)
        dh = np.ones(16, dtype=np.float32) * 0.01
        dx = self.cell.backward(dh, lr=0.001)
        self.assertEqual(dx.shape, (8,))


class TestNPCBrain(unittest.TestCase):

    def setUp(self):
        import numpy as np
        self.brain = NPCBrain(npc_id=1, personality_seed=42)
        self.obs = np.zeros(NPCBrain.INPUT_SIZE, dtype=np.float32)

    def test_observe_returns_valid_action(self):
        action = self.brain.observe(self.obs)
        self.assertGreaterEqual(action, 0)
        self.assertLess(action, NPCBrain.OUTPUT_SIZE)

    def test_reward_updates_memory(self):
        self.brain.observe(self.obs)
        self.brain.receive_reward(1.0)
        self.assertEqual(len(self.brain.memory), 1)
        self.assertAlmostEqual(self.brain.memory[0][2], 1.0)

    def test_learn_returns_float(self):
        for _ in range(20):
            self.brain.observe(self.obs)
            self.brain.receive_reward(0.1)
        loss = self.brain.learn(batch_size=16)
        self.assertIsInstance(loss, float)

    def test_epsilon_decays_with_rewards(self):
        initial_eps = self.brain.epsilon
        for _ in range(100):
            self.brain.observe(self.obs)
            self.brain.receive_reward(1.0)
        self.assertLess(self.brain.epsilon, initial_eps)

    def test_memory_capped(self):
        for _ in range(1200):
            self.brain.observe(self.obs)
            self.brain.receive_reward(0.0)
        self.assertLessEqual(len(self.brain.memory), 1000)


class TestNPC(unittest.TestCase):

    def setUp(self):
        self.npc = NPC(npc_id=5, position=(10.0, 0.0, 10.0),
                       name="TestVillager", faction="villagers")

    def test_initial_state(self):
        self.assertEqual(self.npc.health, 100.0)
        self.assertEqual(self.npc.faction, "villagers")
        self.assertGreaterEqual(self.npc.personality.aggression, 0.0)
        self.assertLessEqual(self.npc.personality.aggression, 1.0)

    def test_act_returns_npc_action(self):
        action = self.npc.act([], (0, 0, 0), {"time_of_day": 0.5, "danger_level": 0.0, "food_availability": 0.5})
        self.assertIsInstance(action, NPCAction)

    def test_receive_event_stores_memory(self):
        self.npc.receive_event("player_nearby", 1.0)
        self.assertEqual(len(self.npc.episodic_memory), 1)
        self.assertEqual(self.npc.episodic_memory[0].event_type, "player_nearby")

    def test_update_relation_clamps(self):
        self.npc.update_relation(99, 5.0)   # way above 1
        self.assertLessEqual(self.npc.relations[99], 1.0)
        self.npc.update_relation(99, -5.0)  # way below -1
        self.assertGreaterEqual(self.npc.relations[99], -1.0)

    def test_multiple_acts(self):
        world_state = {"time_of_day": 0.5, "danger_level": 0.0, "food_availability": 0.5}
        for _ in range(20):
            self.npc.act([], (0, 0, 0), world_state)
        self.assertEqual(self.npc.tick, 20)


class TestNPCSociety(unittest.TestCase):

    def setUp(self):
        self.society = NPCSociety(world_seed=42)
        import random as _r
        _r.seed(42)
        for i in range(6):
            self.society.spawn_npc(
                (float(i*5), 0.0, float(i*3)),
                faction="villagers" if i < 4 else "bandits"
            )

    def test_spawn_count(self):
        self.assertEqual(len(self.society.npcs), 6)

    def test_faction_assignment(self):
        stats = self.society.get_faction_stats()
        self.assertIn("villagers", stats)
        self.assertIn("bandits", stats)
        self.assertEqual(stats["villagers"]["count"], 4)
        self.assertEqual(stats["bandits"]["count"], 2)

    def test_tick_returns_actions(self):
        actions = self.society.tick((25.0, 0.0, 15.0),
                                    {"time_of_day": 0.5, "danger_level": 0.0, "food_availability": 0.5})
        self.assertEqual(len(actions), 6)
        for action in actions.values():
            self.assertIsInstance(action, NPCAction)

    def test_learn_all_returns_float(self):
        world_state = {"time_of_day": 0.5, "danger_level": 0.0, "food_availability": 0.5}
        for _ in range(20):
            self.society.tick((0, 0, 0), world_state)
        loss = self.society.learn_all()
        self.assertIsInstance(loss, float)


# ===========================================================================
# Server Tests (no network, unit-level)
# ===========================================================================

class TestWorldShard(unittest.TestCase):

    def setUp(self):
        from server.server import WorldShard
        self.shard = WorldShard("test_world", seed=42)

    def test_initial_state(self):
        self.assertEqual(self.shard.world_id, "test_world")
        self.assertEqual(self.shard.seed, 42)
        self.assertEqual(len(self.shard.players), 0)

    def test_set_block(self):
        update = self.shard.set_block(10, 64, 10, BlockType.STONE.value)
        self.assertEqual(update["type"], "block_update")
        self.assertEqual(update["wx"], 10)
        self.assertIn("10,64,10", self.shard.modified_blocks)

    def test_chunk_data_structure(self):
        data = self.shard.get_chunk_data(0, 0)
        self.assertIn("cx", data)
        self.assertIn("cz", data)
        self.assertIn("biome", data)
        self.assertIn("blocks", data)
        self.assertEqual(len(data["blocks"]), 256)  # 16*16

    def test_add_chat_stores_entry(self):
        entry = self.shard.add_chat("Alice", "Hello world!")
        self.assertEqual(entry["from"], "Alice")
        self.assertEqual(entry["text"], "Hello world!")
        self.assertEqual(len(self.shard.chat_history), 1)

    def test_chat_max_length(self):
        long_msg = "x" * 500
        entry = self.shard.add_chat("Bob", long_msg)
        self.assertLessEqual(len(entry["text"]), 256)


class TestAuthManager(unittest.TestCase):

    def setUp(self):
        from server.server import AuthManager
        self.auth = AuthManager()

    def test_register_and_login(self):
        token = self.auth.register("alice", "password123")
        self.assertIsNotNone(token)
        pid = self.auth.validate_token(token)
        self.assertIsNotNone(pid)

    def test_duplicate_register_fails(self):
        self.auth.register("bob", "pass1")
        token2 = self.auth.register("bob", "pass2")
        self.assertIsNone(token2)

    def test_login_correct(self):
        self.auth.register("charlie", "secret")
        token = self.auth.login("charlie", "secret")
        self.assertIsNotNone(token)

    def test_login_wrong_password(self):
        self.auth.register("dave", "correct")
        token = self.auth.login("dave", "wrong")
        self.assertIsNone(token)

    def test_login_unknown_user(self):
        token = self.auth.login("nobody", "pass")
        self.assertIsNone(token)

    def test_short_username_rejected(self):
        token = self.auth.register("ab", "password")
        self.assertIsNone(token)


# ===========================================================================
# Integration Tests
# ===========================================================================

class TestWorldGeneratorWithPhysics(unittest.TestCase):
    """Integration: physics laws flow from WorldGenerator into chunks."""

    def test_custom_gravity_in_chunk(self):
        laws = WorldPhysicsLaws(gravity=3.72)  # Mars gravity
        gen = WorldGenerator(seed=7, physics=laws)
        chunk = gen.get_chunk(0, 0, 0)
        self.assertAlmostEqual(chunk.physics.gravity, 3.72)

    def test_world_gen_then_npc_spawn(self):
        from engine.npc_ai.npc_brain import NPC
        gen = WorldGenerator(seed=42)
        h = gen.get_height(0, 0)
        npc = NPC(0, (0.0, float(h), 0.0), name="Spawn Test")
        self.assertGreater(npc.position[1], 0)


class TestHeadlessGameSimulation(unittest.TestCase):
    """Integration: simulate game loop without display."""

    def test_game_simulation_runs(self):
        """Runs a trimmed version of the headless game loop."""
        import random as _r
        _r.seed(0)
        from engine.procedural.world_generator import WorldGenerator
        from engine.npc_ai.npc_brain import NPCSociety

        gen = WorldGenerator(seed=1)
        society = NPCSociety(world_seed=1)
        for i in range(4):
            society.spawn_npc((float(i*10), 0, float(i*5)), faction="neutral")

        for tick in range(30):
            society.tick((tick * 0.5, 0, 0),
                         {"time_of_day": tick/30, "danger_level": 0.0, "food_availability": 0.8})

        self.assertEqual(len(society.npcs), 4)


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    # Run with verbose output
    loader = unittest.TestLoader()
    suite = loader.discover(".", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
