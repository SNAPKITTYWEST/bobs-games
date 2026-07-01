"""BOB SIMS — Sovereign NPC Life Simulation
SPDX-License-Identifier: MIT
Copyright (c) 2026 SnapKitty Collective

Run: python bob_sims.py
Controls: SPACE=pause  N=new NPC  T=time warp  Q=quit
"""
from __future__ import annotations
import tkinter as tk
import hashlib, random, time, threading
from dataclasses import dataclass, field
from typing import Optional

GRID_W, GRID_H = 800, 500
CELL = 14
TICK = 80  # ms

NEEDS  = ["HUNGER","ENERGY","SOCIAL","FUN","HYGIENE","COMFORT"]
JOBS   = ["ENGINEER","ARCHITECT","ARTIST","TRADER","HACKER","SCHOLAR"]
MOODS  = [(0,30,"CRITICAL","#ff3333"),(30,55,"STRESSED","#ff9900"),(55,75,"OKAY","#ffff00"),(75,90,"HAPPY","#00ff99"),(90,101,"THRIVING","#00ffff")]
ROOMS  = [
    {"name":"KITCHEN",  "x":20,  "y":20,  "w":160, "h":110, "restores":"HUNGER",  "color":"#1a2a1a"},
    {"name":"BEDROOM",  "x":200, "y":20,  "w":160, "h":110, "restores":"ENERGY",  "color":"#1a1a2a"},
    {"name":"LOUNGE",   "x":380, "y":20,  "w":160, "h":110, "restores":"SOCIAL",  "color":"#2a1a2a"},
    {"name":"ARCADE",   "x":20,  "y":150, "w":160, "h":110, "restores":"FUN",     "color":"#2a2a1a"},
    {"name":"BATHROOM", "x":200, "y":150, "w":160, "h":110, "restores":"HYGIENE", "color":"#1a2a2a"},
    {"name":"OFFICE",   "x":380, "y":150, "w":160, "h":110, "restores":"COMFORT", "color":"#2a1a1a"},
]
WORM_EVENTS: list[str] = []
NPC_COLORS = ["#ffd700","#00cfff","#00ff99","#ff6b6b","#da70d6","#ffffff","#ffa500","#7fff00"]
NPC_CHARS  = ["@","$","%","&","#","*","!","?"]
NAMES = ["ARIA","CARTO","FLUX","CIPHER","PHANTOM","FORGE","NOVA","ECHO","SAGE","RUNE","BLAZE","LYRA"]

def worm_seal(payload: str) -> str:
    prev = WORM_EVENTS[-1] if WORM_EVENTS else "GENESIS"
    h = hashlib.sha256(f"{prev}|{payload}".encode()).hexdigest()
    WORM_EVENTS.append(h)
    return h[:16]

def mood_info(avg: float):
    for lo,hi,label,color in MOODS:
        if lo <= avg < hi:
            return label, color
    return "UNKNOWN","#ffffff"

@dataclass
class NPC:
    name: str
    job:  str
    x: float = 0
    y: float = 0
    needs: dict = field(default_factory=lambda: {n: random.randint(55,95) for n in NEEDS})
    target_room: Optional[dict] = None
    age: int = 0
    seal: str = ""

    def __post_init__(self):
        self.x = random.uniform(30, 540)
        self.y = random.uniform(30, 280)
        self.seal = worm_seal(f"SPAWN|{self.name}|{self.job}")

    def worst_need(self): return min(self.needs, key=lambda k: self.needs[k])
    def avg_need(self):   return sum(self.needs.values()) / len(self.needs)
    def mood(self):       return mood_info(self.avg_need())

    def tick(self):
        self.age += 1
        for need in self.needs:
            self.needs[need] = max(0, self.needs[need] - random.uniform(0.05, 0.25))
        worst = self.worst_need()
        if self.needs[worst] < 40 and not self.target_room:
            for room in ROOMS:
                if room["restores"] == worst:
                    self.target_room = room
                    break
        if self.target_room:
            tx = self.target_room["x"] + self.target_room["w"]/2
            ty = self.target_room["y"] + self.target_room["h"]/2
            dx, dy = tx - self.x, ty - self.y
            dist = (dx**2+dy**2)**0.5
            if dist > 3:
                self.x += dx/dist * 3
                self.y += dy/dist * 3
            r = self.target_room
            if r["x"] < self.x < r["x"]+r["w"] and r["y"] < self.y < r["y"]+r["h"]:
                need = r["restores"]
                self.needs[need] = min(100, self.needs[need] + random.uniform(0.8,1.5))
                if self.needs[need] > 75:
                    self.target_room = None
                    self.seal = worm_seal(f"RESTORED|{self.name}|{need}")
        else:
            self.x += random.uniform(-1.5,1.5)
            self.y += random.uniform(-1.5,1.5)
        self.x = max(5, min(555, self.x))
        self.y = max(5, min(295, self.y))


class BobSims:
    def __init__(self, root):
        self.root = root
        self.root.title("BOB SIMS — Sovereign Life Simulation")
        self.root.configure(bg="#0a0a0f")
        self.paused = False
        self.warp   = False
        self.tick_n = 0
        self.npcs   = [NPC(NAMES[i], random.choice(JOBS)) for i in range(4)]

        # Canvas
        self.canvas = tk.Canvas(root, width=580, height=320, bg="#0a0a0f", highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, padx=10, pady=10)

        # Side panel
        self.panel = tk.Frame(root, bg="#0a0a0f", width=300)
        self.panel.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=10)

        self.title_lbl = tk.Label(self.panel, text="BOB SIMS — SOVEREIGN NPC SIMULATION",
                                   fg="#ffd700", bg="#0a0a0f", font=("Courier",9,"bold"))
        self.title_lbl.pack(anchor="w")

        self.npc_labels = []
        for i in range(12):
            lbl = tk.Label(self.panel, text="", fg=NPC_COLORS[i%len(NPC_COLORS)],
                           bg="#0a0a0f", font=("Courier",8), justify=tk.LEFT, anchor="w")
            lbl.pack(anchor="w")
            self.npc_labels.append(lbl)

        self.worm_lbl = tk.Label(self.panel, text="", fg="#da70d6", bg="#0a0a0f",
                                  font=("Courier",8), justify=tk.LEFT, anchor="w", wraplength=280)
        self.worm_lbl.pack(anchor="w", pady=(10,0))

        self.tick_lbl = tk.Label(self.panel, text="", fg="#00cfff", bg="#0a0a0f", font=("Courier",8))
        self.tick_lbl.pack(anchor="w")

        # Controls
        ctrl = tk.Frame(root, bg="#0a0a0f")
        ctrl.pack(side=tk.BOTTOM, fill=tk.X)
        for text, cmd in [("SPACE: Pause",self.toggle_pause),("N: New NPC",self.add_npc),("T: Warp",self.toggle_warp)]:
            tk.Button(ctrl, text=text, command=cmd, bg="#1a1a2a", fg="#ffd700",
                      font=("Courier",8), relief=tk.FLAT).pack(side=tk.LEFT, padx=5, pady=5)

        self.root.bind("<space>", lambda e: self.toggle_pause())
        self.root.bind("n", lambda e: self.add_npc())
        self.root.bind("N", lambda e: self.add_npc())
        self.root.bind("t", lambda e: self.toggle_warp())
        self.root.bind("T", lambda e: self.toggle_warp())
        self.root.bind("q", lambda e: root.quit())

        self.loop()

    def toggle_pause(self): self.paused = not self.paused
    def toggle_warp(self):  self.warp = not self.warp
    def add_npc(self):
        if len(self.npcs) < len(NAMES):
            self.npcs.append(NPC(NAMES[len(self.npcs)], random.choice(JOBS)))

    def draw(self):
        c = self.canvas
        c.delete("all")

        # Rooms
        for room in ROOMS:
            x,y,w,h = room["x"],room["y"],room["w"],room["h"]
            c.create_rectangle(x,y,x+w,y+h, fill=room["color"], outline="#00cfff", width=1)
            c.create_text(x+8,y+8, text=room["name"], fill="#00ff99", font=("Courier",7,"bold"), anchor="nw")
            c.create_text(x+8,y+20, text=f"[{room['restores']}]", fill="#da70d6", font=("Courier",6), anchor="nw")

        # NPCs
        for i,npc in enumerate(self.npcs):
            col = NPC_COLORS[i%len(NPC_COLORS)]
            ch  = NPC_CHARS[i%len(NPC_CHARS)]
            c.create_oval(npc.x-6,npc.y-6,npc.x+6,npc.y+6, fill=col, outline="#ffffff")
            c.create_text(npc.x,npc.y, text=ch, fill="#0a0a0f", font=("Courier",8,"bold"))
            c.create_text(npc.x,npc.y-14, text=npc.name, fill=col, font=("Courier",6))

        # Worm footer
        worm = WORM_EVENTS[-1] if WORM_EVENTS else "GENESIS"
        c.create_text(5,305, text=f"WORM: {worm}", fill="#da70d6", font=("Courier",7), anchor="w")
        status = "PAUSED" if self.paused else ("WARP" if self.warp else "LIVE")
        c.create_text(575,305, text=f"TICK:{self.tick_n:06d} {status}", fill="#00cfff", font=("Courier",7), anchor="e")

    def update_panel(self):
        for i,npc in enumerate(self.npcs[:len(self.npc_labels)//2]):
            mood_label, mood_color = npc.mood()
            bar = " ".join(f"{k[:3]}:{'█'*int(v/10)+' '*(10-int(v/10))}{int(v):3d}" for k,v in npc.needs.items())
            text = f"{NPC_CHARS[i%len(NPC_CHARS)]} {npc.name} [{npc.job}] {mood_label}\n  {bar}\n  WORM:{npc.seal}"
            self.npc_labels[i*2].config(text=f"{NPC_CHARS[i%len(NPC_CHARS)]} {npc.name} [{npc.job}]", fg=NPC_COLORS[i%len(NPC_COLORS)])
            self.npc_labels[i*2+1].config(text=f"  MOOD:{mood_label}  WORM:{npc.seal}", fg=mood_color)
        worm = WORM_EVENTS[-1] if WORM_EVENTS else "GENESIS"
        self.worm_lbl.config(text=f"WORM CHAIN:\n{worm}")
        status = "PAUSED" if self.paused else ("⚡WARP" if self.warp else "LIVE")
        self.tick_lbl.config(text=f"TICK: {self.tick_n:06d}  {status}")

    def loop(self):
        if not self.paused:
            steps = 5 if self.warp else 1
            for _ in range(steps):
                for npc in self.npcs:
                    npc.tick()
            self.tick_n += steps
        self.draw()
        self.update_panel()
        delay = 20 if self.warp else TICK
        self.root.after(delay, self.loop)


root = tk.Tk()
app = BobSims(root)
root.mainloop()
