"""
Snake Game Online — نسخة بايثون متصلة بخادم مشترك
=====================================================
لعبة الثعبان الكلاسيكية مبنية باستخدام مكتبة pygame، مع:
- شاشة إدخال اسم مستخدم
- اختيار مستوى الصعوبة (سهل / متوسط / صعب)
- لوحة صدارة أونلاين حقيقية عبر خادم Flask (server.py) يشترك فيها كل من
  يشغّل هذا السكربت ومتصل بنفس الخادم — سواء على نفس الشبكة أو عبر الإنترنت
- تأثيرات بصرية: توهج، جسيمات عند الأكل، اهتزاز شاشة بسيط، تسارع تدريجي

المتطلبات:
    pip install pygame requests

التشغيل:
    1. شغّل الخادم أولًا (مرة واحدة، على أي جهاز):
           python server.py
    2. عدّل قيمة SERVER_URL أدناه لتشير إلى عنوان جهاز الخادم (راجع
       التعليمات داخل server.py لمعرفة كيفية إيجاد هذا العنوان).
    3. شغّل هذا الملف عند كل لاعب:
           python snake_game.py

ملاحظة: إذا تعذر الوصول إلى الخادم (غير مشغّل، أو عنوان خاطئ، أو لا يوجد
اتصال إنترنت)، تستمر اللعبة بالعمل محليًا فقط مع رسالة توضح تعذر الاتصال،
دون أن تتوقف أو تتجمد.
"""

import math
import random
import sys
import threading
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pygame

try:
    import requests
except ImportError:
    requests = None  # سيتم التعامل مع هذه الحالة عند محاولة الاتصال بالخادم

# غيّر هذا العنوان ليشير إلى جهاز الخادم الخاص بك (راجع server.py للتفاصيل)
SERVER_URL = "http://127.0.0.1:5000"
REQUEST_TIMEOUT = 4  # ثوانٍ

# ---------------------------------------------------------------------------
# الإعدادات العامة
# ---------------------------------------------------------------------------

GRID_SIZE = 20
GRID_COUNT = 22
BOARD_PIXELS = GRID_SIZE * GRID_COUNT
SIDEBAR_WIDTH = 260
WINDOW_WIDTH = BOARD_PIXELS + SIDEBAR_WIDTH
WINDOW_HEIGHT = BOARD_PIXELS

LEADERBOARD_MAX_ENTRIES = 10

# الألوان (RGB) — نفس هوية اللعبة الأصلية
COLOR_BG = (6, 10, 20)
COLOR_GRID = (17, 26, 43)
COLOR_PANEL = (19, 26, 43)
COLOR_BORDER = (34, 48, 74)
COLOR_ACCENT = (74, 222, 128)
COLOR_ACCENT_2 = (34, 197, 94)
COLOR_DANGER = (248, 113, 113)
COLOR_GOLD = (251, 191, 36)
COLOR_TEXT = (226, 232, 240)
COLOR_TEXT_DIM = (124, 138, 165)

DIFFICULTIES = {
    "سهل": 150,
    "متوسط": 105,
    "صعب": 70,
}

pygame.init()
pygame.display.set_caption("Snake — لعبة الثعبان")
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
clock = pygame.time.Clock()

FONT_BIG = pygame.font.SysFont("arial", 36, bold=True)
FONT_MED = pygame.font.SysFont("arial", 22, bold=True)
FONT_SMALL = pygame.font.SysFont("arial", 15)
FONT_TINY = pygame.font.SysFont("arial", 12)


# ---------------------------------------------------------------------------
# لوحة الصدارة الأونلاين — اتصال بالخادم عبر HTTP (بدون تجميد الواجهة)
# ---------------------------------------------------------------------------
# كل طلب شبكة يُنفَّذ في خيط (thread) منفصل حتى لا تتجمد نافذة اللعبة أثناء
# انتظار رد الخادم. النتيجة تُكتب في متغيرات مشتركة تقرأها الحلقة الرئيسية.

def fetch_leaderboard_sync() -> Tuple[Optional[List[dict]], Optional[str]]:
    """يجلب لوحة الصدارة من الخادم. يعيد (النتائج, رسالة خطأ)."""
    if requests is None:
        return None, "مكتبة requests غير مثبتة (pip install requests)"
    try:
        resp = requests.get(f"{SERVER_URL}/leaderboard", timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            return resp.json(), None
        return None, f"خطأ من الخادم ({resp.status_code})"
    except requests.exceptions.RequestException:
        return None, "تعذر الاتصال بالخادم"


def submit_score_sync(username: str, score: int) -> Tuple[Optional[List[dict]], bool, Optional[str]]:
    """يرسل نتيجة إلى الخادم. يعيد (اللوحة المحدثة, هل هو رقم قياسي جديد, رسالة خطأ)."""
    if requests is None:
        return None, False, "مكتبة requests غير مثبتة (pip install requests)"
    try:
        resp = requests.post(
            f"{SERVER_URL}/score",
            json={"username": username, "score": score},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("leaderboard", []), data.get("is_new_best", False), None
        return None, False, f"خطأ من الخادم ({resp.status_code})"
    except requests.exceptions.RequestException:
        return None, False, "تعذر الاتصال بالخادم"


# ---------------------------------------------------------------------------
# فئات مساعدة (جسيمات، نصوص منبثقة)
# ---------------------------------------------------------------------------

@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float = 1.0
    color: Tuple[int, int, int] = COLOR_DANGER


@dataclass
class ScorePopup:
    x: float
    y: float
    life: float = 1.0
    text: str = "+10"


# ---------------------------------------------------------------------------
# رسم عناصر واجهة بسيطة
# ---------------------------------------------------------------------------

def draw_text(text, font, color, center=None, topleft=None):
    surf = font.render(text, True, color)
    rect = surf.get_rect()
    if center:
        rect.center = center
    if topleft:
        rect.topleft = topleft
    screen.blit(surf, rect)
    return rect


def draw_rounded_rect(surface, rect, color, radius=6):
    pygame.draw.rect(surface, color, rect, border_radius=radius)


class Button:
    def __init__(self, rect, text, font=FONT_SMALL, active=False):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.font = font
        self.active = active

    def draw(self, surface):
        bg = COLOR_ACCENT if self.active else (13, 19, 34)
        fg = (6, 17, 10) if self.active else COLOR_TEXT_DIM
        draw_rounded_rect(surface, self.rect, bg, radius=8)
        if not self.active:
            pygame.draw.rect(surface, COLOR_BORDER, self.rect, width=1, border_radius=8)
        text_surf = self.font.render(self.text, True, fg)
        surface.blit(text_surf, text_surf.get_rect(center=self.rect.center))

    def is_clicked(self, pos):
        return self.rect.collidepoint(pos)


class TextInput:
    def __init__(self, rect, placeholder="", max_len=16):
        self.rect = pygame.Rect(rect)
        self.text = ""
        self.placeholder = placeholder
        self.max_len = max_len
        self.active = True
        self.cursor_visible = True
        self.cursor_timer = 0

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_RETURN:
                return "submit"
            elif len(self.text) < self.max_len and event.unicode.isprintable():
                self.text += event.unicode
        return None

    def update(self, dt):
        self.cursor_timer += dt
        if self.cursor_timer > 0.5:
            self.cursor_timer = 0
            self.cursor_visible = not self.cursor_visible

    def draw(self, surface):
        draw_rounded_rect(surface, self.rect, (13, 19, 34), radius=10)
        pygame.draw.rect(surface, COLOR_ACCENT if self.active else COLOR_BORDER,
                          self.rect, width=1, border_radius=10)
        display_text = self.text if self.text else self.placeholder
        color = COLOR_TEXT if self.text else COLOR_TEXT_DIM
        text_surf = FONT_SMALL.render(display_text, True, color)
        text_rect = text_surf.get_rect(midleft=(self.rect.x + 12, self.rect.centery))
        surface.blit(text_surf, text_rect)
        if self.active and self.cursor_visible and self.text:
            cursor_x = text_rect.right + 2
            pygame.draw.line(surface, COLOR_TEXT,
                              (cursor_x, self.rect.y + 8), (cursor_x, self.rect.bottom - 8), 2)


# ---------------------------------------------------------------------------
# اللعبة نفسها
# ---------------------------------------------------------------------------

class SnakeGame:
    def __init__(self):
        self.state = "start"  # start | playing | paused | game_over
        self.username = ""
        self.difficulty_name = "متوسط"
        self.base_speed_ms = DIFFICULTIES[self.difficulty_name]
        self.leaderboard: List[dict] = []
        self.my_best = 0

        # حالة الاتصال بالخادم
        self.connection_status = "connecting"  # connecting | online | offline
        self.status_message = "جارٍ الاتصال بالخادم..."
        self.save_status = ""
        self._network_lock = threading.Lock()

        self.refresh_leaderboard_async()

        self.username_input = TextInput(
            (BOARD_PIXELS // 2 - 110, 210, 220, 42),
            placeholder="اكتب اسم المستخدم"
        )

        diff_names = list(DIFFICULTIES.keys())
        total_w = 3 * 90 + 2 * 10
        start_x = BOARD_PIXELS // 2 - total_w // 2
        self.diff_buttons = []
        for i, name in enumerate(diff_names):
            btn = Button((start_x + i * 100, 270, 90, 36), name, active=(name == self.difficulty_name))
            self.diff_buttons.append((name, btn))

        self.start_button = Button((BOARD_PIXELS // 2 - 90, 330, 180, 46), "ابدأ اللعبة", FONT_MED)
        self.restart_button = Button((BOARD_PIXELS // 2 - 90, BOARD_PIXELS // 2 + 70, 180, 46),
                                      "إعادة اللعب", FONT_MED)
        self.resume_button = Button((BOARD_PIXELS // 2 - 90, BOARD_PIXELS // 2, 180, 46),
                                     "متابعة", FONT_MED)

        self.reset_round()

    # -- إعداد جولة جديدة --
    def reset_round(self):
        self.snake = [(10, 10), (9, 10), (8, 10)]
        self.direction = (1, 0)
        self.next_direction = (1, 0)
        self.score = 0
        self.speed_level = 1
        self.current_interval_ms = self.base_speed_ms
        self.time_since_last_tick = 0.0
        self.particles: List[Particle] = []
        self.score_popups: List[ScorePopup] = []
        self.shake = 0.0
        self.food_pulse = 0.0
        self.place_food()
        self.new_record = False

    def place_food(self):
        while True:
            fx = random.randint(0, GRID_COUNT - 1)
            fy = random.randint(0, GRID_COUNT - 1)
            if (fx, fy) not in self.snake:
                self.food = (fx, fy)
                return

    def spawn_particles(self, gx, gy, color):
        cx = gx * GRID_SIZE + GRID_SIZE / 2
        cy = gy * GRID_SIZE + GRID_SIZE / 2
        for i in range(14):
            angle = (2 * math.pi * i) / 14
            speed = random.uniform(1.5, 3.5)
            self.particles.append(Particle(
                x=cx, y=cy,
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed,
                color=color,
            ))

    # -- منطق التحديث --
    def set_direction(self, dx, dy):
        if self.state != "playing":
            return
        cur_dx, cur_dy = self.direction
        if (cur_dx, cur_dy) == (-dx, -dy) and len(self.snake) > 1:
            return
        self.next_direction = (dx, dy)

    def toggle_pause(self):
        if self.state == "playing":
            self.state = "paused"
        elif self.state == "paused":
            self.state = "playing"

    def step(self):
        """خطوة حركة واحدة للثعبان (تُستدعى بمعدل يعتمد على السرعة الحالية)."""
        self.direction = self.next_direction
        dx, dy = self.direction
        if dx == 0 and dy == 0:
            return

        head_x, head_y = self.snake[0]
        new_head = (head_x + dx, head_y + dy)

        if not (0 <= new_head[0] < GRID_COUNT and 0 <= new_head[1] < GRID_COUNT):
            self.end_game()
            return
        if new_head in self.snake:
            self.end_game()
            return

        self.snake.insert(0, new_head)

        if new_head == self.food:
            self.score += 10
            self.score_popups.append(ScorePopup(
                x=self.food[0] * GRID_SIZE + GRID_SIZE / 2,
                y=self.food[1] * GRID_SIZE,
            ))
            self.spawn_particles(*self.food, COLOR_DANGER)
            self.shake = 4.0
            if self.score % 50 == 0 and self.current_interval_ms > 45:
                self.current_interval_ms = max(45, self.current_interval_ms - 8)
                self.speed_level = round((self.base_speed_ms - self.current_interval_ms) / 8) + 1
            self.place_food()
        else:
            self.snake.pop()

    def end_game(self):
        self.state = "game_over"
        self.new_record = False
        if self.score > self.my_best:
            self.my_best = self.score
        self.submit_score_async(self.username, self.score)

    # -- طلبات الشبكة (غير محجوبة/asynchronous عبر threads) --
    def refresh_leaderboard_async(self):
        def worker():
            data, error = fetch_leaderboard_sync()
            with self._network_lock:
                if data is not None:
                    self.leaderboard = data
                    self.connection_status = "online"
                    self.status_message = ""
                else:
                    self.connection_status = "offline"
                    self.status_message = error or "تعذر الاتصال بالخادم"
        threading.Thread(target=worker, daemon=True).start()

    def submit_score_async(self, username: str, score: int):
        self.save_status = "جارٍ حفظ نتيجتك في لوحة الصدارة..."

        def worker():
            leaderboard, is_new_best, error = submit_score_sync(username, score)
            with self._network_lock:
                if leaderboard is not None:
                    self.leaderboard = leaderboard
                    self.connection_status = "online"
                    self.new_record = is_new_best
                    self.save_status = (
                        "✅ تم حفظ نتيجتك في لوحة الصدارة"
                        if is_new_best else
                        "نتيجتك السابقة أعلى — لم يتم التحديث"
                    )
                else:
                    self.connection_status = "offline"
                    self.save_status = f"⚠️ {error or 'تعذر حفظ النتيجة'}"
        threading.Thread(target=worker, daemon=True).start()

    def update(self, dt):
        if self.state == "start":
            self.username_input.update(dt)
            return
        if self.state != "playing":
            return

        self.time_since_last_tick += dt * 1000
        if self.time_since_last_tick >= self.current_interval_ms:
            self.time_since_last_tick = 0
            self.step()

        self.food_pulse += dt * 6
        if self.shake > 0:
            self.shake *= 0.85
            if self.shake < 0.2:
                self.shake = 0

        for p in self.particles:
            p.x += p.vx
            p.y += p.vy
            p.life -= 0.04
        self.particles = [p for p in self.particles if p.life > 0]

        for s in self.score_popups:
            s.life -= 0.02
        self.score_popups = [s for s in self.score_popups if s.life > 0]

    # -- الرسم --
    def draw_board_background(self, offset):
        ox, oy = offset
        pygame.draw.rect(screen, COLOR_BG, (ox, oy, BOARD_PIXELS, BOARD_PIXELS))
        for i in range(GRID_COUNT + 1):
            pygame.draw.line(screen, COLOR_GRID, (ox + i * GRID_SIZE, oy), (ox + i * GRID_SIZE, oy + BOARD_PIXELS))
            pygame.draw.line(screen, COLOR_GRID, (ox, oy + i * GRID_SIZE), (ox + BOARD_PIXELS, oy + i * GRID_SIZE))

    def draw_game(self):
        offset_x = int((random.random() - 0.5) * self.shake)
        offset_y = int((random.random() - 0.5) * self.shake)
        ox, oy = offset_x, offset_y

        self.draw_board_background((ox, oy))

        # الطعام مع نبضة
        pulse = math.sin(self.food_pulse) * 2
        fx, fy = self.food
        pygame.draw.circle(
            screen, COLOR_DANGER,
            (ox + fx * GRID_SIZE + GRID_SIZE // 2, oy + fy * GRID_SIZE + GRID_SIZE // 2),
            int(GRID_SIZE / 2.6 + pulse * 0.3),
        )

        # جسم الثعبان بتدرج لوني
        n = len(self.snake)
        for i, (sx, sy) in enumerate(self.snake):
            t = i / max(n, 1)
            if i == 0:
                color = COLOR_ACCENT
            else:
                g = int(220 - t * 90)
                b = int(129 - t * 40)
                color = (34, max(g, 0), max(b, 0))
            rect = pygame.Rect(ox + sx * GRID_SIZE + 1, oy + sy * GRID_SIZE + 1, GRID_SIZE - 2, GRID_SIZE - 2)
            draw_rounded_rect(screen, rect, color, radius=6)

        # عينا الرأس
        if self.snake:
            hx, hy = self.snake[0]
            cx = ox + hx * GRID_SIZE + GRID_SIZE // 2
            cy = oy + hy * GRID_SIZE + GRID_SIZE // 2
            dx, dy = self.direction
            if dx == 1:
                eyes = [(cx + 3, cy - 4), (cx + 3, cy + 4)]
            elif dx == -1:
                eyes = [(cx - 3, cy - 4), (cx - 3, cy + 4)]
            elif dy == 1:
                eyes = [(cx - 4, cy + 3), (cx + 4, cy + 3)]
            else:
                eyes = [(cx - 4, cy - 3), (cx + 4, cy - 3)]
            for ex, ey in eyes:
                pygame.draw.circle(screen, (6, 17, 10), (ex, ey), 2)

        # الجسيمات
        for p in self.particles:
            alpha_color = p.color
            radius = max(int(2.5 * p.life), 1)
            pygame.draw.circle(screen, alpha_color, (int(ox + p.x), int(oy + p.y)), radius)

        # نصوص النقاط المنبثقة
        for s in self.score_popups:
            popup_surf = FONT_SMALL.render(s.text, True, COLOR_GOLD)
            popup_surf.set_alpha(max(int(255 * s.life), 0))
            rect = popup_surf.get_rect(center=(ox + s.x, oy + s.y - (1 - s.life) * 30))
            screen.blit(popup_surf, rect)

    def draw_sidebar(self):
        sx = BOARD_PIXELS
        pygame.draw.rect(screen, COLOR_PANEL, (sx, 0, SIDEBAR_WIDTH, WINDOW_HEIGHT))
        pygame.draw.line(screen, COLOR_BORDER, (sx, 0), (sx, WINDOW_HEIGHT), 2)

        pad = 20
        y = 24
        draw_text("🐍 Snake", FONT_BIG, COLOR_ACCENT, topleft=(sx + pad, y))

        # مؤشر حالة الاتصال بالخادم
        dot_color = {
            "online": COLOR_ACCENT,
            "offline": COLOR_DANGER,
            "connecting": COLOR_GOLD,
        }.get(self.connection_status, COLOR_TEXT_DIM)
        dot_label = {
            "online": "متصل",
            "offline": "غير متصل",
            "connecting": "جارٍ الاتصال...",
        }.get(self.connection_status, "")
        pygame.draw.circle(screen, dot_color, (sx + SIDEBAR_WIDTH - 24, 34), 4)
        status_surf = FONT_TINY.render(dot_label, True, dot_color)
        screen.blit(status_surf, status_surf.get_rect(midright=(sx + SIDEBAR_WIDTH - 34, 34)))

        y += 46

        if self.username:
            draw_text(f"اللاعب: {self.username}", FONT_SMALL, COLOR_TEXT_DIM, topleft=(sx + pad, y))
            y += 30

        # كروت الإحصائيات
        stats = [("النقاط", str(self.score), COLOR_ACCENT),
                 ("أفضل نتيجة لي", str(self.my_best), COLOR_GOLD),
                 ("مستوى السرعة", str(self.speed_level), COLOR_ACCENT)]
        for label, value, color in stats:
            card_rect = pygame.Rect(sx + pad, y, SIDEBAR_WIDTH - pad * 2, 46)
            draw_rounded_rect(screen, card_rect, (13, 19, 34), radius=10)
            draw_text(label, FONT_TINY, COLOR_TEXT_DIM, topleft=(card_rect.x + 12, card_rect.y + 6))
            draw_text(value, FONT_MED, color, topleft=(card_rect.x + 12, card_rect.y + 20))
            y += 56

        y += 10
        draw_text("🏆 لوحة الصدارة (أونلاين)", FONT_SMALL, COLOR_GOLD, topleft=(sx + pad, y))
        y += 30

        if self.connection_status == "offline" and not self.leaderboard:
            draw_text("تعذر الاتصال بالخادم", FONT_TINY, COLOR_DANGER, topleft=(sx + pad, y))
            y += 20
            draw_text("تحقق من تشغيل server.py", FONT_TINY, COLOR_TEXT_DIM, topleft=(sx + pad, y))
        elif not self.leaderboard:
            draw_text("لا توجد نتائج بعد", FONT_TINY, COLOR_TEXT_DIM, topleft=(sx + pad, y))
        else:
            rank_colors = {0: COLOR_GOLD, 1: (203, 213, 225), 2: (217, 119, 6)}
            for i, entry in enumerate(self.leaderboard[:8]):
                row_rect = pygame.Rect(sx + pad, y, SIDEBAR_WIDTH - pad * 2, 30)
                entry_name = entry.get("username", "???")
                is_me = entry_name.lower() == self.username.lower()
                bg = (13, 45, 30) if is_me else (13, 19, 34)
                draw_rounded_rect(screen, row_rect, bg, radius=6)
                rank_color = rank_colors.get(i, COLOR_TEXT_DIM)
                draw_text(str(i + 1), FONT_TINY, rank_color, topleft=(row_rect.x + 8, row_rect.y + 8))
                name = entry_name
                if len(name) > 14:
                    name = name[:13] + "…"
                draw_text(name, FONT_TINY, COLOR_TEXT, topleft=(row_rect.x + 28, row_rect.y + 8))
                score_surf = FONT_TINY.render(str(entry.get("score", 0)), True, COLOR_ACCENT)
                score_rect = score_surf.get_rect(topright=(row_rect.right - 8, row_rect.y + 8))
                screen.blit(score_surf, score_rect)
                y += 34

        y = WINDOW_HEIGHT - 70
        draw_text("الأسهم: تحريك", FONT_TINY, COLOR_TEXT_DIM, topleft=(sx + pad, y))
        draw_text("مسافة: إيقاف مؤقت", FONT_TINY, COLOR_TEXT_DIM, topleft=(sx + pad, y + 20))
        draw_text("Esc: تبديل المستخدم", FONT_TINY, COLOR_TEXT_DIM, topleft=(sx + pad, y + 40))

    def draw_start_screen(self):
        screen.fill(COLOR_BG)
        draw_text("🐍 Snake — لعبة الثعبان", FONT_BIG, COLOR_ACCENT,
                  center=(BOARD_PIXELS // 2, 110))
        draw_text("أدخل اسم المستخدم لبدء اللعب", FONT_SMALL, COLOR_TEXT_DIM,
                  center=(BOARD_PIXELS // 2, 160))

        self.username_input.draw(screen)

        draw_text("اختر مستوى الصعوبة", FONT_TINY, COLOR_TEXT_DIM,
                  center=(BOARD_PIXELS // 2, 260))
        for name, btn in self.diff_buttons:
            btn.active = (name == self.difficulty_name)
            btn.draw(screen)

        self.start_button.draw(screen)

        if not self.username_input.text.strip():
            draw_text("(الرجاء إدخال اسم مستخدم للمتابعة)", FONT_TINY, COLOR_DANGER,
                      center=(BOARD_PIXELS // 2, 390))

    def draw_overlay(self, title, title_color, subtitle):
        overlay_surf = pygame.Surface((BOARD_PIXELS, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay_surf.fill((6, 10, 20, 230))
        screen.blit(overlay_surf, (0, 0))

        cy = WINDOW_HEIGHT // 2
        draw_text(title, FONT_BIG, title_color, center=(BOARD_PIXELS // 2, cy - 90))
        if self.state == "game_over":
            draw_text(str(self.score), FONT_BIG, COLOR_GOLD, center=(BOARD_PIXELS // 2, cy - 40))
            draw_text(subtitle, FONT_TINY, COLOR_TEXT_DIM, center=(BOARD_PIXELS // 2, cy - 5))
            status_color = COLOR_DANGER if "⚠️" in self.save_status else COLOR_ACCENT
            draw_text(self.save_status, FONT_TINY, status_color, center=(BOARD_PIXELS // 2, cy + 20))
            self.restart_button.draw(screen)
        else:
            self.resume_button.draw(screen)

    def draw(self):
        if self.state == "start":
            self.draw_start_screen()
            return

        self.draw_game()
        self.draw_sidebar()

        if self.state == "paused":
            self.draw_overlay("⏸ إيقاف مؤقت", COLOR_TEXT, "")
        elif self.state == "game_over":
            if self.new_record:
                self.draw_overlay("🏆 رقم قياسي جديد!", COLOR_ACCENT, "أحسنت! تم حفظ نتيجتك في لوحة الصدارة")
            else:
                self.draw_overlay("انتهت اللعبة", COLOR_DANGER, "حاول مرة أخرى لتحسين نتيجتك")

    # -- التعامل مع الأحداث --
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        if self.state == "start":
            result = self.username_input.handle_event(event)
            if event.type == pygame.MOUSEBUTTONDOWN:
                for name, btn in self.diff_buttons:
                    if btn.is_clicked(event.pos):
                        self.difficulty_name = name
                        self.base_speed_ms = DIFFICULTIES[name]
                if self.start_button.is_clicked(event.pos):
                    self.try_start()
            if result == "submit":
                self.try_start()
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.set_direction(0, -1)
            elif event.key == pygame.K_DOWN:
                self.set_direction(0, 1)
            elif event.key == pygame.K_LEFT:
                self.set_direction(-1, 0)
            elif event.key == pygame.K_RIGHT:
                self.set_direction(1, 0)
            elif event.key == pygame.K_SPACE:
                self.toggle_pause()
            elif event.key == pygame.K_ESCAPE:
                self.go_to_start()

        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.state == "paused" and self.resume_button.is_clicked(event.pos):
                self.toggle_pause()
            elif self.state == "game_over" and self.restart_button.is_clicked(event.pos):
                self.reset_round()
                self.state = "playing"

    def try_start(self):
        name = self.username_input.text.strip()
        if not name:
            return
        self.username = name
        self.my_best = 0
        for entry in self.leaderboard:
            if entry.get("username", "").lower() == name.lower():
                self.my_best = entry.get("score", 0)
                break
        self.reset_round()
        self.state = "playing"
        self.refresh_leaderboard_async()

    def go_to_start(self):
        self.state = "start"
        self.username_input.text = self.username
        self.refresh_leaderboard_async()


# ---------------------------------------------------------------------------
# الحلقة الرئيسية
# ---------------------------------------------------------------------------

def main():
    game = SnakeGame()
    while True:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            game.handle_event(event)
        game.update(dt)
        game.draw()
        pygame.display.flip()


if __name__ == "__main__":
    main()
