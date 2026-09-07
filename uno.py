import streamlit as st
import streamlit.components.v1 as components

# إعدادات الصفحة
st.set_page_config(
    page_title="UNO Online P2P & AI (4 Players)",
    page_icon="🎴",
    layout="wide",
)

st.title("🎴 لعبة اونو الاحترافية (4 لاعبين)")
st.write(
    "العَب أونلاين P2P عبر إنشائك غرفة مع أصدقائك أو نافِس الذكاء الاصطناعي (AI)!"
)

# كود اللعبة بالكامل (HTML5 / JavaScript P2P via PeerJS)
uno_p2p_html = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <script src="https://unpkg.com/peerjs@1.5.2/dist/peerjs.min.js"></script>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0e1117; color: white; text-align: center; margin: 0; padding: 10px; }
        .mode-selection { background: #1f293d; padding: 15px; border-radius: 10px; max-width: 600px; margin: auto; }
        input, button, select { padding: 10px; margin: 5px; border-radius: 5px; border: none; font-weight: bold; }
        button { background: #00ffcc; color: #0e1117; cursor: pointer; }
        button:hover { background: #00cca3; }
        .game-board { display: none; margin-top: 15px; }
        .table-center { display: flex; justify-content: center; align-items: center; gap: 20px; margin: 20px 0; }
        .card { width: 70px; height: 105px; border-radius: 8px; display: inline-flex; flex-direction: column; justify-content: center; align-items: center; font-size: 18px; font-weight: bold; color: white; border: 2px solid white; box-shadow: 0 4px 6px rgba(0,0,0,0.3); margin: 3px; cursor: pointer; }
        .red { background: #ff5555; }
        .blue { background: #5555ff; }
        .green { background: #55aa55; }
        .yellow { background: #ffaa00; }
        .black { background: #333333; }
        .hand { display: flex; justify-content: center; flex-wrap: wrap; margin-top: 10px; }
        .players-status { display: flex; justify-content: space-around; background: #161b26; padding: 10px; border-radius: 8px; }
        .active-turn { border: 2px solid #00ffcc; background: #2a3752; border-radius: 6px; padding: 5px; }
    </style>
</head>
<body>

    <div id="setup-panel" class="mode-selection">
        <h3>اختر طريقة اللعب:</h3>
        <button onclick="startAIMode()">🤖 اللعب ضد 3 كمبيوتر (AI)</button>
        <hr style="border-color:#334155;">
        <h4>🌐 اللعب أونلاين (P2P - 4 لاعبين):</h4>
        <input type="text" id="player-name" placeholder="اسمك" value="لاعب 1">
        <br>
        <button onclick="createRoom()">إنشاء غرفة جديدة (Host)</button>
        <br>
        <input type="text" id="room-id-input" placeholder="رمز الغرفة (Room ID)">
        <button onclick="joinRoom()">الانضمام لغرفة</button>
        <p id="room-info" style="color:#00ffcc; font-weight:bold;"></p>
    </div>

    <div id="game-board" class="game-board">
        <div class="players-status" id="players-status"></div>

        <div class="table-center">
            <div>
                <p>الورقة المكشوفة</p>
                <div id="top-card" class="card black">?</div>
            </div>
            <div>
                <p>اللون الحالي</p>
                <div id="color-indicator" style="width:40px; height:40px; border-radius:50%; border:2px solid white; margin:auto;"></div>
            </div>
            <div>
                <button onclick="drawCard()" style="height:50px;">سحب ورقة 🎴</button>
            </div>
        </div>

        <p id="game-log" style="color:#00ffcc; font-size:16px; font-weight:bold;"></p>

        <h3>أوراقك 🫵:</h3>
        <div id="my-hand" class="hand"></div>
    </div>

    <script>
        const COLORS = ["red", "blue", "green", "yellow"];
        const VALUES = ["0","1","2","3","4","5","6","7","8","9","Skip","+2"];
        
        let isHost = false;
        let isAI = false;
        let myIndex = 0;
        let peer = null;
        let connections = [];
        let roomCode = "";
        
        let gameState = {
            deck: [],
            players: [],
            currentCard: null,
            currentColor: "",
            turn: 0,
            direction: 1
        };

        function buildDeck() {
            let deck = [];
            COLORS.forEach(c => {
                VALUES.forEach(v => {
                    deck.push({color: c, value: v});
                    if(v !== "0") deck.push({color: c, value: v});
                });
            });
            for(let i=0; i<4; i++) {
                deck.push({color: "black", value: "Wild"});
                deck.push({color: "black", value: "+4"});
            }
            return deck.sort(() => Math.random() - 0.5);
        }

        function startAIMode() {
            isAI = true;
            document.getElementById("setup-panel").style.display = "none";
            document.getElementById("game-board").style.display = "block";

            gameState.deck = buildDeck();
            gameState.players = [
                { name: "أنت", hand: [], isAI: false },
                { name: "البوت 1 🤖", hand: [], isAI: true },
                { name: "البوت 2 🤖", hand: [], isAI: true },
                { name: "البوت 3 🤖", hand: [], isAI: true }
            ];

            for(let i=0; i<7; i++) {
                gameState.players.forEach(p => p.hand.push(gameState.deck.pop()));
            }

            gameState.currentCard = gameState.deck.pop();
            while(gameState.currentCard.color === "black") {
                gameState.deck.push(gameState.currentCard);
                gameState.currentCard = gameState.deck.pop();
            }
            gameState.currentColor = gameState.currentCard.color;

            updateUI();
        }

        function createRoom() {
            isHost = true;
            myIndex = 0;
            roomCode = Math.random().toString(36).substring(2, 7).toUpperCase();
            peer = new Peer(roomCode);

            document.getElementById("room-info").innerText = "رمز الغرفة الخاص بك: " + roomCode + " (شارك الرمز مع 3 أصدقاء)";
            
            gameState.players.push({ name: document.getElementById("player-name").value, hand: [], isAI: false });

            peer.on('connection', conn => {
                if(connections.length < 3) {
                    connections.push(conn);
                    conn.on('data', data => handleNetworkData(data));
                    conn.on('open', () => {
                        conn.send({ type: 'WELCOME', index: connections.length });
                    });
                }
            });
        }

        function joinRoom() {
            isHost = false;
            let code = document.getElementById("room-id-input").value.trim().toUpperCase();
            peer = new Peer();

            peer.on('open', () => {
                let conn = peer.connect(code);
                connections.push(conn);
                conn.on('data', data => handleNetworkData(data));
                conn.on('open', () => {
                    conn.send({ type: 'JOIN', name: document.getElementById("player-name").value });
                });
            });
        }

        function handleNetworkData(data) {
            if(data.type === 'WELCOME') {
                myIndex = data.index;
                document.getElementById("setup-panel").style.display = "none";
                document.getElementById("game-board").style.display = "block";
            } else if (data.type === 'SYNC') {
                gameState = data.state;
                updateUI();
            } else if (data.type === 'JOIN' && isHost) {
                gameState.players.push({ name: data.name, hand: [], isAI: false });
                if(gameState.players.length === 4) {
                    startOnlineGame();
                }
            }
        }

        function broadcastState() {
            connections.forEach(c => c.send({ type: 'SYNC', state: gameState }));
            updateUI();
        }

        function startOnlineGame() {
            gameState.deck = buildDeck();
            for(let i=0; i<7; i++) {
                gameState.players.forEach(p => p.hand.push(gameState.deck.pop()));
            }
            gameState.currentCard = gameState.deck.pop();
            gameState.currentColor = gameState.currentCard.color;
            document.getElementById("setup-panel").style.display = "none";
            document.getElementById("game-board").style.display = "block";
            broadcastState();
        }

        function playCard(cardIndex) {
            if(gameState.turn !== myIndex) return;

            let p = gameState.players[myIndex];
            let card = p.hand[cardIndex];

            if(card.color !== "black" && card.color !== gameState.currentColor && card.value !== gameState.currentCard.value) {
                alert("ورقة غير مطابقة!");
                return;
            }

            p.hand.splice(cardIndex, 1);
            gameState.currentCard = card;

            if(card.color === "black") {
                let chosenColor = prompt("اختر لوناً: (red, blue, green, yellow)", "red");
                gameState.currentColor = COLORS.includes(chosenColor) ? chosenColor : "red";
            } else {
                gameState.currentColor = card.color;
            }

            if(card.value === "Skip") nextTurn();
            else if(card.value === "+2") {
                nextTurn();
                for(let i=0; i<2; i++) gameState.players[gameState.turn].hand.push(gameState.deck.pop());
            } else if(card.value === "+4") {
                nextTurn();
                for(let i=0; i<4; i++) gameState.players[gameState.turn].hand.push(gameState.deck.pop());
            }

            nextTurn();

            if(isAI) { updateUI(); checkAITurn(); }
            else { broadcastState(); }
        }

        function drawCard() {
            if(gameState.turn !== myIndex) return;
            gameState.players[myIndex].hand.push(gameState.deck.pop());
            nextTurn();
            if(isAI) { updateUI(); checkAITurn(); }
            else { broadcastState(); }
        }

        function nextTurn() {
            gameState.turn = (gameState.turn + gameState.direction + 4) % 4;
        }

        function checkAITurn() {
            if(!isAI) return;
            let currentP = gameState.players[gameState.turn];
            if(currentP.isAI) {
                setTimeout(() => {
                    let playableIdx = currentP.hand.findIndex(c => c.color === "black" || c.color === gameState.currentColor || c.value === gameState.currentCard.value);
                    if(playableIdx !== -1) {
                        let c = currentP.hand.splice(playableIdx, 1)[0];
                        gameState.currentCard = c;
                        gameState.currentColor = (c.color === "black") ? COLORS[Math.floor(Math.random()*4)] : c.color;
                        if(c.value === "Skip") nextTurn();
                    } else {
                        currentP.hand.push(gameState.deck.pop());
                    }
                    nextTurn();
                    updateUI();
                    checkAITurn();
                }, 1000);
            }
        }

        function updateUI() {
            let statusHTML = "";
            gameState.players.forEach((p, idx) => {
                let isActive = (idx === gameState.turn) ? "active-turn" : "";
                statusHTML += `<div class="${isActive}">
                    <strong>${p.name}</strong><br>
                    الأوراق: ${p.hand ? p.hand.length : 0}
                </div>`;
            });
            document.getElementById("players-status").innerHTML = statusHTML;

            let topC = gameState.currentCard;
            let topElem = document.getElementById("top-card");
            topElem.className = `card ${gameState.currentColor || topC.color}`;
            topElem.innerText = topC.value;
            document.getElementById("color-indicator").style.backgroundColor = gameState.currentColor;

            let handHTML = "";
            let myHand = gameState.players[myIndex].hand || [];
            myHand.forEach((c, i) => {
                handHTML += `<div class="card ${c.color}" onclick="playCard(${i})">${c.value}</div>`;
            });
            document.getElementById("my-hand").innerHTML = handHTML;

            document.getElementById("game-log").innerText = (gameState.turn === myIndex) ? "👉 دورك للعب الآن!" : `دور اللاعب: ${gameState.players[gameState.turn].name}`;
        }
    </script>
</body>
</html>
"""

components.html(uno_p2p_html, height=650)