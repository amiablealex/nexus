# app.py
# The main Flask web server application with SocketIO for real-time communication.

import uuid
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room

# Import the game engine from Part 1
from game import Game

# --- Server Setup ---
app = Flask(__name__)
# In a production environment, use a more secure and permanent secret key
app.config['SECRET_KEY'] = 'a-very-secret-and-temporary-key-for-dev'
# Allow any origin for easy development; tighten this in production
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Server State Management ---
# These dictionaries will store the state of all games and players on the server.
# games: {game_id: Game_Object}
games: dict = {}
# player_game_map: {player_sid: game_id}
player_game_map: dict = {}
# lobbies: {game_id: [list of player details]}
lobbies: dict = {}
# A simple way to manage the next available lobby
waiting_lobby_id = str(uuid.uuid4())
lobbies[waiting_lobby_id] = []

# --- Flask HTTP Route ---
@app.route('/')
def index():
    """Serves the main HTML file for the game."""
    return render_template('index.html')

# --- SocketIO Event Handlers ---
@socketio.on('connect')
def handle_connect():
    """A new player has connected. Their unique session ID is request.sid."""
    print(f"Client connected: {request.sid}")
    emit('connection_success', {'sid': request.sid})

@socketio.on('join_lobby')
def handle_join_lobby(data):
    """A player sends their name to join the waiting lobby."""
    player_name = data.get('name', 'Anonymous')
    player_sid = request.sid
    
    # Use the global waiting lobby ID
    game_id = waiting_lobby_id
    
    # Create player object for the lobby
    player_info = {
        'id': player_sid,
        'name': player_name,
        'color': f'hsl({len(lobbies[game_id]) * 90}, 70%, 50%)', # Assign a distinct color
        'is_ready': False
    }

    # Add player to lobby and map their session to the game
    lobbies[game_id].append(player_info)
    player_game_map[player_sid] = game_id
    join_room(game_id)
    
    print(f"Player {player_name} ({player_sid}) joined lobby {game_id}")
    
    # Broadcast the updated lobby list to all players in that lobby
    emit('lobby_update', lobbies[game_id], room=game_id)

@socketio.on('player_ready')
def handle_player_ready():
    """A player clicks the 'Ready' button."""
    player_sid = request.sid
    game_id = player_game_map.get(player_sid)
    
    if not game_id or game_id not in lobbies:
        return # Player not in a valid lobby

    # Mark the player as ready
    for player in lobbies[game_id]:
        if player['id'] == player_sid:
            player['is_ready'] = not player['is_ready'] # Toggle ready state
            break
            
    # Broadcast the change
    emit('lobby_update', lobbies[game_id], room=game_id)

    # Check if we can start the game
    # Conditions: 2-4 players, and all of them are ready.
    lobby = lobbies[game_id]
    players_ready = all(p['is_ready'] for p in lobby)
    player_count = len(lobby)

    if 2 <= player_count <= 4 and players_ready:
        print(f"Starting game {game_id} with {player_count} players.")
        
        # Create the game instance using the engine from game.py
        game = Game(player_details=lobby)
        games[game_id] = game
        
        # Move lobby from waiting to active and create a new waiting lobby
        del lobbies[game_id]
        global waiting_lobby_id
        waiting_lobby_id = str(uuid.uuid4())
        lobbies[waiting_lobby_id] = []
        
        # Send the initial game state to all players in the room
        socketio.emit('game_start', game.get_game_state(), room=game_id)

@socketio.on('player_action')
def handle_player_action(action_data):
    """Handles an action sent by a player during the game."""
    player_sid = request.sid
    game_id = player_game_map.get(player_sid)

    if not game_id or game_id not in games:
        return

    game = games[game_id]

    # Prevent actions if it's not the player's turn, unless it's an 'end_turn' action
    if game.get_current_player().id != player_sid:
        emit('action_error', {'message': "Not your turn."})
        return

    success = game.handle_player_action(player_sid, action_data)

    # If the action was valid, check for win. If not won, advance turn.
    if success:
        if not game.game_over:
            game.next_turn()

        # Broadcast the new state to all players
        socketio.emit('game_update', game.get_game_state(), room=game_id)
    else:
        # If the action was invalid, just send an update to the acting player
        emit('action_error', {'message': game.message})

@socketio.on('disconnect')
def handle_disconnect():
    """A player has disconnected."""
    player_sid = request.sid
    game_id = player_game_map.get(player_sid)
    print(f"Client disconnected: {player_sid}")
    
    # Clean up state
    if game_id:
        leave_room(game_id)
        if game_id in player_game_map:
            del player_game_map[player_sid]
        
        # Handle disconnection from a lobby
        if game_id in lobbies:
            lobbies[game_id] = [p for p in lobbies[game_id] if p['id'] != player_sid]
            # If lobby is now empty, could remove it, but for simplicity we'll leave it
            emit('lobby_update', lobbies[game_id], room=game_id)
        
        # TODO: Handle disconnection from an active game (e.g., mark player as disconnected,
        # allow for reconnection, or end the game if all players leave).
        # For this version, the game will continue but the player cannot rejoin.
            
# --- Main Execution ---
if __name__ == '__main__':
    # Use socketio.run() to start the development server
    # debug=True will auto-reload the server when code changes
    socketio.run(app, debug=True, port=5000)