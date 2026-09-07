"""
Snake Game Online — نسخة Streamlit
=====================================================
نسخة من لعبة الثعبان تعمل داخل المتصفح عبر Streamlit، مع:
- شاشة إدخال اسم مستخدم واختيار مستوى الصعوبة (داخل اللعبة نفسها)
- لوحة صدارة أونلاين حقيقية عبر خادم Flask (server.py) يشترك فيها كل من
  يدخل نفس عنوان الخادم — سواء على نفس الشبكة المحلية أو عبر الإنترنت
- شريط جانبي يعرض عنوان جهازك على الشبكة المحلية (لمشاركته مع اللاعبين
  الآخرين) وحقل لإدخال عنوان الخادم الذي تريد الاتصال به

المتطلبات:
    pip install streamlit requests flask

التشغيل:
    1. شغّل الخادم أولًا، مرة واحدة، على أي جهاز (يُفضّل جهاز المضيف):
           python server.py
    2. شغّل تطبيق اللعبة:
           streamlit run streamlit_app.py
    3. في الشريط الجانبي، تأكد أن "عنوان خادم لوحة الصدارة" يشير إلى
       عنوان الجهاز الذي يشغّل server.py (مثال: http://192.168.1.10:5000).
       - إذا كنت أنت من يشغّل الخادم، سيقترحه التطبيق تلقائيًا.
       - إذا كنت لاعبًا آخر، اطلب هذا العنوان من صاحب الخادم واكتبه يدويًا.
    4. أرسل رابط تطبيق Streamlit (أو نفس الشبكة) واسم عنوان الخادم لأصدقائك
       ليلعبوا معك ويشاركوا نفس لوحة الصدارة.

ملاحظة: إذا تعذر الوصول إلى الخادم، تستمر اللعبة بالعمل محليًا فقط مع
رسالة واضحة تفيد بتعذّر الاتصال، دون أن تتوقف أو تتجمد.
"""

import socket

import requests
import streamlit as st
import streamlit.components.v1 as components

# ---------------------------------------------------------------------------
# إعداد الصفحة
# ---------------------------------------------------------------------------

st.set_page_config(page_title="🐍 Snake Online", page_icon="🐍", layout="wide")

REQUEST_TIMEOUT = 4


def get_local_ip() -> str:
    """يحاول تخمين عنوان IP الخاص بهذا الجهاز على الشبكة المحلية."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        return "127.0.0.1"


# ---------------------------------------------------------------------------
# الشريط الجانبي — إعداد الاتصال بخادم لوحة الصدارة المشتركة
# ---------------------------------------------------------------------------

local_ip = get_local_ip()

with st.sidebar:
    st.markdown("### 🌐 الاتصال بلوحة الصدارة المشتركة")
    st.caption(
        "عنوان جهازك على الشبكة المحلية (شاركه مع بقية اللاعبين إذا كنت "
        "أنت من يشغّل server.py):"
    )
    st.code(f"{local_ip}:5000", language="text")

    if "server_url" not in st.session_state:
        st.session_state.server_url = f"http://{local_ip}:5000"

    server_url = st.text_input(
        "عنوان خادم لوحة الصدارة (Server IP)",
        value=st.session_state.server_url,
        help="مثال: http://192.168.1.10:5000 — اطلب هذا العنوان من صاحب الخادم إن لم تكن أنت من يشغّله.",
    ).strip().rstrip("/")
    st.session_state.server_url = server_url

    check_col, refresh_col = st.columns(2)
    connection_ok = None
    with check_col:
        if st.button("🔄 فحص الاتصال", use_container_width=True):
            try:
                r = requests.get(f"{server_url}/", timeout=REQUEST_TIMEOUT)
                connection_ok = r.status_code == 200
            except requests.exceptions.RequestException:
                connection_ok = False

    if connection_ok is True:
        st.success("متصل بالخادم ✅")
    elif connection_ok is False:
        st.error("تعذر الاتصال بالخادم ⚠️ — تأكد من تشغيل server.py ومن صحة العنوان")

    st.divider()
    st.markdown("### 🏆 لوحة الصدارة")
    with refresh_col:
        pass
    if st.button("تحديث لوحة الصدارة", use_container_width=True):
        st.session_state["_lb_refresh"] = True

    try:
        lb_resp = requests.get(f"{server_url}/leaderboard", timeout=REQUEST_TIMEOUT)
        if lb_resp.status_code == 200:
            leaderboard = lb_resp.json()
            if leaderboard:
                st.table(
                    [
                        {"#": i + 1, "اللاعب": e.get("username", "؟"), "النتيجة": e.get("score", 0)}
                        for i, e in enumerate(leaderboard[:10])
                    ]
                )
            else:
                st.caption("لا توجد نتائج بعد — كن أول من يسجّل نتيجة!")
        else:
            st.caption(f"خطأ من الخادم ({lb_resp.status_code})")
    except requests.exceptions.RequestException:
        st.caption("تعذر جلب لوحة الصدارة من الخادم.")

    st.divider()
    st.markdown(
        "**طريقة اللعب الجماعي:**\n"
        "1. شخص واحد يشغّل `python server.py`.\n"
        "2. الجميع يفتح هذا التطبيق ويكتب نفس عنوان الخادم أعلاه.\n"
        "3. كل من يسجّل نتيجة تظهر تلقائيًا للجميع في لوحة الصدارة."
    )

st.title("🐍 Snake — لعبة الثعبان أونلاين")
st.caption("استخدم أسهم الكيبورد للتحريك، مسافة للإيقاف المؤقت. اضغط داخل مربع اللعبة أولًا حتى تعمل الأسهم.")

# ---------------------------------------------------------------------------
# اللعبة — HTML/JS canvas مضمّن، يتصل مباشرة بخادم لوحة الصدارة عبر fetch()
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
  #wrap {
    position: relative;
    width: 700px;
  }
  canvas {
    display: block;
    background: #060a14;
    border-radius: 10px;
    outline: none;
  }
  #startScreen {
    position: absolute;
    top: 0; left: 0;
    width: 440px; height: 440px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: #e2e8f0;
    text-align: center;
    background: rgba(6,10,20,0.96);
    border-radius: 10px 0 0 10px;
  }
  #startScreen h1 { color: #4ade80; margin: 0 0 6px 0; font-size: 28px; }
  #startScreen p { color: #7c8aa5; margin: 0 0 18px 0; font-size: 13px; }
  #usernameInput {
    width: 220px;
    padding: 10px 12px;
    border-radius: 10px;
    border: 1px solid #22304a;
    background: #0d1322;
    color: #e2e8f0;
    font-size: 14px;
    text-align: center;
    margin-bottom: 16px;
  }
  #usernameInput:focus { outline: none; border-color: #4ade80; }
  .diffRow { display: flex; gap: 8px; margin-bottom: 18px; }
  .diffBtn, #startBtn, .overlayBtn {
    cursor: pointer;
    border: 1px solid #22304a;
    background: #0d1322;
    color: #7c8aa5;
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 13px;
    font-weight: bold;
    font-family: inherit;
  }
  .diffBtn.active { background: #4ade80; color: #06110a; border-color: #4ade80; }
  #startBtn, .overlayBtn {
    background: #4ade80; color: #06110a; padding: 12px 34px; font-size: 15px;
  }
  #startHint { color: #f87171; font-size: 12px; margin-top: 10px; height: 14px; }
  #gameOverlay {
    position: absolute;
    top: 0; left: 0;
    width: 440px; height: 440px;
    display: none;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: #e2e8f0;
    text-align: center;
    background: rgba(6,10,20,0.9);
    border-radius: 10px 0 0 10px;
  }
  #gameOverlay h2 { font-size: 26px; margin: 0 0 10px 0; }
  #overlayScore { font-size: 30px; color: #fbbf24; margin-bottom: 6px; font-weight: bold; }
  #overlaySub { color: #7c8aa5; font-size: 12px; margin-bottom: 6px; }
  #overlaySave { font-size: 12px; margin-bottom: 16px; }
</style>
</head>
<body>
<div id="wrap">
  <canvas id="game" width="700" height="440" tabindex="0"></canvas>

  <div id="startScreen">
    <h1>🐍 Snake</h1>
    <p>أدخل اسم المستخدم لبدء اللعب</p>
    <input id="usernameInput" maxlength="16" placeholder="اكتب اسم المستخدم" />
    <div class="diffRow">
      <button class="diffBtn" data-diff="سهل">سهل</button>
      <button class="diffBtn active" data-diff="متوسط">متوسط</button>
      <button class="diffBtn" data-diff="صعب">صعب</button>
    </div>
    <button id="startBtn">ابدأ اللعبة</button>
    <div id="startHint"></div>
  </div>

  <div id="gameOverlay">
    <h2 id="overlayTitle"></h2>
    <div id="overlayScore"></div>
    <div id="overlaySub"></div>
    <div id="overlaySave"></div>
    <button class="overlayBtn" id="overlayBtn">إعادة اللعب</button>
  </div>
</div>

<script>
(function () {
  const SERVER_URL = "__SERVER_URL__";
  const REQUEST_TIMEOUT_MS = 4000;

  const GRID = 20, COUNT = 22, BOARD = GRID * COUNT, SIDEBAR_W = 260;
  const DIFFS = { "سهل": 150, "متوسط": 105, "صعب": 70 };

  const COLOR_BG = "#060a14", COLOR_GRID = "#111a2b", COLOR_PANEL = "#131a2b",
        COLOR_BORDER = "#22304a", COLOR_ACCENT = "#4ade80", COLOR_DANGER = "#f87171",
        COLOR_GOLD = "#fbbf24", COLOR_TEXT = "#e2e8f0", COLOR_TEXT_DIM = "#7c8aa5";

  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d");

  let state = "start"; // start | playing | paused | game_over
  let username = "";
  let difficulty = "متوسط";
  let baseSpeedMs = DIFFS[difficulty];
  let leaderboard = [];
  let myBest = 0;
  let connectionStatus = "connecting"; // connecting | online | offline
  let saveStatus = "";

  let snake, direction, nextDirection, score, speedLevel, currentIntervalMs,
      timeSinceTick, particles, foodPulse, food, newRecord, shake;

  function withTimeout(promise, ms) {
    return Promise.race([
      promise,
      new Promise((_, reject) => setTimeout(() => reject(new Error("timeout")), ms)),
    ]);
  }

  function fetchLeaderboard() {
    if (!SERVER_URL) { connectionStatus = "offline"; return; }
    withTimeout(fetch(SERVER_URL + "/leaderboard"), REQUEST_TIMEOUT_MS)
      .then((r) => { if (!r.ok) throw new Error("bad status"); return r.json(); })
      .then((data) => { leaderboard = data || []; connectionStatus = "online"; })
      .catch(() => { connectionStatus = "offline"; });
  }

  function submitScore(name, s) {
    saveStatus = "جارٍ حفظ نتيجتك في لوحة الصدارة...";
    if (!SERVER_URL) { connectionStatus = "offline"; saveStatus = "⚠️ لم يتم تحديد عنوان الخادم"; return; }
    withTimeout(
      fetch(SERVER_URL + "/score", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: name, score: s }),
      }),
      REQUEST_TIMEOUT_MS
    )
      .then((r) => { if (!r.ok) throw new Error("bad status"); return r.json(); })
      .then((data) => {
        leaderboard = data.leaderboard || [];
        connectionStatus = "online";
        newRecord = !!data.is_new_best;
        saveStatus = newRecord ? "✅ تم حفظ نتيجتك في لوحة الصدارة" : "نتيجتك السابقة أعلى — لم يتم التحديث";
        renderGameOverOverlay();
      })
      .catch(() => {
        connectionStatus = "offline";
        saveStatus = "⚠️ تعذر حفظ النتيجة";
        renderGameOverOverlay();
      });
  }

  fetchLeaderboard();
  setInterval(fetchLeaderboard, 8000);

  function resetRound() {
    snake = [[10, 10], [9, 10], [8, 10]];
    direction = [1, 0];
    nextDirection = [1, 0];
    score = 0;
    speedLevel = 1;
    currentIntervalMs = baseSpeedMs;
    timeSinceTick = 0;
    particles = [];
    foodPulse = 0;
    shake = 0;
    newRecord = false;
    saveStatus = "";
    placeFood();
  }

  function placeFood() {
    while (true) {
      const fx = Math.floor(Math.random() * COUNT);
      const fy = Math.floor(Math.random() * COUNT);
      if (!snake.some((c) => c[0] === fx && c[1] === fy)) { food = [fx, fy]; return; }
    }
  }

  function spawnParticles(gx, gy, color) {
    const cx = gx * GRID + GRID / 2, cy = gy * GRID + GRID / 2;
    for (let i = 0; i < 14; i++) {
      const angle = (2 * Math.PI * i) / 14;
      const speed = 1.5 + Math.random() * 2.0;
      particles.push({ x: cx, y: cy, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed, life: 1.0, color });
    }
  }

  function setDirection(dx, dy) {
    if (state !== "playing") return;
    const [cdx, cdy] = direction;
    if (cdx === -dx && cdy === -dy && snake.length > 1) return;
    nextDirection = [dx, dy];
  }

  function step() {
    direction = nextDirection;
    const [dx, dy] = direction;
    if (dx === 0 && dy === 0) return;
    const [hx, hy] = snake[0];
    const nh = [hx + dx, hy + dy];
    if (nh[0] < 0 || nh[0] >= COUNT || nh[1] < 0 || nh[1] >= COUNT) { endGame(); return; }
    if (snake.some((c) => c[0] === nh[0] && c[1] === nh[1])) { endGame(); return; }
    snake.unshift(nh);
    if (nh[0] === food[0] && nh[1] === food[1]) {
      score += 10;
      spawnParticles(food[0], food[1], COLOR_DANGER);
      shake = 4.0;
      if (score % 50 === 0 && currentIntervalMs > 45) {
        currentIntervalMs = Math.max(45, currentIntervalMs - 8);
        speedLevel = Math.round((baseSpeedMs - currentIntervalMs) / 8) + 1;
      }
      placeFood();
    } else {
      snake.pop();
    }
  }

  function endGame() {
    state = "game_over";
    newRecord = false;
    if (score > myBest) myBest = score;
    document.getElementById("gameOverlay").style.display = "flex";
    renderGameOverOverlay();
    submitScore(username, score);
  }

  function renderGameOverOverlay() {
    document.getElementById("overlayTitle").textContent = newRecord ? "🏆 رقم قياسي جديد!" : "انتهت اللعبة";
    document.getElementById("overlayTitle").style.color = newRecord ? COLOR_ACCENT : COLOR_DANGER;
    document.getElementById("overlayScore").textContent = String(score);
    document.getElementById("overlaySub").textContent = newRecord
      ? "أحسنت! تم حفظ نتيجتك في لوحة الصدارة" : "حاول مرة أخرى لتحسين نتيجتك";
    const saveEl = document.getElementById("overlaySave");
    saveEl.textContent = saveStatus;
    saveEl.style.color = saveStatus.indexOf("⚠️") >= 0 ? COLOR_DANGER : COLOR_ACCENT;
  }

  function update(dt) {
    if (state !== "playing") return;
    timeSinceTick += dt * 1000;
    if (timeSinceTick >= currentIntervalMs) { timeSinceTick = 0; step(); }
    foodPulse += dt * 6;
    if (shake > 0) { shake *= 0.85; if (shake < 0.2) shake = 0; }
    particles.forEach((p) => { p.x += p.vx; p.y += p.vy; p.life -= 0.04; });
    particles = particles.filter((p) => p.life > 0);
  }

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

  function drawGame() {
    const ox = (Math.random() - 0.5) * shake, oy = (Math.random() - 0.5) * shake;
    ctx.fillStyle = COLOR_BG;
    ctx.fillRect(ox, oy, BOARD, BOARD);
    ctx.strokeStyle = COLOR_GRID;
    ctx.lineWidth = 1;
    for (let i = 0; i <= COUNT; i++) {
      ctx.beginPath(); ctx.moveTo(ox + i * GRID, oy); ctx.lineTo(ox + i * GRID, oy + BOARD); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(ox, oy + i * GRID); ctx.lineTo(ox + BOARD, oy + i * GRID); ctx.stroke();
    }
    const pulse = Math.sin(foodPulse) * 2;
    ctx.fillStyle = COLOR_DANGER;
    ctx.beginPath();
    ctx.arc(ox + food[0] * GRID + GRID / 2, oy + food[1] * GRID + GRID / 2, GRID / 2.6 + pulse * 0.3, 0, 7);
    ctx.fill();
    const n = snake.length;
    snake.forEach((c, i) => {
      const t = i / Math.max(n, 1);
      let color;
      if (i === 0) color = COLOR_ACCENT;
      else {
        const g = Math.max(Math.round(220 - t * 90), 0), b = Math.max(Math.round(129 - t * 40), 0);
        color = `rgb(34,${g},${b})`;
      }
      roundRect(ox + c[0] * GRID + 1, oy + c[1] * GRID + 1, GRID - 2, GRID - 2, 6, color);
    });
    particles.forEach((p) => {
      ctx.fillStyle = p.color;
      const radius = Math.max(2.5 * p.life, 1);
      ctx.beginPath(); ctx.arc(ox + p.x, oy + p.y, radius, 0, 7); ctx.fill();
    });
  }

  function drawSidebar() {
    const sx = BOARD, pad = 20;
    ctx.fillStyle = COLOR_PANEL; ctx.fillRect(sx, 0, SIDEBAR_W, BOARD);
    ctx.strokeStyle = COLOR_BORDER; ctx.beginPath(); ctx.moveTo(sx, 0); ctx.lineTo(sx, BOARD); ctx.stroke();

    ctx.fillStyle = COLOR_ACCENT; ctx.font = "bold 24px Tahoma"; ctx.textAlign = "left"; ctx.textBaseline = "top";
    ctx.fillText("🐍 Snake", sx + pad, 20);

    const dotColor = { online: COLOR_ACCENT, offline: COLOR_DANGER, connecting: COLOR_GOLD }[connectionStatus] || COLOR_TEXT_DIM;
    const dotLabel = { online: "متصل", offline: "غير متصل", connecting: "جارٍ الاتصال..." }[connectionStatus] || "";
    ctx.fillStyle = dotColor; ctx.beginPath(); ctx.arc(sx + SIDEBAR_W - 24, 34, 4, 0, 7); ctx.fill();
    ctx.font = "10px Tahoma"; ctx.textAlign = "right";
    ctx.fillText(dotLabel, sx + SIDEBAR_W - 34, 29);
    ctx.textAlign = "left";

    let y = 70;
    if (username) {
      ctx.fillStyle = COLOR_TEXT_DIM; ctx.font = "13px Tahoma";
      ctx.fillText("اللاعب: " + username, sx + pad, y);
      y += 30;
    }

    const stats = [["النقاط", String(score), COLOR_ACCENT], ["أفضل نتيجة لي", String(myBest), COLOR_GOLD], ["مستوى السرعة", String(speedLevel), COLOR_ACCENT]];
    stats.forEach(([label, value, color]) => {
      roundRect(sx + pad, y, SIDEBAR_W - pad * 2, 46, 10, "#0d1322");
      ctx.fillStyle = COLOR_TEXT_DIM; ctx.font = "10px Tahoma"; ctx.fillText(label, sx + pad + 12, y + 6);
      ctx.fillStyle = color; ctx.font = "bold 18px Tahoma"; ctx.fillText(value, sx + pad + 12, y + 20);
      y += 56;
    });

    y += 6;
    ctx.fillStyle = COLOR_GOLD; ctx.font = "bold 13px Tahoma";
    ctx.fillText("🏆 لوحة الصدارة (أونلاين)", sx + pad, y);
    y += 28;

    if (connectionStatus === "offline" && leaderboard.length === 0) {
      ctx.fillStyle = COLOR_DANGER; ctx.font = "10px Tahoma"; ctx.fillText("تعذر الاتصال بالخادم", sx + pad, y); y += 18;
      ctx.fillStyle = COLOR_TEXT_DIM; ctx.fillText("تحقق من تشغيل server.py", sx + pad, y);
    } else if (leaderboard.length === 0) {
      ctx.fillStyle = COLOR_TEXT_DIM; ctx.font = "10px Tahoma"; ctx.fillText("لا توجد نتائج بعد", sx + pad, y);
    } else {
      const rankColors = { 0: COLOR_GOLD, 1: "#cbd5e1", 2: "#d97706" };
      leaderboard.slice(0, 8).forEach((entry, i) => {
        const isMe = (entry.username || "").toLowerCase() === username.toLowerCase();
        roundRect(sx + pad, y, SIDEBAR_W - pad * 2, 28, 6, isMe ? "#0d2d1e" : "#0d1322");
        ctx.fillStyle = rankColors[i] || COLOR_TEXT_DIM; ctx.font = "10px Tahoma";
        ctx.fillText(String(i + 1), sx + pad + 8, y + 8);
        let name = entry.username || "؟؟؟";
        if (name.length > 14) name = name.slice(0, 13) + "…";
        ctx.fillStyle = COLOR_TEXT; ctx.fillText(name, sx + pad + 28, y + 8);
        ctx.fillStyle = COLOR_ACCENT; ctx.textAlign = "right";
        ctx.fillText(String(entry.score || 0), sx + SIDEBAR_W - pad - 8, y + 8);
        ctx.textAlign = "left";
        y += 32;
      });
    }

    y = BOARD - 66;
    ctx.fillStyle = COLOR_TEXT_DIM; ctx.font = "10px Tahoma";
    ctx.fillText("الأسهم: تحريك", sx + pad, y);
    ctx.fillText("مسافة: إيقاف مؤقت", sx + pad, y + 18);
    ctx.fillText("Esc: تبديل المستخدم", sx + pad, y + 36);
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (state === "start") return; // overlay div handles this screen
    drawGame();
    drawSidebar();
    if (state === "paused") {
      ctx.fillStyle = "rgba(6,10,20,0.85)"; ctx.fillRect(0, 0, BOARD, BOARD);
      ctx.fillStyle = COLOR_TEXT; ctx.font = "bold 24px Tahoma"; ctx.textAlign = "center";
      ctx.fillText("⏸ إيقاف مؤقت", BOARD / 2, BOARD / 2 - 10);
      ctx.textAlign = "left";
    }
  }

  let lastTs = null;
  function loop(ts) {
    if (lastTs === null) lastTs = ts;
    const dt = (ts - lastTs) / 1000;
    lastTs = ts;
    update(dt);
    draw();
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);

  // -- شاشة البداية (عناصر HTML) --
  const startScreen = document.getElementById("startScreen");
  const gameOverlay = document.getElementById("gameOverlay");
  const usernameInput = document.getElementById("usernameInput");
  const startHint = document.getElementById("startHint");

  document.querySelectorAll(".diffBtn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".diffBtn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      difficulty = btn.dataset.diff;
      baseSpeedMs = DIFFS[difficulty];
    });
  });

  function tryStart() {
    const name = usernameInput.value.trim();
    if (!name) { startHint.textContent = "(الرجاء إدخال اسم مستخدم للمتابعة)"; return; }
    username = name;
    myBest = 0;
    const existing = leaderboard.find((e) => (e.username || "").toLowerCase() === name.toLowerCase());
    if (existing) myBest = existing.score || 0;
    startScreen.style.display = "none";
    gameOverlay.style.display = "none";
    resetRound();
    state = "playing";
    canvas.focus();
  }

  document.getElementById("startBtn").addEventListener("click", tryStart);
  usernameInput.addEventListener("keydown", (e) => { if (e.key === "Enter") tryStart(); });

  document.getElementById("overlayBtn").addEventListener("click", () => {
    gameOverlay.style.display = "none";
    resetRound();
    state = "playing";
    canvas.focus();
  });

  function goToStart() {
    state = "start";
    startScreen.style.display = "flex";
    gameOverlay.style.display = "none";
    usernameInput.value = username;
    fetchLeaderboard();
  }

  document.addEventListener("keydown", (e) => {
    if (state === "start") return;
    switch (e.key) {
      case "ArrowUp": setDirection(0, -1); e.preventDefault(); break;
      case "ArrowDown": setDirection(0, 1); e.preventDefault(); break;
      case "ArrowLeft": setDirection(-1, 0); e.preventDefault(); break;
      case "ArrowRight": setDirection(1, 0); e.preventDefault(); break;
      case " ":
        if (state === "playing") state = "paused";
        else if (state === "paused") state = "playing";
        e.preventDefault();
        break;
      case "Escape": goToStart(); break;
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
    components.html(html, height=470, scrolling=False)


render_game(server_url)

st.caption(
    "💡 تلميح: إذا لم تعمل الأسهم، اضغط مرة واحدة داخل مربع اللعبة (Canvas) أولًا لتفعيل التركيز عليه."
)
