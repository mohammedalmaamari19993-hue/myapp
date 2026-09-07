"""
Snake — خادم اللعب الجماعي المتزامن (Real-time Multiplayer)
=====================================================
هذا الخادم هو "الحكم" الوحيد للعبة: هو من يحرّك كل الثعابين، يتحقق من
التصادمات، ويوزّع الطعام — بحيث يرى جميع اللاعبين نفس اللوحة تتحرك في
نفس اللحظة (تزامن حقيقي)، بدل أن تكون لوحة صدارة فقط.

الفكرة:
    - كل لاعب يرسل طلب /join فيحصل على معرّف خاص (player_id) ولون مميز.
    - كل لاعب يرسل اتجاهه الحالي عبر /direction كلما ضغط سهمًا.
    - المتصفح (كل المتصفحات لدى كل اللاعبين) يستعلم عن حالة اللعبة كاملة
      عبر /state عدة مرات في الثانية، ويرسم كل الثعابين كما هي عند الخادم.
    - الخادم نفسه يحرّك كل الثعابين معًا كل TICK_MS مللي ثانية في خيط
      (thread) منفصل يعمل باستمرار في الخلفية — وهذا ما يجعل كل اللاعبين
      يشاهدون نفس الحركة في نفس اللحظة تمامًا.

المتطلبات:
    pip install flask

التشغيل:
    python server.py

سيعمل الخادم افتراضيًا على المنفذ 5000 ويقبل اتصالات من أي جهاز (0.0.0.0).
كل من يشغّل تطبيق Streamlit (streamlit_app.py) ويتصل بهذا الخادم يدخل
نفس اللعبة الحية مع بقية اللاعبين.

ملاحظة عن التوسّع (Scaling):
    هذا الخادم يحتفظ بحالة اللعبة في الذاكرة (in-memory) داخل عملية واحدة.
    مناسب تمامًا للعب بين مجموعة أصدقاء على نفس الشبكة أو خادم استضافة
    بسيط (worker واحد). لا تشغّله بأكثر من worker/process واحد وإلا سيرى
    كل مجموعة لاعبين حالة لعبة مختلفة.
"""

import json
import os
import random
import threading
import time
import uuid

from flask import Flask, jsonify, request

app = Flask(__name__)

# ---------------------------------------------------------------------------
# إعدادات اللعبة
# ---------------------------------------------------------------------------

GRID_COUNT = 26          # عدد الخانات في كل ضلع من اللوحة (لوحة مربعة)
TICK_MS = 130            # كل كم مللي ثانية يتحرك الجميع خطوة واحدة
FOOD_COUNT = 6           # عدد قطع الطعام الموجودة على اللوحة في نفس الوقت
INACTIVE_TIMEOUT_SEC = 20  # إزالة اللاعب إن لم يُرسل أي طلب خلال هذه المدة
STARTING_LENGTH = 3

PLAYER_COLORS = [
    "#4ade80", "#60a5fa", "#f472b6", "#fbbf24",
    "#c084fc", "#fb923c", "#2dd4bf", "#f87171",
]

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leaderboard_server.json")
MAX_STORED_ENTRIES = 200
MAX_RETURNED_ENTRIES = 20

lock = threading.Lock()

# حالة اللعبة الحية بالكامل (في الذاكرة)
state = {
    "players": {},  # player_id -> {username, color, snake:[[x,y],...], direction, next_direction, alive, score, last_seen}
    "foods": [],    # [[x, y], ...]
}


# ---------------------------------------------------------------------------
# لوحة الصدارة الدائمة (أفضل نتيجة لكل لاعب عبر كل الجلسات) — تُحفظ في ملف
# ---------------------------------------------------------------------------

def load_leaderboard():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_leaderboard(entries):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def update_leaderboard(username, score):
    """يحدّث أفضل نتيجة لهذا الاسم إذا كانت النتيجة الجديدة أعلى. يُستدعى من داخل tick() فقط (القفل محجوز أصلًا)."""
    if score <= 0:
        return
    entries = load_leaderboard()
    found = False
    for entry in entries:
        if entry.get("username", "").lower() == username.lower():
            found = True
            if score > entry.get("score", 0):
                entry["score"] = score
            break
    if not found:
        entries.append({"username": username, "score": score})
    entries.sort(key=lambda e: e.get("score", 0), reverse=True)
    save_leaderboard(entries[:MAX_STORED_ENTRIES])


# ---------------------------------------------------------------------------
# أدوات مساعدة لحالة اللعبة
# ---------------------------------------------------------------------------

def occupied_cells():
    cells = set()
    for p in state["players"].values():
        if p["alive"]:
            cells.update(tuple(seg) for seg in p["snake"])
    cells.update(tuple(f) for f in state["foods"])
    return cells


def random_free_cell(exclude=None):
    exclude = exclude or set()
    taken = occupied_cells() | exclude
    for _ in range(400):
        c = (random.randint(0, GRID_COUNT - 1), random.randint(0, GRID_COUNT - 1))
        if c not in taken:
            return c
    return (random.randint(0, GRID_COUNT - 1), random.randint(0, GRID_COUNT - 1))


def spawn_snake():
    """يجد مكانًا فارغًا ويبني ثعبانًا جديدًا بطول STARTING_LENGTH متجهًا لليمين."""
    for _ in range(200):
        hx = random.randint(2, GRID_COUNT - 3)
        hy = random.randint(2, GRID_COUNT - 3)
        cells = [(hx - i, hy) for i in range(STARTING_LENGTH)]
        if all(0 <= cx < GRID_COUNT and 0 <= cy < GRID_COUNT for cx, cy in cells) and not (
            occupied_cells() & set(cells)
        ):
            return [list(c) for c in cells]
    # fallback بسيط إذا فشلت المحاولات (لوحة مزدحمة جدًا)
    return [[3 - i, 3] for i in range(STARTING_LENGTH)]


def ensure_food_count():
    while len(state["foods"]) < FOOD_COUNT:
        state["foods"].append(list(random_free_cell()))


# ---------------------------------------------------------------------------
# حلقة اللعبة — تعمل في الخلفية باستمرار وتحرّك الجميع معًا كل TICK_MS
# ---------------------------------------------------------------------------

def tick():
    now = time.time()

    # 1) إزالة اللاعبين غير النشطين (لم يرسلوا أي طلب منذ مدة)
    for pid in list(state["players"].keys()):
        p = state["players"][pid]
        if now - p["last_seen"] > INACTIVE_TIMEOUT_SEC:
            if p["alive"] and p["score"] > 0:
                update_leaderboard(p["username"], p["score"])
            del state["players"][pid]

    players = state["players"]
    if not players:
        ensure_food_count()
        return

    # 2) تحديث الاتجاه الحالي من آخر اتجاه طلبه كل لاعب
    for p in players.values():
        if p["alive"]:
            p["direction"] = p["next_direction"]

    # 3) احتساب الرأس الجديد المقترح لكل لاعب حي
    proposals = {}
    for pid, p in players.items():
        if not p["alive"] or not p["snake"]:
            continue
        dx, dy = p["direction"]
        hx, hy = p["snake"][0]
        proposals[pid] = (hx + dx, hy + dy)

    if not proposals:
        ensure_food_count()
        return

    # عدد المرات التي يُقترح فيها كل خلية كرأس جديد (لاكتشاف التصادم رأسًا برأس)
    head_counts = {}
    for nh in proposals.values():
        head_counts[nh] = head_counts.get(nh, 0) + 1

    occupied = occupied_cells()
    foods_set = set(tuple(f) for f in state["foods"])

    dead_this_tick = set()
    for pid, nh in proposals.items():
        x, y = nh
        if not (0 <= x < GRID_COUNT and 0 <= y < GRID_COUNT):
            dead_this_tick.add(pid)
            continue
        if head_counts[nh] > 1:
            dead_this_tick.add(pid)
            continue
        if nh in occupied and nh not in foods_set:
            own_tail = tuple(players[pid]["snake"][-1])
            if not (nh == own_tail and len(players[pid]["snake"]) > 1):
                dead_this_tick.add(pid)

    # 4) تحريك اللاعبين الأحياء (غير الذين ماتوا هذه الخطوة)
    eaten_cells = set()
    for pid, nh in proposals.items():
        if pid in dead_this_tick:
            continue
        p = players[pid]
        p["snake"].insert(0, [nh[0], nh[1]])
        if nh in foods_set and nh not in eaten_cells:
            p["score"] += 10
            eaten_cells.add(nh)
        else:
            p["snake"].pop()

    if eaten_cells:
        state["foods"] = [f for f in state["foods"] if tuple(f) not in eaten_cells]

    # 5) تثبيت حالات الموت (حفظ أفضل نتيجة، إفراغ اللوحة من جسم الثعبان الميت)
    for pid in dead_this_tick:
        p = players.get(pid)
        if not p:
            continue
        p["alive"] = False
        if p["score"] > 0:
            update_leaderboard(p["username"], p["score"])
        p["snake"] = []

    ensure_food_count()


def game_loop():
    while True:
        time.sleep(TICK_MS / 1000.0)
        with lock:
            try:
                tick()
            except Exception:
                # لا نريد إيقاف حلقة اللعبة أبدًا بسبب خطأ عابر في جولة واحدة
                pass


_loop_started = False
_loop_start_lock = threading.Lock()


def ensure_loop_started():
    global _loop_started
    with _loop_start_lock:
        if not _loop_started:
            threading.Thread(target=game_loop, daemon=True).start()
            _loop_started = True


ensure_loop_started()


# ---------------------------------------------------------------------------
# CORS — يسمح لصفحات الويب (مثل تطبيق Streamlit) من أي نطاق بالاتصال بالخادم
# ---------------------------------------------------------------------------

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.route("/join", methods=["OPTIONS"])
@app.route("/direction", methods=["OPTIONS"])
@app.route("/respawn", methods=["OPTIONS"])
@app.route("/leave", methods=["OPTIONS"])
def cors_preflight():
    return ("", 204)


# ---------------------------------------------------------------------------
# نقاط الاتصال (API)
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "message": "خادم Snake الجماعي المتزامن يعمل بنجاح"})


@app.route("/join", methods=["POST"])
def join():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()[:16]
    if not username:
        return jsonify({"error": "اسم مستخدم غير صالح"}), 400

    with lock:
        player_id = uuid.uuid4().hex
        color = PLAYER_COLORS[len(state["players"]) % len(PLAYER_COLORS)]
        snake = spawn_snake()
        state["players"][player_id] = {
            "username": username,
            "color": color,
            "snake": snake,
            "direction": [1, 0],
            "next_direction": [1, 0],
            "alive": True,
            "score": 0,
            "last_seen": time.time(),
        }
        ensure_food_count()

    return jsonify({
        "player_id": player_id,
        "color": color,
        "grid_count": GRID_COUNT,
        "tick_ms": TICK_MS,
    })


@app.route("/direction", methods=["POST"])
def direction():
    payload = request.get_json(silent=True) or {}
    player_id = payload.get("player_id")
    dx, dy = payload.get("dx"), payload.get("dy")

    if dx not in (-1, 0, 1) or dy not in (-1, 0, 1) or abs(dx) == abs(dy):
        return jsonify({"error": "اتجاه غير صالح"}), 400

    with lock:
        p = state["players"].get(player_id)
        if not p:
            return jsonify({"error": "لاعب غير معروف"}), 404
        p["last_seen"] = time.time()
        if not p["alive"]:
            return jsonify({"ok": True})
        cur_dx, cur_dy = p["direction"]
        # امنع الرجوع المباشر للخلف (اصطدام فوري بالنفس)
        if not (cur_dx == -dx and cur_dy == -dy and len(p["snake"]) > 1):
            p["next_direction"] = [dx, dy]

    return jsonify({"ok": True})


@app.route("/respawn", methods=["POST"])
def respawn():
    payload = request.get_json(silent=True) or {}
    player_id = payload.get("player_id")

    with lock:
        p = state["players"].get(player_id)
        if not p:
            return jsonify({"error": "لاعب غير معروف"}), 404
        p["snake"] = spawn_snake()
        p["direction"] = [1, 0]
        p["next_direction"] = [1, 0]
        p["alive"] = True
        p["score"] = 0
        p["last_seen"] = time.time()
        ensure_food_count()

    return jsonify({"ok": True})


@app.route("/leave", methods=["POST"])
def leave():
    payload = request.get_json(silent=True) or {}
    player_id = payload.get("player_id")
    with lock:
        p = state["players"].pop(player_id, None)
        if p and p["alive"] and p["score"] > 0:
            update_leaderboard(p["username"], p["score"])
    return jsonify({"ok": True})


@app.route("/state", methods=["GET"])
def get_state():
    player_id = request.args.get("player_id")
    with lock:
        if player_id and player_id in state["players"]:
            state["players"][player_id]["last_seen"] = time.time()
        players_out = [
            {
                "id": pid,
                "username": p["username"],
                "color": p["color"],
                "snake": p["snake"],
                "alive": p["alive"],
                "score": p["score"],
            }
            for pid, p in state["players"].items()
        ]
        foods_out = [list(f) for f in state["foods"]]

    return jsonify({
        "players": players_out,
        "foods": foods_out,
        "grid_count": GRID_COUNT,
        "tick_ms": TICK_MS,
    })


@app.route("/leaderboard", methods=["GET"])
def get_leaderboard():
    entries = load_leaderboard()
    entries.sort(key=lambda e: e.get("score", 0), reverse=True)
    return jsonify(entries[:MAX_RETURNED_ENTRIES])


if __name__ == "__main__":
    print("=" * 50)
    print("خادم Snake الجماعي المتزامن يعمل الآن")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
