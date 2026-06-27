"""BOB SIMS — Sovereign NPC Life Simulation
SPDX-License-Identifier: MIT
Copyright (c) 2026 SnapKitty Collective

Run: python bob_sims.py
Controls: SPACE=pause  Q=quit  N=new NPC  T=time warp
"""
from __future__ import annotations
import curses, hashlib, random, time
from dataclasses import dataclass, field
from typing import Optional

# ── Constants ────────────────────────────────────────────────
GRID_W, GRID_H = 60, 28
TICK = 0.08

NEEDS  = ["HUNGER","ENERGY","SOCIAL","FUN","HYGIENE","COMFORT"]
JOBS   = ["ENGINEER","ARCHITECT","ARTIST","TRADER","HACKER","SCHOLAR"]
MOODS  = {(0,30):"CRITICAL",(30,55):"STRESSED",(55,75):"OKAY",(75,90):"HAPPY",(90,101):"THRIVING"}
ROOMS  = [
    {"name":"KITCHEN",  "x":2,  "y":2,  "w":14, "h":8,  "restores":"HUNGER",  "ch":"K"},
    {"name":"BEDROOM",  "x":18, "y":2,  "w":14, "h":8,  "restores":"ENERGY",  "ch":"B"},
    {"name":"LOUNGE",   "x":34, "y":2,  "w":14, "h":8,  "restores":"SOCIAL",  "ch":"L"},
    {"name":"ARCADE",   "x":2,  "y":13, "w":14, "h":8,  "restores":"FUN",     "ch":"A"},
    {"name":"BATHROOM", "x":18, "y":13, "w":14, "h":8,  "restores":"HYGIENE", "ch":"H"},
    {"name":"OFFICE",   "x":34, "y":13, "w":14, "h":8,  "restores":"COMFORT", "ch":"O"},
]
WORM_EVENTS: list[str] = []

def worm_seal(payload: str) -> str:
    prev = WORM_EVENTS[-1] if WORM_EVENTS else "GENESIS"
    h = hashlib.sha256(f"{prev}|{payload}".encode()).hexdigest()
    WORM_EVENTS.append(h)
    return h[:16]

def mood_label(avg: float) -> str:
    for (lo, hi), label in MOODS.items():
        if lo <= avg < hi:
            return label
    return "UNKNOWN"

@dataclass
class NPC:
    name: str
    job:  str
    x: int = 0
    y: int = 0
    needs: dict = field(default_factory=lambda: {n: random.randint(55,95) for n in NEEDS})
    target_room: Optional[dict] = None
    age: int = 0
    seal: str = ""

    def __post_init__(self):
        self.x = random.randint(3, GRID_W-3)
        self.y = random.randint(3, GRID_H-3)
        self.seal = worm_seal(f"SPAWN|{self.name}|{self.job}")

    def worst_need(self) -> str:
        return min(self.needs, key=lambda k: self.needs[k])

    def avg_need(self) -> float:
        return sum(self.needs.values()) / len(self.needs)

    def mood(self) -> str:
        return mood_label(self.avg_need())

    def tick(self):
        self.age += 1
        # decay all needs
        for need in self.needs:
            decay = random.uniform(0.05, 0.25)
            self.needs[need] = max(0, self.needs[need] - decay)

        # find target room for worst need
        worst = self.worst_need()
        if self.needs[worst] < 40:
            for room in ROOMS:
                if room["restores"] == worst:
                    self.target_room = room
                    break

        # move toward target
        if self.target_room:
            tx = self.target_room["x"] + self.target_room["w"]//2
            ty = self.target_room["y"] + self.target_room["h"]//2
            if abs(self.x - tx) > 1:
                self.x += 1 if tx > self.x else -1
            if abs(self.y - ty) > 1:
                self.y += 1 if ty > self.y else -1

            # in room — restore need
            r = self.target_room
            if r["x"] < self.x < r["x"]+r["w"] and r["y"] < self.y < r["y"]+r["h"]:
                need = r["restores"]
                self.needs[need] = min(100, self.needs[need] + random.uniform(0.8, 1.5))
                if self.needs[need] > 75:
                    self.target_room = None
                    self.seal = worm_seal(f"RESTORED|{self.name}|{need}")
        else:
            # wander
            self.x += random.randint(-1,1)
            self.y += random.randint(-1,1)

        self.x = max(1, min(GRID_W-2, self.x))
        self.y = max(1, min(GRID_H-2, self.y))

NAMES = ["ARIA","CARTO","FLUX","CIPHER","PHANTOM","FORGE","NOVA","ECHO","SAGE","RUNE","BLAZE","LYRA"]

def make_npcs(n=4) -> list[NPC]:
    return [NPC(NAMES[i % len(NAMES)], random.choice(JOBS)) for i in range(n)]

def main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_YELLOW,  -1)
    curses.init_pair(2, curses.COLOR_CYAN,    -1)
    curses.init_pair(3, curses.COLOR_GREEN,   -1)
    curses.init_pair(4, curses.COLOR_RED,     -1)
    curses.init_pair(5, curses.COLOR_MAGENTA, -1)
    curses.init_pair(6, curses.COLOR_WHITE,   -1)

    GOLD  = curses.color_pair(1)|curses.A_BOLD
    CYAN  = curses.color_pair(2)
    GREEN = curses.color_pair(3)|curses.A_BOLD
    RED   = curses.color_pair(4)|curses.A_BOLD
    MAG   = curses.color_pair(5)
    WHITE = curses.color_pair(6)

    npcs   = make_npcs(4)
    paused = False
    warp   = False
    tick_n = 0
    H, W   = stdscr.getmaxyx()

    NPC_CHARS = ['@','$','%','&','#','*','!','?']
    NPC_COLORS = [GOLD, CYAN, GREEN, RED, MAG, WHITE, GOLD, CYAN]

    def safe(y, x, s, attr=0):
        try:
            if 0 <= y < H and 0 <= x < W-1:
                stdscr.addstr(y, x, str(s)[:W-x-1], attr)
        except curses.error:
            pass

    def draw():
        stdscr.erase()

        # Title
        safe(0, 2, "BOB SIMS — SOVEREIGN LIFE SIMULATION", GOLD)
        safe(0, W-30, f"TICK:{tick_n:06d}  {'PAUSED' if paused else 'LIVE  '}", CYAN)

        # Rooms
        for room in ROOMS:
            rx,ry,rw,rh = room["x"],room["y"],room["w"],room["h"]
            for dx in range(rw):
                safe(ry, rx+dx, '-', CYAN)
                safe(ry+rh, rx+dx, '-', CYAN)
            for dy in range(rh):
                safe(ry+dy, rx, '|', CYAN)
                safe(ry+dy, rx+rw, '|', CYAN)
            safe(ry, rx, '+', CYAN)
            safe(ry, rx+rw, '+', CYAN)
            safe(ry+rh, rx, '+', CYAN)
            safe(ry+rh, rx+rw, '+', CYAN)
            safe(ry+1, rx+2, room["name"], GREEN)
            safe(ry+2, rx+2, f"[{room['restores']}]", MAG)

        # NPCs
        for i, npc in enumerate(npcs):
            ch   = NPC_CHARS[i % len(NPC_CHARS)]
            col  = NPC_COLORS[i % len(NPC_COLORS)]
            safe(npc.y, npc.x, ch, col)

        # Status panel (right side)
        px = GRID_W + 2
        safe(1, px, "── NPC STATUS ──────────────", GOLD)
        for i, npc in enumerate(npcs):
            base_y = 2 + i * 7
            col = NPC_COLORS[i % len(NPC_COLORS)]
            safe(base_y,   px, f"{NPC_CHARS[i%len(NPC_CHARS)]} {npc.name} [{npc.job}]", col)
            safe(base_y+1, px, f"  MOOD: {npc.mood()}", GREEN if npc.avg_need()>65 else RED)
            for j, (need, val) in enumerate(npc.needs.items()):
                bar = int(val/10)
                bar_str = '█'*bar + '░'*(10-bar)
                color = GREEN if val>65 else RED if val<35 else WHITE
                safe(base_y+2+j//2, px + (j%2)*20, f"{need[:3]}:{bar_str[:6]}{int(val):3d}", color)
            safe(base_y+5, px, f"  WORM:{npc.seal}", MAG)

        # WORM chain
        safe(H-3, 2, f"WORM CHAIN: {WORM_EVENTS[-1] if WORM_EVENTS else 'GENESIS'}", MAG)
        safe(H-2, 2, "SPACE=pause  N=new NPC  T=warp  Q=quit", WHITE)

        stdscr.refresh()

    while True:
        key = stdscr.getch()
        if key in (ord('q'), ord('Q')): break
        if key == ord(' '): paused = not paused
        if key in (ord('n'), ord('N')) and len(npcs) < len(NAMES):
            npcs.append(NPC(NAMES[len(npcs)], random.choice(JOBS)))
        if key in (ord('t'), ord('T')): warp = not warp

        if not paused:
            steps = 5 if warp else 1
            for _ in range(steps):
                for npc in npcs: npc.tick()
            tick_n += steps

        draw()
        time.sleep(TICK if not warp else 0.02)

curses.wrapper(main)
