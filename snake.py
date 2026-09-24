"""
LEGO Robot Snake
=================
A classic Snake game: you control a little robot that moves around the
screen eating LEGO bricks. Every brick you eat makes your trail longer.
If you run into a wall or your own trail, the game ends.

This file has extra comments explaining what each part of the code does,
written for someone who doesn't code but is curious how it works.
"""

import pygame   # the library that draws graphics and reads the keyboard
import time
import random

# ---------------------------------------------------------------------
# SETTINGS you can safely change to tweak how the game feels
# ---------------------------------------------------------------------

# How many times per second the picture on screen redraws itself.
# Higher = smoother looking. 60 is standard for most games.
RENDER_FPS = 60

# How many times per second the snake actually moves one square.
# This is the "speed" of the game — raise it to make the snake faster,
# lower it to make it slower.
moves_per_second = 5
move_interval = 1.0 / moves_per_second   # do the math once, reuse it

# How big one square of the grid is, in pixels. Everything else (the
# window size, the snake, the bricks) is built from this one number.
block_size = 32

# How many squares wide/tall the play area is.
grid_w = 20
grid_h = 12
window_x = grid_w * block_size   # window width in pixels
window_y = grid_h * block_size   # window height in pixels

# Some basic colors, stored as (Red, Green, Blue) values from 0-255.
black = pygame.Color(0, 0, 0)
white = pygame.Color(255, 255, 255)
red = pygame.Color(255, 0, 0)
green = pygame.Color(0, 255, 0)
blue = pygame.Color(0, 0, 255)

# ---------------------------------------------------------------------
# GETTING THE WINDOW READY
# ---------------------------------------------------------------------

pygame.init()   # starts up pygame so it's ready to draw and take input

pygame.display.set_caption('LEGO Robot Plays Snake!')   # the window's title bar text
game_window = pygame.display.set_mode((window_x, window_y), pygame.RESIZABLE)
fullscreen = False

# We draw the entire game onto this separate "canvas" first, at a fixed
# size, and THEN stretch that finished picture onto the real window.
# That way, whether the window is small, resized, or fullscreen on a
# giant monitor, none of the game's math (grid positions, collisions)
# has to change — we just resize the final picture.
canvas = pygame.Surface((window_x, window_y))


def toggle_fullscreen():
    """Switches between fullscreen and a normal window. Called once at
    startup (so the game opens fullscreen by default) and again any
    time the player presses F11."""
    global game_window, fullscreen
    try:
        if not fullscreen:
            # Ask the computer what the screen's real resolution is,
            # so fullscreen fills the whole monitor correctly.
            info = pygame.display.Info()
            game_window = pygame.display.set_mode(
                (info.current_w, info.current_h), pygame.FULLSCREEN)
            fullscreen = True
        else:
            game_window = pygame.display.set_mode((window_x, window_y), pygame.RESIZABLE)
            fullscreen = False
    except pygame.error:
        # If fullscreen isn't supported on this computer for some
        # reason, just fall back to a normal window instead of crashing.
        fullscreen = False
        game_window = pygame.display.set_mode((window_x, window_y), pygame.RESIZABLE)


fps = pygame.time.Clock()   # a stopwatch pygame uses to keep a steady frame rate


# ---------------------------------------------------------------------
# LOADING PICTURES
# ---------------------------------------------------------------------

def load_scaled_preserving_aspect(path, box_size):
    """Loads an image file and resizes it to fit inside a square of
    size box_size, WITHOUT squashing/stretching it out of shape. Any
    leftover space is left transparent."""
    raw = pygame.image.load(path).convert_alpha()
    w, h = raw.get_size()
    scale = min(box_size / w, box_size / h)
    new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
    scaled = pygame.transform.smoothscale(raw, (new_w, new_h))

    result = pygame.Surface((box_size, box_size), pygame.SRCALPHA)
    result.blit(scaled, ((box_size - new_w) // 2, (box_size - new_h) // 2))
    return result


# Images are loaded ONE TIME here, before the game starts, instead of
# being reloaded every single frame (which would be slow and could
# eventually cause errors).
bg_raw = pygame.image.load("bg.jpeg").convert_alpha()
bg = pygame.transform.scale(bg_raw, (window_x, window_y))   # background, stretched to fill the screen

bot = load_scaled_preserving_aspect("bot.png", block_size)          # the robot picture
lego_brick = load_scaled_preserving_aspect("lego_brick.jpg", block_size)   # the fruit picture

# The robot picture only faces one direction by default. These lines
# make 3 rotated copies of it, so it can visually turn to face
# up/down/left/right as it moves.
bot_facing = {
    'UP': bot,
    'RIGHT': pygame.transform.rotate(bot, -90),
    'DOWN': pygame.transform.rotate(bot, 180),
    'LEFT': pygame.transform.rotate(bot, 90),
}

# A handful of classic LEGO brick colors. Each new piece of the snake's
# trail gets a random one of these.
lego_colors = [
    (196, 40, 27),    # red
    (13, 105, 171),   # blue
    (0, 133, 43),     # green
    (255, 205, 47),   # yellow
    (245, 125, 13),   # orange
    (255, 255, 255),  # white
    (55, 33, 30),     # dark brown
    (99, 95, 82),     # dark stone gray
]


def grayscale_surface(surface, min_lum=90, max_lum=255):
    """Removes the color from a picture, keeping only its light/dark
    shading, so it can be safely recolored afterward. (Recoloring a
    picture that ALREADY has color in it usually looks muddy.)"""
    gray = surface.copy()
    w, h = gray.get_size()
    for x in range(w):
        for y in range(h):
            r, g, b, a = gray.get_at((x, y))
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            lum = int(min_lum + (lum / 255) * (max_lum - min_lum))
            gray.set_at((x, y), (lum, lum, lum, a))
    return gray


def tint_surface(surface, color):
    """Takes a black-and-white picture and colors it, keeping its
    shading/highlights — this is how one plain brick photo becomes a
    red one, a blue one, a green one, etc."""
    tinted = surface.copy()
    tint_layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    tint_layer.fill((*color, 255))
    tinted.blit(tint_layer, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return tinted


# Make one gray version of the brick, then 8 colored versions from it.
lego_brick_gray = grayscale_surface(lego_brick)
lego_bricks_colored = [tint_surface(lego_brick_gray, c) for c in lego_colors]


# ---------------------------------------------------------------------
# THE SNAKE'S STARTING STATE
# ---------------------------------------------------------------------

# The snake's head starts here. [x, y] in pixels.
snake_position = [block_size * 3, block_size * 2]

# The whole snake body is just a list of [x, y] positions, head first.
# It starts as just the head (length 1).
snake_body = [list(snake_position)]

# Remembers where every piece of the snake WAS, right before its most
# recent move — used to smoothly slide it to its new spot instead of
# instantly teleporting there.
prev_snake_body = [list(snake_position)]

# Each piece of the snake's trail gets its own color, saved here in the
# same order as snake_body. Once a piece is colored, it keeps that
# color forever — it's never randomly reassigned. Index 0 is the head,
# which doesn't need a color (it shows the robot picture instead).
trail_colors = [None]


def spawn_fruit():
    """Picks a random empty square for the next brick to appear on
    (never on top of the snake itself)."""
    while True:
        pos = [random.randrange(0, grid_w) * block_size,
               random.randrange(0, grid_h) * block_size]
        if pos not in snake_body:
            return pos


fruit_position = spawn_fruit()
fruit_spawn = True

direction = 'RIGHT'     # which way the snake is currently heading
change_to = direction   # which way the player just asked it to go

score = 0


def show_score(choice, color, font, size):
    """Draws the current score in the corner of the screen."""
    score_font = pygame.font.SysFont(font, size)
    score_surface = score_font.render('Score : ' + str(score), True, color)
    score_rect = score_surface.get_rect()
    canvas.blit(score_surface, score_rect)


def game_over():
    """Shows the final score, waits a couple seconds, then closes the
    game. Called whenever the snake hits a wall or itself."""
    my_font = pygame.font.SysFont('Trebuchet MS', 50)
    game_over_surface = my_font.render('Your Score is: ' + str(score), True, red)
    game_over_rect = game_over_surface.get_rect()
    game_over_rect.midtop = (window_x / 2, window_y / 4)

    canvas.blit(game_over_surface, game_over_rect)
    target_w, target_h = game_window.get_size()
    scale = min(target_w / window_x, target_h / window_y)
    scaled_w, scaled_h = int(window_x * scale), int(window_y * scale)
    scaled_canvas = pygame.transform.smoothscale(canvas, (scaled_w, scaled_h))
    game_window.fill(black)
    game_window.blit(scaled_canvas,
                      ((target_w - scaled_w) // 2, (target_h - scaled_h) // 2))
    pygame.display.flip()

    time.sleep(2)
    pygame.quit()
    quit()


def show_tutorial():
    """Shows a simple instructions screen and waits for the player to
    press a key before the game actually starts."""
    title_font = pygame.font.SysFont('Trebuchet MS', 48, bold=True)
    line_font = pygame.font.SysFont('Trebuchet MS', 26)

    lines = [
        "Use the ARROW KEYS to steer the robot.",
        "Eat the LEGO brick to grow longer and score a point.",
        "Don't hit the walls or your own tail!",
        "Press F11 anytime to switch fullscreen on/off.",
        "",
        "Press any key to start...",
    ]

    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                quit()
            if event.type == pygame.KEYDOWN:
                waiting = False

        # Draw the instructions onto the canvas, same as the main game
        # does, so it also scales correctly to fullscreen/windowed.
        canvas.blit(bg, (0, 0))

        title_surface = title_font.render("LEGO Robot Snake", True, white)
        title_rect = title_surface.get_rect(center=(window_x // 2, window_y // 4))
        canvas.blit(title_surface, title_rect)

        for i, line in enumerate(lines):
            line_surface = line_font.render(line, True, white)
            line_rect = line_surface.get_rect(
                center=(window_x // 2, window_y // 4 + 60 + i * 32))
            canvas.blit(line_surface, line_rect)

        target_w, target_h = game_window.get_size()
        scale = min(target_w / window_x, target_h / window_y)
        scaled_w, scaled_h = int(window_x * scale), int(window_y * scale)
        scaled_canvas = pygame.transform.scale(canvas, (scaled_w, scaled_h))
        game_window.fill(black)
        game_window.blit(scaled_canvas,
                          ((target_w - scaled_w) // 2, (target_h - scaled_h) // 2))
        pygame.display.update()

        fps.tick(RENDER_FPS)


# ---------------------------------------------------------------------
# START THE GAME
# ---------------------------------------------------------------------

toggle_fullscreen()   # the game opens in fullscreen by default
show_tutorial()        # show instructions and wait for a keypress

running = True
move_timer = 0.0

while running:
    # How much real time (in seconds) passed since the last frame.
    dt = fps.tick(RENDER_FPS) / 1000.0

    # --- Read the player's key presses ---
    for event in pygame.event.get():
        if event.type == pygame.QUIT:               # player closed the window
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                change_to = 'UP'
            if event.key == pygame.K_DOWN:
                change_to = 'DOWN'
            if event.key == pygame.K_LEFT:
                change_to = 'LEFT'
            if event.key == pygame.K_RIGHT:
                change_to = 'RIGHT'
            if event.key == pygame.K_F11:
                toggle_fullscreen()

    if not running:
        break

    # Don't let the player instantly reverse into themselves (e.g. you
    # can't go LEFT while currently moving RIGHT).
    if change_to == 'UP' and direction != 'DOWN':
        direction = 'UP'
    if change_to == 'DOWN' and direction != 'UP':
        direction = 'DOWN'
    if change_to == 'LEFT' and direction != 'RIGHT':
        direction = 'LEFT'
    if change_to == 'RIGHT' and direction != 'LEFT':
        direction = 'RIGHT'

    # --- Move the snake, but only "moves_per_second" times a second ---
    # The screen keeps redrawing at a fast, steady rate (RENDER_FPS)
    # even though the snake itself only actually moves a few times a
    # second — that's what keeps the game feeling smooth instead of
    # jerky, no matter how fast/slow the snake is set to move.
    move_timer += dt
    while move_timer >= move_interval:
        move_timer -= move_interval

        # Remember where everything was, so we can smoothly animate
        # sliding from there to the new spot.
        prev_snake_body = [list(p) for p in snake_body]

        if direction == 'UP':
            snake_position[1] -= block_size
        if direction == 'DOWN':
            snake_position[1] += block_size
        if direction == 'LEFT':
            snake_position[0] -= block_size
        if direction == 'RIGHT':
            snake_position[0] += block_size

        # Add the new head position to the front of the snake.
        snake_body.insert(0, list(snake_position))
        trail_colors.insert(0, None)

        if snake_position[0] == fruit_position[0] and snake_position[1] == fruit_position[1]:
            # Ate the fruit! Score a point and grow (by NOT removing
            # the tail below, the snake ends up one square longer).
            score += 1
            fruit_spawn = False
        else:
            # Didn't eat — remove the tail so the snake stays the same
            # length while still sliding forward.
            snake_body.pop()
            trail_colors.pop()

        # Any brand new trail segment (one that doesn't have a color
        # yet) gets a random permanent color right now.
        for i in range(1, len(trail_colors)):
            if trail_colors[i] is None:
                trail_colors[i] = random.choice(lego_bricks_colored)

        if not fruit_spawn:
            fruit_position = spawn_fruit()
        fruit_spawn = True

        # Did the snake run into a wall?
        if snake_position[0] < 0 or snake_position[0] > window_x - block_size:
            game_over()
        if snake_position[1] < 0 or snake_position[1] > window_y - block_size:
            game_over()

        # Did the snake run into its own body?
        for block in snake_body[1:]:
            if snake_position[0] == block[0] and snake_position[1] == block[1]:
                game_over()

    # --- Draw everything ---
    # t goes from 0 (just moved) to 1 (about to move again). We use it
    # to smoothly slide each piece from its old spot to its new one,
    # instead of it jumping there instantly.
    t = move_timer / move_interval
    eased_t = t * t * (3 - 2 * t)   # a "smoothstep" curve: slow-fast-slow instead of constant speed

    canvas.blit(bg, (0, 0))   # draw the background first, everything else on top

    for i, pos in enumerate(snake_body):
        prev = prev_snake_body[i] if i < len(prev_snake_body) else pos
        draw_x = prev[0] + (pos[0] - prev[0]) * eased_t
        draw_y = prev[1] + (pos[1] - prev[1]) * eased_t
        if i == 0:
            canvas.blit(bot_facing[direction], (draw_x, draw_y))   # the head/robot
        else:
            canvas.blit(trail_colors[i], (draw_x, draw_y))         # a trail brick

    canvas.blit(lego_brick, (fruit_position[0], fruit_position[1]))   # the fruit

    show_score(1, white, 'Trebuchet MS', 20)

    # Stretch the finished picture (canvas) onto the real window,
    # keeping its proportions correct (letterboxed) whatever size the
    # window or fullscreen monitor is.
    target_w, target_h = game_window.get_size()
    scale = min(target_w / window_x, target_h / window_y)
    scaled_w, scaled_h = int(window_x * scale), int(window_y * scale)
    scaled_canvas = pygame.transform.smoothscale(canvas, (scaled_w, scaled_h))

    game_window.fill(black)
    game_window.blit(scaled_canvas,
                      ((target_w - scaled_w) // 2, (target_h - scaled_h) // 2))

    pygame.display.update()   # actually show this frame on screen

pygame.quit()
quit()
