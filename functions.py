import pygame
import math

pygame.font.init()
POOL_FONT = pygame.font.SysFont("Arial", 14, bold=True)

BALL_RADIUS = 20
POCKET_RADIUS = 35

def are_balls_moving(balls, threshold=0.2):
    """Returns True if any ball has velocity above the threshold."""
    return any(math.sqrt(b["vel_x"]**2 + b["vel_y"]**2) > threshold for b in balls)

def get_pocket_positions(table_x, table_y, table_w, table_h, cushion):
    """Returns the 6 pocket positions for a standard pool table."""
    return [
        (table_x + cushion, table_y + cushion),
        (table_x + table_w // 2, table_y + cushion - 5),
        (table_x + table_w - cushion, table_y + cushion),
        (table_x + cushion, table_y + table_h - cushion),
        (table_x + table_w // 2, table_y + table_h - cushion + 5),
        (table_x + table_w - cushion, table_y + table_h - cushion)
    ]

# --- Ball ---

# Standard Pool Ball Colors
BALL_COLORS = {
    1: (244, 208, 63), # Yellow
    2: (52, 152, 219), # Blue
    3: (231, 76, 60),  # Red
    4: (142, 68, 173), # Purple
    5: (230, 126, 34), # Orange
    6: (39, 174, 96),  # Green
    7: (123, 36, 28),  # Maroon
    8: (30, 30, 30)    # Black (8-ball)
}

def create_ball(x, y, number):
    """Creates a pool ball based on its standard number (0 is the Cue ball)."""
    radius = BALL_RADIUS
    
    if number == 0:
        color = (255, 255, 255)
        ball_type = "cue"
    elif number == 8:
        color = BALL_COLORS[8]
        ball_type = "8ball"
    elif number < 8:
        color = BALL_COLORS[number]
        ball_type = "solid"
    else:
        # Stripes use the same colors as solids (9 is Yellow, 10 is Blue, etc.)
        color = BALL_COLORS[number - 8]
        ball_type = "stripe"
        
    return {
        "x": x, 
        "y": y, 
        "radius": radius, 
        "color": color,
        "number": number,
        "type": ball_type,
        "dragging": False, 
        "offset_x": 0, 
        "offset_y": 0,
        "vel_x": 0, 
        "vel_y": 0, 
        "prev_x": x, 
        "prev_y": y,
        "bounce_factor": 0.96, # Coefficient of restitution for ball-ball hits
        "friction": 0.991,      # Table felt friction per frame
        "nearby_balls": []
}

def calculate_neighbors(balls):
    """Finds balls that are close."""
    for ball in balls:
        ball["nearby_balls"].clear()

    for i in range(len(balls)):
        b1 = balls[i]
        for j in range(i + 1, len(balls)):
            b2 = balls[j]
            dx = b2["x"] - b1["x"]
            dy = b2["y"] - b1["y"]
            distance_sq = dx**2 + dy**2
            sum_radii = b1["radius"] + b2["radius"]
            max_distance = sum_radii + max(b1["radius"], b2["radius"])

            if distance_sq < max_distance**2:
                b1["nearby_balls"].append(b2)
                b2["nearby_balls"].append(b1)

def draw_ball(screen, ball):
    """Draws the pool ball with standard visual rules."""
    x, y = int(ball["x"]), int(ball["y"])
    r = int(ball["radius"])

    if ball["type"] == "stripe":
        # Draw white base
        pygame.draw.circle(screen, (255, 255, 255), (x, y), r)
        # Draw colored stripe
        stripe_rect = pygame.Rect(x - r + 3, y - r // 2, r * 2 - 6, r)
        pygame.draw.rect(screen, ball["color"], stripe_rect, border_radius=4)
    else:
        # Draw solid base (for solids, 8-ball, and cue)
        pygame.draw.circle(screen, ball["color"], (x, y), r)

    # Draw the white inner circle and number (except for the cue ball)
    if ball["number"] != 0:
        pygame.draw.circle(screen, (255, 255, 255), (x, y), r // 2 + 2)
        text_surf = POOL_FONT.render(str(ball["number"]), True, (0, 0, 0))
        text_rect = text_surf.get_rect(center=(x, y))
        screen.blit(text_surf, text_rect)

    # Draw a thin dark outline for a clean 2D look
    pygame.draw.circle(screen, (50, 50, 50), (x, y), r, 2)

# --- Physics ---

def update_inertia(ball):
    """Calculates throwing velocity based on mouse movement."""
    if ball["dragging"]:
        ball["vel_x"] = ball["x"] - ball["prev_x"]
        ball["vel_y"] = ball["y"] - ball["prev_y"]
        ball["prev_x"] = ball["x"]
        ball["prev_y"] = ball["y"]

def apply_physics(ball, dt_multiplier):
    """Updates position, applies friction, and stops near-zero velocities."""
    if not ball["dragging"]:
        ball["x"] += ball["vel_x"] * dt_multiplier
        ball["y"] += ball["vel_y"] * dt_multiplier

        # Frame-independent friction (applied once per frame)
        adjusted_friction = ball["friction"] ** dt_multiplier
        ball["vel_x"] *= adjusted_friction
        ball["vel_y"] *= adjusted_friction

        # Stop balls that are barely moving
        speed_sq = ball["vel_x"]**2 + ball["vel_y"]**2
        if speed_sq < 0.01:  # threshold² = 0.1²
            ball["vel_x"] = 0
            ball["vel_y"] = 0

CUSHION_BOUNCE = 0.75  # Energy retained when hitting a cushion

def _collide_with_walls(ball, table_x, table_y, table_w, table_h, cushion):
    """Resolves wall penetration and reflects velocity off cushions."""
    left = table_x + cushion + ball["radius"]
    right = table_x + table_w - cushion - ball["radius"]
    top = table_y + cushion + ball["radius"]
    bottom = table_y + table_h - cushion - ball["radius"]

    if ball["x"] < left:
        ball["x"] = left
        ball["vel_x"] = abs(ball["vel_x"]) * CUSHION_BOUNCE
    elif ball["x"] > right:
        ball["x"] = right
        ball["vel_x"] = -abs(ball["vel_x"]) * CUSHION_BOUNCE

    if ball["y"] < top:
        ball["y"] = top
        ball["vel_y"] = abs(ball["vel_y"]) * CUSHION_BOUNCE
    elif ball["y"] > bottom:
        ball["y"] = bottom
        ball["vel_y"] = -abs(ball["vel_y"]) * CUSHION_BOUNCE

def _collide_with_ball(ball, neighbor):
    """Resolves collision between two equal-mass pool balls."""
    dx = neighbor["x"] - ball["x"]
    dy = neighbor["y"] - ball["y"]
    distance_sq = dx * dx + dy * dy
    sum_radii = ball["radius"] + neighbor["radius"]

    if distance_sq >= sum_radii * sum_radii:
        return  # No collision

    distance = math.sqrt(distance_sq) if distance_sq > 0 else 0.001
    nx = dx / distance
    ny = dy / distance

    # Separate overlapping balls (equal mass, split evenly)
    overlap = sum_radii - distance
    ball["x"] -= nx * overlap * 0.5
    ball["y"] -= ny * overlap * 0.5
    neighbor["x"] += nx * overlap * 0.5
    neighbor["y"] += ny * overlap * 0.5

    # Relative velocity along collision normal
    rv_x = ball["vel_x"] - neighbor["vel_x"]
    rv_y = ball["vel_y"] - neighbor["vel_y"]
    vel_along_normal = rv_x * nx + rv_y * ny

    # Only resolve if balls are moving toward each other
    if vel_along_normal <= 0:
        return

    # For equal-mass elastic collision: swap the normal components
    # Apply bounce factor for slight energy loss
    bounce = ball["bounce_factor"]
    impulse = vel_along_normal * (1 + bounce) * 0.5

    ball["vel_x"] -= impulse * nx
    ball["vel_y"] -= impulse * ny
    neighbor["vel_x"] += impulse * nx
    neighbor["vel_y"] += impulse * ny

def check_all_collisions(balls, table_x, table_y, table_w, table_h, cushion):
    """Resolves all ball-ball and ball-wall overlaps for one sub-step."""
    for ball in balls:
        _collide_with_walls(ball, table_x, table_y, table_w, table_h, cushion)
        for neighbor in ball["nearby_balls"]:
            if id(ball) < id(neighbor):
                _collide_with_ball(ball, neighbor)

# --- Mouse ---

def handle_mouse(event, ball):
    """Handles mouse clicks and movement for dragging the ball."""
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        mouse_x, mouse_y = event.pos
        distance = math.sqrt((mouse_x - ball["x"])**2 + (mouse_y - ball["y"])**2)
        if distance <= ball["radius"]:
            ball["dragging"] = True
            ball["offset_x"] = ball["x"] - mouse_x
            ball["offset_y"] = ball["y"] - mouse_y
            ball["vel_x"] = 0
            ball["vel_y"] = 0

    elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
        ball["dragging"] = False

    elif event.type == pygame.MOUSEMOTION:
        if ball["dragging"]:
            mouse_x, mouse_y = event.pos
            ball["x"] = mouse_x + ball["offset_x"]
            ball["y"] = mouse_y + ball["offset_y"]

# --- Stick --- 

def draw_cue_stick(screen, cue_ball, mouse_pos, is_charging):
    """Draws the cue stick and returns the shot vector."""
    dx = cue_ball["x"] - mouse_pos[0]
    dy = cue_ball["y"] - mouse_pos[1]
    dist = math.sqrt(dx**2 + dy**2)
    
    if dist == 0: dist = 0.1
    
    # Normalize the direction
    ux = dx / dist
    uy = dy / dist
    
    # Stick properties
    stick_length = 400
    stick_width_thick = 7
    stick_width_thin = 3
    # Distance from ball (offset)
    offset = 20 + (dist * 0.2 if is_charging else 10) 
    
    # Calculate stick points
    start_x = cue_ball["x"] - ux * offset
    start_y = cue_ball["y"] - uy * offset
    end_x = start_x - ux * stick_length
    end_y = start_y - uy * stick_length
    
    # Draw the stick (a simple polygon for a tapered look)
    perp_x = -uy
    perp_y = ux
    
    points = [
        (start_x + perp_x * stick_width_thin, start_y + perp_y * stick_width_thin),
        (start_x - perp_x * stick_width_thin, start_y - perp_y * stick_width_thin),
        (end_x - perp_x * stick_width_thick, end_y - perp_y * stick_width_thick),
        (end_x + perp_x * stick_width_thick, end_y + perp_y * stick_width_thick)
    ]
    
    # Draw the wood of the stick
    pygame.draw.polygon(screen, (222, 184, 135), points)
    # Draw the tip (darker)
    pygame.draw.line(screen, (50, 50, 50), 
                     (start_x + perp_x * stick_width_thin, start_y + perp_y * stick_width_thin), 
                     (start_x - perp_x * stick_width_thin, start_y - perp_y * stick_width_thin), 4)

    return ux, uy, dist

# --- Table --- 

def check_pockets(balls, table_x, table_y, table_w, table_h, cushion):
    """Checks if any ball has fallen into a pocket and returns data of sunk balls."""
    pockets = get_pocket_positions(table_x, table_y, table_w, table_h, cushion)
    
    balls_to_remove = []
    sunk_data = [] # Track complete data of potted balls

    for ball in balls:
        for px, py in pockets:
            dist = math.sqrt((ball["x"] - px)**2 + (ball["y"] - py)**2)
            if dist < POCKET_RADIUS:
                balls_to_remove.append(ball)
                # Store type and number so we can respawn it if needed
                sunk_data.append({"type": ball["type"], "number": ball["number"]}) 
                break
    
    for ball in balls_to_remove:
        if ball["number"] == 0:
            # Respawn cue ball automatically
            ball["x"], ball["y"] = table_x + table_w // 4, table_y + table_h // 2
            ball["vel_x"], ball["vel_y"] = 0, 0
        else:
            balls.remove(ball)
            
    return sunk_data

def draw_pockets(screen, table_x, table_y, table_w, table_h, cushion):
    """Draws the 6 pockets on the table."""
    pockets = get_pocket_positions(table_x, table_y, table_w, table_h, cushion)
    
    for px, py in pockets:
        pygame.draw.circle(screen, (10, 10, 10), (int(px), int(py)), POCKET_RADIUS)
        pygame.draw.circle(screen, (30, 30, 30), (int(px), int(py)), POCKET_RADIUS, 3)

def draw_table(screen, x, y, w, h, cushion, colors):
    """
    Draws the complete pool table structure.
    colors: A dictionary containing 'wood', 'felt', and 'shadow' keys.
    """
    # 1. Draw the Wood Table Frame (with rounded corners)
    table_rect = pygame.Rect(x, y, w, h)
    pygame.draw.rect(screen, colors['wood'], table_rect, border_radius=20)
    
    # 2. Draw the Green playable area (felt)
    playable_rect = pygame.Rect(
        x + cushion, 
        y + cushion, 
        w - cushion * 2, 
        h - cushion * 2
    )
    pygame.draw.rect(screen, colors['felt'], playable_rect)
    
    # 3. Draw inner cushion shadow/depth
    pygame.draw.rect(screen, colors['shadow'], playable_rect, 8)

# --- HUD ---

def draw_hud(screen, width, p1_name, p2_name, p1_score, p2_score, current_turn, assigned_types):
    center_x = width // 2
    header_height = 180
    
    # 1. Draw turn indicator (centered)
    turn_text = f"{p1_name if current_turn == 0 else p2_name}'s Turn"
    turn_color = (0, 100, 255) if current_turn == 0 else (220, 30, 30)
    
    turn_surf = POOL_FONT.render(turn_text.upper(), True, turn_color)
    turn_rect = turn_surf.get_rect(center=(center_x, header_height // 2))
    screen.blit(turn_surf, turn_rect)

    # 2. Draw avatars and scores
    p1_active = (current_turn == 0)
    p2_active = (current_turn == 1)

    # Position: P1 left of center, P2 right of center
    x_offset = 300 
    avatar_y = 55

    draw_avatar(screen, center_x - x_offset - 70, avatar_y, p1_name, (0, 100, 255), p1_score, p1_active, assigned_types[0])
    draw_avatar(screen, center_x + x_offset, avatar_y, p2_name, (220, 30, 30), p2_score, p2_active, assigned_types[1])  

def draw_avatar(screen, x, y, name, color, score, is_active, ball_type):
    # Border color: Gold/White if active, Dark if not
    border_color = (255, 215, 0) if is_active else (50, 50, 50)
    border_thickness = 5 if is_active else 2

    avatar_rect = pygame.Rect(x, y, 70, 70)
    pygame.draw.rect(screen, color, avatar_rect, border_radius=10)
    pygame.draw.rect(screen, border_color, avatar_rect, border_thickness, border_radius=10) 

    # Display Ball Type Text (Solid, Stripe, or Open Table)
    type_text = ball_type.upper() if ball_type else "OPEN TABLE"
    type_surf = POOL_FONT.render(type_text, True, (180, 180, 180))
    screen.blit(type_surf, (x, y + 80))
    
    # Name Text
    name_color = (255, 255, 255) if is_active else (150, 150, 150)
    name_surf = POOL_FONT.render(name, True, name_color)
    screen.blit(name_surf, (x, y - 25))
    
    # Score Box
    score_bg = pygame.Rect(x + 80, y + 15, 60, 40)
    pygame.draw.rect(screen, (20, 20, 30), score_bg, border_radius=5)
    score_surf = POOL_FONT.render(str(score), True, (255, 255, 255))
    screen.blit(score_surf, score_surf.get_rect(center=score_bg.center))

    # Visual ball indicator if assigned
    if ball_type:
        sample_color = (244, 208, 63) # Yellow for the icon
        ball_x = x + type_surf.get_width() + 15
        if ball_type == "stripe":
            pygame.draw.circle(screen, (255, 255, 255), (ball_x, y + 88), 8)
            pygame.draw.rect(screen, sample_color, (ball_x - 8, y + 84, 16, 8))
        else:
            pygame.draw.circle(screen, sample_color, (ball_x, y + 88), 8)

def draw_aiming_line(screen, cue_ball, balls, mouse_pos, table_x, table_y, table_w, table_h, cushion):
    """Calculates and draws the aiming guideline and deflection angles."""
    dx = cue_ball["x"] - mouse_pos[0]
    dy = cue_ball["y"] - mouse_pos[1]
    dist = math.sqrt(dx**2 + dy**2)
    
    if dist < 0.1: 
        return

    # Shooting direction (normalized)
    ux, uy = dx / dist, dy / dist
    r = cue_ball["radius"]

    min_t = float('inf')
    hit_ball = None

    # 1. Check for collisions with other balls
    for ball in balls:
        if ball["number"] == 0: 
            continue # Skip cue ball
            
        wx = ball["x"] - cue_ball["x"]
        wy = ball["y"] - cue_ball["y"]
        proj = wx * ux + wy * uy

        # If the ball is in front of the ray
        if proj > 0:
            cx = cue_ball["x"] + ux * proj
            cy = cue_ball["y"] + uy * proj
            dist_sq = (ball["x"] - cx)**2 + (ball["y"] - cy)**2

            # If the ray passes close enough to hit the ball
            if dist_sq <= (2 * r)**2:
                offset = math.sqrt((2 * r)**2 - dist_sq)
                t = proj - offset
                if 0 < t < min_t:
                    min_t = t
                    hit_ball = ball

    # 2. Check for collisions with walls (cushions)
    bound_left = table_x + cushion + r
    bound_right = table_x + table_w - cushion - r
    bound_top = table_y + cushion + r
    bound_bottom = table_y + table_h - cushion - r

    t_wall_x = float('inf')
    t_wall_y = float('inf')

    if ux > 0: t_wall_x = (bound_right - cue_ball["x"]) / ux
    elif ux < 0: t_wall_x = (bound_left - cue_ball["x"]) / ux

    if uy > 0: t_wall_y = (bound_bottom - cue_ball["y"]) / uy
    elif uy < 0: t_wall_y = (bound_top - cue_ball["y"]) / uy

    t_wall = min(t_wall_x, t_wall_y)

    # 3. Choose the closest hit (ball or wall)
    if t_wall < min_t:
        min_t = t_wall
        hit_ball = None

    # Exact impact point of the cue ball
    end_x = cue_ball["x"] + ux * min_t
    end_y = cue_ball["y"] + uy * min_t

    # Draw the main aiming line
    pygame.draw.line(screen, (255, 255, 255), (cue_ball["x"], cue_ball["y"]), (end_x, end_y), 2)

    if hit_ball:
        # Draw Ghost Ball (Hollow circle)
        pygame.draw.circle(screen, (255, 255, 255), (int(end_x), int(end_y)), int(r), 1)

        # Calculate target ball direction
        nx = hit_ball["x"] - end_x
        ny = hit_ball["y"] - end_y
        n_dist = math.sqrt(nx**2 + ny**2)
        if n_dist > 0:
            nx /= n_dist
            ny /= n_dist

        # Draw target ball trajectory line
        target_end_x = hit_ball["x"] + nx * 50
        target_end_y = hit_ball["y"] + ny * 50
        pygame.draw.line(screen, hit_ball["color"], (hit_ball["x"], hit_ball["y"]), (target_end_x, target_end_y), 3)

        # Calculate cue ball deflection (Tangent vector)
        dot = ux * nx + uy * ny
        def_x = ux - dot * nx
        def_y = uy - dot * ny
        
        def_dist = math.sqrt(def_x**2 + def_y**2)
        if def_dist > 0:
            def_x /= def_dist
            def_y /= def_dist
            cue_end_x = end_x + def_x * 40
            cue_end_y = end_y + def_y * 40
            pygame.draw.line(screen, (255, 255, 255), (end_x, end_y), (cue_end_x, cue_end_y), 2)
    else:
        # Only hit wall, draw ghost ball there
        pygame.draw.circle(screen, (255, 255, 255), (int(end_x), int(end_y)), int(r), 1)