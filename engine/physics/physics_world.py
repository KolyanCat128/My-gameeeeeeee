"""
INFINITUM — Physics Simulation Engine
======================================
Custom rigid-body, fluid and soft-body physics engine.
Physics constants are fully customisable per world / region.
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
from enum import Enum


# ---------------------------------------------------------------------------
# Math primitives
# ---------------------------------------------------------------------------

@dataclass
class Vec3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __add__(self, o: "Vec3") -> "Vec3":
        return Vec3(self.x + o.x, self.y + o.y, self.z + o.z)

    def __sub__(self, o: "Vec3") -> "Vec3":
        return Vec3(self.x - o.x, self.y - o.y, self.z - o.z)

    def __mul__(self, s: float) -> "Vec3":
        return Vec3(self.x * s, self.y * s, self.z * s)

    def __rmul__(self, s: float) -> "Vec3":
        return self.__mul__(s)

    def __truediv__(self, s: float) -> "Vec3":
        return Vec3(self.x / s, self.y / s, self.z / s)

    def __neg__(self) -> "Vec3":
        return Vec3(-self.x, -self.y, -self.z)

    def dot(self, o: "Vec3") -> float:
        return self.x * o.x + self.y * o.y + self.z * o.z

    def cross(self, o: "Vec3") -> "Vec3":
        return Vec3(
            self.y * o.z - self.z * o.y,
            self.z * o.x - self.x * o.z,
            self.x * o.y - self.y * o.x,
        )

    def length(self) -> float:
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)

    def normalize(self) -> "Vec3":
        l = self.length()
        if l < 1e-9:
            return Vec3(0, 0, 0)
        return self / l

    def __repr__(self) -> str:
        return f"Vec3({self.x:.3f}, {self.y:.3f}, {self.z:.3f})"


@dataclass
class AABB:
    """Axis-Aligned Bounding Box for broad-phase collision."""
    min: Vec3
    max: Vec3

    def overlaps(self, other: "AABB") -> bool:
        return (self.min.x <= other.max.x and self.max.x >= other.min.x and
                self.min.y <= other.max.y and self.max.y >= other.min.y and
                self.min.z <= other.max.z and self.max.z >= other.min.z)

    def contains(self, p: Vec3) -> bool:
        return (self.min.x <= p.x <= self.max.x and
                self.min.y <= p.y <= self.max.y and
                self.min.z <= p.z <= self.max.z)


# ---------------------------------------------------------------------------
# Material system
# ---------------------------------------------------------------------------

@dataclass
class Material:
    name: str
    density: float        # kg/m³
    restitution: float    # bounciness 0..1
    friction: float       # 0..1
    melting_point: float  # °C
    hardness: float       # relative, 1 = stone
    is_fluid: bool = False
    viscosity: float = 0.0  # only for fluids


MATERIALS: Dict[str, Material] = {
    "stone":    Material("stone",    2700,  0.2,  0.8, 1650, 7.0),
    "wood":     Material("wood",      700,  0.3,  0.7,  300, 2.0),
    "sand":     Material("sand",     1600,  0.1,  0.6,  800, 1.0),
    "iron":     Material("iron",     7874,  0.4,  0.6, 1538, 9.0),
    "rubber":   Material("rubber",   1200,  0.9,  0.9,  200, 0.5),
    "water":    Material("water",    1000,  0.05, 0.0,    0, 0.0, is_fluid=True, viscosity=1.0),
    "lava":     Material("lava",     2900,  0.05, 0.0, 1200, 0.0, is_fluid=True, viscosity=100.0),
    "air":      Material("air",         1,  0.0,  0.0, -200, 0.0, is_fluid=True, viscosity=0.01),
    "ice":      Material("ice",       917,  0.1,  0.05,   0, 3.0),
    "crystal":  Material("crystal",  2500,  0.7,  0.3, 2000, 10.0),
}


# ---------------------------------------------------------------------------
# Rigid body
# ---------------------------------------------------------------------------

@dataclass
class RigidBody:
    body_id: int
    position: Vec3
    velocity: Vec3 = field(default_factory=Vec3)
    acceleration: Vec3 = field(default_factory=Vec3)
    angular_velocity: Vec3 = field(default_factory=Vec3)
    mass: float = 1.0           # kg
    inv_mass: float = 1.0       # 1/mass (0 = static)
    restitution: float = 0.5
    friction: float = 0.5
    is_static: bool = False
    is_sleeping: bool = False
    material: str = "stone"
    size: Vec3 = field(default_factory=lambda: Vec3(1, 1, 1))
    temperature: float = 20.0   # °C
    health: float = 100.0
    force_accum: Vec3 = field(default_factory=Vec3)  # accumulated forces this tick

    def __post_init__(self):
        if self.is_static:
            self.inv_mass = 0.0
        else:
            self.inv_mass = 1.0 / self.mass if self.mass > 0 else 0.0

    @property
    def aabb(self) -> AABB:
        half = self.size * 0.5
        return AABB(self.position - half, self.position + half)

    def apply_force(self, f: Vec3) -> None:
        if not self.is_static:
            self.force_accum = self.force_accum + f

    def apply_impulse(self, impulse: Vec3) -> None:
        if not self.is_static:
            self.velocity = self.velocity + impulse * self.inv_mass


# ---------------------------------------------------------------------------
# Collision detection and resolution
# ---------------------------------------------------------------------------

@dataclass
class ContactPoint:
    body_a: RigidBody
    body_b: Optional[RigidBody]   # None = world/floor
    normal: Vec3
    penetration: float


class CollisionDetector:
    @staticmethod
    def aabb_vs_aabb(a: RigidBody, b: RigidBody) -> Optional[ContactPoint]:
        aa, ab = a.aabb, b.aabb
        if not aa.overlaps(ab):
            return None

        # Find minimum penetration axis
        dx = min(aa.max.x - ab.min.x, ab.max.x - aa.min.x)
        dy = min(aa.max.y - ab.min.y, ab.max.y - aa.min.y)
        dz = min(aa.max.z - ab.min.z, ab.max.z - aa.min.z)

        if dx < dy and dx < dz:
            nx = 1.0 if a.position.x < b.position.x else -1.0
            normal = Vec3(nx, 0, 0)
            penetration = dx
        elif dy < dz:
            ny = 1.0 if a.position.y < b.position.y else -1.0
            normal = Vec3(0, ny, 0)
            penetration = dy
        else:
            nz = 1.0 if a.position.z < b.position.z else -1.0
            normal = Vec3(0, 0, nz)
            penetration = dz

        return ContactPoint(body_a=a, body_b=b, normal=normal, penetration=penetration)

    @staticmethod
    def body_vs_floor(body: RigidBody, floor_y: float = 0.0) -> Optional[ContactPoint]:
        bottom = body.position.y - body.size.y * 0.5
        if bottom < floor_y:
            return ContactPoint(
                body_a=body, body_b=None,
                normal=Vec3(0, 1, 0),
                penetration=floor_y - bottom,
            )
        return None


class CollisionResolver:
    @staticmethod
    def resolve(contact: ContactPoint) -> None:
        a = contact.body_a
        b = contact.body_b

        # Positional correction (Baumgarte)
        correction_ratio = 0.8
        if b is None:
            # vs. floor
            a.position = a.position + contact.normal * contact.penetration * correction_ratio
            # velocity along normal
            vn = a.velocity.dot(contact.normal)
            if vn < 0:
                e = a.restitution
                j = -(1 + e) * vn * a.mass
                a.velocity = a.velocity + contact.normal * (j / a.mass)
                # friction
                tangent = a.velocity - contact.normal * a.velocity.dot(contact.normal)
                if tangent.length() > 1e-4:
                    t = tangent.normalize()
                    jt = -a.velocity.dot(t) * a.mass
                    mu = a.friction
                    jt = max(-abs(j) * mu, min(abs(j) * mu, jt))
                    a.velocity = a.velocity + t * (jt / a.mass)
        else:
            # Two-body resolution
            total_inv = a.inv_mass + b.inv_mass
            if total_inv < 1e-9:
                return
            # Separate them
            correction = contact.normal * (contact.penetration * correction_ratio / total_inv)
            a.position = a.position + correction * a.inv_mass
            b.position = b.position - correction * b.inv_mass

            rel_vel = a.velocity - b.velocity
            vn = rel_vel.dot(contact.normal)
            if vn > 0:
                return
            e = min(a.restitution, b.restitution)
            j = -(1 + e) * vn / total_inv
            impulse = contact.normal * j
            a.apply_impulse(impulse)
            b.apply_impulse(-impulse)


# ---------------------------------------------------------------------------
# Fluid simulation (simple SPH-lite grid)
# ---------------------------------------------------------------------------

@dataclass
class FluidCell:
    density: float = 0.0
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    pressure: float = 0.0


class FluidSimulator:
    """
    Simple 2-D grid-based fluid simulation (Eulerian approach).
    Suitable for water / lava effects in voxel worlds.
    """

    def __init__(self, width: int, height: int,
                 gravity: float = 9.81, viscosity: float = 1.0):
        self.width = width
        self.height = height
        self.gravity = gravity
        self.viscosity = viscosity
        self.cells: List[List[FluidCell]] = [
            [FluidCell() for _ in range(height)] for _ in range(width)
        ]
        self.solid: List[List[bool]] = [
            [False] * height for _ in range(width)
        ]

    def add_fluid(self, x: int, y: int, density: float = 1.0) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.cells[x][y].density += density

    def set_solid(self, x: int, y: int) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.solid[x][y] = True

    def step(self, dt: float) -> None:
        """Advance simulation by dt seconds."""
        w, h = self.width, self.height
        new_cells = [[FluidCell() for _ in range(h)] for _ in range(w)]

        for x in range(w):
            for y in range(h):
                cell = self.cells[x][y]
                if self.solid[x][y] or cell.density < 1e-4:
                    continue

                # Gravity
                cell.velocity_y -= self.gravity * dt

                # Viscosity (damping)
                cell.velocity_x *= (1 - self.viscosity * dt * 0.1)
                cell.velocity_y *= (1 - self.viscosity * dt * 0.1)

                # Advect: move fluid to neighbour
                nx = x + (1 if cell.velocity_x > 0 else -1)
                ny = y + (1 if cell.velocity_y < 0 else -1)  # y down

                # Clamp and check solids
                target_x = max(0, min(w - 1, nx))
                target_y = max(0, min(h - 1, ny))

                if self.solid[target_x][target_y]:
                    # Bounce
                    cell.velocity_x *= -0.5
                    cell.velocity_y *= -0.5
                    target_x, target_y = x, y

                new_cells[target_x][target_y].density += cell.density
                new_cells[target_x][target_y].velocity_x += cell.velocity_x
                new_cells[target_x][target_y].velocity_y += cell.velocity_y

        self.cells = new_cells

    def get_density(self, x: int, y: int) -> float:
        return self.cells[x][y].density if 0 <= x < self.width and 0 <= y < self.height else 0.0


# ---------------------------------------------------------------------------
# Temperature / state-change system
# ---------------------------------------------------------------------------

class ThermalSimulator:
    """Handles heat propagation and material state changes."""

    CONDUCTIVITY = {
        "iron":   80.0,
        "stone":  1.7,
        "wood":   0.12,
        "water":  0.6,
        "air":    0.025,
        "ice":    2.2,
    }

    def propagate(self, bodies: List[RigidBody], dt: float) -> None:
        for i, a in enumerate(bodies):
            for b in bodies[i+1:]:
                dist = (a.position - b.position).length()
                if dist < 1.0:
                    k_a = self.CONDUCTIVITY.get(a.material, 1.0)
                    k_b = self.CONDUCTIVITY.get(b.material, 1.0)
                    k = 2 * k_a * k_b / (k_a + k_b)
                    delta = k * (b.temperature - a.temperature) * dt / max(dist, 0.1)
                    a.temperature += delta
                    b.temperature -= delta

        # State changes (melting, freezing)
        for body in bodies:
            mat = MATERIALS.get(body.material)
            if mat and not mat.is_fluid:
                if body.temperature > mat.melting_point:
                    body.health -= (body.temperature - mat.melting_point) * dt * 0.1


# ---------------------------------------------------------------------------
# Destruction system
# ---------------------------------------------------------------------------

class DestructionSystem:
    """Simulates object destruction and fracturing."""

    @staticmethod
    def apply_damage(body: RigidBody, damage: float, impact_point: Vec3) -> List[RigidBody]:
        """
        Apply damage; if body dies return list of fragment bodies.
        """
        mat = MATERIALS.get(body.material)
        effective_damage = damage / (mat.hardness if mat else 1.0)
        body.health -= effective_damage

        if body.health <= 0:
            return DestructionSystem._shatter(body, impact_point)
        return []

    @staticmethod
    def _shatter(body: RigidBody, impact: Vec3) -> List[RigidBody]:
        """Produce 4–8 random fragment bodies."""
        import random as _r
        fragments = []
        n = _r.randint(4, 8)
        for i in range(n):
            spread = Vec3(
                _r.uniform(-0.5, 0.5),
                _r.uniform(0.2, 1.0),
                _r.uniform(-0.5, 0.5),
            )
            frag = RigidBody(
                body_id = body.body_id * 1000 + i,
                position = body.position + spread * 0.3,
                velocity = spread * _r.uniform(1.0, 5.0),
                mass = body.mass / n,
                restitution = body.restitution * 0.7,
                friction = body.friction,
                material = body.material,
                size = body.size * (1.0 / n ** (1/3)),
                health = 10.0,
            )
            fragments.append(frag)
        return fragments


# ---------------------------------------------------------------------------
# Main Physics World
# ---------------------------------------------------------------------------

class PhysicsWorld:
    """
    The top-level physics simulation world.
    Integrates rigid bodies, fluid, thermal and destruction systems.
    """

    def __init__(self, gravity: Vec3 = None,
                 air_resistance: float = 0.02,
                 floor_y: float = 0.0):
        self.gravity = gravity or Vec3(0, -9.81, 0)
        self.air_resistance = air_resistance
        self.floor_y = floor_y
        self.bodies: List[RigidBody] = []
        self._next_id = 0
        self._detector = CollisionDetector()
        self._resolver = CollisionResolver()
        self._thermal = ThermalSimulator()
        self._pending_fragments: List[RigidBody] = []

    # -- body management --

    def add_body(self, position: Vec3, mass: float = 1.0,
                 material: str = "stone", size: Vec3 = None,
                 is_static: bool = False, **kwargs) -> RigidBody:
        body = RigidBody(
            body_id=self._next_id,
            position=position,
            mass=mass,
            is_static=is_static,
            material=material,
            size=size or Vec3(1, 1, 1),
            **kwargs,
        )
        self._next_id += 1
        self.bodies.append(body)
        return body

    def remove_body(self, body: RigidBody) -> None:
        self.bodies = [b for b in self.bodies if b.body_id != body.body_id]

    # -- simulation step --

    def step(self, dt: float) -> None:
        """Advance the physics world by dt seconds."""
        dt = min(dt, 0.05)  # clamp for stability

        # 1. Integrate forces → velocities → positions
        g = self.gravity
        for body in self.bodies:
            if body.is_static or body.is_sleeping:
                continue

            # Gravity + accumulated forces
            total_force = g * body.mass + body.force_accum
            body.force_accum = Vec3()  # clear

            body.acceleration = total_force * body.inv_mass

            # Air resistance
            body.velocity = body.velocity * (1 - self.air_resistance * dt)

            body.velocity = body.velocity + body.acceleration * dt
            body.position = body.position + body.velocity * dt

        # 2. Collision detection & resolution
        n = len(self.bodies)
        for i in range(n):
            # vs floor
            contact = CollisionDetector.body_vs_floor(self.bodies[i], self.floor_y)
            if contact:
                CollisionResolver.resolve(contact)

            # vs other bodies
            for j in range(i + 1, n):
                contact = CollisionDetector.aabb_vs_aabb(self.bodies[i], self.bodies[j])
                if contact:
                    CollisionResolver.resolve(contact)

        # 3. Thermal propagation
        self._thermal.propagate(self.bodies, dt)

        # 4. Add any pending fragments
        self.bodies.extend(self._pending_fragments)
        self._pending_fragments.clear()

    def apply_explosion(self, center: Vec3, radius: float, force: float) -> None:
        """Apply explosive force to all bodies within radius."""
        for body in self.bodies:
            if body.is_static:
                continue
            diff = body.position - center
            dist = diff.length()
            if dist < radius and dist > 1e-6:
                falloff = 1.0 - dist / radius
                impulse_vec = diff.normalize() * (force * falloff)
                body.apply_impulse(impulse_vec)
                # Damage
                damage = force * falloff * 10
                frags = DestructionSystem.apply_damage(body, damage, center)
                if frags:
                    self.remove_body(body)
                    self._pending_fragments.extend(frags)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== INFINITUM Physics Simulation ===\n")

    world = PhysicsWorld(gravity=Vec3(0, -9.81, 0), floor_y=0.0)

    # Drop a stone cube from height 20
    stone = world.add_body(
        position=Vec3(0, 20, 0),
        mass=10.0,
        material="stone",
        size=Vec3(1, 1, 1),
        velocity=Vec3(1, 0, 0),
    )

    print("Simulating 200 steps (dt=0.05s each):")
    for i in range(200):
        world.step(0.05)
        if i % 40 == 0:
            print(f"  t={i*0.05:.2f}s  pos={stone.position}  vel={stone.velocity}")

    print(f"\nFinal position: {stone.position}")
    print(f"Final velocity: {stone.velocity}")

    # Explosion test
    world2 = PhysicsWorld()
    bodies = []
    for i in range(5):
        b = world2.add_body(Vec3(float(i) * 2, 5, 0), mass=5.0, material="stone",
                            health=50.0)
        bodies.append(b)

    print("\nExplosion test — 5 bodies, explosion at center:")
    world2.apply_explosion(Vec3(4, 5, 0), radius=6.0, force=200.0)
    for b in list(world2.bodies):
        print(f"  Body {b.body_id}: pos={b.position}  vel={b.velocity}  hp={b.health:.1f}")
    print(f"  Fragments spawned: {len(world2._pending_fragments)}")

    print("\nFluid simulation (10×10 grid, water falling):")
    fluid = FluidSimulator(10, 10, gravity=9.81, viscosity=1.0)
    fluid.add_fluid(5, 9, density=5.0)
    fluid.set_solid(5, 0)
    for _ in range(20):
        fluid.step(0.05)
    print("  Density column at x=5:")
    for y in range(9, -1, -1):
        d = fluid.get_density(5, y)
        bar = "█" * int(d * 3)
        print(f"  y={y}: {d:.2f} {bar}")

    print("\n✅ Physics simulation OK")
