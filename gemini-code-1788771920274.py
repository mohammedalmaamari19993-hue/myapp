import json
import os
import random
import sys
import urllib.request
import pygame

# تهيئة Pygame
pygame.init()

# أبعاد الشاشة
WIDTH, HEIGHT = 800, 450
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Bounce Classic - 20 Levels with Online Leaderboard")

# الألوان
BG_COLOR = (18, 24, 48)
WALL_COLOR = (139, 69, 19)
WALL_BORDER = (90, 45, 12)
SPIKE_COLOR = (255, 51, 102)
RING_COLOR = (255, 215, 0)
BALL_COLOR = (255, 85, 0)
BALL_SHINE = (255, 170, 160)
WHITE = (255, 255, 255)
CYAN = (0, 255, 204)
OVERLAY_BG = (12, 15, 29, 235)

# الخطوط
FONT_TITLE = pygame.font.SysFont("Arial", 28, bold=True)
FONT_HUD = pygame.font.SysFont("Arial", 16, bold=True)
FONT_SMALL = pygame.font.SysFont("Arial", 14)

# أبعاد الشبكة واللعبة
TILE_SIZE = 32
MAX_LEVELS = 20

# رابط الخادم العام للوحة الصدارة (JSONBin API)
API_URL = "https://api.jsonbin.io/v3/b/65f000000000000000000000"  # يمكن استبداله بـ Endpoint خاص بك


# --- إدارة لوحة الصدارة عبر النت ---
def fetch_global_leaderboard():
    """جلب قائمة المتصدرين من الإنترنت"""
    try:
        req = urllib.request.Request(
            API_URL + "/latest", headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            return data.get("record", {}).get("scores", [])
    except Exception:
        # لوحة صدارة افتراضية محلياً عند عدم وجود اتصال
        return [
            {"name": "ProPlayer", "score": 2000},
            {"name": "BounceMaster", "score": 1500},
            {"name": "GamerX", "score": 1000},
        ]


def submit_global_score(player_name, score):
    """إرسال نتيجة جديدة للوحة الصدارة"""
    try:
        scores = fetch_global_leaderboard()
        scores.append({"name": player_name, "score": score})
        # ترتيب النتائج تنازلياً والإبقاء على أفضل 5
        scores = sorted(scores, key=lambda x: x["score"], reverse=True)[:5]

        data = json.dumps({"scores": scores}).encode("utf-8")
        req = urllib.request.Request(
            API_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass


# --- كائن الكرة ---
class Ball:

    def __init__(self, x, y):
        self.radius = 12
        self.reset(x, y)
        self.speed = 5
        self.jump_strength = -10
        self.gravity = 0.45

    def reset(self, x, y):
        self.x = x
        self.y = y
        self.vx = 0
        self.vy = 0
        self.is_grounded = False

    def update(self, keys):
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.vx = self.speed
        elif keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.vx = -self.speed
        else:
            self.vx *= 0.8

        if (
            keys[pygame.K_UP]
            or keys[pygame.K_w]
            or keys[pygame.K_SPACE]
        ) and self.is_grounded:
            self.vy = self.jump_strength
            self.is_grounded = False

        self.vy += self.gravity

    def draw(self, surface):
        pygame.draw.circle(
            surface, BALL_COLOR, (int(self.x), int(self.y)), self.radius
        )
        pygame.draw.circle(
            surface, BALL_SHINE, (int(self.x) - 3, int(self.y) - 3), 3
        )


# --- توليد المستويات ---
def generate_level(lvl):
    grid = [[0 for _ in range(25)] for _ in range(9)]
    for i in range(25):
        grid[0][i] = 1
        grid[8][i] = 1
    for i in range(9):
        grid[i][0] = 1
        grid[i][24] = 1

    spike_count = min(2 + lvl, 12)
    ring_count = min(2 + (lvl // 2), 7)
    platform_count = min(3 + (lvl // 3), 8)

    for i in range(platform_count):
        px = int(3 + i * (18 / platform_count))
        py = int(3 + (i % 3) * 1.5)
        grid[py][px] = 1
        if px + 1 < 24:
            grid[py][px + 1] = 1

    rings = 0
    while rings < ring_count:
        rx, ry = random.randint(2, 21), random.randint(2, 6)
        if grid[ry][rx] == 0:
            grid[ry][rx] = 3
            rings += 1

    spikes = 0
    while spikes < spike_count:
        sx = random.randint(3, 21)
        if grid[7][sx] == 0:
            grid[7][sx] = 2
            spikes += 1

    return grid


# --- تشغيل اللعبة الرئيسي ---
def main():
    clock = pygame.time.Clock()
    current_level = 1
    lives = 3
    total_score = 0
    player_name = "Player1"

    leaderboard = fetch_global_leaderboard()

    def init_level(lvl):
        grid = generate_level(lvl)
        rings = []
        total_rings = 0
        for r in range(9):
            for c in range(25):
                if grid[r][c] == 3:
                    rings.append({"r": r, "c": c, "collected": False})
                    total_rings += 1
        ball = Ball(60, 150)
        return grid, ball, rings, total_rings

    grid, ball, rings, total_rings = init_level(current_level)
    collected_rings = 0
    is_game_over = False
    is_level_complete = False

    while True:
        keys = pygame.key.get_pressed()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if is_game_over or is_level_complete:
                    if event.key == pygame.K_RETURN:
                        if is_game_over:
                            # حفظ النتيجة بجدول الصدارة العالمي
                            submit_global_score(player_name, total_score)
                            leaderboard = fetch_global_leaderboard()
                            total_score = 0
                            current_level = 1
                            lives = 3

                        grid, ball, rings, total_rings = init_level(
                            current_level
                        )
                        collected_rings = 0
                        is_game_over = False
                        is_level_complete = False

        if not is_game_over and not is_level_complete:
            ball.update(keys)

            # التصادم الأفقي
            ball.x += ball.vx
            for r in range(9):
                for c in range(25):
                    tile = grid[r][c]
                    if tile in (1, 2):
                        tx, ty = c * TILE_SIZE, r * TILE_SIZE
                        if (
                            ball.x + ball.radius > tx
                            and ball.x - ball.radius < tx + TILE_SIZE
                            and ball.y + ball.radius > ty
                            and ball.y - ball.radius < ty + TILE_SIZE
                        ):

                            if tile == 2:  # أصاب شوكاً
                                lives -= 1
                                if lives <= 0:
                                    is_game_over = True
                                else:
                                    ball.reset(60, 150)
                                break

                            if ball.vx > 0:
                                ball.x = tx - ball.radius
                            elif ball.vx < 0:
                                ball.x = tx + TILE_SIZE + ball.radius
                            ball.vx = 0

            # التصادم الرأسي
            ball.y += ball.vy
            ball.is_grounded = False
            for r in range(9):
                for c in range(25):
                    tile = grid[r][c]
                    if tile in (1, 2):
                        tx, ty = c * TILE_SIZE, r * TILE_SIZE
                        if (
                            ball.x + ball.radius > tx
                            and ball.x - ball.radius < tx + TILE_SIZE
                            and ball.y + ball.radius > ty
                            and ball.y - ball.radius < ty + TILE_SIZE
                        ):

                            if tile == 2:
                                lives -= 1
                                if lives <= 0:
                                    is_game_over = True
                                else:
                                    ball.reset(60, 150)
                                break

                            if ball.vy > 0:
                                ball.y = ty - ball.radius
                                ball.is_grounded = True
                            elif ball.vy < 0:
                                ball.y = ty + TILE_SIZE + ball.radius
                            ball.vy = 0

            # جمع الحلقات واحتساب النقاط
            for ring in rings:
                if not ring["collected"]:
                    rx = ring["c"] * TILE_SIZE + TILE_SIZE // 2
                    ry = ring["r"] * TILE_SIZE + TILE_SIZE // 2
                    dist = ((ball.x - rx) ** 2 + (ball.y - ry) ** 2) ** 0.5
                    if dist < ball.radius + 8:
                        ring["collected"] = True
                        collected_rings += 1
                        total_score += 100  # 100 نقطة لكل حلقة
                        if collected_rings == total_rings:
                            is_level_complete = True
                            total_score += 500  # بونص إنهاء المستوى
                            if current_level < MAX_LEVELS:
                                current_level += 1

        # --- الرسم (Render) ---
        SCREEN.fill(BG_COLOR)

        # رسم عناصر اللعبة
        for r in range(9):
            for c in range(25):
                tile = grid[r][c]
                tx, ty = c * TILE_SIZE, r * TILE_SIZE
                if tile == 1:
                    pygame.draw.rect(
                        SCREEN, WALL_COLOR, (tx, ty, TILE_SIZE, TILE_SIZE)
                    )
                    pygame.draw.rect(
                        SCREEN, WALL_BORDER, (tx, ty, TILE_SIZE, TILE_SIZE), 2
                    )
                elif tile == 2:
                    points = [
                        (tx, ty + TILE_SIZE),
                        (tx + TILE_SIZE // 2, ty),
                        (tx + TILE_SIZE, ty + TILE_SIZE),
                    ]
                    pygame.draw.polygon(SCREEN, SPIKE_COLOR, points)

        for ring in rings:
            if not ring["collected"]:
                rx = ring["c"] * TILE_SIZE + TILE_SIZE // 2
                ry = ring["r"] * TILE_SIZE + TILE_SIZE // 2
                pygame.draw.circle(SCREEN, RING_COLOR, (rx, ry), 9, 3)

        ball.draw(SCREEN)

        # رسم الهيدر والنقاط
        hud_text = FONT_HUD.render(
            f"LVL: {current_level}/{MAX_LEVELS}  SCORE: {total_score}  RINGS: {collected_rings}/{total_rings}  LIVES: {'❤️'*lives}",
            True,
            CYAN,
        )
        SCREEN.blit(hud_text, (15, 10))

        # --- شاشة الفوز/الخسارة + لوحة الصدارة العالمية ---
        if is_game_over or is_level_complete:
            s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            s.fill(OVERLAY_BG)
            SCREEN.blit(s, (0, 0))

            if is_game_over:
                title = FONT_TITLE.render("GAME OVER", True, SPIKE_COLOR)
                msg = FONT_HUD.render(
                    "Press [ENTER] to Submit Score & Restart", True, WHITE
                )
            else:
                title = FONT_TITLE.render(
                    "LEVEL COMPLETE! 🎉", True, RING_COLOR
                )
                msg = FONT_HUD.render("Press [ENTER] for Next Level!", True, WHITE)

            SCREEN.blit(
                title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 2 - 160)
            )
            SCREEN.blit(
                msg, (WIDTH // 2 - msg.get_width() // 2, HEIGHT // 2 - 110)
            )

            # رسم لوحة الصدارة (Top 5 Leaderboard)
            board_title = FONT_HUD.render(
                "🏆 GLOBAL LEADERBOARD (Top Players) 🏆", True, RING_COLOR
            )
            SCREEN.blit(
                board_title,
                (WIDTH // 2 - board_title.get_width() // 2, HEIGHT // 2 - 60),
            )

            for idx, item in enumerate(leaderboard[:5]):
                entry_text = FONT_SMALL.render(
                    f"{idx+1}. {item.get('name', 'Anon')} - {item.get('score', 0)} pts",
                    True,
                    WHITE,
                )
                SCREEN.blit(
                    entry_text,
                    (
                        WIDTH // 2 - entry_text.get_width() // 2,
                        HEIGHT // 2 - 25 + (idx * 22),
                    ),
                )

        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()