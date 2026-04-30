"""
INFINITUM — NPC Neural Network AI System
==========================================
Each NPC has an individual LSTM-based neural network that:
  - Perceives the world (nearby entities, player position, health, hunger, etc.)
  - Learns from interactions and rewards
  - Develops a unique personality and memory
  - Communicates with other NPCs to form social structures

No external ML libraries required — pure NumPy implementation.
"""

import math
import random
import json
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any
from enum import Enum

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False
    # Minimal fallback (for environments without numpy)
    class _NP:
        @staticmethod
        def zeros(shape):
            if isinstance(shape, int):
                return [0.0] * shape
            return [[0.0] * shape[1] for _ in range(shape[0])]
        @staticmethod
        def tanh(x):
            if isinstance(x, list):
                return [math.tanh(v) for v in x]
            return math.tanh(x)
        @staticmethod
        def random(*args):
            return random.gauss(0, 0.1)
    np = _NP()


# ---------------------------------------------------------------------------
# Utility activation functions
# ---------------------------------------------------------------------------

def sigmoid(x):
    try:
        return 1.0 / (1.0 + np.exp(-np.clip(x, -500, 500)))
    except Exception:
        if hasattr(x, '__iter__'):
            return [1.0 / (1.0 + math.exp(-max(-500, min(500, v)))) for v in x]
        return 1.0 / (1.0 + math.exp(-max(-500, min(500, x))))


def tanh_act(x):
    try:
        return np.tanh(x)
    except Exception:
        if hasattr(x, '__iter__'):
            return [math.tanh(v) for v in x]
        return math.tanh(x)


def relu(x):
    try:
        return np.maximum(0, x)
    except Exception:
        if hasattr(x, '__iter__'):
            return [max(0.0, v) for v in x]
        return max(0.0, x)


def softmax(x):
    try:
        e = np.exp(x - np.max(x))
        return e / e.sum()
    except Exception:
        m = max(x)
        e = [math.exp(v - m) for v in x]
        s = sum(e)
        return [v / s for v in e]


# ---------------------------------------------------------------------------
# Minimal LSTM cell (NumPy)
# ---------------------------------------------------------------------------

class LSTMCell:
    """
    Single LSTM cell with forget, input, output and cell gates.
    input_size  → hidden units → output (action logits)
    """

    def __init__(self, input_size: int, hidden_size: int, seed: int = 0):
        self.input_size = input_size
        self.hidden_size = hidden_size
        rng = np.random.default_rng(seed)
        scale = 0.1

        # Combined weight matrix [4*H, I+H] for all gates
        self.W = rng.standard_normal((4 * hidden_size, input_size + hidden_size)).astype(np.float32) * scale
        self.b = np.zeros((4 * hidden_size,), dtype=np.float32)

        # Hidden and cell state
        self.h = np.zeros((hidden_size,), dtype=np.float32)
        self.c = np.zeros((hidden_size,), dtype=np.float32)

        # For BPTT (store last activation cache)
        self._cache: Optional[dict] = None

    def reset_state(self) -> None:
        self.h = np.zeros_like(self.h)
        self.c = np.zeros_like(self.c)

    def forward(self, x: np.ndarray) -> np.ndarray:
        """x: (input_size,) → returns new hidden state (hidden_size,)"""
        combined = np.concatenate([x, self.h])
        gates = self.W @ combined + self.b  # (4*H,)
        H = self.hidden_size

        f = sigmoid(gates[0:H])          # forget gate
        i = sigmoid(gates[H:2*H])        # input gate
        g = tanh_act(gates[2*H:3*H])     # cell gate
        o = sigmoid(gates[3*H:4*H])      # output gate

        self.c = f * self.c + i * g
        self.h = o * tanh_act(self.c)

        self._cache = {"x": x, "h_prev": self.h.copy(), "c_prev": self.c.copy(),
                       "f": f, "i": i, "g": g, "o": o}
        return self.h

    def backward(self, dh: np.ndarray, lr: float = 0.001) -> np.ndarray:
        """
        Simplified one-step BPTT.
        Returns dx (gradient w.r.t. input).
        """
        if self._cache is None:
            return np.zeros(self.input_size)

        cache = self._cache
        H = self.hidden_size
        x   = cache["x"]

        # Gradient of output gate
        d_o  = dh * tanh_act(self.c) * cache["o"] * (1 - cache["o"])
        d_c  = dh * cache["o"] * (1 - tanh_act(self.c) ** 2)
        d_f  = d_c * cache["c_prev"] * cache["f"] * (1 - cache["f"])
        d_i  = d_c * cache["g"] * cache["i"] * (1 - cache["i"])
        d_g  = d_c * cache["i"] * (1 - cache["g"] ** 2)

        d_gates = np.concatenate([d_f, d_i, d_g, d_o])
        combined = np.concatenate([x, cache["h_prev"]])

        # Weight gradients
        dW = np.outer(d_gates, combined)
        db = d_gates

        # Parameter update
        self.W -= lr * np.clip(dW, -1, 1)
        self.b -= lr * np.clip(db, -1, 1)

        # Gradient for input
        dx = (self.W.T @ d_gates)[:self.input_size]
        return dx


# ---------------------------------------------------------------------------
# NPC Brain — full network
# ---------------------------------------------------------------------------

class NPCBrain:
    """
    Two-layer LSTM brain + linear output head.
    Input:  state vector (positions, health, nearby entities, etc.)
    Output: action probabilities
    """

    INPUT_SIZE  = 32   # observation vector size
    HIDDEN_SIZE = 64
    OUTPUT_SIZE = 16   # possible actions

    def __init__(self, npc_id: int, personality_seed: int = None):
        self.npc_id = npc_id
        seed = personality_seed if personality_seed is not None else npc_id
        self.lstm1 = LSTMCell(self.INPUT_SIZE, self.HIDDEN_SIZE, seed=seed)
        self.lstm2 = LSTMCell(self.HIDDEN_SIZE, self.HIDDEN_SIZE, seed=seed + 1)
        rng = np.random.default_rng(seed + 2)
        self.W_out = rng.standard_normal((self.OUTPUT_SIZE, self.HIDDEN_SIZE)).astype(np.float32) * 0.1
        self.b_out = np.zeros(self.OUTPUT_SIZE, dtype=np.float32)
        self.memory: List[Tuple[np.ndarray, int, float]] = []  # (state, action, reward)
        self.total_reward: float = 0.0
        self.learning_rate: float = 0.001
        self.epsilon: float = 0.2  # exploration rate

    def reset_episode(self) -> None:
        self.lstm1.reset_state()
        self.lstm2.reset_state()

    def observe(self, state: np.ndarray) -> int:
        """
        Forward pass: state → action index.
        Uses ε-greedy exploration.
        """
        h1 = self.lstm1.forward(state)
        h2 = self.lstm2.forward(h1)
        logits = self.W_out @ h2 + self.b_out
        probs = softmax(logits)

        if random.random() < self.epsilon:
            action = random.randint(0, self.OUTPUT_SIZE - 1)
        else:
            action = int(np.argmax(probs))

        self.memory.append((state.copy(), action, 0.0))
        return action

    def receive_reward(self, reward: float) -> None:
        if self.memory:
            s, a, _ = self.memory[-1]
            self.memory[-1] = (s, a, reward)
            self.total_reward += reward
            # Decay exploration over time
            self.epsilon = max(0.02, self.epsilon * 0.9999)
        # Cap memory size
        if len(self.memory) > 1000:
            self.memory = self.memory[-1000:]

    def learn(self, batch_size: int = 16) -> float:
        """Simple policy-gradient update on recent experience."""
        if len(self.memory) < batch_size:
            return 0.0

        batch = self.memory[-batch_size:]
        total_loss = 0.0

        for state, action, reward in batch:
            h1 = self.lstm1.forward(state)
            h2 = self.lstm2.forward(h1)
            logits = self.W_out @ h2 + self.b_out
            probs = softmax(logits)

            # Policy gradient loss
            log_prob = math.log(max(probs[action], 1e-8))
            loss = -log_prob * reward
            total_loss += loss

            # Backprop output layer
            d_logits = probs.copy()
            d_logits[action] -= 1.0
            d_logits *= reward * self.learning_rate

            dh2 = self.W_out.T @ d_logits
            self.W_out -= self.learning_rate * np.outer(d_logits, h2)
            self.b_out -= self.learning_rate * d_logits

            # Backprop LSTM layers
            dx2 = self.lstm2.backward(dh2, self.learning_rate)
            self.lstm1.backward(dx2, self.learning_rate)

        # Trim memory
        if len(self.memory) > 1000:
            self.memory = self.memory[-1000:]

        return total_loss / batch_size

    def save(self, path: str) -> None:
        data = {
            "npc_id": self.npc_id,
            "total_reward": self.total_reward,
            "epsilon": self.epsilon,
            "W_out": self.W_out.tolist(),
            "b_out": self.b_out.tolist(),
        }
        with open(path, "w") as f:
            json.dump(data, f)

    def load(self, path: str) -> None:
        with open(path) as f:
            data = json.load(f)
        self.total_reward = data["total_reward"]
        self.epsilon = data["epsilon"]
        self.W_out = np.array(data["W_out"], dtype=np.float32)
        self.b_out = np.array(data["b_out"], dtype=np.float32)


# ---------------------------------------------------------------------------
# NPC Actions
# ---------------------------------------------------------------------------

class NPCAction(Enum):
    IDLE         = 0
    WALK_NORTH   = 1
    WALK_SOUTH   = 2
    WALK_EAST    = 3
    WALK_WEST    = 4
    RUN          = 5
    ATTACK       = 6
    FLEE         = 7
    GATHER       = 8
    BUILD        = 9
    TALK         = 10
    TRADE        = 11
    SLEEP        = 12
    EAT          = 13
    PATROL       = 14
    CALL_ALLIES  = 15


# ---------------------------------------------------------------------------
# NPC entity
# ---------------------------------------------------------------------------

@dataclass
class NPCPersonality:
    aggression:   float = 0.5   # 0=passive, 1=aggressive
    curiosity:    float = 0.5
    sociability:  float = 0.5
    loyalty:      float = 0.5
    intelligence: float = 0.5


@dataclass
class NPCMemoryEntry:
    event_type: str
    position: Tuple[float, float, float]
    tick: int
    value: float  # positive = good memory, negative = bad


class NPC:
    """
    A fully AI-driven non-player character.
    Each NPC has:
      - individual neural network brain
      - personality traits
      - episodic memory
      - social relations with other NPCs
      - needs (hunger, fatigue, social)
    """

    def __init__(self, npc_id: int, position: Tuple[float, float, float],
                 name: str = "", faction: str = "neutral"):
        self.npc_id = npc_id
        self.position = list(position)
        self.name = name or f"NPC_{npc_id}"
        self.faction = faction

        # Stats
        self.health = 100.0
        self.hunger = 0.0      # 0=full, 100=starving
        self.fatigue = 0.0
        self.social_need = 0.0

        # Personality (randomised per NPC)
        rng = random.Random(npc_id)
        self.personality = NPCPersonality(
            aggression=rng.random(),
            curiosity=rng.random(),
            sociability=rng.random(),
            loyalty=rng.random(),
            intelligence=rng.random(),
        )

        # Brain
        self.brain = NPCBrain(npc_id, personality_seed=npc_id)

        # Memory
        self.episodic_memory: List[NPCMemoryEntry] = []
        self.relations: Dict[int, float] = {}  # npc_id → relationship score

        self.current_action = NPCAction.IDLE
        self.tick = 0

    # -- observation builder --

    def build_observation(self, nearby_npcs: List["NPC"],
                          player_pos: Tuple[float, float, float],
                          world_state: dict) -> np.ndarray:
        obs = np.zeros(NPCBrain.INPUT_SIZE, dtype=np.float32)

        # Self state
        obs[0] = self.health / 100.0
        obs[1] = self.hunger / 100.0
        obs[2] = self.fatigue / 100.0
        obs[3] = self.social_need / 100.0

        # Personality
        obs[4] = self.personality.aggression
        obs[5] = self.personality.curiosity
        obs[6] = self.personality.sociability
        obs[7] = self.personality.loyalty

        # Relative player position (normalised)
        dx = (player_pos[0] - self.position[0]) / 100.0
        dy = (player_pos[1] - self.position[1]) / 100.0
        dz = (player_pos[2] - self.position[2]) / 100.0
        obs[8]  = max(-1, min(1, dx))
        obs[9]  = max(-1, min(1, dy))
        obs[10] = max(-1, min(1, dz))

        # Nearby NPCs (up to 3)
        for k, other in enumerate(nearby_npcs[:3]):
            base = 11 + k * 4
            rel_dist = math.sqrt(sum((a - b)**2 for a, b in zip(self.position, other.position)))
            obs[base]   = min(1, rel_dist / 50.0)
            obs[base+1] = other.health / 100.0
            obs[base+2] = self.relations.get(other.npc_id, 0.0)
            obs[base+3] = 1.0 if other.faction == self.faction else -1.0

        # World state
        obs[23] = world_state.get("time_of_day", 0.5)
        obs[24] = world_state.get("danger_level", 0.0)
        obs[25] = world_state.get("food_availability", 0.5)

        # Recent memory influence
        if self.episodic_memory:
            last = self.episodic_memory[-1]
            obs[26] = max(-1, min(1, last.value / 10.0))

        return obs

    def act(self, nearby_npcs: List["NPC"],
            player_pos: Tuple[float, float, float],
            world_state: dict) -> NPCAction:
        """Choose and execute an action."""
        obs = self.build_observation(nearby_npcs, player_pos, world_state)
        action_idx = self.brain.observe(obs)
        self.current_action = NPCAction(action_idx)
        self._execute_action(self.current_action)
        self.tick += 1
        return self.current_action

    def _execute_action(self, action: NPCAction) -> None:
        speed = 0.5
        if action == NPCAction.WALK_NORTH: self.position[2] -= speed
        elif action == NPCAction.WALK_SOUTH: self.position[2] += speed
        elif action == NPCAction.WALK_EAST:  self.position[0] += speed
        elif action == NPCAction.WALK_WEST:  self.position[0] -= speed
        elif action == NPCAction.RUN:
            self.position[0] += speed * 2
            self.fatigue += 2
        elif action == NPCAction.EAT:
            self.hunger = max(0, self.hunger - 20)
        elif action == NPCAction.SLEEP:
            self.fatigue = max(0, self.fatigue - 10)

        # Passive needs increase
        self.hunger  = min(100, self.hunger  + 0.1)
        self.fatigue = min(100, self.fatigue + 0.05)

    def receive_event(self, event_type: str, value: float, position=None) -> None:
        pos = position or tuple(self.position)
        self.episodic_memory.append(NPCMemoryEntry(
            event_type=event_type, position=pos,
            tick=self.tick, value=value,
        ))
        self.brain.receive_reward(value)
        if len(self.episodic_memory) > 200:
            self.episodic_memory = self.episodic_memory[-200:]

    def update_relation(self, other_id: int, delta: float) -> None:
        self.relations[other_id] = max(-1.0, min(1.0,
            self.relations.get(other_id, 0.0) + delta))


# ---------------------------------------------------------------------------
# NPC Society — manages a group of NPCs
# ---------------------------------------------------------------------------

class NPCSociety:
    """
    Manages a population of NPCs, handles interactions,
    faction dynamics and collective learning.
    """

    def __init__(self, world_seed: int = 0):
        self.world_seed = world_seed
        self.npcs: Dict[int, NPC] = {}
        self._next_id = 0
        self.factions: Dict[str, List[int]] = {}  # faction → list of npc_ids

    def spawn_npc(self, position: Tuple[float, float, float],
                  name: str = "", faction: str = "neutral") -> NPC:
        npc = NPC(self._next_id, position, name=name, faction=faction)
        self.npcs[self._next_id] = npc
        self.factions.setdefault(faction, []).append(self._next_id)
        self._next_id += 1
        return npc

    def tick(self, player_pos: Tuple[float, float, float],
             world_state: dict) -> Dict[int, NPCAction]:
        actions = {}
        npc_list = list(self.npcs.values())

        for npc in npc_list:
            # Find nearby NPCs (within 30 units)
            nearby = [
                other for other in npc_list
                if other.npc_id != npc.npc_id and
                math.sqrt(sum((a-b)**2 for a,b in zip(npc.position, other.position))) < 30
            ]
            action = npc.act(nearby, player_pos, world_state)
            actions[npc.npc_id] = action

            # Social interactions
            for other in nearby[:2]:
                if random.random() < npc.personality.sociability * 0.1:
                    npc.update_relation(other.npc_id, 0.01)
                    other.update_relation(npc.npc_id, 0.01)

        return actions

    def learn_all(self) -> float:
        total = 0.0
        for npc in self.npcs.values():
            total += npc.brain.learn()
        return total / max(1, len(self.npcs))

    def get_faction_stats(self) -> dict:
        stats = {}
        for faction, ids in self.factions.items():
            members = [self.npcs[i] for i in ids if i in self.npcs]
            stats[faction] = {
                "count": len(members),
                "avg_health": sum(m.health for m in members) / max(1, len(members)),
                "avg_reward": sum(m.brain.total_reward for m in members) / max(1, len(members)),
            }
        return stats


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== INFINITUM NPC AI System ===\n")

    society = NPCSociety(world_seed=42)

    # Spawn some NPCs
    for i in range(10):
        faction = "villagers" if i < 7 else "bandits"
        pos = (random.uniform(0, 100), 0, random.uniform(0, 100))
        society.spawn_npc(pos, faction=faction)

    player_pos = (50.0, 0.0, 50.0)
    world_state = {"time_of_day": 0.5, "danger_level": 0.3, "food_availability": 0.7}

    print(f"Spawned {len(society.npcs)} NPCs in 2 factions")
    print("\nRunning 50 simulation ticks...")

    rewards = []
    for tick in range(50):
        actions = society.tick(player_pos, world_state)

        # Simulate events
        for npc in society.npcs.values():
            dist_to_player = math.sqrt(sum((a-b)**2 for a,b in zip(npc.position, player_pos)))
            if dist_to_player < 10:
                npc.receive_event("player_nearby", -0.5 if npc.faction == "bandits" else 0.3)
            if npc.hunger > 70:
                npc.receive_event("hungry", -1.0)

        if tick % 10 == 9:
            avg_loss = society.learn_all()
            rewards.append(avg_loss)
            print(f"  Tick {tick+1}: avg_loss={avg_loss:.4f}")

    print("\nFaction statistics:")
    for faction, stats in society.get_faction_stats().items():
        print(f"  {faction}: {stats['count']} members, "
              f"avg_health={stats['avg_health']:.1f}, "
              f"avg_reward={stats['avg_reward']:.2f}")

    print("\nSample NPC memories:")
    npc0 = list(society.npcs.values())[0]
    print(f"  {npc0.name} ({npc0.faction}): {len(npc0.episodic_memory)} memories, "
          f"epsilon={npc0.brain.epsilon:.3f}")

    print("\n✅ NPC AI system OK")
