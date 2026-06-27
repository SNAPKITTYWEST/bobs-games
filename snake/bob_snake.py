"""
BOB SOVEREIGN SNAKE — Python/curses
Run: python bob_snake.py
"""
import curses, random, hashlib, time

def main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    curses.start_color()
    curses.init_pair(1, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # gold
    curses.init_pair(2, curses.COLOR_RED,    curses.COLOR_BLACK)  # food
    curses.init_pair(3, curses.COLOR_CYAN,   curses.COLOR_BLACK)  # border
    curses.init_pair(4, curses.COLOR_WHITE,  curses.COLOR_BLACK)  # text

    GOLD  = curses.color_pair(1) | curses.A_BOLD
    RED   = curses.color_pair(2) | curses.A_BOLD
    CYAN  = curses.color_pair(3)
    WHITE = curses.color_pair(4)

    H, W = stdscr.getmaxyx()
    GH, GW = 20, 40
    OY, OX = 3, (W - GW) // 2   # grid origin

    def draw_chrome():
        stdscr.clear()
        title = "  B O B   S O V E R E I G N   S N A K E  "
        stdscr.addstr(1, (W - len(title)) // 2, title, GOLD)
        ctrl = "WASD / ARROWS  |  Q: quit"
        stdscr.addstr(2, (W - len(ctrl)) // 2, ctrl, WHITE)

        # border
        for x in range(GW + 2):
            stdscr.addch(OY,      OX + x - 1, '-', CYAN)
            stdscr.addch(OY + GH + 1, OX + x - 1, '-', CYAN)
        for y in range(GH + 2):
            stdscr.addch(OY + y, OX - 1,      '|', CYAN)
            stdscr.addch(OY + y, OX + GW,     '|', CYAN)
        stdscr.addch(OY,          OX - 1,      '+', CYAN)
        stdscr.addch(OY,          OX + GW,     '+', CYAN)
        stdscr.addch(OY + GH + 1, OX - 1,      '+', CYAN)
        stdscr.addch(OY + GH + 1, OX + GW,     '+', CYAN)

    def draw_cell(y, x, ch, attr):
        try:
            stdscr.addch(OY + y + 1, OX + x, ch, attr)
        except curses.error:
            pass

    def erase_cell(y, x):
        draw_cell(y, x, ' ', WHITE)

    def draw_score(score):
        s = f"SCORE: {score}"
        stdscr.addstr(OY + GH + 2, OX, s + "          ", GOLD)

    def spawn_food(snake):
        sset = set(snake)
        while True:
            fx = random.randint(1, GW - 2)
            fy = random.randint(1, GH - 2)
            if (fy, fx) not in sset:
                return fy, fx

    # init snake
    sy, sx = GH // 2, GW // 2
    snake = [(sy, sx), (sy, sx-1), (sy, sx-2)]
    direction = (0, 1)   # going right
    score = 0
    fy, fx = spawn_food(snake)

    draw_chrome()
    # draw initial snake
    for i, (y, x) in enumerate(snake):
        draw_cell(y, x, 'O' if i == 0 else '#', GOLD)
    draw_cell(fy, fx, '*', RED)
    draw_score(score)
    stdscr.refresh()

    DIR_MAP = {
        ord('w'): (-1, 0), ord('W'): (-1, 0),
        ord('s'): ( 1, 0), ord('S'): ( 1, 0),
        ord('a'): ( 0,-1), ord('A'): ( 0,-1),
        ord('d'): ( 0, 1), ord('D'): ( 0, 1),
        curses.KEY_UP:    (-1, 0),
        curses.KEY_DOWN:  ( 1, 0),
        curses.KEY_LEFT:  ( 0,-1),
        curses.KEY_RIGHT: ( 0, 1),
    }

    tick = 0.13

    while True:
        time.sleep(tick)
        key = stdscr.getch()

        if key in (ord('q'), ord('Q')):
            break

        if key in DIR_MAP:
            nd = DIR_MAP[key]
            # prevent reversing
            if (nd[0] + direction[0], nd[1] + direction[1]) != (0, 0):
                direction = nd

        # new head
        hy, hx = snake[0][0] + direction[0], snake[0][1] + direction[1]

        # wall collision
        if not (0 < hx < GW - 1 and 0 < hy < GH - 1):
            break

        # self collision
        if (hy, hx) in set(snake):
            break

        # eat food?
        ate = (hy == fy and hx == fx)

        if not ate:
            tail = snake.pop()
            erase_cell(tail[0], tail[1])

        snake.insert(0, (hy, hx))

        if ate:
            score += 10
            fy, fx = spawn_food(snake)
            draw_cell(fy, fx, '*', RED)
            draw_score(score)
            if tick > 0.06:
                tick -= 0.005   # speed up

        # draw prev head as body
        if len(snake) > 1:
            draw_cell(snake[1][0], snake[1][1], '#', GOLD)

        # draw new head
        draw_cell(hy, hx, 'O', GOLD)
        stdscr.refresh()

    # game over
    seal = hashlib.sha256(f"BOB-SNAKE-{score}".encode()).hexdigest()
    go1 = "+-------------------------+"
    go2 = f"|   SCORE: {score:<5}  SEALED   |"
    go3 = "|    W O R M  S E A L E D |"
    go4 = "+-------------------------+"
    cy = OY + GH // 2
    cx = OX + GW // 2 - 14
    stdscr.addstr(cy,   cx, go1, GOLD)
    stdscr.addstr(cy+1, cx, go2, GOLD)
    stdscr.addstr(cy+2, cx, go3, GOLD)
    stdscr.addstr(cy+3, cx, go4, GOLD)
    stdscr.addstr(cy+5, cx, seal[:40], WHITE)
    stdscr.refresh()
    time.sleep(3)

curses.wrapper(main)
