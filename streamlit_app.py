"""
Snake — لعب جماعي حقيقي P2P (بدون أي خادم Python على الإطلاق)
=====================================================
هذه نسخة مختلفة جذريًا: لا يوجد خادم Flask، ولا منفذ 5000، ولا حاجة لتشغيل
شيء غير هذا الملف. الاتصال بين اللاعبين يتم مباشرة متصفح-إلى-متصفح عبر
WebRTC (مكتبة PeerJS) — وهذا هو المعنى الحقيقي لـ "P2P": لا تمر بيانات
اللعبة عبر أي خادم تديره أنت، بل تنتقل مباشرة بين أجهزة اللاعبين.

كيف يعمل بدون خادم؟
    - أول شخص يدخل برمز غرفة معيّن يصبح تلقائيًا "المضيف" (Host): متصفحه
      هو من يشغّل حلقة اللعبة (تحريك الثعابين، التصادمات، الطعام) — تمامًا
      كما كان يفعل الخادم سابقًا، لكن الآن في متصفح اللاعب نفسه بلغة
      JavaScript.
    - أي شخص آخر يدخل بنفس رمز الغرفة يتصل مباشرة بمتصفح المضيف عبر
      WebRTC، ويرسل له ضغطات الأسهم، ويستقبل منه حالة اللوحة كاملة عدة
      مرات في الثانية.
    - رمز الغرفة هو "الرقم السرّي": من يعرفه يدخل نفس اللعبة، ومن لا
      يعرفه لا يستطيع الوصول إليها إطلاقًا.

ملاحظة مهمة (خاصية P2P وليست عيبًا في الكود):
    بما أن متصفح المضيف هو من يشغّل اللعبة، فإن إغلاقه لصفحة اللعبة أو
    فقدانه الاتصال بالإنترنت ينهي الجولة لبقية اللاعبين في نفس الغرفة —
    تمامًا كما يحدث في أي لعبة P2P حقيقية بلا خادم مركزي.

    كذلك، لإتمام "المصافحة" الأولى بين المتصفحين (signaling) تُستخدم خدمة
    PeerJS السحابية المجانية (0.peerjs.com) — وهذه فقط تساعد الطرفين على
    "التعارف" في البداية؛ بعدها تنتقل كل بيانات اللعبة مباشرة بينهما. هذا
    يعني أن الجهاز يحتاج اتصالًا بالإنترنت (وليس بالضرورة نفس الشبكة
    المحلية كما في السابق) — وهذه فائدة إضافية: يمكن اللعب بين أجهزة على
    شبكات مختلفة تمامًا، وليس فقط نفس الجهاز أو نفس الواي فاي.

التشغيل (أمر واحد فقط، بلا أي إعداد):
    streamlit run streamlit_app.py
"""

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="🐍 Snake Online — P2P بغرف خاصة", page_icon="🐍", layout="wide")

st.title("🐍 Snake — لعب جماعي حقيقي P2P (بدون خادم)")
st.caption(
    "اتفق مع أصدقائك على رمز غرفة سرّي. أول من يدخل به يصبح 'المضيف' وتُبنى "
    "اللعبة في متصفحه مباشرة، ومن يدخل بنفس الرمز بعده يتصل به مباشرة "
    "(P2P عبر WebRTC) — بلا أي خادم وسيط من عندنا."
)
st.info(
    "💡 المضيف (أول من يدخل بالرمز) يجب أن يبقي تبويب اللعبة مفتوحًا طوال "
    "وقت اللعب — إغلاقه ينهي الجولة لبقية لاعبي نفس الغرفة، تمامًا كما في "
    "أي اتصال P2P حقيقي بلا خادم مركزي.",
    icon="ℹ️",
)

GAME_HTML = r"""
<!DOCTYPE html>
<html lang="ar">
<head>
<meta charset="utf-8" />
<script src="https://unpkg.com/peerjs@1.5.4/dist/peerjs.min.js"></script>
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
  #startHint { color: #f87171; font-size: 12px; margin-top: 10px; min-height: 14px; max-width: 320px; }
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
    <h1>🐍 Snake — P2P</h1>
    <p>لا يوجد خادم — أول من يدخل برمز الغرفة يصبح المضيف، ومن يدخل بعده بنفس الرمز يتصل به مباشرة.</p>
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
  const GRID_COUNT = 26;
  const TICK_MS = 130;
  const FOOD_COUNT = 6;
  const STARTING_LENGTH = 3;
  const PLAYER_COLORS = [
    "#4ade80", "#60a5fa", "#f472b6", "#fbbf24",
    "#c084fc", "#fb923c", "#2dd4bf", "#f87171",
  ];

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
  let myId = null;
  let myColor = COLOR_ACCENT;
  let gridCount = GRID_COUNT;
  let cellSize = BOARD / gridCount;
  let latestState = { players: [], foods: [] };
  let connectionOk = true;
  let lastScoreShown = 0;

  // -------- حالة P2P --------
  let isHost = false;
  let hostPeer = null;        // Peer الخاص بي عندما أكون المضيف
  let hostConnections = {};   // peerId -> DataConnection (فقط عند كوني مضيفًا)
  let clientPeer = null;      // Peer الخاص بي عندما أكون لاعبًا عاديًا
  let clientConn = null;      // اتصالي بالمضيف (فقط عند كوني لاعبًا عاديًا)
  let room = null;            // {players:{}, foods:[]} — موجود فقط لدى المضيف
  let gameLoopHandle = null;

  function slugifyRoom(raw) {
    const slug = raw.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40);
    return "arcsnake-" + (slug || "default");
  }

  // ---------------------------------------------------------------------
  // منطق اللعبة (يعمل فقط داخل متصفح المضيف)
  // ---------------------------------------------------------------------
  function occupiedCells() {
    const cells = new Set();
    Object.values(room.players).forEach((p) => {
      if (p.alive) p.snake.forEach((seg) => cells.add(seg[0] + "," + seg[1]));
    });
    room.foods.forEach((f) => cells.add(f[0] + "," + f[1]));
    return cells;
  }

  function randomFreeCell() {
    const taken = occupiedCells();
    for (let i = 0; i < 400; i++) {
      const x = Math.floor(Math.random() * GRID_COUNT);
      const y = Math.floor(Math.random() * GRID_COUNT);
      if (!taken.has(x + "," + y)) return [x, y];
    }
    return [Math.floor(Math.random() * GRID_COUNT), Math.floor(Math.random() * GRID_COUNT)];
  }

  function spawnSnake() {
    for (let i = 0; i < 200; i++) {
      const hx = 2 + Math.floor(Math.random() * (GRID_COUNT - 4));
      const hy = 2 + Math.floor(Math.random() * (GRID_COUNT - 4));
      const cells = [];
      for (let k = 0; k < STARTING_LENGTH; k++) cells.push([hx - k, hy]);
      const ok = cells.every(([cx, cy]) => cx >= 0 && cx < GRID_COUNT && cy >= 0 && cy < GRID_COUNT);
      if (ok) {
        const taken = occupiedCells();
        if (cells.every(([cx, cy]) => !taken.has(cx + "," + cy))) return cells;
      }
    }
    const fb = [];
    for (let k = 0; k < STARTING_LENGTH; k++) fb.push([3 - k, 3]);
    return fb;
  }

  function ensureFoodCount() {
    while (room.foods.length < FOOD_COUNT) room.foods.push(randomFreeCell());
  }

  function buildStateOut() {
    return {
      type: "state",
      players: Object.entries(room.players).map(([id, p]) => ({
        id, username: p.username, color: p.color, snake: p.snake, alive: p.alive, score: p.score,
      })),
      foods: room.foods,
      grid_count: GRID_COUNT,
      tick_ms: TICK_MS,
    };
  }

  function broadcastState() {
    const out = buildStateOut();
    latestState = out;
    connectionOk = true;
    handleMyStatus(out);
    Object.values(hostConnections).forEach((conn) => { if (conn.open) conn.send(out); });
  }

  function tickRoom() {
    const players = room.players;
    const ids = Object.keys(players);
    if (ids.length === 0) { ensureFoodCount(); broadcastState(); return; }

    ids.forEach((id) => { const p = players[id]; if (p.alive) p.direction = p.nextDirection; });

    const proposals = {};
    ids.forEach((id) => {
      const p = players[id];
      if (!p.alive || !p.snake.length) return;
      const [dx, dy] = p.direction;
      const [hx, hy] = p.snake[0];
      proposals[id] = [hx + dx, hy + dy];
    });

    const proposalIds = Object.keys(proposals);
    if (proposalIds.length === 0) { ensureFoodCount(); broadcastState(); return; }

    const headCounts = {};
    proposalIds.forEach((id) => {
      const key = proposals[id].join(",");
      headCounts[key] = (headCounts[key] || 0) + 1;
    });

    const occupied = occupiedCells();
    const foodsSet = new Set(room.foods.map((f) => f.join(",")));
    const deadThisTick = new Set();

    proposalIds.forEach((id) => {
      const [x, y] = proposals[id];
      if (x < 0 || x >= GRID_COUNT || y < 0 || y >= GRID_COUNT) { deadThisTick.add(id); return; }
      const key = x + "," + y;
      if (headCounts[key] > 1) { deadThisTick.add(id); return; }
      if (occupied.has(key) && !foodsSet.has(key)) {
        const snake = players[id].snake;
        const tail = snake[snake.length - 1];
        if (!(tail[0] === x && tail[1] === y && snake.length > 1)) deadThisTick.add(id);
      }
    });

    const eatenCells = new Set();
    proposalIds.forEach((id) => {
      if (deadThisTick.has(id)) return;
      const p = players[id];
      const [nx, ny] = proposals[id];
      p.snake.unshift([nx, ny]);
      const key = nx + "," + ny;
      if (foodsSet.has(key) && !eatenCells.has(key)) {
        p.score += 10;
        eatenCells.add(key);
      } else {
        p.snake.pop();
      }
    });

    if (eatenCells.size) room.foods = room.foods.filter((f) => !eatenCells.has(f.join(",")));

    deadThisTick.forEach((id) => {
      const p = players[id];
      if (!p) return;
      p.alive = false;
      p.snake = [];
    });

    ensureFoodCount();
    broadcastState();
  }

  // ---------------------------------------------------------------------
  // إنشاء/الانضمام لغرفة عبر WebRTC (PeerJS)
  // ---------------------------------------------------------------------
  function handleHostIncoming(conn, msg) {
    if (!msg || !msg.type) return;
    if (msg.type === "join") {
      const username = String(msg.username || "").trim().slice(0, 16);
      if (!username) return;
      hostConnections[conn.peer] = conn;
      const color = PLAYER_COLORS[Object.keys(room.players).length % PLAYER_COLORS.length];
      room.players[conn.peer] = {
        username, color, snake: spawnSnake(), direction: [1, 0], nextDirection: [1, 0], alive: true, score: 0,
      };
      ensureFoodCount();
      conn.send({ type: "joined", player_id: conn.peer, color, grid_count: GRID_COUNT, tick_ms: TICK_MS });
    } else if (msg.type === "direction") {
      const p = room.players[conn.peer];
      if (!p || !p.alive) return;
      const dx = msg.dx, dy = msg.dy;
      if (![-1, 0, 1].includes(dx) || ![-1, 0, 1].includes(dy) || Math.abs(dx) === Math.abs(dy)) return;
      const [cdx, cdy] = p.direction;
      if (!(cdx === -dx && cdy === -dy && p.snake.length > 1)) p.nextDirection = [dx, dy];
    } else if (msg.type === "respawn") {
      const p = room.players[conn.peer];
      if (!p) return;
      p.snake = spawnSnake();
      p.direction = [1, 0]; p.nextDirection = [1, 0]; p.alive = true; p.score = 0;
      ensureFoodCount();
    }
  }

  function becomeHost(username, roomSlug) {
    hostPeer = new Peer(roomSlug);
    hostPeer.on("open", (id) => {
      isHost = true;
      myId = id;
      room = { players: {}, foods: [] };
      const color = PLAYER_COLORS[0];
      myColor = color;
      gridCount = GRID_COUNT;
      room.players[myId] = {
        username, color, snake: spawnSnake(), direction: [1, 0], nextDirection: [1, 0], alive: true, score: 0,
      };
      ensureFoodCount();
      startPlaying();
      gameLoopHandle = setInterval(tickRoom, TICK_MS);
      broadcastState();

      hostPeer.on("connection", (conn) => {
        conn.on("data", (msg) => handleHostIncoming(conn, msg));
        conn.on("close", () => {
          delete hostConnections[conn.peer];
          if (room) delete room.players[conn.peer];
        });
      });
    });
    hostPeer.on("error", (err) => {
      if (err.type === "unavailable-id") {
        hostPeer = null;
        joinAsClient(username, roomSlug);
      } else {
        startHint.textContent = "⚠️ تعذر إنشاء الغرفة (" + err.type + "). تأكد من اتصالك بالإنترنت وحاول مجددًا.";
      }
    });
  }

  function joinAsClient(username, roomSlug) {
    clientPeer = new Peer();
    let settled = false;

    clientPeer.on("open", () => {
      clientConn = clientPeer.connect(roomSlug, { reliable: true });

      const timeoutHandle = setTimeout(() => {
        if (!settled) {
          startHint.textContent = "⚠️ لا يوجد أحد بهذا الرمز حاليًا. اتفق مع صديقك على الدخول أولًا، أو تأكد من الرمز.";
        }
      }, 7000);

      clientConn.on("open", () => clientConn.send({ type: "join", username }));

      clientConn.on("data", (msg) => {
        if (!msg || !msg.type) return;
        if (msg.type === "joined") {
          settled = true;
          clearTimeout(timeoutHandle);
          myId = msg.player_id;
          myColor = msg.color;
          gridCount = msg.grid_count || GRID_COUNT;
          startPlaying();
        } else if (msg.type === "state") {
          settled = true;
          clearTimeout(timeoutHandle);
          latestState = msg;
          gridCount = msg.grid_count || gridCount;
          connectionOk = true;
          handleMyStatus(msg);
        }
      });

      clientConn.on("close", () => {
        connectionOk = false;
        if (phase === "playing") {
          liveCount.textContent = "";
        }
      });
      clientConn.on("error", () => { startHint.textContent = "⚠️ تعذر الاتصال بالمضيف."; });
    });

    clientPeer.on("error", (err) => {
      startHint.textContent = "⚠️ خطأ شبكة (" + err.type + "). تأكد من اتصالك بالإنترنت.";
    });
  }

  function handleMyStatus(state) {
    const me = (state.players || []).find((p) => p.id === myId);
    if (me) {
      lastScoreShown = me.score;
      if (!me.alive && gameOverlay.style.display !== "flex") {
        document.getElementById("overlayScore").textContent = String(me.score);
        gameOverlay.style.display = "flex";
      }
    }
  }

  function startPlaying() {
    phase = "playing";
    startScreen.style.display = "none";
    gameOverlay.style.display = "none";
    canvas.focus();
  }

  function sendDirection(dx, dy) {
    if (!myId) return;
    if (isHost) {
      const p = room.players[myId];
      if (!p || !p.alive) return;
      const [cdx, cdy] = p.direction;
      if (!(cdx === -dx && cdy === -dy && p.snake.length > 1)) p.nextDirection = [dx, dy];
    } else if (clientConn && clientConn.open) {
      clientConn.send({ type: "direction", dx, dy });
    }
  }

  function respawn() {
    if (!myId) return;
    if (isHost) {
      const p = room.players[myId];
      if (p) {
        p.snake = spawnSnake();
        p.direction = [1, 0]; p.nextDirection = [1, 0]; p.alive = true; p.score = 0;
        ensureFoodCount();
      }
    } else if (clientConn && clientConn.open) {
      clientConn.send({ type: "respawn" });
    }
    gameOverlay.style.display = "none";
    canvas.focus();
  }

  function leaveGame() {
    if (isHost) {
      if (gameLoopHandle) clearInterval(gameLoopHandle);
      Object.values(hostConnections).forEach((c) => { try { c.close(); } catch (e) {} });
      if (hostPeer) { try { hostPeer.destroy(); } catch (e) {} }
      hostPeer = null; hostConnections = {}; room = null; gameLoopHandle = null;
    } else {
      if (clientConn) { try { clientConn.close(); } catch (e) {} }
      if (clientPeer) { try { clientPeer.destroy(); } catch (e) {} }
      clientPeer = null; clientConn = null;
    }
    isHost = false;
    myId = null;
    phase = "start";
    gameOverlay.style.display = "none";
    startScreen.style.display = "flex";
    usernameInput.value = "";
    liveCount.textContent = "";
  }

  window.addEventListener("beforeunload", () => { leaveGame(); });

  // ---------------------------------------------------------------------
  // الرسم (نفسه للمضيف واللاعبين العاديين — كلاهما يرسم latestState)
  // ---------------------------------------------------------------------
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
      const isMe = p.id === myId;
      p.snake.forEach((seg, i) => {
        const alpha = i === 0 ? 1 : Math.max(0.45, 1 - i * 0.03);
        ctx.globalAlpha = alpha;
        roundRect(seg[0] * cellSize + 1, seg[1] * cellSize + 1, cellSize - 2, cellSize - 2, 5, p.color);
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
    ctx.fillText(connectionOk ? (isHost ? "أنت المضيف (P2P)" : "متصل P2P بالمضيف") : "انقطع الاتصال", sx + SIDEBAR_W - 30, 22);
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
        const isMe = p.id === myId;
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
    startHint.textContent = "جارٍ الاتصال...";
    becomeHost(name, slugifyRoom(room));
  });
  usernameInput.addEventListener("keydown", (e) => { if (e.key === "Enter") document.getElementById("startBtn").click(); });
  roomInput.addEventListener("keydown", (e) => { if (e.key === "Enter") document.getElementById("startBtn").click(); });

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

components.html(GAME_HTML, height=545, scrolling=False)

st.caption(
    "💡 لا يوجد خادم من عندنا في هذه النسخة إطلاقًا — كل بيانات اللعبة تنتقل "
    "مباشرة بين متصفحات اللاعبين عبر WebRTC. أول من يدخل برمز غرفة معيّن هو "
    "من 'يستضيف' تلك الجولة."
)
