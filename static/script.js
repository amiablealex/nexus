// script.js
// This file contains all the client-side logic to render the game and handle user interactions.

document.addEventListener('DOMContentLoaded', () => {
    const socket = io();

    // --- DOM Elements ---
    const lobbyView = document.getElementById('lobby-view');
    const gameView = document.getElementById('game-view');
    const playerNameInput = document.getElementById('player-name-input');
    const joinLobbyBtn = document.getElementById('join-lobby-btn');
    const lobbyPlayersContainer = document.getElementById('lobby-players-container');
    const playerList = document.getElementById('player-list');
    const playerReadyBtn = document.getElementById('player-ready-btn');
    const gameMessage = document.getElementById('game-message');
    const boardContainer = document.getElementById('board-container');
    const leftPlayerPanel = document.getElementById('left-player-panel');
    const rightPlayerPanel = document.getElementById('right-player-panel');
    const endTurnBtn = document.getElementById('end-turn-btn');
    const gameOverModal = document.getElementById('game-over-modal');
    const winnerAnnouncement = document.getElementById('winner-announcement');

    // --- Client State ---
    let playerSid = null;
    let gameState = null;

    // --- Socket Event Listeners ---
    socket.on('connection_success', (data) => {
        playerSid = data.sid;
        console.log('Connected to server with SID:', playerSid);
    });

    socket.on('lobby_update', (players) => {
        updateLobby(players);
    });

    socket.on('game_start', (initialGameState) => {
        console.log('Game is starting!', initialGameState);
        lobbyView.classList.add('hidden');
        gameView.classList.remove('hidden');
        updateUI(initialGameState);
    });
    
    socket.on('game_update', (newGameState) => {
        console.log('Received game update:', newGameState);
        updateUI(newGameState);
    });

    socket.on('action_error', (data) => {
        // Simple feedback for invalid actions
        gameMessage.textContent = data.message;
        setTimeout(() => {
            if (gameState) gameMessage.textContent = gameState.message;
        }, 2000);
    });

    // --- UI Update Functions ---
    function updateLobby(players) {
        playerList.innerHTML = '';
        players.forEach(p => {
            const li = document.createElement('li');
            li.style.borderLeft = `5px solid ${p.color}`;
            li.innerHTML = `
                <span>${p.name} ${p.id === playerSid ? '(You)' : ''}</span>
                <span class="status ${p.is_ready ? 'ready' : ''}">${p.is_ready ? 'Ready' : 'Waiting...'}</span>
            `;
            playerList.appendChild(li);
        });
    }

    function updateUI(state) {
        gameState = state;
        renderBoard(state.board);
        updatePlayerPanels(state.players, state.current_player_id);
        updateGameMessage(state.message);
        
        // Manage turn button
        if (!state.game_over && state.current_player_id === playerSid) {
            endTurnBtn.classList.remove('hidden');
            endTurnBtn.disabled = false;
        } else {
            endTurnBtn.classList.add('hidden');
        }
        
        checkGameOver(state);
    }
    
    function updatePlayerPanels(players, currentPlayerId) {
        leftPlayerPanel.innerHTML = '';
        rightPlayerPanel.innerHTML = '';
        
        players.forEach((p, index) => {
            const panel = (index < 2) ? leftPlayerPanel : rightPlayerPanel;
            const card = document.createElement('div');
            card.className = `player-card ${p.id === currentPlayerId ? 'active' : ''}`;
            card.innerHTML = `
                <div class="player-header">
                    <div class="player-color-dot" style="background-color: ${p.color};"></div>
                    <span class="player-name">${p.name} ${p.id === playerSid ? '(You)' : ''}</span>
                </div>
                <div class="player-stats">
                    <div>
                        <div class="stat">${p.action_points}</div>
                        <div class="stat-label">Action Points</div>
                    </div>
                    <div>
                        <div class="stat">${p.controlled_resources}</div>
                        <div class="stat-label">Resources</div>
                    </div>
                </div>
            `;
            panel.appendChild(card);
        });
    }

    function updateGameMessage(message) {
        gameMessage.textContent = message;
    }
    
    function checkGameOver(state) {
        if (state.game_over) {
            winnerAnnouncement.textContent = `${state.winner} Wins!`;
            gameOverModal.classList.remove('hidden');
            endTurnBtn.classList.add('hidden');
        }
    }

    // --- Board Rendering (SVG) ---
    function renderBoard(board) {
        const containerSize = boardContainer.getBoundingClientRect();
        const hexSize = (containerSize.width / (board.radius * 2 + 1)) / 1.75;
        const width = containerSize.width;
        const height = containerSize.height;
        const origin = { x: width / 2, y: height / 2 };

        let svg = `<svg width="${width}" height="${height}" viewbox="0 0 ${width} ${height}">`;

        // Render Edges (for clicking) and Conduits first (bottom layer)
        const drawnEdges = new Set();
        board.hexes.forEach(hex => {
            const p1 = hexToPixel({q: hex.q, r: hex.r}, hexSize, origin);
            // Get neighbors to draw edges
            const neighbors = getNeighbors({q: hex.q, r: hex.r});
            neighbors.forEach(n => {
                const edgeKey = JSON.stringify([...[hex, n].map(h => `${h.q},${h.r}`)].sort());
                if (!drawnEdges.has(edgeKey)) {
                    const p2 = hexToPixel(n, hexSize, origin);
                    
                    // Check if a conduit exists on this edge
                    const conduit = board.conduits.find(c => 
                        (c.hex1[0] === hex.q && c.hex1[1] === hex.r && c.hex2[0] === n.q && c.hex2[1] === n.r) ||
                        (c.hex2[0] === hex.q && c.hex2[1] === hex.r && c.hex1[0] === n.q && c.hex1[1] === n.r)
                    );

                    // Add clickable edge
                    svg += `<line class="edge" x1="${p1.x}" y1="${p1.y}" x2="${p2.x}" y2="${p2.y}" data-q1="${hex.q}" data-r1="${hex.r}" data-q2="${n.q}" data-r2="${n.r}"/>`;

                    if (conduit) {
                        const owner = gameState.players.find(p => p.id === conduit.player_id);
                        svg += `<line class="conduit ${conduit.reinforced ? 'reinforced' : ''}" x1="${p1.x}" y1="${p1.y}" x2="${p2.x}" y2="${p2.y}" style="stroke: ${owner.color};"/>`;
                    }
                    drawnEdges.add(edgeKey);
                }
            });
        });

        // Render Hexes (top layer)
        board.hexes.forEach(hex => {
            const center = hexToPixel({q: hex.q, r: hex.r}, hexSize, origin);
            const corners = hexCorners(center, hexSize);
            const points = corners.map(p => `${p.x},${p.y}`).join(' ');
            let hexClass = 'hex';
            if (hex.is_base_for) {
                hexClass += ' base';
                const owner = gameState.players.find(p => p.id === hex.is_base_for);
                if (owner) hexClass += ` player-${owner.id}`;
            }
            if (hex.resource) hexClass += ` resource-${hex.resource}`;

            svg += `<polygon class="${hexClass}" points="${points}" data-q="${hex.q}" data-r="${hex.r}"/>`;
            if (hex.resource) {
                 svg += `<text class="hex-text" x="${center.x}" y="${center.y + 5}">${hex.resource}</text>`;
            }
        });

        svg += '</svg>';
        boardContainer.innerHTML = svg;
    }
    
    // --- Hex Grid Helper Functions ---
    function hexToPixel(hex, size, origin) {
        const x = size * (3/2 * hex.q) + origin.x;
        const y = size * (Math.sqrt(3)/2 * hex.q + Math.sqrt(3) * hex.r) + origin.y;
        return { x, y };
    }

    function hexCorners(center, size) {
        const corners = [];
        for (let i = 0; i < 6; i++) {
            const angle_deg = 60 * i - 30;
            const angle_rad = Math.PI / 180 * angle_deg;
            corners.push({
                x: center.x + size * Math.cos(angle_rad),
                y: center.y + size * Math.sin(angle_rad)
            });
        }
        return corners;
    }
    
    function getNeighbors(hex) {
        const directions = [[1, 0], [0, 1], [-1, 1], [-1, 0], [0, -1], [1, -1]];
        return directions.map(d => ({ q: hex.q + d[0], r: hex.r + d[1] }));
    }


    // --- Event Handlers for User Input ---
    joinLobbyBtn.addEventListener('click', () => {
        const name = playerNameInput.value.trim();
        if (name) {
            socket.emit('join_lobby', { name });
            playerNameInput.parentElement.classList.add('hidden');
            lobbyPlayersContainer.classList.remove('hidden');
        }
    });

    playerReadyBtn.addEventListener('click', () => {
        socket.emit('player_ready');
    });
    
    endTurnBtn.addEventListener('click', () => {
        // A simple pass action for when the player is done
        socket.emit('player_action', {type: 'end_turn'});
        endTurnBtn.disabled = true; // Prevent spamming
    });

    boardContainer.addEventListener('click', (event) => {
        const target = event.target;
        if (target.classList.contains('edge')) {
            const { q1, r1, q2, r2 } = target.dataset;
            // TODO: Add menu for reinforce/sabotage. For now, click always places.
            socket.emit('player_action', {
                type: 'place_conduit',
                hex1: [parseInt(q1), parseInt(r1)],
                hex2: [parseInt(q2), parseInt(r2)]
            });
        }
    });

});