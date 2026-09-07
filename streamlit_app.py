"""
Snake Game Online — لعب جماعي متزامن (Real-time Multiplayer) عبر Streamlit
=====================================================
نسخة من لعبة الثعبان يشترك فيها كل اللاعبين في نفس اللوحة، في نفس الوقت،
ويشاهدون ثعابين بعضهم البعض تتحرك لحظيًا. كل من يفتح هذا التطبيق يكتب
اسم مستخدم فقط ويدخل اللعبة الحية مباشرة — بدون أي إعداد أو عنوان IP.

كيف يعمل التزامن:
    الخادم (server.py) هو من يحرّك كل الثعابين معًا كل جزء من الثانية،
    ويحتفظ بحالة اللعبة الكاملة. هذه الصفحة تتصل بنفس الخادم (عنوان ثابت
    داخل الكود) وتستعلم عن حالة اللوحة عدة مرات في الثانية لترسمها لحظيًا،
    وترسل ضغطات الأسهم فور حدوثها — بحيث يرى الجميع نفس اللوحة تتزامن.

المتطلبات:
    pip install streamlit requests flask

التشغيل:
    1. شغّل خادم اللعبة الحية مرة واحدة (يفضَّل على جهاز واحد ثابت):
           python server.py
    2. شغّل تطبيق اللعبة:
           streamlit run streamlit_app.py
    3. أرسل رابط تطبيق Streamlit فقط لأصدقائك — كل من يفتحه يكتب اسمه
       ويدخل نفس اللعبة الحية معهم مباشرة.

ملاحظة للمطوّر / من يستضيف التطبيق:
    القيمة الافتراضية لـ SERVER_URL بالأسفل هي "http://127.0.0.1:5000"
    (تعمل عندما يشتغل server.py على نفس الجهاز). إذا كنت تنشر التطبيق على
    الإنترنت لأشخاص من أماكن مختلفة، استضف server.py على خدمة مثل Render
    أو Railway، ثم غيّر SERVER_URL بالأسفل (أو عرّف متغير بيئة
    SNAKE_SERVER_URL) ليشير لرابط ذلك الخادم. هذه خطوة تُنفَّذ مرة واحدة من
    طرفك، ولا يراها أو يتعامل معها اللاعبون إطلاقًا.
"""

import os

import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="🐍 Snake Online — لعب جماعي متزامن", page_icon="🐍", layout="wide")

REQUEST_TIMEOUT = 4

# عنوان خادم اللعبة الحية — ثابت، لا يظهر للاعبين ولا يُطلب منهم إدخاله.
# غيّره هنا فقط إذا كنت تستضيف server.py على جهاز/رابط مختلف.
SERVER_URL = os.environ.get("SNAKE_SERVER_URL", "http://127.0.0.1:5000").rstrip("/")

st.title("🐍 Snake — لعب جماعي متزامن")
st.caption(
    "اكتب اسم مستخدم داخل مربع اللعبة وادخل مباشرة إلى نفس اللوحة مع بقية "
    "اللاعبين المتصلين الآن — الجميع يتحرك في نفس الوقت. استخدم أسهم "
    "الكيبورد، واضغط داخل مربع اللعبة أولًا لتفعيلها."
)

with st.sidebar:
    st.markdown("### 🏆 أفضل النتائج على الإطلاق")
    if st.button("🔄 تحديث", use_container_width=True):
        st.rerun()
    try:
        lb_resp = requests.get(f"{SERVER_URL}/leaderboard", timeout=REQUEST_TIMEOUT)
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
        st.caption("⚠️ تعذر الاتصال بخادم اللعبة. تأكد من تشغيل server.py.")

# ---------------------------------------------------------------------------
# اللعبة — HTML/JS canvas مضمّن، يتصل مباشرة بخادم اللعبة الحية
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
  #usernameInput {
    width: 220px; padding: 10px 12px; border-radius: 10px;
    border: 1px solid #22304a; background: #0d1322; color: #e2e8f0;
    font-size: 14px; text-align: center; margin-bottom: 16px;
  }
  #usernameInput:focus { outline: none; border-color: #4ade80; }
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
    <p>لعب جماعي متزامن — كل من يدخل بنفس اسم الخادم يشاركك نفس اللوحة الآن. اكتب اسمك وادخل مباشرة.</p>
    <input id="usernameInput" maxlength="16" placeholder="اكتب اسم المستخدم" />
    <button id="startBtn">ادخل اللعبة</button>
    <div id="startHint"></div>
    <div id="liveCount"></div>
  </div>

  <div id="gameOverlay">
    <h2 id="overlayTitle">انتهت اللعبة</h2>
    <div id="overlayScore"></div>
    <div id="overlaySub">حاول مرة أخرى — بقية اللاعبين ما زالوا يلعبون الآن</div>
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
  const startHint = document.getElementById("startHint");
  const liveCount = document.getElementById("liveCount");

  let phase = "start"; // start | playing
  let playerId = null;
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
    withTimeout(fetch(SERVER_URL + "/state"), REQUEST_TIMEOUT_MS)
      .then((r) => r.json())
      .then((data) => { liveCount.textContent = "🟢 لاعبون متصلون الآن: " + (data.players ? data.players.length : 0); })
      .catch(() => { liveCount.textContent = "⚠️ تعذر الاتصال بخادم اللعبة"; });
  }
  refreshLobbyCount();
  setInterval(refreshLobbyCount, 2000);

  function join(username) {
    withTimeout(
      fetch(SERVER_URL + "/join", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username }),
      }),
      REQUEST_TIMEOUT_MS
    )
      .then((r) => { if (!r.ok) throw new Error("bad status"); return r.json(); })
      .then((data) => {
        playerId = data.player_id;
        myColor = data.color;
        gridCount = data.grid_count;
        cellSize = BOARD / gridCount;
        phase = "playing";
        startScreen.style.display = "none";
        gameOverlay.style.display = "none";
        canvas.focus();
      })
      .catch(() => { startHint.textContent = "⚠️ تعذر الاتصال بخادم اللعبة. تأكد من تشغيل server.py."; });
  }

  function sendDirection(dx, dy) {
    if (!playerId) return;
    fetch(SERVER_URL + "/direction", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ player_id: playerId, dx, dy }),
    }).catch(() => {});
  }

  function respawn() {
    if (!playerId) return;
    withTimeout(
      fetch(SERVER_URL + "/respawn", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ player_id: playerId }),
      }),
      REQUEST_TIMEOUT_MS
    )
      .then(() => { gameOverlay.style.display = "none"; canvas.focus(); })
      .catch(() => {});
  }

  function leaveGame() {
    if (playerId) {
      const payload = JSON.stringify({ player_id: playerId });
      if (navigator.sendBeacon) {
        navigator.sendBeacon(SERVER_URL + "/leave", new Blob([payload], { type: "application/json" }));
      } else {
        fetch(SERVER_URL + "/leave", { method: "POST", headers: { "Content-Type": "application/json" }, body: payload }).catch(() => {});
      }
    }
    playerId = null;
    phase = "start";
    gameOverlay.style.display = "none";
    startScreen.style.display = "flex";
    usernameInput.value = "";
    refreshLobbyCount();
  }

  window.addEventListener("beforeunload", () => {
    if (playerId) {
      const payload = JSON.stringify({ player_id: playerId });
      if (navigator.sendBeacon) {
        navigator.sendBeacon(SERVER_URL + "/leave", new Blob([payload], { type: "application/json" }));
      }
    }
  });

  function pollState() {
    if (phase !== "playing" || !playerId) return;
    withTimeout(fetch(SERVER_URL + "/state?player_id=" + playerId), REQUEST_TIMEOUT_MS)
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
    ctx.fillText("👥 اللاعبون المتصلون الآن", sx + pad, y);
    y += 26;

    const players = (latestState.players || []).slice().sort((a, b) => b.score - a.score);
    if (players.length === 0) {
      ctx.fillStyle = COLOR_TEXT_DIM; ctx.font = "10px Tahoma";
      ctx.fillText("لا يوجد لاعبون آخرون حاليًا", sx + pad, y);
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
    if (!name) { startHint.textContent = "(الرجاء إدخال اسم مستخدم للمتابعة)"; return; }
    startHint.textContent = "جارٍ الدخول...";
    join(name);
  });
  usernameInput.addEventListener("keydown", (e) => {
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
    "💡 تلميح: كل من يفتح هذا التطبيق (نفس الرابط) ويكتب اسمه يدخل تلقائيًا نفس "
    "اللوحة الحية ويشاهد بقية اللاعبين يتحركون معه في نفس الوقت."
)
