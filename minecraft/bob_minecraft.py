#!/usr/bin/env python3
"""
BOB MINECRAFT — Sovereign Voxel World
Requires: pip install pygame numpy

Controls:
  WASD / Arrows  move            Q / Esc  quit
  Mouse          look            Space    jump
  Left click     mine block      Right click  place block
  1-8            select block    Scroll   cycle block
"""
import sys, math, hashlib, random
import pygame
import numpy as np

# ── Display ──────────────────────────────────────────────────────────────────
RW, RH   = 480, 270       # low-res render target
SCALE    = 3              # displayed at RW*SCALE × RH*SCALE  (1440 × 810)
WIN_W    = RW * SCALE
WIN_H    = RH * SCALE
COL_W    = 3              # pixels per ray column
N_COLS   = RW // COL_W   # 160 columns
FOV_FAC  = 0.66           # half-width of camera plane  (≈ 66° HFOV)
PROJ_F   = RH * 0.68      # projection scale factor

# ── Block types ──────────────────────────────────────────────────────────────
AIR=0; GRASS=1; DIRT=2; STONE=3; WOOD=4; GOLD=5; GLASS=6; LAVA=7; SAND=8; BEDROCK=9
BNAMES = ['AIR','GRASS','DIRT','STONE','WOOD','GOLD','GLASS','LAVA','SAND','BEDROCK']

# Colors per block: [top, side-z (lighter), side-x (darker)]
BC = {
    GRASS:  [(82,180,82),   (52,148,52),   (40,118,40)],
    DIRT:   [(132,94,60),   (104,64,32),   (86,52,24)],
    STONE:  [(142,142,156), (110,110,124), (90,90,104)],
    WOOD:   [(158,110,62),  (120,80,32),   (100,64,24)],
    GOLD:   [(255,220,0),   (212,170,0),   (180,140,0)],
    GLASS:  [(200,224,252), (170,198,242), (150,178,222)],
    LAVA:   [(255,90,12),   (212,56,0),    (182,38,0)],
    SAND:   [(220,196,102), (184,160,74),  (162,140,56)],
    BEDROCK:[(22,22,30),    (14,14,22),    (8,8,14)],
}
SKY_TOP  = (6, 6, 20)
SKY_BOT  = (12, 12, 32)
GND_COL  = (14, 11, 7)
FOG_DIST = 22.0

# ── World ─────────────────────────────────────────────────────────────────────
WX, WY, WZ = 64, 24, 64
world      = np.zeros((WX, WY, WZ), dtype=np.uint8)
hmap       = np.full((WX, WZ), -1, dtype=np.int16)   # topmost solid Y

def _refresh_hmap(x, z):
    col = world[x, :, z]
    nz  = np.flatnonzero(col)
    hmap[x, z] = int(nz[-1]) if len(nz) else -1

def gb(x, y, z):
    x, y, z = int(x), int(y), int(z)
    if 0 <= x < WX and 0 <= y < WY and 0 <= z < WZ:
        return int(world[x, y, z])
    return BEDROCK

def sb(x, y, z, v):
    x, y, z = int(x), int(y), int(z)
    if 0 <= x < WX and 0 <= y < WY and 0 <= z < WZ:
        world[x, y, z] = v
        _refresh_hmap(x, z)

def gen_world():
    for x in range(WX):
        for z in range(WZ):
            h = int(10 + 4*math.sin(x*.15) + 3*math.cos(z*.12)
                       + 2*math.sin((x+z)*.08) + math.cos(x*.07)*math.sin(z*.09)*2)
            h = max(3, min(WY-3, h))
            world[x, 0,   z] = BEDROCK
            if h > 4: world[x, 1:h-3, z] = STONE
            if h > 3: world[x, max(1,h-3):h, z] = DIRT
            world[x, h, z] = GRASS
    # gold ore seams
    gx = np.random.randint(0, WX, 220)
    gy = np.random.randint(1,  8, 220)
    gz = np.random.randint(0, WZ, 220)
    for i in range(220):
        if world[gx[i], gy[i], gz[i]] == STONE:
            world[gx[i], gy[i], gz[i]] = GOLD
    # sand patches at coasts
    for _ in range(120):
        sx, sz = random.randint(0,WX-1), random.randint(0,WZ-1)
        for y in range(WY-1, 0, -1):
            if world[sx,y,sz] == GRASS:
                if random.random() < .4: world[sx,y,sz] = SAND
                break
    # trees
    for _ in range(26):
        tx, tz = random.randint(3, WX-4), random.randint(3, WZ-4)
        for y in range(WY-1, 0, -1):
            if world[tx, y, tz] == GRASS:
                for h in range(1, 5):
                    if y+h < WY: world[tx, y+h, tz] = WOOD
                break
    # rebuild full height map
    for x in range(WX):
        for z in range(WZ):
            _refresh_hmap(x, z)

gen_world()

# ── Player ───────────────────────────────────────────────────────────────────
class Player:
    __slots__ = ('x','y','z','yaw','pitch','vy','on_ground','sel')
    def __init__(self):
        self.x = WX/2 + .5;  self.y = 0.0;  self.z = WZ/2 + .5
        self.yaw = 0.0;  self.pitch = 0.0
        self.vy = 0.0;   self.on_ground = False
        self.sel = GRASS
        # spawn above surface
        ix, iz = int(self.x), int(self.z)
        for y in range(WY-1, 0, -1):
            if gb(ix, y, iz) != AIR:
                self.y = y + 2.2;  break
    def eye(self):
        return self.x, self.y - 0.3, self.z

GRAV   = 0.055
JUMP_V = 0.44
SPEED  = 0.09

def solid(x, y, z):
    b = gb(x, y, z)
    return b != AIR and b != GLASS

def player_move(p, dx, dz):
    nx = p.x + dx
    if not (solid(nx, p.y-.1, p.z) or solid(nx, p.y-1., p.z) or solid(nx, p.y-1.9, p.z)):
        p.x = nx
    nz = p.z + dz
    if not (solid(p.x, p.y-.1, nz) or solid(p.x, p.y-1., nz) or solid(p.x, p.y-1.9, nz)):
        p.z = nz

def physics(p):
    p.vy += GRAV
    ny = p.y + p.vy
    if p.vy > 0 and solid(p.x, ny-1.95, p.z):
        p.on_ground = True;  p.vy = 0.0
    elif p.vy < 0 and solid(p.x, ny-.05, p.z):
        p.vy = 0.0
    else:
        p.y = ny;  p.on_ground = False
    p.x = max(.5, min(WX-.5, p.x))
    p.y = max(2.0, min(WY-1., p.y))
    p.z = max(.5, min(WZ-.5, p.z))

# ── Renderer ──────────────────────────────────────────────────────────────────
_sky = None   # cached gradient surface

def _make_sky(w, h):
    s = pygame.Surface((w, h))
    for y in range(h):
        t = y / max(1, h-1)
        c = (int(SKY_TOP[0] + t*(SKY_BOT[0]-SKY_TOP[0])),
             int(SKY_TOP[1] + t*(SKY_BOT[1]-SKY_TOP[1])),
             int(SKY_TOP[2] + t*(SKY_BOT[2]-SKY_TOP[2])))
        pygame.draw.line(s, c, (0, y), (w, y))
    return s

def _fog(col, dist):
    t = min(1.0, dist / FOG_DIST)
    return (int(col[0]*(1-t) + GND_COL[0]*t),
            int(col[1]*(1-t) + GND_COL[1]*t),
            int(col[2]*(1-t) + 10*t))

def render(surf, p):
    global _sky
    w, h = surf.get_size()
    if _sky is None or _sky.get_size() != (w, h):
        _sky = _make_sky(w, h)

    fx = math.cos(p.yaw);  fz = math.sin(p.yaw)
    # camera plane (correct: left-col = left of view)
    plx =  fz * FOV_FAC
    plz = -fx * FOV_FAC
    ex, ey, ez = p.eye()
    horizon = h * 0.5 + p.pitch * h * 0.4
    ihor    = int(horizon)

    # sky
    surf.blit(_sky, (0, 0))
    if ihor < h:
        surf.fill(GND_COL, (0, ihor, w, h - ihor))

    EPS = 1e-10

    for ci in range(N_COLS):
        col_px = ci * COL_W
        camX   = 2.0 * col_px / w - 1.0   # -1..+1

        rdx = fx + plx * camX
        rdz = fz + plz * camX

        mx, mz = int(p.x), int(p.z)
        sx = 1 if rdx >= 0 else -1
        sz = 1 if rdz >= 0 else -1
        ddx = abs(1.0/rdx) if abs(rdx) > EPS else 1e9
        ddz = abs(1.0/rdz) if abs(rdz) > EPS else 1e9
        sdx = (mx+1-p.x)*ddx if rdx >= 0 else (p.x-mx)*ddx
        sdz = (mz+1-p.z)*ddz if rdz >= 0 else (p.z-mz)*ddz
        face_x = sdx < sdz

        # first step: leave player's own cell
        if sdx < sdz: mx += sx; sdx += ddx; face_x = True
        else:          mz += sz; sdz += ddz; face_x = False

        hit_x = hit_z = -1
        for _ in range(48):
            if 0 <= mx < WX and 0 <= mz < WZ:
                top_y = hmap[mx, mz]
                if top_y > 0:
                    dxh = mx + 0.5 - p.x
                    dzh = mz + 0.5 - p.z
                    pd  = dxh*fx + dzh*fz
                    if pd > 0.2:
                        s_top = horizon - ((top_y + 1 - ey) / pd) * PROJ_F
                        if s_top < h - 1:
                            hit_x, hit_z = mx, mz;  break
            if sdx < sdz: mx += sx; sdx += ddx; face_x = True
            else:          mz += sz; sdz += ddz; face_x = False

        if hit_x < 0:
            continue

        dxh = hit_x + 0.5 - p.x
        dzh = hit_z + 0.5 - p.z
        pd  = max(0.25, dxh*fx + dzh*fz)

        # draw every solid span in the hit column
        yy = WY - 1
        while yy >= 1:
            bl = gb(hit_x, yy, hit_z)
            if bl != AIR:
                y_top = yy
                while yy >= 1 and gb(hit_x, yy, hit_z) != AIR:
                    yy -= 1
                y_bot = yy + 1
                s_top = int(horizon - ((y_top + 1 - ey) / pd) * PROJ_F)
                s_bot = int(horizon - ((y_bot     - ey) / pd) * PROJ_F)
                dt = max(0, s_top)
                db = min(h, s_bot)
                if db > dt:
                    cols  = BC.get(bl, [(120,120,120),(90,90,90),(70,70,70)])
                    c_idx = 2 if face_x else 1   # darker if x-face, lighter if z-face
                    col   = _fog(cols[c_idx], pd)
                    pygame.draw.rect(surf, col, (col_px, dt, COL_W, db - dt))
            else:
                yy -= 1

# ── Aim raycast ───────────────────────────────────────────────────────────────
def raycast_aim(p):
    ex, ey, ez = p.eye()
    dx = math.cos(p.yaw) * math.cos(p.pitch)
    dy = -math.sin(p.pitch)
    dz = math.sin(p.yaw) * math.cos(p.pitch)
    EPS = 1e-10
    ix, iy, iz = int(ex), int(ey), int(ez)
    sx = 1 if dx>=0 else -1;  sy = 1 if dy>=0 else -1;  sz = 1 if dz>=0 else -1
    ddx = abs(1/dx) if abs(dx)>EPS else 1e9
    ddy = abs(1/dy) if abs(dy)>EPS else 1e9
    ddz = abs(1/dz) if abs(dz)>EPS else 1e9
    tx = (ix+1-ex)*ddx if dx>=0 else (ex-ix)*ddx
    ty = (iy+1-ey)*ddy if dy>=0 else (ey-iy)*ddy
    tz = (iz+1-ez)*ddz if dz>=0 else (ez-iz)*ddz
    px_, py_, pz_ = ix, iy, iz
    for _ in range(52):
        b = gb(ix, iy, iz)
        if b != AIR:
            return (ix, iy, iz), (px_, py_, pz_)
        px_, py_, pz_ = ix, iy, iz
        if tx < ty and tx < tz:   ix += sx;  tx += ddx
        elif ty < tz:              iy += sy;  ty += ddy
        else:                      iz += sz;  tz += ddz
    return None, None

# ── WORM chain ────────────────────────────────────────────────────────────────
_worm = 'GENESIS'
def seal(evt):
    global _worm
    _worm = hashlib.sha256(f'{_worm}|{evt}'.encode()).hexdigest()

seal('WORLD_GEN')

# ── HUD ───────────────────────────────────────────────────────────────────────
SLOTS  = [GRASS, DIRT, STONE, WOOD, GOLD, GLASS, LAVA, SAND]
SNAMES = ['GRASS','DIRT','STONE','WOOD','GOLD','GLASS','LAVA','SAND']

def draw_hud(screen, p, fps, aimed):
    W, H = screen.get_size()
    fn = pygame.font.SysFont('Courier New', 13, bold=True)

    # top info bar
    bar = pygame.Surface((W, 24), pygame.SRCALPHA)
    bar.fill((0, 0, 0, 165))
    screen.blit(bar, (0, 0))
    info = (f"XYZ {p.x:.0f},{p.y:.0f},{p.z:.0f}  |  "
            f"{aimed:<8}  |  FPS {fps:>3}  |  WORM {_worm[:14]}...")
    screen.blit(fn.render(info, True, (255, 215, 0)), (7, 5))

    # crosshair
    cx, cy = W//2, H//2
    pygame.draw.line(screen, (0,0,0),       (cx-12,cy),(cx+12,cy), 3)
    pygame.draw.line(screen, (0,0,0),       (cx,cy-12),(cx,cy+12), 3)
    pygame.draw.line(screen, (255,255,255), (cx-10,cy),(cx+10,cy), 2)
    pygame.draw.line(screen, (255,255,255), (cx,cy-10),(cx,cy+10), 2)

    # toolbar
    SZ, GAP = 46, 3
    tw = len(SLOTS) * (SZ + GAP) - GAP
    tx = (W - tw) // 2
    ty = H - SZ - 10
    bg = pygame.Surface((tw+8, SZ+8), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 175))
    screen.blit(bg, (tx-4, ty-4))
    si = SLOTS.index(p.sel) if p.sel in SLOTS else 0
    for i, bl in enumerate(SLOTS):
        bx = tx + i*(SZ+GAP)
        cols = BC.get(bl, [(100,100,100)]*3)
        pygame.draw.rect(screen, cols[0],  (bx, ty,       SZ, SZ//2))
        pygame.draw.rect(screen, cols[1],  (bx, ty+SZ//2, SZ, SZ - SZ//2))
        border_col = (255, 215, 0) if i == si else (55, 55, 65)
        border_w   = 3 if i == si else 1
        pygame.draw.rect(screen, border_col, (bx-1, ty-1, SZ+2, SZ+2), border_w)
        lt = fn.render(SNAMES[i][:3], True, (255, 255, 255))
        screen.blit(lt, (bx + 2, ty + SZ - 15))

    # selected block name
    bn = fn.render(SNAMES[si], True, (255, 215, 0))
    screen.blit(bn, ((W - bn.get_width())//2, ty - 22))

# ── Intro screen ──────────────────────────────────────────────────────────────
def show_intro(screen):
    W, H   = screen.get_size()
    f_big  = pygame.font.SysFont('Courier New', 52, bold=True)
    f_med  = pygame.font.SysFont('Courier New', 18, bold=True)
    f_sm   = pygame.font.SysFont('Courier New', 14)
    clock  = pygame.time.Clock()
    lines  = [
        ('BOB MINECRAFT',                                            (255,215,0), f_big, H//2-140),
        ('SOVEREIGN VOXEL WORLD  ·  WORM SEALED',                   (90,90,110), f_med, H//2-60),
        ('WASD / Arrows  =  move          Space  =  jump',          (55,55,75),  f_sm,  H//2+10),
        ('Mouse          =  look          Q/Esc  =  quit',          (55,55,75),  f_sm,  H//2+32),
        ('Left Click     =  mine          Right Click  =  place',   (55,55,75),  f_sm,  H//2+54),
        ('1-8 / Scroll   =  select block',                          (55,55,75),  f_sm,  H//2+76),
        ('PRESS ANY KEY OR CLICK TO ENTER THE WORLD',               (255,215,0), f_med, H//2+130),
    ]
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:          pygame.quit(); sys.exit()
            if ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                return
        screen.fill((4, 4, 18))
        for text, col, font, y in lines:
            s = font.render(text, True, col)
            screen.blit(s, (W//2 - s.get_width()//2, y))
        pygame.display.flip()
        clock.tick(30)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    pygame.init()
    screen       = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption('BOB MINECRAFT — Sovereign Voxel World')
    render_surf  = pygame.Surface((RW, RH))
    clock        = pygame.time.Clock()

    show_intro(screen)

    pygame.mouse.set_visible(False)
    pygame.event.set_grab(True)

    p          = Player()
    fps        = 0
    frame      = 0
    aimed      = 'AIR'
    mine_cool  = 0
    place_cool = 0

    while True:
        clock.tick(60)
        frame += 1
        if frame % 20 == 0:
            fps = int(clock.get_fps())

        # ── events ──
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            if ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_ESCAPE, pygame.K_q):
                    pygame.quit(); sys.exit()
                if ev.key == pygame.K_SPACE and p.on_ground:
                    p.vy = -JUMP_V;  p.on_ground = False
                for i in range(len(SLOTS)):
                    k = getattr(pygame, f'K_{i+1}', None)
                    if k and ev.key == k:
                        p.sel = SLOTS[i]

            if ev.type == pygame.MOUSEMOTION:
                p.yaw    = (p.yaw + ev.rel[0] * .002) % (2*math.pi)
                p.pitch  = max(-1.3, min(1.3, p.pitch + ev.rel[1] * .002))

            if ev.type == pygame.MOUSEWHEEL:
                si  = SLOTS.index(p.sel) if p.sel in SLOTS else 0
                p.sel = SLOTS[(si + (-1 if ev.y > 0 else 1)) % len(SLOTS)]

        # ── movement ──
        fx = math.cos(p.yaw);  fz = math.sin(p.yaw)
        keys = pygame.key.get_pressed()
        if keys[pygame.K_w] or keys[pygame.K_UP]:    player_move(p,  fx*SPEED,  fz*SPEED)
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  player_move(p, -fx*SPEED, -fz*SPEED)
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  player_move(p, -fz*SPEED,  fx*SPEED)
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: player_move(p,  fz*SPEED, -fx*SPEED)

        physics(p)

        # ── held-button mining / placing ──
        mine_cool  = max(0, mine_cool  - 1)
        place_cool = max(0, place_cool - 1)
        mb = pygame.mouse.get_pressed()

        if mb[0] and mine_cool == 0:
            bp, _ = raycast_aim(p)
            if bp and gb(*bp) != BEDROCK:
                seal(f'BREAK|{BNAMES[gb(*bp)]}')
                sb(*bp, AIR)
                mine_cool = 7

        if mb[2] and place_cool == 0:
            bp, prev = raycast_aim(p)
            if bp and prev and gb(*prev) == AIR:
                seal(f'PLACE|{BNAMES[p.sel]}')
                sb(*prev, p.sel)
                place_cool = 7

        # ── update aimed label every 6 frames ──
        if frame % 6 == 0:
            bp, _ = raycast_aim(p)
            aimed = BNAMES[gb(*bp)] if bp else 'AIR'

        # ── draw ──
        render(render_surf, p)
        scaled = pygame.transform.scale(render_surf, (WIN_W, WIN_H))
        screen.blit(scaled, (0, 0))
        draw_hud(screen, p, fps, aimed)
        pygame.display.flip()

if __name__ == '__main__':
    main()
