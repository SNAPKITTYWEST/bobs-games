#!/bin/bash
# BOB SNAKE — build + run
# Run inside WSL2: bash build_snake.sh

set -e

echo "[BOB] Assembling bob_snake.asm..."
nasm -f elf64 bob_snake.asm -o bob_snake.o

echo "[BOB] Linking..."
ld bob_snake.o -o bob_snake

echo "[BOB] WORM SEALED. Launching..."
./bob_snake
