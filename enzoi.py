"""ENZOI SANDBOX FRAMEWORK v1.0
SPDX-License-Identifier: MIT
Bel Esprit D'Accord Trust · SnapKitty Collective · 2026

WORM SEALED - Evidence or Silence.
Pure Python / tkinter. Zero PyPI dependencies.

Provides:
- WORMSeal registry
- Avatar with idle/walk/attack/dead states, sprite-sheet support,
  procedural fallback rendering, collision box, inventory, and stat bars
- Tile / World with tile map, collision rectangles, and portal triggers
- InputHandler for tkinter games
"""
from __future__ import annotations

import hashlib
import json
import math
import time
import tkinter as tk
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Iterable, Optional


TILE_SIZE = 32
FLOOR = 0
WALL = 1
PORTAL = 2
WATER = 3


class AvatarState(Enum):
    IDLE = auto()
    WALK = auto()
    ATTACK = auto()
    DEAD = auto()


class TileType(Enum):
    FLOOR = FLOOR
    WALL = WALL
    PORTAL = PORTAL
    WATER = WATER


class WORMSeal:
    """Write-once-read-many identity seal registry."""

    _registry: dict[str, dict] = {}

    @staticmethod
    def seal(name: str, job: str, spawn_time: float) -> str:
        raw = f"{name}|{job}|{spawn_time:.6f}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        WORMSeal._registry[digest] = {
            "name": name,
            "job": job,
            "spawn_time": spawn_time,
            "seal": digest,
            "verified": True,
        }
        return digest

    @staticmethod
    def verify(digest: str) -> bool:
        return digest in WORMSeal._registry

    @staticmethod
    def read(digest: str) -> Optional[dict]:
        record = WORMSeal._registry.get(digest)
        return dict(record) if record else None

    @staticmethod
    def dump() -> str:
        return json.dumps(WORMSeal._registry, indent=2)


@dataclass
class InventorySlot:
    item_name: str = ""
    quantity: int = 0
    tag: str = ""

    def is_empty(self) -> bool:
        return self.item_name == "" or self.quantity <= 0

    def label(self) -> str:
        return "" if self.is_empty() else self.item_name[:1].upper()

    def __str__(self) -> str:
        return "[empty]" if self.is_empty() else f"{self.item_name} x{self.quantity}"


@dataclass
class Tile:
    type: TileType = TileType.FLOOR
    destination: str | None = None
    color: str | None = None

    def default_color(self) -> str:
        if self.color:
            return self.color
        if self.type == TileType.FLOOR:
            return "#2d2d2d"
        if self.type == TileType.WALL:
            return "#6b4c3b"
        if self.type == TileType.PORTAL:
            return "#9b30ff"
        if self.type == TileType.WATER:
            return "#1e90ff"
        return "#ffffff"


@dataclass
class TileRect:
    x: float
    y: float
    w: float
    h: float

    def intersects(self, other: "TileRect") -> bool:
        return not (
            self.x + self.w <= other.x
            or self.x >= other.x + other.w
            or self.y + self.h <= other.y
            or self.y >= other.y + other.h
        )


@dataclass
class PortalTrigger:
    key: str
    title: str
    x: float
    y: float
    radius: float
    callback: Callable[[str], None] | None = None


class InputHandler:
    def __init__(self, root: tk.Tk | tk.Widget) -> None:
        self.keys: set[str] = set()
        root.bind("<KeyPress>", self._down)
        root.bind("<KeyRelease>", self._up)

    def _down(self, event: tk.Event) -> None:
        self.keys.add(event.keysym)

    def _up(self, event: tk.Event) -> None:
        self.keys.discard(event.keysym)

    def pressed(self, *keys: str) -> bool:
        return any(key in self.keys for key in keys)

    def axis(self) -> tuple[float, float]:
        dx = float(self.pressed("d", "D", "Right")) - float(self.pressed("a", "A", "Left"))
        dy = float(self.pressed("s", "S", "Down")) - float(self.pressed("w", "W", "Up"))
        if dx or dy:
            mag = math.hypot(dx, dy)
            return dx / mag, dy / mag
        return 0.0, 0.0


class Avatar:
    """Sovereign avatar with WORM-sealed identity and Enzoi animation state."""

    MAX_SLOTS = 8

    def __init__(
        self,
        name: str,
        job: str = "Agent",
        x: float = 1,
        y: float = 1,
        *,
        color: str = "#4FC3F7",
        accent: str = "#00ff88",
        sprite_sheet: str | Path | None = None,
        frame_width: int = 32,
        frame_height: int = 32,
        speed: float = 180.0,
        tile_mode: bool = False,
    ) -> None:
        self.name = name
        self.job = job
        self.spawn_time = time.time()
        self.color = color
        self.accent = accent
        self.tile_mode = tile_mode

        self.x = float(x * TILE_SIZE if tile_mode else x)
        self.y = float(y * TILE_SIZE if tile_mode else y)
        self.tile_x = int(x)
        self.tile_y = int(y)
        self.vx = 0.0
        self.vy = 0.0
        self.speed = speed
        self.facing = "down"

        self.state = AvatarState.IDLE
        self.frame = 0
        self.frame_timer = 0.0
        self.attack_timer = 0.0
        self.attack_duration = 0.22

        self.health = 100.0
        self.energy = 100.0
        self.mood = 75.0
        self.hunger = 20.0

        self.collision_w = 24
        self.collision_h = 28
        self.frame_width = frame_width
        self.frame_height = frame_height

        self.inventory: list[InventorySlot] = [InventorySlot() for _ in range(self.MAX_SLOTS)]
        self.inventory_open = False

        self.identity_seal = WORMSeal.seal(name, job, self.spawn_time)
        self.worm_seal = self.identity_seal

        self._sheet: tk.PhotoImage | None = None
        self._frames: dict[AvatarState, list[tk.PhotoImage]] = {}
        if sprite_sheet:
            self.load_sprite_sheet(sprite_sheet, frame_width, frame_height)

    @property
    def rect(self) -> TileRect:
        return TileRect(self.x - self.collision_w / 2, self.y - self.collision_h / 2, self.collision_w, self.collision_h)

    def load_sprite_sheet(self, path: str | Path, frame_width: int, frame_height: int) -> None:
        p = Path(path)
        if not p.exists():
            return
        try:
            self._sheet = tk.PhotoImage(file=str(p))
        except tk.TclError:
            return
        cols = max(1, self._sheet.width() // frame_width)
        rows = max(1, self._sheet.height() // frame_height)
        states = [AvatarState.IDLE, AvatarState.WALK, AvatarState.ATTACK, AvatarState.DEAD]
        for row, state in enumerate(states[:rows]):
            self._frames[state] = []
            for col in range(cols):
                frame = tk.PhotoImage(width=frame_width, height=frame_height)
                frame.copy(
                    self._sheet,
                    from_coords=(col * frame_width, row * frame_height, (col + 1) * frame_width, (row + 1) * frame_height),
                    to=(0, 0),
                )
                self._frames[state].append(frame)

    def add_item(self, item_name: str, quantity: int = 1, tag: str = "") -> bool:
        for slot in self.inventory:
            if slot.item_name == item_name and slot.tag == tag:
                slot.quantity += quantity
                return True
        for slot in self.inventory:
            if slot.is_empty():
                slot.item_name = item_name
                slot.quantity = quantity
                slot.tag = tag
                return True
        return False

    def set_velocity(self, dx: float, dy: float) -> None:
        if self.state == AvatarState.DEAD:
            self.vx = 0
            self.vy = 0
            return
        self.vx = dx * self.speed
        self.vy = dy * self.speed
        if dx or dy:
            self.state = AvatarState.WALK
            if abs(dx) > abs(dy):
                self.facing = "right" if dx > 0 else "left"
            else:
                self.facing = "down" if dy > 0 else "up"
        elif self.state != AvatarState.ATTACK:
            self.state = AvatarState.IDLE

    def attack(self) -> None:
        if self.state != AvatarState.DEAD:
            self.state = AvatarState.ATTACK
            self.attack_timer = self.attack_duration
            self.frame = 0
            self.frame_timer = 0.0

    def move(self, dx: int, dy: int, world: "World") -> bool:
        """Grid movement compatibility with the Enzoi spec."""
        new_x = self.tile_x + dx
        new_y = self.tile_y + dy
        if 0 <= new_x < world.width and 0 <= new_y < world.height:
            if world.tiles[new_y][new_x].type != TileType.WALL:
                self.tile_x = new_x
                self.tile_y = new_y
                self.x = new_x * world.tile_size + world.tile_size / 2
                self.y = new_y * world.tile_size + world.tile_size / 2
                self.state = AvatarState.WALK
                return True
        return False

    def interact(self, world: "World") -> str | None:
        if 0 <= self.tile_x < world.width and 0 <= self.tile_y < world.height:
            tile = world.tiles[self.tile_y][self.tile_x]
            if tile.type == TileType.PORTAL:
                return tile.destination
        portal = world.portal_at(self.x, self.y)
        return portal.key if portal else None

    def update_stats(self, dt: float = 1.0) -> None:
        if self.state == AvatarState.WALK:
            self.energy -= 4.5 * dt
            self.hunger += 2.5 * dt
            self.mood += 0.4 * dt
        elif self.state == AvatarState.ATTACK:
            self.energy -= 8.0 * dt
            self.hunger += 4.0 * dt
        else:
            self.energy += 3.0 * dt
            self.mood += 0.2 * dt

        if self.hunger > 80:
            self.mood -= 2.0 * dt
        if self.energy < 20:
            self.mood -= 2.4 * dt

        self.health = max(0.0, min(100.0, self.health))
        self.energy = max(0.0, min(100.0, self.energy))
        self.mood = max(0.0, min(100.0, self.mood))
        self.hunger = max(0.0, min(100.0, self.hunger))
        if self.health <= 0:
            self.state = AvatarState.DEAD

    def update(self, dt: float, world: "World") -> None:
        if self.state == AvatarState.DEAD:
            self.update_stats(dt)
            return
        old_x, old_y = self.x, self.y
        self.x += self.vx * dt
        if world.collides(self.rect):
            self.x = old_x
        self.y += self.vy * dt
        if world.collides(self.rect):
            self.y = old_y

        self.tile_x = max(0, min(world.width - 1, int(self.x // world.tile_size)))
        self.tile_y = max(0, min(world.height - 1, int(self.y // world.tile_size)))

        if self.state == AvatarState.ATTACK:
            self.attack_timer -= dt
            if self.attack_timer <= 0:
                self.state = AvatarState.IDLE

        self.update_stats(dt)

        self.frame_timer += dt
        frame_delay = 0.12 if self.state == AvatarState.WALK else 0.22
        if self.frame_timer >= frame_delay:
            self.frame_timer = 0.0
            max_frames = max(1, len(self._frames.get(self.state, [])) or (4 if self.state == AvatarState.WALK else 2))
            self.frame = (self.frame + 1) % max_frames

    def draw(self, canvas: tk.Canvas, *, scale_x: float = 1.0, scale_y: float = 1.0) -> None:
        x = self.x * scale_x
        y = self.y * scale_y
        frames = self._frames.get(self.state) or self._frames.get(AvatarState.IDLE)
        if frames:
            image = frames[self.frame % len(frames)]
            canvas.create_image(x, y, image=image)
            refs = getattr(canvas, "_enzoi_refs", [])
            refs.append(image)
            canvas._enzoi_refs = refs[-64:]
        else:
            self._draw_procedural(canvas, x, y)
        self.draw_stat_bars(canvas, x, y - 42)
        self.draw_inventory(canvas, x - 72, y + 38)

    def _draw_procedural(self, canvas: tk.Canvas, x: float, y: float) -> None:
        dead = self.state == AvatarState.DEAD
        attack = self.state == AvatarState.ATTACK
        walk = self.state == AvatarState.WALK
        bob = 0 if dead else 2 * math.sin(time.time() * (9 if walk else 4) + self.frame)
        body_color = "#555555" if dead else ("#ff4444" if attack else self.accent)
        head_color = "#777777" if dead else self.color

        canvas.create_oval(x - 12, y - 31 + bob, x + 12, y - 7 + bob, fill=head_color, outline="#ffffff", width=1)
        canvas.create_rectangle(x - 14, y - 8 + bob, x + 14, y + 23 + bob, fill=body_color, outline=head_color, width=2)
        eye_y = y - 22 + bob
        canvas.create_rectangle(x - 7, eye_y, x - 3, eye_y + 3, fill="#020204", outline="")
        canvas.create_rectangle(x + 3, eye_y, x + 7, eye_y + 3, fill="#020204", outline="")
        arm = 22 if attack else 12
        canvas.create_line(x - 14, y + 2 + bob, x - arm, y + 13 + bob, fill=head_color, width=3)
        canvas.create_line(x + 14, y + 2 + bob, x + arm, y + 13 + bob, fill=head_color, width=3)
        leg = 5 if walk and self.frame % 2 else 0
        canvas.create_line(x - 7, y + 23 + bob, x - 11 - leg, y + 33 + bob, fill=head_color, width=3)
        canvas.create_line(x + 7, y + 23 + bob, x + 11 + leg, y + 33 + bob, fill=head_color, width=3)
        canvas.create_text(x, y - 47, text=self.name, fill=head_color, font=("Courier New", 8, "bold"))

    def draw_stat_bars(self, canvas: tk.Canvas, x: float, y: float) -> None:
        stats = [(self.health, "#ff3333"), (self.energy, "#33ccff"), (self.mood, "#ffcc00"), (self.hunger, "#ff8800")]
        for i, (value, color) in enumerate(stats):
            top = y + i * 5
            canvas.create_rectangle(x - 24, top, x + 24, top + 3, fill="#101820", outline="")
            canvas.create_rectangle(x - 24, top, x - 24 + 48 * (value / 100.0), top + 3, fill=color, outline="")

    def draw_inventory(self, canvas: tk.Canvas, x: float, y: float) -> None:
        for i, slot in enumerate(self.inventory):
            left = x + i * 18
            canvas.create_rectangle(left, y, left + 14, y + 14, fill="#222222", outline="#666666")
            if not slot.is_empty():
                canvas.create_text(left + 7, y + 7, text=slot.label(), fill="#ffffff", font=("Courier New", 7, "bold"))


class World:
    def __init__(self, width: int = 16, height: int = 16, *, tile_size: int = TILE_SIZE) -> None:
        self.width = width
        self.height = height
        self.tile_size = tile_size
        self.tiles: list[list[Tile]] = [[Tile(TileType.FLOOR) for _ in range(width)] for _ in range(height)]
        self.rooms: dict[str, list[list[Tile]]] = {}
        self.current_room = "start"
        self.collision: list[TileRect] = []
        self.portals: list[PortalTrigger] = []

    def add_room(self, name: str, tiles: list[list[Tile]]) -> None:
        self.rooms[name] = tiles

    def load_room(self, name: str) -> bool:
        if name not in self.rooms:
            return False
        self.tiles = self.rooms[name]
        self.current_room = name
        return True

    def generate_sample_world(self) -> None:
        for y in range(self.height):
            for x in range(self.width):
                if x == 0 or y == 0 or x == self.width - 1 or y == self.height - 1:
                    self.tiles[y][x] = Tile(TileType.WALL)
        for y in range(3, min(7, self.height - 1)):
            for x in range(3, min(7, self.width - 1)):
                self.tiles[y][x] = Tile(TileType.WATER)
        if self.width > 10 and self.height > 10:
            self.tiles[10][10] = Tile(TileType.PORTAL, destination="portal")

    def add_wall(self, x: float, y: float, w: float, h: float) -> None:
        self.collision.append(TileRect(x, y, w, h))

    def add_room_walls(self, x: float, y: float, w: float, h: float, *, doorways: Iterable[TileRect] = ()) -> None:
        walls = [
            TileRect(x, y, w, 10),
            TileRect(x, y + h - 10, w, 10),
            TileRect(x, y, 10, h),
            TileRect(x + w - 10, y, 10, h),
        ]
        doors = list(doorways)
        for wall in walls:
            if not any(wall.intersects(door) for door in doors):
                self.collision.append(wall)

    def add_portal(self, key: str, title: str, x: float, y: float, radius: float, callback: Callable[[str], None] | None = None) -> None:
        self.portals.append(PortalTrigger(key, title, x, y, radius, callback))

    def collides(self, rect: TileRect) -> bool:
        pixel_width = self.width * self.tile_size
        pixel_height = self.height * self.tile_size
        if rect.x < 0 or rect.y < 0 or rect.x + rect.w > pixel_width or rect.y + rect.h > pixel_height:
            return True
        tile_left = max(0, int(rect.x // self.tile_size))
        tile_right = min(self.width - 1, int((rect.x + rect.w) // self.tile_size))
        tile_top = max(0, int(rect.y // self.tile_size))
        tile_bottom = min(self.height - 1, int((rect.y + rect.h) // self.tile_size))
        for ty in range(tile_top, tile_bottom + 1):
            for tx in range(tile_left, tile_right + 1):
                if self.tiles[ty][tx].type == TileType.WALL:
                    return True
        return any(rect.intersects(wall) for wall in self.collision)

    def portal_at(self, x: float, y: float) -> PortalTrigger | None:
        for portal in self.portals:
            if math.hypot(portal.x - x, portal.y - y) <= portal.radius:
                return portal
        tx = int(x // self.tile_size)
        ty = int(y // self.tile_size)
        if 0 <= tx < self.width and 0 <= ty < self.height:
            tile = self.tiles[ty][tx]
            if tile.type == TileType.PORTAL and tile.destination:
                return PortalTrigger(tile.destination, tile.destination, x, y, self.tile_size / 2)
        return None

    def nearest_portal(self, x: float, y: float) -> PortalTrigger | None:
        if not self.portals:
            return None
        return min(self.portals, key=lambda portal: math.hypot(portal.x - x, portal.y - y))
