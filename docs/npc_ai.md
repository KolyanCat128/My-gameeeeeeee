# NPC AI System

## Overview

Every NPC in INFINITUM has its own **independent neural network** that persists
across sessions, learns from interactions, and develops a unique personality.

## Architecture

```
Observation Vector (32 floats)
       │
  ┌────▼──────────────┐
  │  LSTM Layer 1     │  64 hidden units
  │  (LSTMCell)       │
  └────┬──────────────┘
       │
  ┌────▼──────────────┐
  │  LSTM Layer 2     │  64 hidden units
  │  (LSTMCell)       │
  └────┬──────────────┘
       │
  ┌────▼──────────────┐
  │  Linear Output    │  16 action logits
  └────┬──────────────┘
       │
  ┌────▼──────────────┐
  │   Softmax         │  action probabilities
  └───────────────────┘
```

## Observation Vector (32 dims)

| Index | Meaning |
|-------|---------|
| 0 | Normalised health (0–1) |
| 1 | Hunger level (0–1) |
| 2 | Fatigue level (0–1) |
| 3 | Social need (0–1) |
| 4–7 | Personality traits (aggression, curiosity, sociability, loyalty) |
| 8–10 | Relative player position (normalised, clamped ±1) |
| 11–22 | Nearby NPC descriptors (up to 3 × 4 features each) |
| 23 | Time of day (0–1) |
| 24 | Danger level (0–1) |
| 25 | Food availability (0–1) |
| 26 | Last memory valence |
| 27–31 | Reserved for custom plugins |

## Action Space (16 actions)

| Index | Action |
|-------|--------|
| 0 | IDLE |
| 1–4 | Walk N/S/E/W |
| 5 | Run |
| 6 | Attack |
| 7 | Flee |
| 8 | Gather |
| 9 | Build |
| 10 | Talk |
| 11 | Trade |
| 12 | Sleep |
| 13 | Eat |
| 14 | Patrol |
| 15 | Call Allies |

## Learning Algorithm

NPCs learn via **online policy gradient**:
- Each `(state, action, reward)` triple is stored in episodic memory (max 1000)
- Every N ticks, a mini-batch of 16 samples is used for a gradient update
- The LSTM weights are updated in place (no separate target network needed
  for this prototype)
- Exploration uses ε-greedy with exponential decay

## Social Structures

- NPCs track **relationship scores** (−1 … +1) with every other NPC they meet
- Positive relationships grow through proximity and cooperative actions
- Negative relationships result from attacks or resource competition
- NPCs in the same faction share information about threats and food sources

## Persistence

Each NPC brain can be saved/loaded with `brain.save(path)` / `brain.load(path)`.
In the full game, brains are stored per-world in a key-value store (e.g., RocksDB).

## GPU Acceleration (Production)

In the production Unreal Engine 5 build:
- LSTM inference is batched across all NPCs in a scene into a single GPU kernel
- Gradients are accumulated asynchronously on a background thread
- Approximate nearest-neighbour search replaces the O(N²) social scan
