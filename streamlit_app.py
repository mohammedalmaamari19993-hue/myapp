"""
Snake — لعب جماعي متزامن بغرف خاصة (ملف واحد فقط، بدون server.py)
=====================================================
هذا ملف واحد يشمل كل شيء: منطق الخادم (الذي يحرّك كل الثعابين معًا بتزامن
حقيقي) يعمل الآن في خيط خلفي داخل نفس عملية Streamlit. لا حاجة لتشغيل
server.py في نافذة منفصلة، ولا لأمرين مختلفين. الأمر الوحيد المطلوب:

    streamlit run streamlit_app.py

نظام "رمز الغرفة" (الرقم السرّي):
    عند الدخول يكتب كل لاعب اسمه + رمز غرفة (أي كلمة أو أرقام يتفق عليها
    مع أصدقائه، مثل: 4821 أو "فريقنا"). كل من يدخل بنفس الرمز يشارك نفس
    اللوحة الحية، وأي شخص آخر يستخدم نفس رابط التطبيق برمز مختلف يكون في
    لعبة منفصلة تمامًا ولا يرى لاعبيكم إطلاقًا — حتى لو كانت اللعبة تعمل
    على نفس الخادم في نفس اللحظة.

ملاحظة عن الاستضافة على الإنترنت:
    هذا الإعداد يعمل بدون أي خطوات إضافية عندما يشغّله الجميع محليًا أو من
    نفس الشبكة. إذا نشرت التطبيق على خدمة سحابية عامة، تأكد أن منصتك تسمح
    بفتح منفذ إضافي (SNAKE_SERVER_PORT) يصل إليه متصفح كل لاعب مباشرة —
    بعض المنصات (مثل Streamlit Community Cloud) تفتح فقط منفذ Streamlit
    العام ولا تُوصِّل أي منفذ آخر من الخارج.
"""

import json
import os
import random
import threading
import time
import uuid

import requests
import streamlit as st
import streamlit.components.v1 as components
from flask import Flask, jsonify, request

st.set_page_config(page_title="🐍 Snake Online — غرف خاصة", page_icon="🐍", layout="wide")

# ---------------------------------------------------------------------------
# إعدادات اللعبة
# ---------------------------------------------------------------------------
GRID_COUNT = 26
TICK_MS = 130
FOOD_COUNT = 6
INACTIVE_TIMEOUT_SEC = 20
STARTING_LENGTH = 3
EMPTY_ROOM_TIMEOUT_SEC = 300  # يُحذف الغرفة من الذاكرة بعد هذه المدة بدون أي لاعبين

PLAYER_COLORS = [
    "#4ade80", "#60a5fa", "#f472b6", "#fbbf24",
    "#c084fc", "#fb923c", "#2dd4bf", "#f87171",
]

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leaderboard_server.json")
MAX_STORED_ENTRIES = 200
MAX_RETURNED_ENTRIES = 20

SERVER_PORT = int(os.environ.get("SNAKE_SERVER_PORT", "5000"))
SERVER_URL = os.environ.get("SNAKE_SERVER_URL", f"http://127.0.0.1:{SERVER_PORT}")


# ---------------------------------------------------------------------------
# لوحة الصدارة الدائمة (تُحفظ في ملف، عامة لكل الغرف)
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
# محرّك اللعبة — غرف متعددة، كل غرفة معزولة تمامًا عن البقية
# ---------------------------------------------------------------------------
@st.cache_resource
def get_engine():
    """يُنشأ مرة واحدة فقط طوال عمر عملية Streamlit (Singleton حقيقي)، بغض
    النظر عن عدد مرات إعادة تشغيل سكربت الصفحة لكل مستخدم يفتحها."""
    return {
        "lock": threading.RLock(),
        "rooms": {},  # room_code -> {"players": {...}, "foods": [...], "last_activity": ts}
        "loop_started": False,
        "flask_started": False,
    }


ENGINE = get_engine()
LOCK = ENGINE["lock"]
ROOMS = ENGINE["rooms"]


def get_room(code):
    room = ROOMS.get(code)
    if room is None:
        room = {"players": {}, "foods": [], "last_activity": time.time()}
        ROOMS[code] = room
    return room


def occupied_cells(room):
    cells = set()
    for p in room["players"].values():
        if p["alive"]:
            cells.update(tuple(seg) for seg in p["snake"])
    cells.update(tuple(f) for f in room["foods"])
    return cells


def random_free_cell(room, exclude=None):
    exclude = exclude or set()
    taken = occupied_cells(room) | exclude
    for _ in range(400):
        c = (random.randint(0, GRID_COUNT - 1), random.randint(0, GRID_COUNT - 1))
        if c not in taken:
            return c
    return (random.randint(0, GRID_COUNT - 1), random.randint(0, GRID_COUNT - 1))


def spawn_snake(room):
    for _ in range(200):
        hx = random.randint(2, GRID_COUNT - 3)
        hy = random.randint(2, GRID_COUNT - 3)
        cells = [(hx - i, hy) for i in range(STARTING_LENGTH)]
        if all(0 <= cx < GRID_COUNT and 0 <= cy < GRID_COUNT for cx, cy in cells) and not (
            occupied_cells(room) & set(cells)
        ):
            return [list(c) for c in cells]
    return [[3 - i, 3] for i in range(STARTING_LENGTH)]


def ensure_food_count(room):
    while len(room["foods"]) < FOOD_COUNT:
        room["foods"].append(list(random_free_cell(room)))


def tick_room(room):
    now = time.time()

    for pid in list(room["players"].keys()):
        p = room["players"][pid]
        if now - p["last_seen"] > INACTIVE_TIMEOUT_SEC:
            if p["alive"] and p["score"] > 0:
                update_leaderboard(p["username"], p["score"])
            del room["players"][pid]

    players = room["players"]
    if not players:
        ensure_food_count(room)
        return

    room["last_activity"] = now

    for p in players.values():
        if p["alive"]:
            p["direction"] = p["next_direction"]

    proposals = {}
    for pid, p in players.items():
        if not p["alive"] or not p["snake"]:
            continue
        dx, dy = p["direction"]
        hx, hy = p["snake"][0]
        proposals[pid] = (hx + dx, hy + dy)

    if not proposals:
        ensure_food_count(room)
        return

    head_counts = {}
    for nh in proposals.values():
        head_counts[nh] = head_counts.get(nh, 0) + 1

    occupied = occupied_cells(room)
    foods_set = set(tuple(f) for f in room["foods"])

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
        room["foods"] = [f for f in room["foods"] if tuple(f) not in eaten_cells]

    for pid in dead_this_tick:
        p = players.get(pid)
        if not p:
            continue
        p["alive"] = False
        if p["score"] > 0:
            update_leaderboard(p["username"], p["score"])
        p["snake"] = []

    ensure_food_count(room)


def game_loop():
    while True:
        time.sleep(TICK_MS / 1000.0)
        with LOCK:
            now = time.time()
            for code in list(ROOMS.keys()):
                room = ROOMS[code]
                try:
                    tick_room(room)
                except Exception:
                    pass
                if not room["players"] and now - room["last_activity"] > EMPTY_ROOM_TIMEOUT_SEC:
                    del ROOMS[code]


if not ENGINE["loop_started"]:
    threading.Thread(target=game_loop, daemon=True).start()
    ENGINE["loop_started"] = True


# ---------------------------------------------------------------------------
# خادم Flask الداخلي — يعمل في خيط خلفي داخل نفس عملية Streamlit
# ---------------------------------------------------------------------------
flask_app = Flask(__name__)


@flask_app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@flask_app.route("/join", methods=["OPTIONS"])
@flask_app.route("/direction", methods=["OPTIONS"])
@flask_app.route("/respawn", methods=["OPTIONS"])
@flask_app.route("/leave", methods=["OPTIONS"])
def cors_preflight():
    return ("", 204)


@flask_app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "rooms": len(ROOMS)})


@flask_app.route("/join", methods=["POST"])
def join():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()[:16]
    room_code = str(payload.get("room", "")).strip()[:24]
    if not username:
        return jsonify({"error": "اسم مستخدم غير صالح"}), 400
    if not room_code:
        return jsonify({"error": "رمز غرفة غير صالح"}), 400

    with LOCK:
        room = get_room(room_code)
        player_id = uuid.uuid4().hex
        color = PLAYER_COLORS[len(room["players"]) % len(PLAYER_COLORS)]
        snake = spawn_snake(room)
        room["players"][player_id] = {
            "username": username,
            "color": color,
            "snake": snake,
            "direction": [1, 0],
            "next_direction": [1, 0],
            "alive": True,
            "score": 0,
            "last_seen": time.time(),
        }
        ensure_food_count(room)

    return jsonify({
        "player_id": player_id,
        "color": color,
        "grid_count": GRID_COUNT,
        "tick_ms": TICK_MS,
    })


@flask_app.route("/direction", methods=["POST"])
def direction():
    payload = request.get_json(silent=True) or {}
    player_id = payload.get("player_id")
    room_code = str(payload.get("room", "")).strip()[:24]
    dx, dy = payload.get("dx"), payload.get("dy")

    if dx not in (-1, 0, 1) or dy not in (-1, 0, 1) or abs(dx) == abs(dy):
        return jsonify({"error": "اتجاه غير صالح"}), 400

    with LOCK:
        room = ROOMS.get(room_code)
        p = room["players"].get(player_id) if room else None
        if not p:
            return jsonify({"error": "لاعب غير معروف"}), 404
        p["last_seen"] = time.time()
        if not p["alive"]:
            return jsonify({"ok": True})
        cur_dx, cur_dy = p["direction"]
        if not (cur_dx == -dx and cur_dy == -dy and len(p["snake"]) > 1):
            p["next_direction"] = [dx, dy]

    return jsonify({"ok": True})


@flask_app.route("/respawn", methods=["POST"])
def respawn():
    payload = request.get_json(silent=True) or {}
    player_id = payload.get("player_id")
    room_code = str(payload.get("room", "")).strip()[:24]

    with LOCK:
        room = ROOMS.get(room_code)
        p = room["players"].get(player_id) if room else None
        if not p:
            return jsonify({"error": "لاعب غير معروف"}), 404
        p["snake"] = spawn_snake(room)
        p["direction"] = [1, 0]
        p["next_direction"] = [1, 0]
        p["alive"] = True
        p["score"] = 0
        p["last_seen"] = time.time()
        ensure_food_count(room)

    return jsonify({"ok": True})


@flask_app.route("/leave", methods=["POST"])
def leave():
    payload = request.get_json(silent=True) or {}
    player_id = payload.get("player_id")
    room_code = str(payload.get("room", "")).strip()[:24]
    with LOCK:
        room = ROOMS.get(room_code)
        if room:
            p = room["players"].pop(player_id, None)
            if p and p["alive"] and p["score"] > 0:
                update_leaderboard(p["username"], p["score"])
    return jsonify({"ok": True})


@flask_app.route("/state", methods=["GET"])
def get_state():
    player_id = request.args.get("player_id")
    room_code = str(request.args.get("room", "")).strip()[:24]
    with LOCK:
        room = ROOMS.get(room_code)
        if not room:
            return jsonify({"players": [], "foods": [], "grid_count": GRID_COUNT, "tick_ms": TICK_MS})
        if player_id and player_id in room["players"]:
            room["players"][player_id]["last_seen"] = time.time()
        players_out = [
            {
                "id": pid,
                "username": p["username"],
                "color": p["color"],
                "snake": p["snake"],
                "alive": p["alive"],
                "score": p["score"],
            }
            for pid, p in room["players"].items()
        ]
        foods_out = [list(f) for f in room["foods"]]

    return jsonify({
        "players": players_out,
        "foods": foods_out,
        "grid_count": GRID_COUNT,
        "tick_ms": TICK_MS,
    })


@flask_app.route("/leaderboard", methods=["GET"])
def get_leaderboard():
    entries = load_leaderboard()
    entries.sort(key=lambda e: e.get("score", 0), reverse=True)
    return jsonify(entries[:MAX_RETURNED_ENTRIES])


def run_flask():
    flask_app.run(host="0.0.0.0", port=SERVER_PORT, debug=False, threaded=True, use_reloader=False)


if not ENGINE["flask_started"]:
    threading.Thread(target=run_flask, daemon=True).start()
    ENGINE["flask_started"] = True
    time.sleep(0.3)  # مهلة صغيرة لضمان جهوزية الخادم الداخلي قبل أول طلب من الواجهة


# ---------------------------------------------------------------------------
# واجهة Streamlit
# ---------------------------------------------------------------------------
st.title("🐍 Snake — لعب جماعي متزامن بغرف خاصة")
st.caption(
    "اتفق مع أصدقائك على رمز غرفة سرّي (أي كلمة أو أرقام)، وليكتب كل واحد "
    "منكم نفس الرمز عند الدخول — من يدخل بنفس الرمز يشاركك نفس اللوحة، ومن "
    "يستخدم رمزًا مختلفًا يكون في لعبة منفصلة تمامًا حتى لو فتح نفس الرابط."
)

with st.sidebar:
    st.markdown("### 🏆 أفضل النتائج على الإطلاق")
    if st.button("🔄 تحديث", use_container_width=True):
        st.rerun()
    try:
        lb_resp = requests.get(f"{SERVER_URL}/leaderboard", timeout=4)
        if lb_resp.status_code == 200:
            leaderboard = lb_resp.json()
            if leaderboard:
                st.table(
                    [
                        {"#": i + 1, "اللاعب": e.get("username", "؟"), "أفضل نتيجة": e.get("score", 0)}
                        for i, e in enumerate(leaderboard[:10])
                    ]
                )
            else:
                st.caption("لا توجد نتائج بعد — كن أول من يسجّل نتيجة!")
        else:
            st.caption(f"خطأ من الخادم ({lb_resp.status_code})")
    except requests.exceptions.RequestException:
        st.caption("⚠️ الخادم الداخلي لم يجهز بعد — أعد تحميل الصفحة بعد لحظات.")

# ---------------------------------------------------------------------------
# اللعبة — HTML/JS canvas مضمّن، يتصل بالخادم الداخلي المدمج في هذا الملف
# ---------------------------------------------------------------------------

GAME_HTML = r"""
<!DOCTYPE html>
<html lang="ar">
<head>
<meta charset="utf-8" />
<style>
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: #060a14;
    font-family: 'Tahoma', 'Segoe UI', sans-serif;
    display: flex;
    justify-content: center;
  }
  #wrap { position: relative; width: 750px; }
  canvas { display: block; background: #060a14; border-radius: 10px; outline: none; }
  #startScreen {
    position: absolute; top: 0; left: 0; width: 520px; height: 520px;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    color: #e2e8f0; text-align: center;
    background: rgba(6,10,20,0.97);
    border-radius: 10px 0 0 10px;
  }
  #startScreen h1 { color: #4ade80; margin: 0 0 6px 0; font-size: 28px; }
  #startScreen p { color: #7c8aa5; margin: 0 0 18px 0; font-size: 13px; max-width: 340px; }
  #usernameInput, #roomInput {
    width: 220px; padding: 10px 12px; border-radius: 10px;
    border: 1px solid #22304a; background: #0d1322; color: #e2e8f0;
    font-size: 14px; text-align: center; margin-bottom: 12px;
  }
  #usernameInput:focus, #roomInput:focus { outline: none; border-color: #4ade80; }
  #roomInput { margin-bottom: 16px; letter-spacing: 1px; }
  #startBtn, .overlayBtn {
    cursor: pointer; border: 1px solid #22304a; background: #4ade80; color: #06110a;
    border-radius: 8px; padding: 12px 34px; font-size: 15px; font-weight: bold; font-family: inherit;
  }
  #startHint { color: #f87171; font-size: 12px; margin-top: 10px; height: 14px; }
  #liveCount { color: #7c8aa5; font-size: 12px; margin-top: 14px; }
  #gameOverlay {
    position: absolute; top: 0; left: 0; width: 520px; height: 520px;
    display: none; flex-direction: column; align-items: center; justify-content: center;
    color: #e2e8f0; text-align: center;
    background: rgba(6,10,20,0.9);
    border-radius: 10px 0 0 10px;
  }
  #gameOverlay h2 { font-size: 26px; margin: 0 0 10px 0; }
  #overlayScore { font-size: 30px; color: #fbbf24; margin-bottom: 6px; font-weight: bold; }
  #overlaySub { color: #7c8aa5; font-size: 12px; margin-bottom: 20px; }
  #leaveBtn {
    margin-top: 10px; cursor: pointer; background: transparent; border: 1px solid #22304a;
    color: #7c8aa5; border-radius: 8px; padding: 8px 20px; font-size: 12px; font-family: inherit;
  }
</style>
</head>
<body>
<div id="wrap">
  <canvas id="game" width="750" height="520" tabindex="0"></canvas>

  <div id="startScreen">
    <h1>🐍 Snake</h1>
    <p>لعب جماعي متزامن — من يدخل بنفس رمز الغرفة السرّي يشاركك نفس اللوحة الآن.</p>
    <input id="usernameInput" maxlength="16" placeholder="اكتب اسم المستخدم" />
    <input id="roomInput" maxlength="24" placeholder="رمز الغرفة السرّي (مثال: 4821)" />
    <button id="startBtn">ادخل اللعبة</button>
    <div id="startHint"></div>
    <div id="liveCount"></div>
  </div>

  <div id="gameOverlay">
    <h2 id="overlayTitle">انتهت اللعبة</h2>
    <div id="overlayScore"></div>
    <div id="overlaySub">حاول مرة أخرى — بقية لاعبي غرفتك ما زالوا يلعبون الآن</div>
    <button class="overlayBtn" id="respawnBtn">إعادة الدخول</button>
    <button id="leaveBtn">مغادرة اللعبة</button>
  </div>
</div>

<script>
(function () {
  const SERVER_URL = "__SERVER_URL__";
  const REQUEST_TIMEOUT_MS = 4000;
  const POLL_MS = 90; // أسرع من نبضة الخادم لتقليل التأخير الظاهر

  const BOARD = 520, SIDEBAR_W = 230;
  const COLOR_BG = "#060a14", COLOR_GRID = "#111a2b", COLOR_PANEL = "#131a2b",
        COLOR_BORDER = "#22304a", COLOR_ACCENT = "#4ade80", COLOR_DANGER = "#f87171",
        COLOR_GOLD = "#fbbf24", COLOR_TEXT = "#e2e8f0", COLOR_TEXT_DIM = "#7c8aa5";

  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d");
  const startScreen = document.getElementById("startScreen");
  const gameOverlay = document.getElementById("gameOverlay");
  const usernameInput = document.getElementById("usernameInput");
  const roomInput = document.getElementById("roomInput");
  const startHint = document.getElementById("startHint");
  const liveCount = document.getElementById("liveCount");

  let phase = "start"; // start | playing
  let playerId = null;
  let roomCode = null;
  let myColor = COLOR_ACCENT;
  let gridCount = 26;
  let cellSize = BOARD / gridCount;
  let latestState = { players: [], foods: [] };
  let connectionOk = true;
  let lastScoreShown = 0;

  function withTimeout(promise, ms) {
    return Promise.race([
      promise,
      new Promise((_, reject) => setTimeout(() => reject(new Error("timeout")), ms)),
    ]);
  }

  function refreshLobbyCount() {
    if (phase !== "start") return;
    const room = roomInput.value.trim();
    if (!room) {
      liveCount.textContent = "اكتب رمز الغرفة لرؤية عدد اللاعبين المتصلين بها الآن";
      return;
    }
    withTimeout(fetch(SERVER_URL + "/state?room=" + encodeURIComponent(room)), REQUEST_TIMEOUT_MS)
      .then((r) => r.json())
      .then((data) => { liveCount.textContent = "🟢 لاعبون في هذه الغرفة الآن: " + (data.players ? data.players.length : 0); })
      .catch(() => { liveCount.textContent = "⚠️ تعذر الاتصال بخادم اللعبة"; });
  }
  refreshLobbyCount();
  setInterval(refreshLobbyCount, 2000);
  roomInput.addEventListener("input", refreshLobbyCount);

  function join(username, room) {
    withTimeout(
      fetch(SERVER_URL + "/join", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, room }),
      }),
      REQUEST_TIMEOUT_MS
    )
      .then((r) => { if (!r.ok) throw new Error("bad status"); return r.json(); })
      .then((data) => {
        playerId = data.player_id;
        roomCode = room;
        myColor = data.color;
        gridCount = data.grid_count;
        cellSize = BOARD / gridCount;
        phase = "playing";
        startScreen.style.display = "none";
        gameOverlay.style.display = "none";
        canvas.focus();
      })
      .catch(() => { startHint.textContent = "⚠️ تعذر الاتصال بخادم اللعبة. أعد تحميل الصفحة وحاول مجددًا."; });
  }

  function sendDirection(dx, dy) {
    if (!playerId || !roomCode) return;
    fetch(SERVER_URL + "/direction", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ player_id: playerId, room: roomCode, dx, dy }),
    }).catch(() => {});
  }

  function respawn() {
    if (!playerId || !roomCode) return;
    withTimeout(
      fetch(SERVER_URL + "/respawn", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ player_id: playerId, room: roomCode }),
      }),
      REQUEST_TIMEOUT_MS
    )
      .then(() => { gameOverlay.style.display = "none"; canvas.focus(); })
      .catch(() => {});
  }

  function leaveGame() {
    if (playerId && roomCode) {
      const payload = JSON.stringify({ player_id: playerId, room: roomCode });
      if (navigator.sendBeacon) {
        navigator.sendBeacon(SERVER_URL + "/leave", new Blob([payload], { type: "application/json" }));
      } else {
        fetch(SERVER_URL + "/leave", { method: "POST", headers: { "Content-Type": "application/json" }, body: payload }).catch(() => {});
      }
    }
    playerId = null;
    roomCode = null;
    phase = "start";
    gameOverlay.style.display = "none";
    startScreen.style.display = "flex";
    usernameInput.value = "";
    refreshLobbyCount();
  }

  window.addEventListener("beforeunload", () => {
    if (playerId && roomCode) {
      const payload = JSON.stringify({ player_id: playerId, room: roomCode });
      if (navigator.sendBeacon) {
        navigator.sendBeacon(SERVER_URL + "/leave", new Blob([payload], { type: "application/json" }));
      }
    }
  });

  function pollState() {
    if (phase !== "playing" || !playerId || !roomCode) return;
    withTimeout(
      fetch(SERVER_URL + "/state?player_id=" + playerId + "&room=" + encodeURIComponent(roomCode)),
      REQUEST_TIMEOUT_MS
    )
      .then((r) => { if (!r.ok) throw new Error("bad status"); return r.json(); })
      .then((data) => {
        latestState = data;
        gridCount = data.grid_count || gridCount;
        cellSize = BOARD / gridCount;
        connectionOk = true;

        const me = data.players.find((p) => p.id === playerId);
        if (me) {
          lastScoreShown = me.score;
          if (!me.alive && gameOverlay.style.display !== "flex") {
            document.getElementById("overlayScore").textContent = String(me.score);
            gameOverlay.style.display = "flex";
          }
        }
      })
      .catch(() => { connectionOk = false; });
  }
  setInterval(pollState, POLL_MS);

  function roundRect(x, y, w, h, r, color) {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
    ctx.fill();
  }

  function drawBoard() {
    ctx.fillStyle = COLOR_BG;
    ctx.fillRect(0, 0, BOARD, BOARD);
    ctx.strokeStyle = COLOR_GRID;
    ctx.lineWidth = 1;
    for (let i = 0; i <= gridCount; i++) {
      ctx.beginPath(); ctx.moveTo(i * cellSize, 0); ctx.lineTo(i * cellSize, BOARD); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, i * cellSize); ctx.lineTo(BOARD, i * cellSize); ctx.stroke();
    }

    ctx.fillStyle = COLOR_DANGER;
    (latestState.foods || []).forEach((f) => {
      ctx.beginPath();
      ctx.arc(f[0] * cellSize + cellSize / 2, f[1] * cellSize + cellSize / 2, cellSize / 2.6, 0, 7);
      ctx.fill();
    });

    (latestState.players || []).forEach((p) => {
      if (!p.alive || !p.snake || p.snake.length === 0) return;
      const isMe = p.id === playerId;
      p.snake.forEach((seg, i) => {
        const color = i === 0 ? p.color : p.color;
        const alpha = i === 0 ? 1 : Math.max(0.45, 1 - i * 0.03);
        ctx.globalAlpha = alpha;
        roundRect(seg[0] * cellSize + 1, seg[1] * cellSize + 1, cellSize - 2, cellSize - 2, 5, color);
        ctx.globalAlpha = 1;
      });
      if (isMe) {
        const head = p.snake[0];
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 2;
        ctx.strokeRect(head[0] * cellSize, head[1] * cellSize, cellSize, cellSize);
      }
      const head = p.snake[0];
      ctx.fillStyle = COLOR_TEXT;
      ctx.font = "10px Tahoma";
      ctx.textAlign = "center";
      ctx.fillText(p.username, head[0] * cellSize + cellSize / 2, head[1] * cellSize - 4);
      ctx.textAlign = "left";
    });
  }

  function drawSidebar() {
    const sx = BOARD, pad = 16;
    ctx.fillStyle = COLOR_PANEL; ctx.fillRect(sx, 0, SIDEBAR_W, BOARD);
    ctx.strokeStyle = COLOR_BORDER; ctx.beginPath(); ctx.moveTo(sx, 0); ctx.lineTo(sx, BOARD); ctx.stroke();

    ctx.fillStyle = COLOR_ACCENT; ctx.font = "bold 22px Tahoma"; ctx.textAlign = "left"; ctx.textBaseline = "top";
    ctx.fillText("🐍 Snake", sx + pad, 18);

    const dotColor = connectionOk ? COLOR_ACCENT : COLOR_DANGER;
    ctx.fillStyle = dotColor; ctx.beginPath(); ctx.arc(sx + SIDEBAR_W - 20, 26, 4, 0, 7); ctx.fill();
    ctx.font = "10px Tahoma"; ctx.textAlign = "right";
    ctx.fillStyle = COLOR_TEXT_DIM;
    ctx.fillText(connectionOk ? "متزامن الآن" : "انقطع الاتصال", sx + SIDEBAR_W - 30, 22);
    ctx.textAlign = "left";

    let y = 56;
    ctx.fillStyle = COLOR_GOLD; ctx.font = "bold 12px Tahoma";
    ctx.fillText("👥 لاعبو هذه الغرفة الآن", sx + pad, y);
    y += 26;

    const players = (latestState.players || []).slice().sort((a, b) => b.score - a.score);
    if (players.length === 0) {
      ctx.fillStyle = COLOR_TEXT_DIM; ctx.font = "10px Tahoma";
      ctx.fillText("لا يوجد لاعبون آخرون في غرفتك حاليًا", sx + pad, y);
    } else {
      players.slice(0, 10).forEach((p) => {
        const isMe = p.id === playerId;
        roundRect(sx + pad, y, SIDEBAR_W - pad * 2, 30, 6, isMe ? "#0d2d1e" : "#0d1322");
        ctx.fillStyle = p.color; ctx.beginPath(); ctx.arc(sx + pad + 10, y + 15, 5, 0, 7); ctx.fill();
        let name = p.username;
        if (name.length > 12) name = name.slice(0, 11) + "…";
        ctx.fillStyle = p.alive ? COLOR_TEXT : COLOR_TEXT_DIM; ctx.font = "11px Tahoma";
        ctx.fillText(name + (p.alive ? "" : " (خرج)"), sx + pad + 22, y + 10);
        ctx.fillStyle = COLOR_ACCENT; ctx.textAlign = "right"; ctx.font = "11px Tahoma";
        ctx.fillText(String(p.score), sx + SIDEBAR_W - pad - 8, y + 10);
        ctx.textAlign = "left";
        y += 34;
      });
    }

    y = BOARD - 60;
    ctx.fillStyle = COLOR_TEXT_DIM; ctx.font = "10px Tahoma";
    ctx.fillText("الأسهم: تحريك", sx + pad, y);
    ctx.fillText("نتيجتك الحالية: " + lastScoreShown, sx + pad, y + 18);
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (phase !== "playing") return;
    drawBoard();
    drawSidebar();
  }

  function loop() {
    draw();
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);

  document.getElementById("startBtn").addEventListener("click", () => {
    const name = usernameInput.value.trim();
    const room = roomInput.value.trim();
    if (!name) { startHint.textContent = "(الرجاء إدخال اسم مستخدم للمتابعة)"; return; }
    if (!room) { startHint.textContent = "(الرجاء إدخال رمز الغرفة السرّي)"; return; }
    startHint.textContent = "جارٍ الدخول...";
    join(name, room);
  });
  usernameInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") document.getElementById("startBtn").click();
  });
  roomInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") document.getElementById("startBtn").click();
  });

  document.getElementById("respawnBtn").addEventListener("click", respawn);
  document.getElementById("leaveBtn").addEventListener("click", leaveGame);

  document.addEventListener("keydown", (e) => {
    if (phase !== "playing") return;
    switch (e.key) {
      case "ArrowUp": sendDirection(0, -1); e.preventDefault(); break;
      case "ArrowDown": sendDirection(0, 1); e.preventDefault(); break;
      case "ArrowLeft": sendDirection(-1, 0); e.preventDefault(); break;
      case "ArrowRight": sendDirection(1, 0); e.preventDefault(); break;
      case "Escape": leaveGame(); break;
    }
  });

  canvas.addEventListener("click", () => canvas.focus());
})();
</script>
</body>
</html>
"""


def render_game(server_url: str):
    html = GAME_HTML.replace("__SERVER_URL__", server_url.replace('"', ""))
    components.html(html, height=545, scrolling=False)


render_game(SERVER_URL)

st.caption(
    "💡 من يعرف رمز الغرفة نفسه يدخل نفس اللوحة الحية معك مباشرة، بينما أي "
    "شخص آخر يفتح هذا التطبيق برمز مختلف يلعب في لوحة منفصلة تمامًا ولا "
    "يراك إطلاقًا."
)
