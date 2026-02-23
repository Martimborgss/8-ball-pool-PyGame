import pygame
import random
import math
import sys
from functions import *

pygame.init()

log_file = open("log.txt", "w") 
sys.stdout = log_file

# --- Window Configurations ---
WIDTH = 1920
HEIGHT = 1080
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.NOFRAME) 
pygame.display.set_caption("Beer Hunter Simulator - Full HD")
clock = pygame.time.Clock()
FPS = 120
MENU_FONT = pygame.font.SysFont("Arial", 40, bold=True)

# --- Table Configurations ---
TABLE_W = 1500
TABLE_H = 750
TABLE_X = (WIDTH - TABLE_W) // 2 
TABLE_Y = 250
CUSHION_SIZE = 60

# --- Colors ---
BG_COLOR = (25, 30, 45)
TABLE_COLORS = {
    'wood': (80, 50, 30),
    'felt': (35, 110, 65),
    'shadow': (20, 70, 40)
}

# --- Game State Variables ---
GRAVITY = 0.0
balls = []
player_names = ["", ""]
player_ball_types = [None, None]
player_scores = [0, 0]

input_active = 0 
current_player_idx = 0 
game_started = False
game_over = False  
game_over_time = 0
winner_name = ""    

shot_taken = False
charging_shot = False
balls_sunk_in_shot = [] # Tracks balls pocketed during the current turn

def setup_rack():
    """Sets up the table with the standard 8-ball triangle."""
    balls.clear()
    balls.append(create_ball(TABLE_X + TABLE_W // 4, TABLE_Y + TABLE_H // 2, 0)) # Cue Ball
    rack_numbers = [1, 9, 2, 10, 8, 3, 4, 11, 12, 5, 13, 14, 6, 15, 7]
    start_x = TABLE_X + TABLE_W * 0.72
    start_y = TABLE_Y + TABLE_H // 2
    radius = 20
    idx = 0
    for row in range(5):
        for col in range(row + 1):
            x_offset = row * (radius * 1.732)
            y_offset = (col - row / 2.0) * (radius * 2.05)
            balls.append(create_ball(start_x + x_offset, start_y + y_offset, rack_numbers[idx]))
            idx += 1

setup_rack()

# --- Main Game Loop ---
running = True
while running:
    milli = clock.tick(FPS) 
    dt_multiplier = milli / (1000 / FPS) 
    mouse_pos = pygame.mouse.get_pos()
    
    # Helper variables for this frame
    cue_ball = balls[0] if len(balls) > 0 and balls[0]["number"] == 0 else None

    # ==========================================
    # 1. EVENT HANDLING (Mouse & Keyboard)
    # ==========================================
    for event in pygame.event.get():
        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
            running = False
        
        if game_over:    
            if pygame.time.get_ticks() - game_over_time > 4000:
                game_over = False
                player_ball_types = [None, None]
                player_scores = [0, 0]
                shot_taken = False
                charging_shot = False
                balls_sunk_in_shot.clear()
                current_player_idx = random.randint(0, 1)
                setup_rack()
        
        # --- Menu Events ---
        elif not game_started:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    if player_names[input_active] != "":
                        if input_active == 0:
                            input_active = 1
                        else:
                            current_player_idx = random.randint(0, 1)
                            game_started = True
                            setup_rack()
                elif event.key == pygame.K_BACKSPACE:
                    player_names[input_active] = player_names[input_active][:-1]
                else:
                    if len(player_names[input_active]) < 12:
                        player_names[input_active] += event.unicode
        # --- Game Events ---
        else:
            moving = any(math.sqrt(b["vel_x"]**2 + b["vel_y"]**2) > 0.2 for b in balls)   
            is_dragging = False
            for ball in balls:
                was_dragging = ball.get("dragging", False)
                handle_mouse(event, ball) #un comment this line to drag the balls
                
                # Trigger shot logic if a ball was dragged and released
                if was_dragging and not ball.get("dragging", False):
                    shot_taken = True 
                if ball.get("dragging", False):
                    is_dragging = True

            # 2. Cue Stick Shooting
            if not moving and cue_ball and not is_dragging:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    charging_shot = True
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    if charging_shot:
                        ux, uy, dist = draw_cue_stick(screen, cue_ball, mouse_pos, True)
                        power = min(dist * 0.15, 30)
                        cue_ball["vel_x"] = ux * power
                        cue_ball["vel_y"] = uy * power
                        
                        charging_shot = False
                        shot_taken = True
                        balls_sunk_in_shot = [] # Reset tracking for the new shot

    # ==========================================
    # 2. GAME LOGIC (Physics & Rules)
    # ==========================================
    if game_started:
        moving = any(math.sqrt(b["vel_x"]**2 + b["vel_y"]**2) > 0.2 for b in balls)   
        # --- Physics Updates ---
        for ball in balls:
            update_inertia(ball)
            apply_physics(ball, GRAVITY, dt_multiplier)
            
        # --- Pocket Collisions & Instant UI Updates ---
        sunk_this_frame = check_pockets(balls, TABLE_X, TABLE_Y, TABLE_W, TABLE_H, CUSHION_SIZE)
        
        if sunk_this_frame:
            for b_data in sunk_this_frame:
                b_type = b_data["type"] if isinstance(b_data, dict) else b_data
                b_num = b_data["number"] if isinstance(b_data, dict) else -1
                sunk_8ball = False
                if b_type == "8ball": sunk_8ball = True
                balls_sunk_in_shot.append(b_data)

                if b_type in ["solid", "stripe", "8ball"]:
                    # 1. Instant Assign
                    if player_ball_types[current_player_idx] is None:
                        if sunk_8ball: 
                            game_over = True 
                            winner_name = player_names[1 - current_player_idx]
                            game_over_time = pygame.time.get_ticks()
                            break
                        player_ball_types[current_player_idx] = b_type
                        player_ball_types[1 - current_player_idx] = "stripe" if b_type == "solid" else "solid"
                        player_scores[current_player_idx] += 1
                    
                    # 2. Instant Score
                    elif b_type == player_ball_types[current_player_idx]:
                        player_scores[current_player_idx] += 1
                        print(f"PONTO! Player {current_player_idx + 1} marcou.")
                    
                    # 3. Penalty (Potted opponent's ball)
                    else:
                        print("Potted opponent's ball! Respawning in center...")
                        if b_num != -1 and b_num != 8: 
                            mid_x, mid_y = TABLE_X + TABLE_W // 2, TABLE_Y + TABLE_H // 2
                            balls.append(create_ball(mid_x, mid_y, b_num))

        moving = any(math.sqrt(b["vel_x"]**2 + b["vel_y"]**2) > 0.2 for b in balls)   
        
        if shot_taken and not moving and not game_over:
            keep_turn = False
            foul = False
            sunk_8ball = False
            
            for b_data in balls_sunk_in_shot:
                b_type = b_data.get("type") if isinstance(b_data, dict) else b_data
                
                if b_type == "cue":
                    foul = True
                elif b_type == "8ball":
                    sunk_8ball = True
                elif player_ball_types[current_player_idx] == b_type:
                    keep_turn = True
                elif b_type in ["solid", "stripe"]:
                    foul = True # Meteu a bola do adversário
            
            # --- Regras da Bola 8 ---
            if sunk_8ball:
                my_type = player_ball_types[current_player_idx]
                my_balls_this_shot = sum(1 for b in balls_sunk_in_shot if (b.get("type") if isinstance(b, dict) else b) == my_type)
                points_before_shot = player_scores[current_player_idx] - my_balls_this_shot
                
                # Vitória Limpa
                if my_type is not None and points_before_shot >= 7 and my_balls_this_shot == 0 and not foul:
                    game_over = True
                    game_over_time = pygame.time.get_ticks()
                    winner_name = player_names[current_player_idx]
                    print(f"VITÓRIA: {winner_name} meteu a preta e ganhou o jogo!")
                else:
                    # Derrota por falta / bola preta fora de tempo
                    game_over = True
                    game_over_time = pygame.time.get_ticks()
                    winner_name = player_names[1 - current_player_idx]
                    print(f"DERROTA: Jogada ilegal com a preta. {winner_name} ganha automaticamente!")
            
            # --- Troca de turno ---
            if not game_over:
                if foul or not keep_turn:
                    current_player_idx = 1 - current_player_idx
                    print(f"TURNO: Agora joga o Player {current_player_idx + 1}")
            
            # Fim da tacada - limpa a variável para a próxima jogada
            shot_taken = False 
            balls_sunk_in_shot.clear()

        # --- Ball Collisions ---
        calculate_neighbors(balls)
        for _ in range(8):
            check_all_collisions(balls, TABLE_X, TABLE_Y, TABLE_W, TABLE_H, CUSHION_SIZE, dt_multiplier)            

    # ==========================================
    # 3. RENDERING (Drawing to Screen)
    # ==========================================
    screen.fill(BG_COLOR)

    if not game_started:
        # --- Draw Menu ---
        txt = f"Player {input_active + 1} Name: {player_names[input_active]}"
        surf = MENU_FONT.render(txt, True, (255, 255, 255))
        screen.blit(surf, (WIDTH//2 - 300, HEIGHT//2))
        
        sub_txt = MENU_FONT.render("Press ENTER to confirm", True, (150, 150, 150))
        screen.blit(sub_txt, (WIDTH//2 - 300, HEIGHT//2 + 60))
        
    else:
        # --- Draw Table & Balls ---
        draw_table(screen, TABLE_X, TABLE_Y, TABLE_W, TABLE_H, CUSHION_SIZE, TABLE_COLORS)
        draw_pockets(screen, TABLE_X, TABLE_Y, TABLE_W, TABLE_H, CUSHION_SIZE)
        
        for ball in balls:
            draw_ball(screen, ball)
            
        # --- Draw Cue Stick ---
        if not moving and cue_ball:
            draw_aiming_line(screen, cue_ball, balls, mouse_pos, TABLE_X, TABLE_Y, TABLE_W, TABLE_H, CUSHION_SIZE)
            draw_cue_stick(screen, cue_ball, mouse_pos, charging_shot)

        # --- Draw HUD ---
        pygame.draw.rect(screen, (15, 20, 30), (0, 0, WIDTH, 180))
        pygame.draw.line(screen, (60, 70, 90), (0, 180), (WIDTH, 180), 2)
        
        draw_hud(screen, WIDTH, player_names[0], player_names[1], 
                 player_scores[0], player_scores[1], 
                 current_player_idx, player_ball_types)
    
        if game_over:
            overlay = pygame.Surface((WIDTH, HEIGHT))
            overlay.set_alpha(200) 
            overlay.fill((10, 10, 15))
            screen.blit(overlay, (0, 0))
            
            win_txt = f"{winner_name} VENCEU!"
            win_surf = MENU_FONT.render(win_txt.upper(), True, (255, 215, 0))
            screen.blit(win_surf, (WIDTH//2 - win_surf.get_width()//2, HEIGHT//2 - 50))
            
            # --- NOVO TEXTO AQUI ---
            restart_txt = MENU_FONT.render("A iniciar nova partida...", True, (150, 150, 150))
            screen.blit(restart_txt, (WIDTH//2 - restart_txt.get_width()//2, HEIGHT//2 + 50))
        
    pygame.display.flip()

log_file.close()
pygame.quit()