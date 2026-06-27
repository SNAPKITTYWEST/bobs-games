"""BOB PARALLIVE — Concurrent Sovereign Agent Life
SPDX-License-Identifier: MIT
Copyright (c) 2026 SnapKitty Collective

Run: python bob_parallive.py
Controls: Q=quit  SPACE=pause  A=add agent  R=reset
"""
from __future__ import annotations
import curses, hashlib, random, time, threading
from dataclasses import dataclass, field
from queue import Queue

GRID_W, GRID_H = 55, 24
TICK = 0.05
MAX_AGENTS = 12

STATES = ["IDLE","SEEKING","WORKING","RESTING","SOCIALIZING","CRITICAL"]
STATE_COLORS = {
    "IDLE":10,"SEEKING":11,"WORKING":10,"RESTING":12,"SOCIALIZING":13,"CRITICAL":9
}

WORM_LOG: list[str] = []
WORM_LOCK = threading.Lock()

def worm_seal(evt: str) -> str:
    with WORM_LOCK:
        prev = WORM_LOG[-1] if WORM_LOG else "GENESIS"
        h = hashlib.sha256(f"{prev}|{evt}".encode()).hexdigest()[:12]
        WORM_LOG.append(h)
        return h

@dataclass
class Agent:
    uid: int
    name: str
    x: float = 0.0
    y: float = 0.0
    state: str = "IDLE"
    energy: float = 100.0
    social: float = 100.0
    work_done: int = 0
    messages: list[str] = field(default_factory=list)
    seal: str = ""
    lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self):
        self.x = float(random.randint(3, GRID_W-3))
        self.y = float(random.randint(3, GRID_H-3))
        self.seal = worm_seal(f"SPAWN|{self.name}")

    def run(self, agents: list['Agent'], stop: threading.Event):
        while not stop.is_set():
            with self.lock:
                self._tick(agents)
            time.sleep(random.uniform(0.04, 0.10))

    def _tick(self, agents: list['Agent']):
        self.energy = max(0, self.energy - random.uniform(0.1, 0.4))
        self.social = max(0, self.social - random.uniform(0.05, 0.2))

        if self.energy < 20:
            self.state = "CRITICAL"
        elif self.energy < 40:
            self.state = "RESTING"
            self.energy = min(100, self.energy + 1.2)
        elif self.social < 30:
            self.state = "SOCIALIZING"
            # move toward nearest other agent
            nearest = self._nearest(agents)
            if nearest:
                with nearest.lock:
                    dx = nearest.x - self.x
                    dy = nearest.y - self.y
                    dist = max(1, (dx**2+dy**2)**0.5)
                    self.x += dx/dist * 0.8
                    self.y += dy/dist * 0.8
                    if dist < 2:
                        self.social = min(100, self.social + 2.0)
                        nearest.social = min(100, nearest.social + 1.5)
                        msg = f"{self.name}↔{nearest.name}"
                        self.messages.append(msg)
                        if len(self.messages) > 4: self.messages.pop(0)
                        self.seal = worm_seal(f"SOCIAL|{msg}")
        elif random.random() < 0.3:
            self.state = "WORKING"
            self.work_done += 1
            self.energy = max(0, self.energy - 0.3)
            if self.work_done % 10 == 0:
                self.seal = worm_seal(f"WORK|{self.name}|{self.work_done}")
        else:
            self.state = "IDLE"
            # wander
            self.x += random.uniform(-0.5, 0.5)
            self.y += random.uniform(-0.5, 0.5)

        self.x = max(1.0, min(float(GRID_W-2), self.x))
        self.y = max(1.0, min(float(GRID_H-2), self.y))

    def _nearest(self, agents: list['Agent']) -> 'Agent | None':
        best, best_d = None, float('inf')
        for a in agents:
            if a.uid == self.uid: continue
            d = (a.x-self.x)**2 + (a.y-self.y)**2
            if d < best_d:
                best_d, best = d, a
        return best

AGENT_NAMES = ["ROBOB","CARTO","FLUX","CIPHER","PHANTOM","FORGE",
               "NOVA","ECHO","SAGE","RUNE","BLAZE","LYRA"]
AGENT_CHARS = ['R','C','F','X','P','G','N','E','S','U','B','L']

def main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    curses.start_color()
    curses.use_default_colors()
    for i in range(1,8):
        curses.init_pair(i, [0,curses.COLOR_YELLOW,curses.COLOR_CYAN,
                             curses.COLOR_GREEN,curses.COLOR_RED,
                             curses.COLOR_MAGENTA,curses.COLOR_WHITE][i], -1)

    GOLD  = curses.color_pair(1)|curses.A_BOLD
    CYAN  = curses.color_pair(2)
    GREEN = curses.color_pair(3)|curses.A_BOLD
    RED   = curses.color_pair(4)|curses.A_BOLD
    MAG   = curses.color_pair(5)
    WHITE = curses.color_pair(6)

    H, W = stdscr.getmaxyx()

    def safe(y, x, s, attr=0):
        try:
            if 0 <= y < H and 0 <= x < W-1:
                stdscr.addstr(y, x, str(s)[:max(0,W-x-1)], attr)
        except curses.error:
            pass

    stop_evt = threading.Event()
    agents: list[Agent] = []
    threads: list[threading.Thread] = []

    def add_agent():
        if len(agents) >= MAX_AGENTS: return
        i = len(agents)
        a = Agent(i, AGENT_NAMES[i % len(AGENT_NAMES)])
        agents.append(a)
        t = threading.Thread(target=a.run, args=(agents, stop_evt), daemon=True)
        t.start()
        threads.append(t)

    for _ in range(4): add_agent()

    paused = False
    frame  = 0

    try:
        while True:
            key = stdscr.getch()
            if key in (ord('q'),ord('Q')): break
            if key == ord(' '): paused = not paused
            if key in (ord('a'),ord('A')): add_agent()
            if key in (ord('r'),ord('R')):
                for a in agents: a.energy=100.0; a.social=100.0

            if paused:
                time.sleep(0.05)
                continue

            stdscr.erase()

            # Border
            for x in range(GRID_W+2):
                safe(2, x, '-', CYAN)
                safe(GRID_H+3, x, '-', CYAN)
            for y in range(2, GRID_H+4):
                safe(y, 0, '|', CYAN)
                safe(y, GRID_W+1, '|', CYAN)

            # Title
            safe(0, 2, "BOB PARALLIVE — CONCURRENT SOVEREIGN AGENTS", GOLD)
            safe(0, W-25, f"AGENTS:{len(agents):02d}  FRAME:{frame:05d}", CYAN)
            safe(1, 2, f"THREADS: {len(threads)} LIVE  WORM: {WORM_LOG[-1] if WORM_LOG else 'GENESIS'}", MAG)

            # Draw agents on grid
            for i, a in enumerate(agents):
                with a.lock:
                    gx = int(a.x) + 1
                    gy = int(a.y) + 3
                    ch = AGENT_CHARS[i % len(AGENT_CHARS)]
                    col_map = {"IDLE":WHITE,"SEEKING":CYAN,"WORKING":GREEN,
                               "RESTING":CYAN,"SOCIALIZING":MAG,"CRITICAL":RED}
                    col = col_map.get(a.state, WHITE)
                    safe(gy, gx, ch, col)

            # Status panel
            px = GRID_W + 4
            safe(2, px, "── AGENT STATUS ─────────────", GOLD)
            for i, a in enumerate(agents[:8]):
                with a.lock:
                    by = 3 + i*3
                    ch = AGENT_CHARS[i%len(AGENT_CHARS)]
                    e_bar = '█'*int(a.energy/10) + '░'*(10-int(a.energy/10))
                    s_bar = '█'*int(a.social/10) + '░'*(10-int(a.social/10))
                    state_col = {"IDLE":WHITE,"WORKING":GREEN,"CRITICAL":RED,
                                 "SOCIALIZING":MAG,"RESTING":CYAN}.get(a.state, WHITE)
                    safe(by,   px, f"{ch} {a.name:<8} [{a.state:<11}]", state_col)
                    safe(by+1, px, f"  NRG:{e_bar[:8]} SOC:{s_bar[:8]} WRK:{a.work_done:04d}", WHITE)
                    if a.messages:
                        safe(by+2, px, f"  ↔ {a.messages[-1]}", MAG)

            # WORM log (last 4)
            safe(H-5, 2, "── WORM CHAIN ──────────────────────────", GOLD)
            for i, evt in enumerate(WORM_LOG[-4:]):
                safe(H-4+i, 2, f"  {evt}", MAG)

            safe(H-1, 2, "A=add  SPACE=pause  R=reset  Q=quit", WHITE)
            stdscr.refresh()
            frame += 1
            time.sleep(TICK)

    finally:
        stop_evt.set()

curses.wrapper(main)
