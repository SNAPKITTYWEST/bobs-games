"""BOB PARALLIVE - Concurrent Sovereign Agent Life, tkinter edition.
SPDX-License-Identifier: MIT
Copyright (c) 2026 SnapKitty Collective

Run: python bob_parallive.py
Controls: Q/Esc=quit  Space=pause  A=add agent  R=reset
"""
from __future__ import annotations

import hashlib
import math
import random
import tkinter as tk
from dataclasses import dataclass, field

WORLD_W = 760
WORLD_H = 440
PANEL_W = 330
MAX_AGENTS = 12
TICK_MS = 55

BG = "#050507"
PANEL = "#0d0d12"
GRID = "#151923"
GOLD = "#ffd700"
CYAN = "#00d4ff"
GREEN = "#00ff88"
RED = "#ff3333"
MAGENTA = "#d36bff"
WHITE = "#ececec"
MUTED = "#7b7b86"

AGENT_NAMES = ["ROBOB", "CARTO", "FLUX", "CIPHER", "PHANTOM", "FORGE", "NOVA", "ECHO", "SAGE", "RUNE", "BLAZE", "LYRA"]
AGENT_CHARS = ["R", "C", "F", "X", "P", "G", "N", "E", "S", "U", "B", "L"]
STATE_COLORS = {
    "IDLE": WHITE,
    "SEEKING": CYAN,
    "WORKING": GREEN,
    "RESTING": CYAN,
    "SOCIALIZING": MAGENTA,
    "CRITICAL": RED,
}

WORM_LOG: list[str] = []


def worm_seal(evt: str) -> str:
    prev = WORM_LOG[-1] if WORM_LOG else "GENESIS"
    digest = hashlib.sha256(f"{prev}|{evt}".encode("utf-8")).hexdigest()[:16]
    WORM_LOG.append(digest)
    return digest


@dataclass
class Agent:
    uid: int
    name: str
    x: float = field(default_factory=lambda: random.uniform(50, WORLD_W - 50))
    y: float = field(default_factory=lambda: random.uniform(50, WORLD_H - 50))
    vx: float = 0.0
    vy: float = 0.0
    state: str = "IDLE"
    energy: float = 100.0
    social: float = 100.0
    work_done: int = 0
    messages: list[str] = field(default_factory=list)
    seal: str = ""

    def __post_init__(self) -> None:
        self.seal = worm_seal(f"SPAWN|{self.name}")

    def nearest(self, agents: list["Agent"]) -> "Agent | None":
        candidates = [agent for agent in agents if agent.uid != self.uid]
        if not candidates:
            return None
        return min(candidates, key=lambda agent: (agent.x - self.x) ** 2 + (agent.y - self.y) ** 2)

    def tick(self, agents: list["Agent"], paused: bool) -> None:
        if paused:
            return

        self.energy = max(0.0, self.energy - random.uniform(0.12, 0.36))
        self.social = max(0.0, self.social - random.uniform(0.05, 0.18))

        if self.energy < 18:
            self.state = "CRITICAL"
            self.energy = min(100.0, self.energy + 0.9)
            self.vx *= 0.4
            self.vy *= 0.4
        elif self.energy < 42:
            self.state = "RESTING"
            self.energy = min(100.0, self.energy + 1.5)
            self.vx *= 0.7
            self.vy *= 0.7
        elif self.social < 32:
            self.state = "SOCIALIZING"
            other = self.nearest(agents)
            if other:
                self.seek(other.x, other.y, 1.6)
                if math.hypot(other.x - self.x, other.y - self.y) < 28:
                    self.social = min(100.0, self.social + 3.0)
                    other.social = min(100.0, other.social + 1.6)
                    if random.random() < 0.08:
                        msg = f"{self.name}<->{other.name}: expand the city"
                        self.messages.append(msg)
                        self.messages = self.messages[-4:]
                        self.seal = worm_seal(f"SOCIAL|{msg}")
        elif random.random() < 0.35:
            self.state = "WORKING"
            self.work_done += 1
            self.energy = max(0.0, self.energy - 0.35)
            self.seek(WORLD_W * 0.72, WORLD_H * 0.58, 1.1)
            if self.work_done % 14 == 0:
                self.seal = worm_seal(f"WORK|{self.name}|{self.work_done}")
        else:
            self.state = "IDLE"
            self.vx += random.uniform(-0.35, 0.35)
            self.vy += random.uniform(-0.35, 0.35)

        speed = math.hypot(self.vx, self.vy)
        if speed > 2.4:
            self.vx = self.vx / speed * 2.4
            self.vy = self.vy / speed * 2.4
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.92
        self.vy *= 0.92
        self.x = max(18, min(WORLD_W - 18, self.x))
        self.y = max(18, min(WORLD_H - 18, self.y))

    def seek(self, tx: float, ty: float, force: float) -> None:
        dx = tx - self.x
        dy = ty - self.y
        dist = math.hypot(dx, dy) or 1.0
        self.vx += dx / dist * force * 0.22
        self.vy += dy / dist * force * 0.22


class BobParallive:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("BOB PARALLIVE - Sovereign Agents")
        self.root.configure(bg=BG)
        self.root.minsize(1040, 620)

        self.frame = 0
        self.paused = False
        self.agents: list[Agent] = []

        self.canvas = tk.Canvas(root, width=WORLD_W, height=WORLD_H + 86, bg=BG, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.panel = tk.Frame(root, width=PANEL_W, bg=PANEL)
        self.panel.pack(side=tk.RIGHT, fill=tk.Y)
        self.panel.pack_propagate(False)

        self.title = tk.Label(self.panel, text="BOB PARALLIVE", fg=GOLD, bg=PANEL, font=("Courier New", 16, "bold"))
        self.title.pack(anchor="w", padx=14, pady=(14, 2))
        self.sub = tk.Label(self.panel, text="CONCURRENT SOVEREIGN AGENTS", fg=CYAN, bg=PANEL, font=("Courier New", 9, "bold"))
        self.sub.pack(anchor="w", padx=14, pady=(0, 12))

        self.status_labels: list[tk.Label] = []
        for _ in range(MAX_AGENTS):
            label = tk.Label(self.panel, text="", fg=WHITE, bg=PANEL, justify=tk.LEFT, anchor="w", font=("Courier New", 8))
            label.pack(anchor="w", padx=14, pady=1)
            self.status_labels.append(label)

        self.worm = tk.Label(self.panel, text="", fg=MAGENTA, bg=PANEL, justify=tk.LEFT, anchor="w", wraplength=PANEL_W - 28, font=("Courier New", 8))
        self.worm.pack(anchor="w", padx=14, pady=(14, 0))

        buttons = tk.Frame(self.panel, bg=PANEL)
        buttons.pack(anchor="w", padx=14, pady=12)
        for text, command in (("Pause", self.toggle_pause), ("Add", self.add_agent), ("Reset", self.reset_agents)):
            tk.Button(buttons, text=text, command=command, bg="#171720", fg=GOLD, activebackground="#23232d", activeforeground=WHITE, relief=tk.FLAT, font=("Courier New", 8, "bold")).pack(side=tk.LEFT, padx=(0, 6))

        root.bind("<space>", lambda _event: self.toggle_pause())
        root.bind("a", lambda _event: self.add_agent())
        root.bind("A", lambda _event: self.add_agent())
        root.bind("r", lambda _event: self.reset_agents())
        root.bind("R", lambda _event: self.reset_agents())
        root.bind("q", lambda _event: root.destroy())
        root.bind("Q", lambda _event: root.destroy())
        root.bind("<Escape>", lambda _event: root.destroy())
        root.bind("<Configure>", lambda _event: self.draw())

        for _ in range(4):
            self.add_agent()
        self.loop()

    def add_agent(self) -> None:
        if len(self.agents) >= MAX_AGENTS:
            return
        i = len(self.agents)
        self.agents.append(Agent(i, AGENT_NAMES[i % len(AGENT_NAMES)]))

    def reset_agents(self) -> None:
        for agent in self.agents:
            agent.energy = 100.0
            agent.social = 100.0
            agent.state = "IDLE"
            agent.vx = 0.0
            agent.vy = 0.0
        worm_seal("RESET|ALL_AGENTS")

    def toggle_pause(self) -> None:
        self.paused = not self.paused

    def draw_grid(self) -> None:
        for x in range(0, WORLD_W + 1, 40):
            self.canvas.create_line(x, 70, x, 70 + WORLD_H, fill=GRID)
        for y in range(70, 70 + WORLD_H + 1, 40):
            self.canvas.create_line(0, y, WORLD_W, y, fill=GRID)
        self.canvas.create_rectangle(2, 72, WORLD_W - 2, 70 + WORLD_H - 2, outline=CYAN, width=2)
        self.canvas.create_rectangle(WORLD_W * 0.64, 70 + WORLD_H * 0.43, WORLD_W * 0.88, 70 + WORLD_H * 0.74, outline=GOLD, fill="#1c1710")
        self.canvas.create_text(WORLD_W * 0.76, 70 + WORLD_H * 0.47, text="WORKSHOP", fill=GOLD, font=("Courier New", 9, "bold"))
        self.canvas.create_rectangle(WORLD_W * 0.08, 70 + WORLD_H * 0.12, WORLD_W * 0.35, 70 + WORLD_H * 0.32, outline=MAGENTA, fill="#171022")
        self.canvas.create_text(WORLD_W * 0.215, 70 + WORLD_H * 0.16, text="SOCIAL COMMONS", fill=MAGENTA, font=("Courier New", 9, "bold"))

    def draw(self) -> None:
        self.canvas.delete("all")
        width = max(WORLD_W, self.canvas.winfo_width())
        self.canvas.create_rectangle(0, 0, width, 64, fill=PANEL, outline="#20202a")
        self.canvas.create_text(18, 18, text="BOB PARALLIVE - CONCURRENT SOVEREIGN AGENTS", fill=GOLD, font=("Courier New", 14, "bold"), anchor="w")
        state = "PAUSED" if self.paused else "LIVE"
        last = WORM_LOG[-1] if WORM_LOG else "GENESIS"
        self.canvas.create_text(18, 44, text=f"AGENTS {len(self.agents):02d}  FRAME {self.frame:06d}  THREADLESS TK LOOP  WORM {last}", fill=CYAN, font=("Courier New", 9), anchor="w")

        self.draw_grid()
        for i, agent in enumerate(self.agents):
            color = STATE_COLORS.get(agent.state, WHITE)
            x = agent.x
            y = 70 + agent.y
            r = 10 if agent.state != "CRITICAL" else 12
            self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=color, outline=WHITE, width=1)
            self.canvas.create_text(x, y + 1, text=AGENT_CHARS[i % len(AGENT_CHARS)], fill=BG, font=("Courier New", 9, "bold"))
            self.canvas.create_text(x, y - 18, text=agent.name, fill=color, font=("Courier New", 7, "bold"))
            if agent.messages:
                self.canvas.create_text(x + 14, y + 18, text=agent.messages[-1][:30], fill=MAGENTA, font=("Courier New", 7), anchor="w")

        self.canvas.create_text(18, 70 + WORLD_H + 26, text="SPACE pause   A add agent   R reset needs   Q quit", fill=MUTED, font=("Courier New", 9), anchor="w")
        self.canvas.create_text(width - 20, 70 + WORLD_H + 26, text=state, fill=GREEN if not self.paused else RED, font=("Courier New", 10, "bold"), anchor="e")

    def update_panel(self) -> None:
        for i, label in enumerate(self.status_labels):
            if i >= len(self.agents):
                label.config(text="", fg=WHITE)
                continue
            agent = self.agents[i]
            energy = "#" * int(agent.energy / 12.5)
            social = "#" * int(agent.social / 12.5)
            text = (
                f"{AGENT_CHARS[i % len(AGENT_CHARS)]} {agent.name:<8} {agent.state:<11}\n"
                f"  NRG:{energy:<8} {agent.energy:05.1f}\n"
                f"  SOC:{social:<8} {agent.social:05.1f} WRK:{agent.work_done:04d}\n"
                f"  WORM:{agent.seal}"
            )
            label.config(text=text, fg=STATE_COLORS.get(agent.state, WHITE))
        self.worm.config(text="WORM CHAIN\n" + "\n".join(WORM_LOG[-6:]))

    def loop(self) -> None:
        for agent in list(self.agents):
            agent.tick(self.agents, self.paused)
        if not self.paused:
            self.frame += 1
        self.draw()
        self.update_panel()
        self.root.after(TICK_MS, self.loop)


if __name__ == "__main__":
    root = tk.Tk()
    BobParallive(root)
    root.mainloop()
