"""BOB SOVEREIGN SNAKE - tkinter edition.
SPDX-License-Identifier: MIT
Copyright (c) 2026 SnapKitty Collective

Run: python bob_snake.py
Controls: WASD / arrows to move, Space to restart, Q/Esc to quit.
"""
from __future__ import annotations

import hashlib
import random
import time
import tkinter as tk
from pathlib import Path

GRID_W = 40
GRID_H = 24
START_DELAY_MS = 135
MIN_DELAY_MS = 55
SPEED_STEP_MS = 4

BG = "#050507"
PANEL = "#0d0d12"
GOLD = "#ffd700"
GOLD_DARK = "#9b6b00"
RED = "#ff3333"
CYAN = "#00d4ff"
GREEN = "#00ff88"
MAGENTA = "#d36bff"
WHITE = "#e8e8e8"

DIRS: dict[str, tuple[int, int]] = {
    "Up": (0, -1),
    "Down": (0, 1),
    "Left": (-1, 0),
    "Right": (1, 0),
    "w": (0, -1),
    "W": (0, -1),
    "s": (0, 1),
    "S": (0, 1),
    "a": (-1, 0),
    "A": (-1, 0),
    "d": (1, 0),
    "D": (1, 0),
}


class BobSnake:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("BOB SOVEREIGN SNAKE")
        self.root.configure(bg=BG)
        self.root.minsize(760, 560)

        self.high_score_path = Path(__file__).with_name("snake_high_score.txt")
        self.high_score = self._load_high_score()

        self.canvas = tk.Canvas(root, bg=BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.direction = (1, 0)
        self.pending_direction = self.direction
        self.snake: list[tuple[int, int]] = []
        self.food = (0, 0)
        self.score = 0
        self.delay_ms = START_DELAY_MS
        self.game_over = False
        self.paused = False
        self.last_tick = time.time()

        self.cell = 18
        self.origin_x = 0
        self.origin_y = 0
        self.board_w = 0
        self.board_h = 0

        for key in list(DIRS):
            root.bind(f"<{key}>", self.on_key)
        root.bind("<space>", self.restart)
        root.bind("<Escape>", lambda _event: root.destroy())
        root.bind("q", lambda _event: root.destroy())
        root.bind("Q", lambda _event: root.destroy())
        root.bind("p", self.toggle_pause)
        root.bind("P", self.toggle_pause)
        root.bind("<Configure>", lambda _event: self.draw())

        self.reset()
        self.loop()

    def _load_high_score(self) -> int:
        try:
            return max(0, int(self.high_score_path.read_text(encoding="utf-8").strip()))
        except (OSError, ValueError):
            return 0

    def _save_high_score(self) -> None:
        try:
            self.high_score_path.write_text(str(self.high_score), encoding="utf-8")
        except OSError:
            pass

    def reset(self) -> None:
        mid_x = GRID_W // 2
        mid_y = GRID_H // 2
        self.snake = [(mid_x, mid_y), (mid_x - 1, mid_y), (mid_x - 2, mid_y)]
        self.direction = (1, 0)
        self.pending_direction = self.direction
        self.score = 0
        self.delay_ms = START_DELAY_MS
        self.game_over = False
        self.paused = False
        self.food = self.spawn_food()
        self.draw()

    def restart(self, _event: tk.Event | None = None) -> None:
        if self.game_over:
            self.reset()

    def toggle_pause(self, _event: tk.Event | None = None) -> None:
        if not self.game_over:
            self.paused = not self.paused
            self.draw()

    def on_key(self, event: tk.Event) -> None:
        if self.game_over:
            return
        next_dir = DIRS.get(event.keysym) or DIRS.get(event.char)
        if not next_dir:
            return
        if (next_dir[0] + self.direction[0], next_dir[1] + self.direction[1]) != (0, 0):
            self.pending_direction = next_dir

    def spawn_food(self) -> tuple[int, int]:
        occupied = set(self.snake)
        free = [(x, y) for y in range(1, GRID_H - 1) for x in range(1, GRID_W - 1) if (x, y) not in occupied]
        if not free:
            return (-1, -1)
        return random.choice(free)

    def step(self) -> None:
        if self.game_over or self.paused:
            return

        self.direction = self.pending_direction
        head_x, head_y = self.snake[0]
        dx, dy = self.direction
        new_head = (head_x + dx, head_y + dy)
        ate = new_head == self.food

        if ate:
            collision_body = set(self.snake)
        else:
            collision_body = set(self.snake[:-1])

        wall_hit = not (0 < new_head[0] < GRID_W - 1 and 0 < new_head[1] < GRID_H - 1)
        self_hit = new_head in collision_body
        if wall_hit or self_hit:
            self.end_game()
            return

        self.snake.insert(0, new_head)
        if ate:
            self.score += 10
            self.delay_ms = max(MIN_DELAY_MS, self.delay_ms - SPEED_STEP_MS)
            self.food = self.spawn_food()
            if self.food == (-1, -1):
                self.end_game()
                return
        else:
            self.snake.pop()

    def end_game(self) -> None:
        self.game_over = True
        if self.score > self.high_score:
            self.high_score = self.score
            self._save_high_score()
        self.draw()

    def update_geometry(self) -> None:
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        usable_w = max(200, width - 48)
        usable_h = max(160, height - 132)
        self.cell = max(8, min(usable_w // GRID_W, usable_h // GRID_H))
        self.board_w = self.cell * GRID_W
        self.board_h = self.cell * GRID_H
        self.origin_x = (width - self.board_w) // 2
        self.origin_y = 82

    def draw(self) -> None:
        self.update_geometry()
        c = self.canvas
        c.delete("all")

        width = c.winfo_width()
        c.create_rectangle(0, 0, width, 70, fill=PANEL, outline="#20202a")
        c.create_text(width // 2, 22, text="B O B   S O V E R E I G N   S N A K E", fill=GOLD, font=("Courier New", 18, "bold"))
        status = "PAUSED" if self.paused else ("WORM SEALED" if self.game_over else "LIVE")
        c.create_text(width // 2, 50, text=f"SCORE {self.score:04d}  |  HIGH {self.high_score:04d}  |  SPEED {1000 // self.delay_ms:02d} TPS  |  {status}", fill=WHITE, font=("Courier New", 10))

        x0 = self.origin_x
        y0 = self.origin_y
        x1 = x0 + self.board_w
        y1 = y0 + self.board_h
        c.create_rectangle(x0 - 2, y0 - 2, x1 + 2, y1 + 2, outline=CYAN, width=2)
        c.create_rectangle(x0, y0, x1, y1, fill="#09090d", outline="")

        for x in range(GRID_W):
            for y in range(GRID_H):
                if x in (0, GRID_W - 1) or y in (0, GRID_H - 1):
                    self.draw_cell(x, y, "#121824", CYAN)

        fx, fy = self.food
        if fx >= 0:
            self.draw_cell(fx, fy, RED, "#ff7777", oval=True)

        for i, (x, y) in enumerate(reversed(self.snake)):
            is_head = i == len(self.snake) - 1
            fill = GOLD if is_head else "#dca900"
            outline = "#fff2a0" if is_head else GOLD_DARK
            self.draw_cell(x, y, fill, outline, oval=is_head)

        if self.game_over:
            self.draw_game_over()

        c.create_text(x0, y1 + 20, text="WASD / ARROWS move   P pause   SPACE restart after seal   Q quit", fill="#8e8e9a", font=("Courier New", 9), anchor="w")

    def draw_cell(self, x: int, y: int, fill: str, outline: str, oval: bool = False) -> None:
        pad = max(1, self.cell // 9)
        x0 = self.origin_x + x * self.cell + pad
        y0 = self.origin_y + y * self.cell + pad
        x1 = self.origin_x + (x + 1) * self.cell - pad
        y1 = self.origin_y + (y + 1) * self.cell - pad
        if oval:
            self.canvas.create_oval(x0, y0, x1, y1, fill=fill, outline=outline, width=2)
        else:
            self.canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline)

    def draw_game_over(self) -> None:
        seal = hashlib.sha256(f"BOB-SNAKE:{self.score}:{self.high_score}".encode("utf-8")).hexdigest()
        cx = self.origin_x + self.board_w // 2
        cy = self.origin_y + self.board_h // 2
        w = min(520, self.board_w - 40)
        h = 170
        self.canvas.create_rectangle(cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2, fill="#070707", outline=GOLD, width=3)
        self.canvas.create_text(cx, cy - 48, text="W O R M   S E A L E D", fill=GOLD, font=("Courier New", 20, "bold"))
        self.canvas.create_text(cx, cy - 14, text=f"SCORE: {self.score}    HIGH: {self.high_score}", fill=WHITE, font=("Courier New", 12, "bold"))
        self.canvas.create_text(cx, cy + 18, text=f"SHA-256: {seal[:40]}", fill=MAGENTA, font=("Courier New", 10))
        self.canvas.create_text(cx, cy + 52, text="SPACE to restart   Q to quit", fill=GREEN, font=("Courier New", 10, "bold"))

    def loop(self) -> None:
        self.step()
        self.draw()
        self.root.after(self.delay_ms if not self.paused else 100, self.loop)


if __name__ == "__main__":
    root = tk.Tk()
    BobSnake(root)
    root.mainloop()
