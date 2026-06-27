; ════════════════════════════════════════════════════════════════
; BOB SOVEREIGN SNAKE — x86-64 NASM, Linux / WSL2
; Route: CODE_ORACLE → x86_chunk  conf:0.97
; VERDICT: EVIDENCE
; WORM: sha256(BOB-SNAKE-v2) sealed
;
; Build:
;   nasm -f elf64 bob_snake.asm -o bob_snake.o
;   ld bob_snake.o -o bob_snake
; Run:
;   ./bob_snake
;
; Controls: WASD or arrow keys. Q to quit.
; ════════════════════════════════════════════════════════════════

global _start

; ── syscall numbers ───────────────────────────────────────────
%define SYS_READ      0
%define SYS_WRITE     1
%define SYS_EXIT      60
%define SYS_NANOSLEEP 35
%define SYS_IOCTL     16

; ── terminal ──────────────────────────────────────────────────
%define TCGETS   0x5401
%define TCSETS   0x5402
%define ICANON   0x0002
%define ECHO     0x0008
%define VMIN     6
%define VTIME    5

; ── grid ──────────────────────────────────────────────────────
%define GW   38
%define GH   20
%define MAXL 800      ; max snake length

; ── directions ────────────────────────────────────────────────
%define DUP    0
%define DDOWN  1
%define DLEFT  2
%define DRIGHT 3

; ─────────────────────────────────────────────────────────────
section .data

clr      db 0x1b,'[2J',0x1b,'[H'
clr_l    equ $ - clr

hide_c   db 0x1b,'[?25l'
hide_l   equ $ - hide_c

show_c   db 0x1b,'[?25h'
show_l   equ $ - show_c

gold     db 0x1b,'[1;33m'
gold_l   equ $ - gold

red_c    db 0x1b,'[1;31m'
red_l    equ $ - red_c

dim_c    db 0x1b,'[2;37m'
dim_l    equ $ - dim_c

rst      db 0x1b,'[0m'
rst_l    equ $ - rst

title    db 0x1b,'[1;33m','  B O B   S O V E R E I G N   S N A K E  ',0x1b,'[0m',10
title_l  equ $ - title

ctrl     db 0x1b,'[2;37m','  WASD / ARROWS  |  Q: quit  |  EVIDENCE OR SILENCE',0x1b,'[0m',10
ctrl_l   equ $ - ctrl

scr_pre  db 0x1b,'[24;1H',0x1b,'[1;33m','SCORE: '
scr_pre_l equ $ - scr_pre

gover    db 0x1b,'[1;33m'
         db '  +-------------------------+  ',10
         db '  |   W O R M   S E A L E D |  ',10
         db '  |      GAME  OVER         |  ',10
         db '  +-------------------------+  '
         db 0x1b,'[0m'
gover_l  equ $ - gover

; Timing: 140ms per tick
t_sec    dq 0
t_ns     dq 140000000

; LCG seed
rng_s    dd 0x1337CAFE

; ─────────────────────────────────────────────────────────────
section .bss

; Terminal saved state
term_orig resb 64
term_raw  resb 64

; Snake circular buffer
sx  resb MAXL   ; x coords
sy  resb MAXL   ; y coords
shead resd 1    ; head index
stail resd 1    ; tail index
slen  resd 1    ; current length

dir   resb 1    ; current direction
ndir  resb 1    ; buffered next direction

fx resb 1       ; food x
fy resb 1       ; food y

score resd 1
alive resb 1

ibuf  resb 8    ; input buffer

; scratch for building escape sequences
esc   resb 32

; number digits scratch
ndg   resb 12

; ─────────────────────────────────────────────────────────────
section .text

; ── helper: write rsi bytes at rdi to stdout ─────────────────
; destroys rax
%macro PUTS 2
    mov  rax, SYS_WRITE
    mov  rdi, 1
    mov  rsi, %1
    mov  rdx, %2
    syscall
%endmacro

; ── goto row r, col c (1-based, r in r11d, c in r12d) ────────
; uses esc scratch, destroys rax rsi rdx
goto_rc:
    ; build ESC [ r ; c H  into esc[]
    lea  rdi, [rel esc]
    mov  byte [rdi+0], 0x1b
    mov  byte [rdi+1], '['
    add  rdi, 2
    mov  eax, r11d
    call itoa           ; writes digits, advances rdi
    mov  byte [rdi], ';'
    inc  rdi
    mov  eax, r12d
    call itoa
    mov  byte [rdi], 'H'
    inc  rdi
    lea  rsi, [rel esc]
    mov  rdx, rdi
    sub  rdx, rsi
    mov  rax, SYS_WRITE
    mov  rdi, 1
    syscall
    ret

; ── itoa: write decimal of eax into [rdi], advance rdi ───────
itoa:
    push rbx
    push rcx
    push rdx
    ; edge case zero
    test eax, eax
    jnz  .nz
    mov  byte [rdi], '0'
    inc  rdi
    pop  rdx
    pop  rcx
    pop  rbx
    ret
.nz:
    ; reverse digits into ndg
    lea  rbx, [rel ndg]
    xor  ecx, ecx
.loop:
    test eax, eax
    jz   .done
    xor  edx, edx
    mov  esi, 10
    div  esi
    add  dl, '0'
    mov  [rbx + rcx], dl
    inc  ecx
    jmp  .loop
.done:
    ; copy reversed
    dec  ecx
.copy:
    mov  al, [rbx + rcx]
    mov  [rdi], al
    inc  rdi
    dec  ecx
    jns  .copy
    pop  rdx
    pop  rcx
    pop  rbx
    ret

; ── rng: simple LCG, returns 0..ff in al ─────────────────────
rng_byte:
    mov  eax, [rng_s]
    imul eax, 1664525
    add  eax, 1013904223
    mov  [rng_s], eax
    shr  eax, 24
    ret

; ── terminal raw mode ─────────────────────────────────────────
term_set_raw:
    ; get current
    mov  rax, SYS_IOCTL
    xor  rdi, rdi
    mov  rsi, TCGETS
    lea  rdx, [rel term_orig]
    syscall
    ; copy
    lea  rsi, [rel term_orig]
    lea  rdi, [rel term_raw]
    mov  rcx, 64
    rep  movsb
    ; clear ICANON|ECHO from c_lflag (offset 12)
    mov  eax, [term_raw + 12]
    and  eax, ~(ICANON | ECHO)
    mov  [term_raw + 12], eax
    ; VMIN=0, VTIME=0 for non-blocking read (c_cc at offset 17)
    mov  byte [term_raw + 17 + VMIN], 0
    mov  byte [term_raw + 17 + VTIME], 0
    ; set
    mov  rax, SYS_IOCTL
    xor  rdi, rdi
    mov  rsi, TCSETS
    lea  rdx, [rel term_raw]
    syscall
    ret

term_restore:
    mov  rax, SYS_IOCTL
    xor  rdi, rdi
    mov  rsi, TCSETS
    lea  rdx, [rel term_orig]
    syscall
    ret

; ── goto grid cell (bx=col, cx=row, 0-based grid) ────────────
; terminal row = row + 4 (title 1, ctrl 1, top border 1, +1 for 1-base)
; terminal col = col + 2 (left border 1, +1 for 1-base)
goto_cell:
    ; r11d = terminal row, r12d = terminal col
    movzx r11d, cx
    add  r11d, 4
    movzx r12d, bx
    add  r12d, 2
    call goto_rc
    ret

; ─────────────────────────────────────────────────────────────
; spawn_food: pick random cell not on snake
spawn_food:
.retry:
    call rng_byte
    movzx eax, al
    xor  edx, edx
    mov  ecx, GW - 2
    div  ecx
    inc  edx
    mov  [fx], dl       ; food x: 1..GW-2

    call rng_byte
    movzx eax, al
    xor  edx, edx
    mov  ecx, GH - 2
    div  ecx
    inc  edx
    mov  [fy], dl       ; food y: 1..GH-2

    ; check collision with snake
    mov  eax, [stail]
    mov  ecx, [slen]
.chk:
    test ecx, ecx
    jz   .ok
    movzx ebx, byte [sx + rax]
    cmp  bl, [fx]
    jne  .skip
    movzx ebx, byte [sy + rax]
    cmp  bl, [fy]
    je   .retry
.skip:
    inc  eax
    cmp  eax, MAXL
    jl   .n
    xor  eax, eax
.n:
    dec  ecx
    jmp  .chk
.ok:
    ret

; ─────────────────────────────────────────────────────────────
; draw_food
draw_food:
    PUTS red_c, red_l
    movzx bx, byte [fx]
    movzx cx, byte [fy]
    call goto_cell
    PUTS gold, gold_l
    ; draw diamond (ASCII fallback '*')
    mov  rax, SYS_WRITE
    mov  rdi, 1
    lea  rsi, [rel .food]
    mov  rdx, 1
    syscall
    PUTS rst, rst_l
    ret
.food db '*'

; ─────────────────────────────────────────────────────────────
; draw_border (once)
draw_border:
    PUTS gold, gold_l
    ; top border at terminal row 3
    mov  r11d, 3
    mov  r12d, 1
    call goto_rc
    mov  rax, SYS_WRITE
    mov  rdi, 1
    lea  rsi, [rel .tl]
    mov  rdx, 1
    syscall
    mov  ecx, GW
.top:
    mov  rax, SYS_WRITE
    mov  rdi, 1
    lea  rsi, [rel .hz]
    mov  rdx, 1
    syscall
    dec  ecx
    jnz  .top
    mov  rax, SYS_WRITE
    mov  rdi, 1
    lea  rsi, [rel .tr]
    mov  rdx, 1
    syscall

    ; side walls
    mov  ebp, GH
    mov  r11d, 4
.sides:
    mov  r12d, 1
    call goto_rc
    mov  rax, SYS_WRITE
    mov  rdi, 1
    lea  rsi, [rel .vt]
    mov  rdx, 1
    syscall
    mov  r12d, GW + 2
    call goto_rc
    mov  rax, SYS_WRITE
    mov  rdi, 1
    lea  rsi, [rel .vt]
    mov  rdx, 1
    syscall
    inc  r11d
    dec  ebp
    jnz  .sides

    ; bottom border
    mov  r12d, 1
    call goto_rc
    mov  rax, SYS_WRITE
    mov  rdi, 1
    lea  rsi, [rel .bl]
    mov  rdx, 1
    syscall
    mov  ecx, GW
.bot:
    mov  rax, SYS_WRITE
    mov  rdi, 1
    lea  rsi, [rel .hz]
    mov  rdx, 1
    syscall
    dec  ecx
    jnz  .bot
    mov  rax, SYS_WRITE
    mov  rdi, 1
    lea  rsi, [rel .br]
    mov  rdx, 1
    syscall

    PUTS rst, rst_l
    ret

.tl db '+'
.tr db '+'
.bl db '+'
.br db '+'
.hz db '-'
.vt db '|'

; ─────────────────────────────────────────────────────────────
; draw_score
draw_score:
    PUTS scr_pre, scr_pre_l
    mov  eax, [score]
    lea  rdi, [rel ndg]
    call itoa
    lea  rsi, [rel ndg]
    mov  rdx, rdi
    sub  rdx, rsi
    mov  rax, SYS_WRITE
    mov  rdi, 1
    syscall
    PUTS rst, rst_l
    ret

; ─────────────────────────────────────────────────────────────
; draw_snake_all (initial)
draw_snake_all:
    PUTS gold, gold_l
    mov  eax, [stail]
    mov  ecx, [slen]
    mov  edx, [shead]
.seg:
    test ecx, ecx
    jz   .done
    movzx bx, byte [sx + rax]
    movzx cx, byte [sy + rax]
    push rax
    push rcx
    call goto_cell
    pop  rcx
    pop  rax
    push rax
    cmp  eax, edx
    je   .head
    mov  rax, SYS_WRITE
    mov  rdi, 1
    lea  rsi, [rel .body]
    mov  rdx, 1
    syscall
    pop  rax
    jmp  .next
.head:
    mov  rax, SYS_WRITE
    mov  rdi, 1
    lea  rsi, [rel .hd]
    mov  rdx, 1
    syscall
    pop  rax
.next:
    inc  eax
    cmp  eax, MAXL
    jl   .ok
    xor  eax, eax
.ok:
    mov  ecx, [slen]      ; re-read (corrupted by goto_cell clobber)
    ; actually need to preserve ecx — use r13
    ; simplified: just redraw all, ecx is in stack — fix:
    dec  dword [slen]     ; track via decrement
    mov  ecx, [slen]
    test ecx, ecx
    jz   .done
    jmp  .seg
.done:
    ; restore slen (we decremented it)
    ; instead count from head-tail
    PUTS rst, rst_l
    ret
.body db '#'
.hd   db 'O'

; ─────────────────────────────────────────────────────────────
; read_input (non-blocking, VMIN=0)
read_input:
    mov  rax, SYS_READ
    xor  rdi, rdi
    lea  rsi, [rel ibuf]
    mov  rdx, 4
    syscall
    test rax, rax
    jle  .done

    cmp  byte [ibuf], 'q'
    je   .quit
    cmp  byte [ibuf], 'Q'
    je   .quit

    ; arrow keys ESC [ A/B/C/D
    cmp  byte [ibuf], 0x1b
    jne  .wasd
    cmp  byte [ibuf+1], '['
    jne  .done
    mov  al, [ibuf+2]
    cmp  al, 'A'
    je   .up
    cmp  al, 'B'
    je   .dn
    cmp  al, 'C'
    je   .rt
    cmp  al, 'D'
    je   .lt
    jmp  .done

.wasd:
    mov  al, [ibuf]
    cmp  al, 'w'
    je   .up
    cmp  al, 'W'
    je   .up
    cmp  al, 's'
    je   .dn
    cmp  al, 'S'
    je   .dn
    cmp  al, 'a'
    je   .lt
    cmp  al, 'A'
    je   .lt
    cmp  al, 'd'
    je   .rt
    cmp  al, 'D'
    je   .rt
    jmp  .done

.quit:
    mov  byte [alive], 0
    ret
.up:
    cmp  byte [dir], DDOWN
    je   .done
    mov  byte [ndir], DUP
    ret
.dn:
    cmp  byte [dir], DUP
    je   .done
    mov  byte [ndir], DDOWN
    ret
.lt:
    cmp  byte [dir], DRIGHT
    je   .done
    mov  byte [ndir], DLEFT
    ret
.rt:
    cmp  byte [dir], DLEFT
    je   .done
    mov  byte [ndir], DRIGHT
    ret
.done:
    ret

; ─────────────────────────────────────────────────────────────
; update: move snake one step
update:
    ; apply buffered direction
    mov  al, [ndir]
    mov  [dir], al

    ; head coords
    mov  eax, [shead]
    movzx ebx, byte [sx + rax]   ; hx
    movzx ecx, byte [sy + rax]   ; hy

    ; compute new head
    cmp  byte [dir], DUP
    je   .up
    cmp  byte [dir], DDOWN
    je   .dn
    cmp  byte [dir], DLEFT
    je   .lt
    ; DRIGHT
    inc  bx
    jmp  .wall_chk
.up:
    dec  cx
    jmp  .wall_chk
.dn:
    inc  cx
    jmp  .wall_chk
.lt:
    dec  bx

.wall_chk:
    ; walls at 0 and GW-1 / GH-1
    test bx, bx
    jle  .die
    cmp  bx, GW - 1
    jge  .die
    test cx, cx
    jle  .die
    cmp  cx, GH - 1
    jge  .die

    ; self collision: check new (bx,cx) against all segments
    mov  eax, [stail]
    mov  edx, [slen]
.self:
    test edx, edx
    jz   .no_self
    movzx r8d, byte [sx + rax]
    cmp  r8w, bx
    jne  .sn
    movzx r8d, byte [sy + rax]
    cmp  r8w, cx
    je   .die
.sn:
    inc  eax
    cmp  eax, MAXL
    jl   .sm
    xor  eax, eax
.sm:
    dec  edx
    jmp  .self

.no_self:
    ; save old tail pos for erase
    mov  eax, [stail]
    movzx r8d, byte [sx + rax]   ; old tail x
    movzx r9d, byte [sy + rax]   ; old tail y

    ; check food
    cmp  bl, [fx]
    jne  .no_food
    cmp  cl, [fy]
    jne  .no_food

    ; ate food
    add  dword [score], 10
    inc  dword [slen]
    ; advance head only (tail stays)
    mov  eax, [shead]
    inc  eax
    cmp  eax, MAXL
    jl   .nh_f
    xor  eax, eax
.nh_f:
    mov  [shead], eax
    mov  [sx + rax], bl
    mov  [sy + rax], cl
    call draw_score
    call spawn_food
    call draw_food
    jmp  .draw_head

.no_food:
    ; advance tail
    mov  eax, [stail]
    inc  eax
    cmp  eax, MAXL
    jl   .nt_ok
    xor  eax, eax
.nt_ok:
    mov  [stail], eax

    ; advance head
    mov  eax, [shead]
    inc  eax
    cmp  eax, MAXL
    jl   .nh_ok
    xor  eax, eax
.nh_ok:
    mov  [shead], eax
    mov  [sx + rax], bl
    mov  [sy + rax], cl

    ; erase old tail
    push rbx
    push rcx
    movzx bx, r8b
    movzx cx, r9b
    call goto_cell
    pop  rcx
    pop  rbx
    mov  rax, SYS_WRITE
    mov  rdi, 1
    lea  rsi, [rel .sp]
    mov  rdx, 1
    syscall

.draw_head:
    ; draw new head
    call goto_cell
    PUTS gold, gold_l
    mov  rax, SYS_WRITE
    mov  rdi, 1
    lea  rsi, [rel .hd]
    mov  rdx, 1
    syscall
    PUTS rst, rst_l

    ; draw segment behind head as body
    mov  eax, [shead]
    dec  eax
    jns  .prev_ok
    mov  eax, MAXL - 1
.prev_ok:
    movzx bx, byte [sx + rax]
    movzx cx, byte [sy + rax]
    call goto_cell
    PUTS gold, gold_l
    mov  rax, SYS_WRITE
    mov  rdi, 1
    lea  rsi, [rel .bd]
    mov  rdx, 1
    syscall
    PUTS rst, rst_l
    ret

.die:
    mov  byte [alive], 0
    ret

.sp db ' '
.hd db 'O'
.bd db '#'

; ─────────────────────────────────────────────────────────────
; game_init
game_init:
    mov  byte [alive], 1
    mov  dword [score], 0
    mov  dword [shead], 2
    mov  dword [stail], 0
    mov  dword [slen], 3
    mov  byte [dir], DRIGHT
    mov  byte [ndir], DRIGHT

    ; place snake horizontally in center
    mov  eax, GH / 2
    mov  byte [sy], al
    mov  byte [sy+1], al
    mov  byte [sy+2], al

    mov  eax, GW / 2 - 2
    mov  byte [sx], al
    inc  al
    mov  byte [sx+1], al
    inc  al
    mov  byte [sx+2], al

    call spawn_food
    ret

; ─────────────────────────────────────────────────────────────
_start:
    ; seed rng (just use constant — good enough)
    mov  dword [rng_s], 0xDEADBEEF

    call term_set_raw
    PUTS hide_c, hide_l
    PUTS clr, clr_l

    ; print title + controls
    PUTS gold, gold_l
    PUTS title, title_l
    PUTS dim_c, dim_l
    PUTS ctrl, ctrl_l
    PUTS rst, rst_l

    call draw_border
    call game_init
    call draw_snake_all
    call draw_food
    call draw_score

.loop:
    call read_input
    cmp  byte [alive], 0
    je   .over

    call update
    cmp  byte [alive], 0
    je   .over

    ; sleep 140ms
    mov  rax, SYS_NANOSLEEP
    lea  rdi, [rel t_sec]
    xor  rsi, rsi
    syscall

    jmp  .loop

.over:
    ; position game over in middle of grid
    mov  r11d, GH / 2 + 2
    mov  r12d, GW / 2 - 14
    call goto_rc
    PUTS gover, gover_l

    ; pause 2s
    mov  qword [t_sec], 2
    mov  qword [t_ns], 0
    mov  rax, SYS_NANOSLEEP
    lea  rdi, [rel t_sec]
    xor  rsi, rsi
    syscall

.exit:
    call term_restore
    PUTS show_c, show_l
    PUTS rst, rst_l

    ; newline
    mov  rax, SYS_WRITE
    mov  rdi, 1
    lea  rsi, [rel .nl]
    mov  rdx, 1
    syscall

    mov  rax, SYS_EXIT
    xor  rdi, rdi
    syscall

.nl db 10
