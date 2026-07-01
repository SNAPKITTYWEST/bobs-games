"""KITTYVERSE - Unified Sovereign Game Hub built on Enzoi.
SPDX-License-Identifier: MIT
Copyright (c) 2026 SnapKitty Collective

Run: python kittyverse.py

Windows friendly: pure Python stdlib + tkinter. No packages.

Controls:
  Choose avatar: ARIA / CARTO / FLUX
  WASD / Arrow keys  Walk the Enzoi avatar
  Enter / E          Use nearby portal
  Mouse click        Click a portal or civilization map cell
  Space              Seal current identity + hub state
  Q / Escape         Quit
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import subprocess
import sys
import time
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path

from enzoi import Avatar, InputHandler, Tile, TileType, World

ROOT = Path(__file__).resolve().parent
IDENTITY_FILE = ROOT / "kittyverse_identity.json"

BG = "#020204"
PANEL = "#071017"
PANEL_2 = "#0b131c"
GRID = "#122531"
GOLD = "#ffd700"
TEAL = "#00d4cc"
GREEN = "#00ff88"
RED = "#ff4444"
MAGENTA = "#d36bff"
WHITE = "#e8fbff"
MUTED = "#73808a"

TILE_SIZE = 32
GRID_COLS = 30
GRID_ROWS = 22
HUD_HEIGHT = 60
PICKER_W = 220
PICKER_H = 120

HUB_W = GRID_COLS * TILE_SIZE
HUB_H = GRID_ROWS * TILE_SIZE + HUD_HEIGHT
SIDEBAR_W = 340
TICK_MS = 33
CIV_TICK_MS = 1500

BLOCK_TYPES: dict[str, dict] = {
    "WOOD": {"color": (139, 90, 43), "label": "W"},
    "STONE": {"color": (120, 120, 120), "label": "S"},
    "GLASS": {"color": (173, 216, 230), "label": "G"},
    "SOVEREIGN": {"color": (255, 215, 0), "label": "Ω"},
}

WORLD_STRUCTURES: list[dict] = [
    {
        "name": "TOWN_HALL",
        "origin": (3, 3),
        "layout": [
            *[(dx, 0, "STONE") for dx in range(5)],
            *[(dx, 3, "STONE") for dx in range(5)],
            *[(0, dy, "STONE") for dy in range(1, 3)],
            *[(4, dy, "STONE") for dy in range(1, 3)],
            (2, 0, "SOVEREIGN"),
        ],
    },
    {
        "name": "MARKET",
        "origin": (12, 3),
        "layout": [
            *[(dx, 0, "WOOD") for dx in range(4)],
            *[(dx, 3, "WOOD") for dx in range(4)],
            *[(0, dy, "WOOD") for dy in range(1, 3)],
            *[(3, dy, "WOOD") for dy in range(1, 3)],
            (1, 1, "GLASS"),
        ],
    },
    {
        "name": "SOVEREIGN_TOWER",
        "origin": (7, 8),
        "layout": [
            *[(dx, dy, "STONE") for dx in range(3) for dy in range(3)],
            *[(1, dy, "SOVEREIGN") for dy in range(3, 7)],
            (1, 7, "GLASS"),
        ],
    },
]


@dataclass
class PortalSpec:
    key: str
    title: str
    path: Path
    x: float
    y: float
    radius: float
    color: str
    description: str
    launches: int = 0


@dataclass
class Block:
    block_type: str
    tile_x: int
    tile_y: int
    timestamp: float
    worm_seal: str
    placed_by: str


@dataclass
class BuildState:
    active: bool = False
    picker_open: bool = False
    picker_origin: tuple[int, int] = (0, 0)
    selected_block: str = "WOOD"


@dataclass
class NPCAgent:
    name: str
    color: tuple[int, int, int]
    tile_x: float
    tile_y: float
    target_tile: tuple[int, int]
    speed: float
    pause_timer: float
    state: str


NPC_DEFS: list[dict] = [
    {"name": "ARIA", "color": (255, 105, 180), "speed": 2.5},
    {"name": "CARTO", "color": (64, 224, 208), "speed": 2.0},
    {"name": "FLUX", "color": (148, 0, 211), "speed": 3.0},
]


@dataclass
class Faction:
    name: str
    color: str
    resources: int = 20
    influence: int = 0


@dataclass
class CivAgent:
    name: str
    faction: str
    x: int
    y: int
    task: str = "survey"
    mood: str = "steady"
    last_action: str = ""


class WormChain:
    def __init__(self) -> None:
        self.head = "GENESIS"
        self.events: list[dict[str, str]] = []

    def seal(self, event_type: str, payload: str) -> str:
        stamp = f"{time.time():.3f}"
        digest = hashlib.sha256(f"{self.head}|{event_type}|{payload}|{stamp}".encode("utf-8")).hexdigest()
        self.head = digest
        self.events.append({"type": event_type, "payload": payload, "timestamp": stamp, "seal": digest})
        self.events = self.events[-80:]
        return digest


class BobOracle:
    """Local BOB protocol: every action is EVIDENCE or SILENCE."""

    def __init__(self) -> None:
        self.last_portal_launch = 0.0
        self.verdicts: list[dict[str, str | float]] = []

    def adjudicate(self, action: str, context: str) -> dict[str, str | float]:
        now = time.time()
        verdict = "EVIDENCE"
        score = 0.84
        reason = "Action matches Kittyverse Trust Deed."

        if action == "portal_launch" and now - self.last_portal_launch < 1.2:
            verdict, score, reason = "SILENCE", 0.22, "Portal launch throttled to prevent duplicate execution."
        elif action == "portal_launch" and "NO_IDENTITY" in context:
            verdict, score, reason = "SILENCE", 0.12, "No WORM-sealed avatar identity."
        elif action == "map_claim" and "neutral" not in context and random.random() < 0.18:
            verdict, score, reason = "SILENCE", 0.34, "Territory conflict requires CARTO review."
        elif action == "identity":
            score, reason = 0.96, "Avatar identity is WORM sealed."
        elif action == "hub_seal":
            score, reason = 0.91, "Hub state can be sealed."

        if action == "portal_launch" and verdict == "EVIDENCE":
            self.last_portal_launch = now

        result = {"verdict": verdict, "score": score, "reason": reason, "action": action, "context": context}
        self.verdicts.insert(0, result)
        self.verdicts = self.verdicts[:14]
        return result


class KittyverseApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("KITTYVERSE - Enzoi Sovereign Game Civilization")
        self.root.configure(bg=BG)
        self.root.minsize(1120, 720)

        self.worm = WormChain()
        self.bob = BobOracle()
        self.input = InputHandler(root)
        self.avatar: Avatar | None = None
        self.avatar_profile: dict[str, str] | None = None
        self.frame = 0
        self.last_time = time.time()
        self.message = "Choose an avatar. WORM identity must exist before a portal opens."
        self.running_children: list[subprocess.Popen] = []

        self.portals = {
            "SIMS": PortalSpec(
                "SIMS",
                "BOB SIMS",
                ROOT / "sims" / "bob_sims.py",
                24 * TILE_SIZE,
                5 * TILE_SIZE,
                46,
                TEAL,
                "NPC needs, rooms, WORM state.",
            ),
            "SNAKE": PortalSpec(
                "SNAKE",
                "BOB SNAKE",
                ROOT / "snake" / "bob_snake.py",
                24 * TILE_SIZE,
                16 * TILE_SIZE,
                46,
                GOLD,
                "Gold snake, red food, sealed game over.",
            ),
        }

        self.world = World(GRID_COLS, GRID_ROWS, tile_size=TILE_SIZE)
        self.buildings: dict[tuple[int, int], Block] = {}
        self.worm_vault: list[dict] = []
        self.build_state = BuildState()
        self.npcs = self._spawn_npcs()
        self._load_world_structures()
        for portal in self.portals.values():
            self.world.add_portal(portal.key, portal.title, portal.x, portal.y, portal.radius)

        self.factions = {
            "CARTO": Faction("CARTO", GOLD, resources=28),
            "FORGE": Faction("FORGE", "#ff8c1a", resources=22),
            "FLUX": Faction("FLUX", TEAL, resources=34),
            "NOVA": Faction("NOVA", MAGENTA, resources=18),
        }
        self.civ_w = 12
        self.civ_h = 8
        self.territory: list[list[str]] = [["neutral" for _ in range(self.civ_w)] for _ in range(self.civ_h)]
        self.agents = [
            CivAgent("CARTO", "CARTO", 2, 2, "govern"),
            CivAgent("FORGE", "FORGE", 8, 2, "build"),
            CivAgent("FLUX", "FLUX", 2, 6, "trade"),
            CivAgent("NOVA", "NOVA", 9, 6, "paint"),
            CivAgent("PHANTOM", "CARTO", 5, 4, "audit"),
            CivAgent("ROBOB", "FLUX", 6, 4, "oracle"),
        ]
        for agent in self.agents:
            self.territory[agent.y][agent.x] = agent.faction

        self._build_ui()
        self._bind()
        self.worm.seal("BOOT", "KITTYVERSE Enzoi hub initialized")
        self._log_verdict(self.bob.adjudicate("hub_seal", "boot state"))
        self._draw()
        self._loop()
        self._civ_loop()

    def _spawn_npcs(self) -> list[NPCAgent]:
        spawns = [(10, 16), (17, 12), (21, 8)]
        npcs: list[NPCAgent] = []
        for idx, definition in enumerate(NPC_DEFS):
            tile = spawns[idx]
            npcs.append(
                NPCAgent(
                    name=definition["name"],
                    color=definition["color"],
                    tile_x=float(tile[0]),
                    tile_y=float(tile[1]),
                    target_tile=tile,
                    speed=definition["speed"],
                    pause_timer=random.uniform(0.3, 1.2),
                    state="PAUSING",
                )
            )
        return npcs

    def _rgb(self, color: tuple[int, int, int]) -> str:
        return f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"

    def _tile_center(self, tile_x: float, tile_y: float) -> tuple[float, float]:
        return tile_x * TILE_SIZE + TILE_SIZE / 2, tile_y * TILE_SIZE + TILE_SIZE / 2

    def _tile_from_point(self, px: float, py: float) -> tuple[int, int]:
        return int(px // TILE_SIZE), int(py // TILE_SIZE)

    def _is_buildable_tile(self, tile_x: int, tile_y: int) -> bool:
        if not (0 <= tile_x < GRID_COLS and 0 <= tile_y < GRID_ROWS):
            return False
        if (tile_x, tile_y) in self.buildings:
            return False
        for portal in self.portals.values():
            pcx, pcy = self._tile_from_point(portal.x, portal.y)
            if abs(pcx - tile_x) <= 1 and abs(pcy - tile_y) <= 1:
                return False
        if self.avatar and self.avatar.tile_x == tile_x and self.avatar.tile_y == tile_y:
            return False
        return self.world.tiles[tile_y][tile_x].type != TileType.WALL

    def _seal_block(self, block_type: str, tile_x: int, tile_y: int, placed_by: str) -> tuple[float, str]:
        ts = time.time()
        seal = hashlib.sha256(f"{self.worm.head}|{block_type}|{tile_x},{tile_y}|{placed_by}|{ts:.6f}".encode("utf-8")).hexdigest()
        self.worm_vault.append({"seal": seal, "block_type": block_type, "pos": (tile_x, tile_y), "ts": ts})
        self.worm.seal("BLOCK_PLACE", f"{block_type}|{tile_x},{tile_y}|{placed_by}|{seal}")
        return ts, seal

    def _place_block(self, tile_x: int, tile_y: int, block_type: str, placed_by: str = "PLAYER") -> bool:
        if not self._is_buildable_tile(tile_x, tile_y):
            return False
        ts, seal = self._seal_block(block_type, tile_x, tile_y, placed_by)
        self.buildings[(tile_x, tile_y)] = Block(block_type, tile_x, tile_y, ts, seal, placed_by)
        self.world.tiles[tile_y][tile_x] = Tile(TileType.WALL, color=self._rgb(BLOCK_TYPES[block_type]["color"]))
        return True

    def _load_world_structures(self) -> None:
        for structure in WORLD_STRUCTURES:
            origin_x, origin_y = structure["origin"]
            for dx, dy, block_type in structure["layout"]:
                self._place_block(origin_x + dx, origin_y + dy, block_type, "WORLD_INIT")

    def _toggle_build_mode(self) -> None:
        self.build_state.active = not self.build_state.active
        self.build_state.picker_open = self.build_state.active
        if self.avatar:
            self.build_state.picker_origin = (int(self.avatar.x + 28), int(self.avatar.y - 28))
        self.message = "BUILD MODE: click a tile to WORM-seal a block." if self.build_state.active else "Build mode closed."

    def _select_block(self, block_type: str) -> None:
        if block_type in BLOCK_TYPES:
            self.build_state.selected_block = block_type
            self.message = f"Selected block: {block_type}"

    def _random_free_tile(self) -> tuple[int, int]:
        for _ in range(120):
            tile = (random.randint(1, GRID_COLS - 2), random.randint(1, GRID_ROWS - 2))
            if self._is_walkable_for_npc(tile[0], tile[1]):
                return tile
        return 1, 1

    def _is_walkable_for_npc(self, tile_x: int, tile_y: int) -> bool:
        if not (0 <= tile_x < GRID_COLS and 0 <= tile_y < GRID_ROWS):
            return False
        return self.world.tiles[tile_y][tile_x].type != TileType.WALL

    def _update_npcs(self, dt: float) -> None:
        for npc in self.npcs:
            if npc.state == "PAUSING":
                npc.pause_timer -= dt
                if npc.pause_timer <= 0:
                    npc.target_tile = self._random_free_tile()
                    npc.state = "WALKING"
                continue
            tx, ty = npc.target_tile
            dx = tx - npc.tile_x
            dy = ty - npc.tile_y
            dist = math.hypot(dx, dy)
            if dist < 0.05:
                npc.tile_x = float(tx)
                npc.tile_y = float(ty)
                npc.pause_timer = random.uniform(0.4, 1.6)
                npc.state = "PAUSING"
                continue
            step = min(dist, npc.speed * dt)
            npc.tile_x += dx / dist * step
            npc.tile_y += dy / dist * step

    def _build_ui(self) -> None:
        self.shell = tk.Frame(self.root, bg=BG)
        self.shell.pack(fill=tk.BOTH, expand=True)

        self.main = tk.Frame(self.shell, bg=BG)
        self.main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.sidebar = tk.Frame(self.shell, bg=PANEL, width=SIDEBAR_W)
        self.sidebar.pack(side=tk.RIGHT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        self.canvas = tk.Canvas(self.main, width=HUB_W, height=HUB_H, bg=BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 6))
        self.canvas.bind("<Button-1>", self._on_canvas_click)

        self.status = tk.Label(self.main, text="", bg=BG, fg=MUTED, anchor="w", justify=tk.LEFT, font=("Courier New", 9))
        self.status.pack(fill=tk.X, padx=14, pady=(0, 10))

        self._side_label("KITTYVERSE", GOLD, 18, bold=True).pack(anchor="w", padx=14, pady=(14, 0))
        self._side_label("ENZOI SANDBOX RUNTIME", TEAL, 9, bold=True).pack(anchor="w", padx=14, pady=(0, 10))

        self.avatar_panel = tk.Frame(self.sidebar, bg=PANEL)
        self.avatar_panel.pack(fill=tk.X, padx=14, pady=(0, 10))
        self._rebuild_avatar_panel()

        self.verdict_box = tk.Text(self.sidebar, height=11, bg="#03080c", fg=WHITE, insertbackground=WHITE, relief=tk.FLAT, font=("Courier New", 8), wrap=tk.WORD)
        self.verdict_box.pack(fill=tk.X, padx=14, pady=(0, 12))
        self.verdict_box.configure(state=tk.DISABLED)

        self._side_label("CIVILIZATION MAP", GOLD, 10, bold=True).pack(anchor="w", padx=14, pady=(0, 6))
        self.civ_canvas = tk.Canvas(self.sidebar, width=SIDEBAR_W - 28, height=205, bg="#03080c", highlightthickness=1, highlightbackground=GRID)
        self.civ_canvas.pack(padx=14, pady=(0, 12))
        self.civ_canvas.bind("<Button-1>", self._on_civ_click)

        self.agent_box = tk.Text(self.sidebar, height=12, bg=PANEL, fg=WHITE, relief=tk.FLAT, font=("Courier New", 8), wrap=tk.WORD)
        self.agent_box.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 12))
        self.agent_box.configure(state=tk.DISABLED)

        buttons = tk.Frame(self.sidebar, bg=PANEL)
        buttons.pack(fill=tk.X, padx=14, pady=(0, 14))
        for label, command in (
            ("SIMS", lambda: self._launch_portal("SIMS")),
            ("SNAKE", lambda: self._launch_portal("SNAKE")),
            ("Seal", self._seal_hub),
        ):
            tk.Button(buttons, text=label, command=command, bg="#15212b", fg=GOLD, activebackground="#203342", activeforeground=WHITE, relief=tk.FLAT, font=("Courier New", 8, "bold")).pack(side=tk.LEFT, padx=(0, 6))

    def _side_label(self, text: str, fg: str, size: int, bold: bool = False) -> tk.Label:
        return tk.Label(self.sidebar, text=text, bg=PANEL, fg=fg, font=("Courier New", size, "bold" if bold else "normal"))

    def _rebuild_avatar_panel(self) -> None:
        for child in self.avatar_panel.winfo_children():
            child.destroy()
        tk.Label(self.avatar_panel, text="AVATAR IDENTITY", bg=PANEL, fg=GOLD, font=("Courier New", 10, "bold")).pack(anchor="w")
        if not self.avatar:
            tk.Label(self.avatar_panel, text="Pick a BOB SIMS avatar. Identity is sealed before entering portals.", bg=PANEL, fg=MUTED, justify=tk.LEFT, wraplength=300, font=("Courier New", 8)).pack(anchor="w", pady=(4, 8))
            for name, color, accent, faction in (
                ("ARIA", "#ffd700", "#4aa3ff", "NOVA"),
                ("CARTO", "#ffd700", "#1a2730", "CARTO"),
                ("FLUX", "#00d4cc", "#182a2f", "FLUX"),
            ):
                tk.Button(
                    self.avatar_panel,
                    text=f"{name}  [{faction}]",
                    command=lambda n=name, c=color, a=accent, f=faction: self._select_avatar(n, c, a, f),
                    bg="#15212b",
                    fg=color,
                    activebackground="#203342",
                    activeforeground=WHITE,
                    relief=tk.FLAT,
                    font=("Courier New", 9, "bold"),
                ).pack(fill=tk.X, pady=2)
        else:
            tk.Label(self.avatar_panel, text=f"{self.avatar.name} [{self.avatar_profile['faction']}]", bg=PANEL, fg=self.avatar.color, font=("Courier New", 11, "bold")).pack(anchor="w", pady=(4, 0))
            tk.Label(self.avatar_panel, text=f"SEAL: {self.avatar.identity_seal[:28]}...", bg=PANEL, fg=GREEN, justify=tk.LEFT, wraplength=310, font=("Courier New", 8)).pack(anchor="w", pady=(2, 0))
            tk.Label(self.avatar_panel, text="Inventory: ID, WORM, Portal Key", bg=PANEL, fg=MUTED, font=("Courier New", 8)).pack(anchor="w", pady=(4, 0))

    def _bind(self) -> None:
        self.root.bind("<Return>", lambda _event: self._use_nearest_portal())
        self.root.bind("e", lambda _event: self._use_nearest_portal())
        self.root.bind("E", lambda _event: self._use_nearest_portal())
        self.root.bind("b", lambda _event: self._toggle_build_mode())
        self.root.bind("B", lambda _event: self._toggle_build_mode())
        for index, block_type in enumerate(BLOCK_TYPES, start=1):
            self.root.bind(str(index), lambda _event, bt=block_type: self._select_block(bt))
        self.root.bind("<space>", lambda _event: self._seal_hub())
        self.root.bind("q", lambda _event: self._quit())
        self.root.bind("Q", lambda _event: self._quit())
        self.root.bind("<Escape>", lambda _event: self._quit())
        self.root.protocol("WM_DELETE_WINDOW", self._quit)

    def _select_avatar(self, name: str, color: str, accent: str, faction: str) -> None:
        self.avatar = Avatar(name=name, job=faction, x=2.5 * TILE_SIZE, y=2.5 * TILE_SIZE, color=color, accent=accent, speed=180.0)
        enzoi_seal = self.avatar.identity_seal
        chain_seal = self.worm.seal("IDENTITY", f"{name}|{faction}|KITTYVERSE|{enzoi_seal}")
        self.avatar.add_item("Identity", 1, "key")
        self.avatar.add_item("WORM", 1, "seal")
        self.avatar.add_item("Portal Key", 1, "key")
        self.avatar_profile = {"name": name, "faction": faction, "seal": enzoi_seal, "chain_seal": chain_seal}
        IDENTITY_FILE.write_text(json.dumps(self.avatar_profile, indent=2), encoding="utf-8")
        verdict = self.bob.adjudicate("identity", f"{name}|{faction}")
        self._log_verdict(verdict)
        self.message = f"{name} entered KITTYVERSE. Enzoi identity sealed: {enzoi_seal[:18]}..."
        self._rebuild_avatar_panel()

    def _loop(self) -> None:
        now = time.time()
        dt = min(0.05, now - self.last_time)
        self.last_time = now
        self.frame += 1
        if self.avatar:
            dx, dy = self.input.axis()
            self.avatar.set_velocity(dx, dy)
            self.avatar.update(dt, self.world)
        self._update_npcs(dt)
        self._draw()
        self.root.after(TICK_MS, self._loop)

    def _civ_loop(self) -> None:
        self._advance_civilization()
        self._draw_civ()
        self._draw_agents()
        self.root.after(CIV_TICK_MS, self._civ_loop)

    def _draw(self) -> None:
        c = self.canvas
        c.delete("all")
        c._enzoi_refs = []
        width = max(HUB_W, c.winfo_width())
        height = max(HUB_H, c.winfo_height())
        sx = width / HUB_W
        sy = height / HUB_H

        def x(v: float) -> float:
            return v * sx

        def y(v: float) -> float:
            return v * sy

        c.create_rectangle(0, 0, width, height, fill=BG, outline="")
        for gx in range(0, HUB_W, 40):
            c.create_line(x(gx), 0, x(gx), height, fill="#071923")
        for gy in range(0, HUB_H, 40):
            c.create_line(0, y(gy), width, y(gy), fill="#071923")

        self._draw_room(c, x, y, 40, 58, 300, 160, "BOB ENGINE HALL", TEAL)
        self._draw_room(c, x, y, 380, 72, 300, 160, "SIMS PORTAL BAY", self.portals["SIMS"].color)
        self._draw_room(c, x, y, 380, 312, 300, 160, "SNAKE PORTAL BAY", self.portals["SNAKE"].color)
        self._draw_room(c, x, y, 44, 286, 300, 174, "VORTEX CIV MAP", MAGENTA)
        c.create_line(x(300), y(135), x(380), y(152), fill=GRID, width=14)
        c.create_line(x(300), y(360), x(380), y(392), fill=GRID, width=14)
        c.create_line(x(196), y(218), x(196), y(286), fill=GRID, width=14)

        self._draw_buildings(c, x, y)

        for wall in self.world.collision:
            c.create_rectangle(x(wall.x), y(wall.y), x(wall.x + wall.w), y(wall.y + wall.h), outline="#1d3a45", fill="#08131a")

        for portal in self.portals.values():
            pulse = 1 + math.sin(self.frame * 0.12 + portal.launches) * 0.08
            r = portal.radius * pulse
            c.create_oval(x(portal.x - r), y(portal.y - r), x(portal.x + r), y(portal.y + r), outline=portal.color, width=4)
            c.create_oval(x(portal.x - r * 0.58), y(portal.y - r * 0.58), x(portal.x + r * 0.58), y(portal.y + r * 0.58), fill="#02070a", outline=portal.color, width=1)
            c.create_text(x(portal.x), y(portal.y - 72), text=portal.title, fill=portal.color, font=("Courier New", 12, "bold"))
            c.create_text(x(portal.x), y(portal.y + 72), text=portal.description, fill=MUTED, font=("Courier New", 8))

        self._draw_npcs(c, x, y)

        if self.avatar:
            self.avatar.draw(c, scale_x=sx, scale_y=sy)
        else:
            c.create_text(x(370), y(255), text="SELECT ARIA / CARTO / FLUX TO ENTER", fill=GOLD, font=("Courier New", 18, "bold"))

        c.create_text(x(58), y(34), text="KITTYVERSE HUB", fill=GOLD, font=("Courier New", 18, "bold"), anchor="w")
        c.create_text(x(58), y(512), text=self.message, fill=WHITE, font=("Courier New", 9), anchor="w")
        self._draw_build_picker(c, x, y)

        nearest = self._nearest_portal()
        in_range = bool(self.avatar and nearest and self._dist_to_portal(nearest) < nearest.radius + 28)
        hint = "ENTER/E use portal" if in_range else "WASD move | click portals | SPACE seal"
        avatar_line = "NO_IDENTITY" if not self.avatar else f"{self.avatar.name} ENERGY:{self.avatar.energy:05.1f} MOOD:{self.avatar.mood:05.1f}"
        build_line = f"BUILD:{'ON' if self.build_state.active else 'OFF'} {self.build_state.selected_block} BLOCKS:{len(self.buildings)} VAULT:{len(self.worm_vault)}"
        self.status.config(text=f"{hint}   B toggle build | 1-4 block   {avatar_line}   {build_line}   WORM:{self.worm.head[:24]}...")

    def _draw_room(self, canvas: tk.Canvas, sx, sy, x: int, y: int, w: int, h: int, label: str, color: str) -> None:
        canvas.create_rectangle(sx(x), sy(y), sx(x + w), sy(y + h), fill=PANEL_2, outline=color, width=2)
        canvas.create_text(sx(x + 12), sy(y + 12), text=label, fill=color, font=("Courier New", 9, "bold"), anchor="nw")

    def _draw_buildings(self, canvas: tk.Canvas, sx, sy) -> None:
        for block in self.buildings.values():
            meta = BLOCK_TYPES[block.block_type]
            color = self._rgb(meta["color"])
            x0 = block.tile_x * TILE_SIZE
            y0 = block.tile_y * TILE_SIZE
            canvas.create_rectangle(sx(x0 + 2), sy(y0 + 2), sx(x0 + TILE_SIZE - 2), sy(y0 + TILE_SIZE - 2), fill=color, outline="#050507", width=2)
            canvas.create_line(sx(x0 + 5), sy(y0 + 5), sx(x0 + TILE_SIZE - 5), sy(y0 + 5), fill="#ffffff")
            canvas.create_text(sx(x0 + TILE_SIZE / 2), sy(y0 + TILE_SIZE / 2), text=meta["label"], fill=BG, font=("Courier New", 10, "bold"))
            if block.placed_by == "PLAYER":
                canvas.create_rectangle(sx(x0 + 6), sy(y0 + TILE_SIZE - 9), sx(x0 + TILE_SIZE - 6), sy(y0 + TILE_SIZE - 6), fill=GREEN, outline="")

    def _draw_npcs(self, canvas: tk.Canvas, sx, sy) -> None:
        for npc in self.npcs:
            px, py = self._tile_center(npc.tile_x, npc.tile_y)
            color = self._rgb(npc.color)
            bob = 2 * math.sin(self.frame * 0.17 + npc.tile_x)
            canvas.create_oval(sx(px - 10), sy(py - 16 + bob), sx(px + 10), sy(py + 4 + bob), fill=color, outline=WHITE)
            canvas.create_rectangle(sx(px - 11), sy(py + 1 + bob), sx(px + 11), sy(py + 22 + bob), fill=PANEL_2, outline=color, width=2)
            canvas.create_text(sx(px), sy(py - 24), text=npc.name, fill=color, font=("Courier New", 7, "bold"))
            canvas.create_text(sx(px), sy(py + 32), text=npc.state, fill=MUTED, font=("Courier New", 6))

    def _draw_build_picker(self, canvas: tk.Canvas, sx, sy) -> None:
        if not self.build_state.picker_open:
            return
        origin_x, origin_y = self.build_state.picker_origin
        origin_x = max(16, min(HUB_W - PICKER_W - 16, origin_x))
        origin_y = max(48, min(HUB_H - HUD_HEIGHT - PICKER_H - 16, origin_y))
        canvas.create_rectangle(sx(origin_x), sy(origin_y), sx(origin_x + PICKER_W), sy(origin_y + PICKER_H), fill="#050b10", outline=GOLD, width=2)
        canvas.create_text(sx(origin_x + 12), sy(origin_y + 12), text="BUILD PICKER", fill=GOLD, font=("Courier New", 9, "bold"), anchor="nw")
        for index, block_type in enumerate(BLOCK_TYPES):
            meta = BLOCK_TYPES[block_type]
            bx = origin_x + 16 + index * 50
            by = origin_y + 42
            selected = block_type == self.build_state.selected_block
            canvas.create_rectangle(sx(bx), sy(by), sx(bx + 38), sy(by + 38), fill=self._rgb(meta["color"]), outline=GREEN if selected else "#35505c", width=3 if selected else 1)
            canvas.create_text(sx(bx + 19), sy(by + 19), text=meta["label"], fill=BG, font=("Courier New", 12, "bold"))
            canvas.create_text(sx(bx + 19), sy(by + 52), text=f"{index + 1}", fill=WHITE, font=("Courier New", 8, "bold"))
        canvas.create_text(sx(origin_x + 12), sy(origin_y + PICKER_H - 18), text="Click tile to place · B close", fill=MUTED, font=("Courier New", 8), anchor="w")

    def _draw_civ(self) -> None:
        c = self.civ_canvas
        c.delete("all")
        w = int(c["width"])
        h = int(c["height"])
        cell = min(w / self.civ_w, h / self.civ_h)
        ox = (w - cell * self.civ_w) / 2
        oy = (h - cell * self.civ_h) / 2
        for yy in range(self.civ_h):
            for xx in range(self.civ_w):
                owner = self.territory[yy][xx]
                color = "#091219" if owner == "neutral" else self.factions[owner].color
                c.create_rectangle(ox + xx * cell, oy + yy * cell, ox + (xx + 1) * cell, oy + (yy + 1) * cell, fill=color, outline="#102530")
                if owner != "neutral":
                    c.create_text(ox + xx * cell + cell / 2, oy + yy * cell + cell / 2, text=owner[0], fill=BG, font=("Courier New", 8, "bold"))
        for agent in self.agents:
            c.create_oval(ox + agent.x * cell + 4, oy + agent.y * cell + 4, ox + (agent.x + 1) * cell - 4, oy + (agent.y + 1) * cell - 4, fill=WHITE, outline=self.factions[agent.faction].color, width=2)
            c.create_text(ox + agent.x * cell + cell / 2, oy + agent.y * cell + cell / 2, text=agent.name[0], fill=BG, font=("Courier New", 8, "bold"))

    def _draw_agents(self) -> None:
        self.agent_box.configure(state=tk.NORMAL)
        self.agent_box.delete("1.0", tk.END)
        for faction in self.factions.values():
            self.agent_box.insert(tk.END, f"{faction.name:<6} INF:{faction.influence:02d} RES:{faction.resources:03d}\n")
        self.agent_box.insert(tk.END, "\n")
        for agent in self.agents:
            self.agent_box.insert(tk.END, f"{agent.name:<7} {agent.faction:<6} {agent.task:<7} ({agent.x},{agent.y})\n")
            if agent.last_action:
                self.agent_box.insert(tk.END, f"  {agent.last_action}\n")
        self.agent_box.configure(state=tk.DISABLED)

    def _advance_civilization(self) -> None:
        agent = random.choice(self.agents)
        dx, dy = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1), (0, 0)])
        agent.x = max(0, min(self.civ_w - 1, agent.x + dx))
        agent.y = max(0, min(self.civ_h - 1, agent.y + dy))
        owner = self.territory[agent.y][agent.x]
        context = "neutral tile" if owner == "neutral" else f"{owner} tile"
        verdict = self.bob.adjudicate("map_claim", context)
        if verdict["verdict"] == "EVIDENCE":
            previous = self.territory[agent.y][agent.x]
            self.territory[agent.y][agent.x] = agent.faction
            self.factions[agent.faction].influence += 1
            self.factions[agent.faction].resources += random.randint(1, 4)
            agent.task = random.choice(["build", "trade", "audit", "paint", "govern"])
            agent.mood = "active"
            agent.last_action = f"claimed {previous}->{agent.faction}"
            seal = self.worm.seal("CIV_CLAIM", f"{agent.name}|{agent.faction}|{agent.x},{agent.y}")
            self.message = f"{agent.name} claimed tile ({agent.x},{agent.y}) | {seal[:12]}..."
        else:
            agent.task = "review"
            agent.mood = "blocked"
            agent.last_action = "SILENCE: CARTO review"
            self.worm.seal("CIV_SILENCE", f"{agent.name}|{agent.x},{agent.y}")
            self.message = f"BOB blocked {agent.name}: {verdict['reason']}"
        self._log_verdict(verdict)

    def _on_canvas_click(self, event: tk.Event) -> None:
        width = max(HUB_W, self.canvas.winfo_width())
        height = max(HUB_H, self.canvas.winfo_height())
        px = event.x / (width / HUB_W)
        py = event.y / (height / HUB_H)
        if self.build_state.active:
            if self._handle_picker_click(px, py):
                return
            tile_x, tile_y = self._tile_from_point(px, py)
            context = f"{self.build_state.selected_block}|{tile_x},{tile_y}"
            verdict = self.bob.adjudicate("block_place", context)
            self._log_verdict(verdict)
            if verdict["verdict"] == "EVIDENCE" and self._place_block(tile_x, tile_y, self.build_state.selected_block, "PLAYER"):
                if self.avatar:
                    self.avatar.attack()
                block = self.buildings[(tile_x, tile_y)]
                self.message = f"Placed {block.block_type} at ({tile_x},{tile_y}) | WORM {block.worm_seal[:16]}..."
            else:
                self.worm.seal("BLOCK_SILENCE", context)
                self.message = f"SILENCE: cannot place {self.build_state.selected_block} at ({tile_x},{tile_y})."
            return
        for portal in self.portals.values():
            if math.hypot(portal.x - px, portal.y - py) <= portal.radius + 16:
                self._launch_portal(portal.key)
                return

    def _handle_picker_click(self, px: float, py: float) -> bool:
        if not self.build_state.picker_open:
            return False
        origin_x, origin_y = self.build_state.picker_origin
        origin_x = max(16, min(HUB_W - PICKER_W - 16, origin_x))
        origin_y = max(48, min(HUB_H - HUD_HEIGHT - PICKER_H - 16, origin_y))
        if not (origin_x <= px <= origin_x + PICKER_W and origin_y <= py <= origin_y + PICKER_H):
            return False
        for index, block_type in enumerate(BLOCK_TYPES):
            bx = origin_x + 16 + index * 50
            by = origin_y + 42
            if bx <= px <= bx + 38 and by <= py <= by + 38:
                self._select_block(block_type)
                return True
        return True

    def _on_civ_click(self, event: tk.Event) -> None:
        w = int(self.civ_canvas["width"])
        h = int(self.civ_canvas["height"])
        cell = min(w / self.civ_w, h / self.civ_h)
        ox = (w - cell * self.civ_w) / 2
        oy = (h - cell * self.civ_h) / 2
        x = int((event.x - ox) / cell)
        y = int((event.y - oy) / cell)
        if not (0 <= x < self.civ_w and 0 <= y < self.civ_h):
            return
        owner = self.territory[y][x]
        verdict = self.bob.adjudicate("hub_seal", f"inspect tile {x},{y}|{owner}")
        self._log_verdict(verdict)
        self.worm.seal("MAP_INSPECT", f"{x},{y}|{owner}")
        self.message = f"Tile ({x},{y}) owner: {owner}"

    def _nearest_portal(self) -> PortalSpec | None:
        if not self.avatar:
            return None
        portal_trigger = self.world.nearest_portal(self.avatar.x, self.avatar.y)
        return self.portals.get(portal_trigger.key) if portal_trigger else None

    def _dist_to_portal(self, portal: PortalSpec) -> float:
        if not self.avatar:
            return 9999
        return math.hypot(portal.x - self.avatar.x, portal.y - self.avatar.y)

    def _use_nearest_portal(self) -> None:
        portal = self._nearest_portal()
        if portal and self._dist_to_portal(portal) < portal.radius + 28:
            self._launch_portal(portal.key)
        else:
            verdict = self.bob.adjudicate("portal_launch", "NO_IDENTITY" if not self.avatar else "no portal in range")
            self._log_verdict(verdict)
            self.worm.seal("SILENCE", str(verdict["context"]))
            self.message = "SILENCE: choose an avatar or move closer to a portal."

    def _launch_portal(self, key: str) -> None:
        portal = self.portals[key]
        context = f"{key}|{self.avatar.identity_seal if self.avatar else 'NO_IDENTITY'}"
        verdict = self.bob.adjudicate("portal_launch", context)
        self._log_verdict(verdict)
        if verdict["verdict"] != "EVIDENCE":
            self.worm.seal("PORTAL_BLOCKED", context)
            self.message = f"SILENCE: {portal.title} blocked by BOB."
            return
        if not portal.path.exists():
            self.worm.seal("PORTAL_MISSING", str(portal.path))
            self.message = f"SILENCE: missing {portal.path.name}"
            return
        env = os.environ.copy()
        env["KITTYVERSE_AVATAR"] = self.avatar.name if self.avatar else ""
        env["KITTYVERSE_IDENTITY_SEAL"] = self.avatar.identity_seal if self.avatar else ""
        env["KITTYVERSE_WORM_HEAD"] = self.worm.head
        try:
            child = subprocess.Popen([sys.executable, str(portal.path)], cwd=str(portal.path.parent), env=env)
            self.running_children.append(child)
            portal.launches += 1
            if self.avatar:
                self.avatar.attack()
            seal = self.worm.seal("PORTAL_LAUNCH", context)
            self.message = f"{portal.title} launched as {self.avatar.name}. WORM {seal[:16]}..."
        except OSError as exc:
            self.worm.seal("PORTAL_ERROR", f"{key}|{exc}")
            self.message = f"SILENCE: launch failed: {exc}"

    def _seal_hub(self) -> None:
        payload = "NO_IDENTITY"
        if self.avatar:
            payload = (
                f"{self.avatar.name}|{self.avatar.x:.1f},{self.avatar.y:.1f}|"
                f"energy={self.avatar.energy:.1f}|mood={self.avatar.mood:.1f}|"
                f"buildings={len(self.buildings)}|vault={len(self.worm_vault)}|block={self.build_state.selected_block}"
            )
        verdict = self.bob.adjudicate("hub_seal", payload)
        self._log_verdict(verdict)
        if verdict["verdict"] == "EVIDENCE":
            seal = self.worm.seal("HUB_STATE", payload)
            self.message = f"Hub state WORM sealed: {seal[:24]}..."
        else:
            self.worm.seal("HUB_SILENCE", payload)
            self.message = "SILENCE: hub state not sealed."

    def _log_verdict(self, verdict: dict[str, str | float]) -> None:
        self.verdict_box.configure(state=tk.NORMAL)
        self.verdict_box.delete("1.0", tk.END)
        for item in self.bob.verdicts:
            v = str(item["verdict"])
            score = float(item["score"])
            action = str(item["action"])
            reason = str(item["reason"])
            self.verdict_box.insert(tk.END, f"{v:<8} {score:.3f} {action}\n")
            self.verdict_box.insert(tk.END, f"  {reason}\n\n")
        self.verdict_box.configure(state=tk.DISABLED)

    def _quit(self) -> None:
        self.worm.seal("QUIT", "KITTYVERSE shutdown")
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    KittyverseApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
