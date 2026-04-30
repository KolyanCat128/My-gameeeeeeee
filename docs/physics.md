# Physics System

## Overview

The INFINITUM physics engine provides:
- Rigid body dynamics with AABB collision
- Fluid simulation (Eulerian grid-based)
- Thermal conduction and material state changes
- Procedural destruction and fracturing

## Rigid Body Integration

Semi-implicit Euler integration:
```
F_total = gravity * mass + applied_forces
a = F_total / mass
v += a * dt
v *= (1 - air_resistance * dt)   # drag
x += v * dt
```

## Collision Pipeline

1. **Broad phase**: AABB overlap test (O(N²) prototype; BVH in production)
2. **Narrow phase**: Penetration depth + contact normal
3. **Resolution**: Baumgarte positional correction + impulse-based velocity change
4. **Friction**: Coulomb friction applied along the contact tangent

## Fluid Simulation

Grid-based Eulerian advection:
- Each cell stores `density`, `velocity_x`, `velocity_y`
- Gravity applied each step
- Viscosity is a linear damping on velocity
- Fluid is moved to neighbouring cells based on velocity direction
- Solid cells block flow and cause velocity reflection

## Thermal System

- Each `RigidBody` has a `temperature` (°C)
- Heat flows between close bodies using a harmonic mean conductivity:
  `k = 2*kA*kB / (kA + kB)`
- If temperature exceeds `melting_point`, the body loses `health`

## Destruction

- `apply_damage(body, damage, impact_point)` reduces body health
- Health reduction is scaled by material hardness
- At 0 health, the body shatters into 4–8 randomly-sized fragments
- Fragments inherit velocity spread from the impact direction

## Customisable Constants

All constants are configurable via `WorldPhysicsLaws`:

```python
laws = WorldPhysicsLaws(
    gravity = 9.81,           # Earth
    air_resistance = 0.02,
    temperature_base = 20.0,
    time_scale = 2.0,         # 2× speed
)
```

## Production Notes

In the Unreal Engine 5 build, the physics engine is replaced by:
- **Chaos** for rigid bodies and destruction
- **Niagara** for fluid particle effects
- Custom CUDA kernels for thermal propagation at scale
