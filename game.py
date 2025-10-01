# game.py
# Contains the core logic for the Nexus Miners game, independent of the server or UI.

import random
from collections import deque
from typing import Dict, List, Tuple, Optional, Set, Any

# --- Constants for Game Balance ---
GRID_RADIUS = 4  # The size of the hex grid from the center to any edge. 3 is small, 5 is large.
BASE_AP_PER_TURN = 4  # Action Points each player gets at the start of their turn.
RESOURCE_BONUS_AP = 1  # Extra AP gained for each controlled resource node.
WIN_CONDITION_RESOURCES = 3  # Number of resource nodes required to win.

# --- Action Point Costs ---
COST_PLACE_CONDUIT = 1
COST_REINFORCE_CONDUIT = 2
COST_SABOTAGE_CONDUIT = 3

# --- Helper Data Structures & Types ---
# Using axial coordinates for the hex grid. 'q' and 'r' are the two axes.
# The third coordinate 's' is constrained by q + r + s = 0.
HexCoord = Tuple[int, int]  # (q, r)

# Represents an edge between two hexes. Stored as a sorted tuple to be canonical.
Edge = Tuple[HexCoord, HexCoord]

class Hex:
    """Represents a single hexagonal tile on the game board."""
    def __init__(self, q: int, r: int, resource: Optional[str] = None, is_base_for: Optional[str] = None):
        self.q = q
        self.r = r
        self.s = -q - r
        self.resource = resource  # e.g., 'IRON', 'POWER', 'CARBON', or 'NEXUS'
        self.is_base_for = is_base_for # Player ID of the owner of the base

    @property
    def coordinates(self) -> HexCoord:
        return (self.q, self.r)

    def __repr__(self):
        return f"Hex({self.q}, {self.r}, resource={self.resource})"

class Player:
    """Represents a player in the game."""
    def __init__(self, player_id: str, name: str, color: str):
        self.id = player_id
        self.name = name
        self.color = color
        self.action_points = 0
        self.base_hex: Optional[HexCoord] = None

    def __repr__(self):
        return f"Player({self.name}, AP:{self.action_points})"

class Board:
    """Manages the game board, including hexes, resources, and conduits."""
    def __init__(self, players: List[Player]):
        self.radius = GRID_RADIUS
        self.hexes: Dict[HexCoord, Hex] = {}
        self.conduits: Dict[Edge, Dict[str, Any]] = {}  # {edge: {"player_id": str, "reinforced": bool}}
        self._generate_grid()
        self._place_special_hexes(players)

    def _generate_grid(self):
        """Creates a hexagonal grid of the specified radius."""
        for q in range(-self.radius, self.radius + 1):
            for r in range(-self.radius, self.radius + 1):
                if -q - r in range(-self.radius, self.radius + 1):
                    self.hexes[(q, r)] = Hex(q, r)
    
    def _place_special_hexes(self, players: List[Player]):
        """Places the Nexus, player bases, and resources on the grid."""
        edge_hexes = [h for h in self.hexes.values() if max(abs(h.q), abs(h.r), abs(h.s)) == self.radius]
        internal_hexes = [h for h in self.hexes.values() if max(abs(h.q), abs(h.r), abs(h.s)) < self.radius]
        
        # Place Nexus in the center
        self.hexes[(0, 0)].resource = "NEXUS"

        # Place player bases on the edges, spaced out
        base_indices = [i * (len(edge_hexes) // len(players)) for i in range(len(players))]
        for i, player in enumerate(players):
            base_hex = edge_hexes[base_indices[i]]
            base_hex.is_base_for = player.id
            player.base_hex = base_hex.coordinates

        # Place resources on internal hexes
        potential_resource_spots = [h for h in internal_hexes if h.resource is None]
        random.shuffle(potential_resource_spots)
        
        resource_types = ["IRON", "CARBON", "POWER"]
        num_resource_nodes = min(len(potential_resource_spots), max(9, len(players) * 3))

        for i in range(num_resource_nodes):
            hex_to_place = potential_resource_spots[i]
            hex_to_place.resource = resource_types[i % len(resource_types)]

    def get_neighbors(self, hex_coord: HexCoord) -> List[HexCoord]:
        """Returns a list of valid neighbor coordinates for a given hex."""
        q, r = hex_coord
        # Directions in axial coordinates
        directions = [(1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1)]
        neighbors = []
        for dq, dr in directions:
            neighbor_coord = (q + dq, r + dr)
            if neighbor_coord in self.hexes:
                neighbors.append(neighbor_coord)
        return neighbors

class Game:
    """The main class that orchestrates the entire game."""
    def __init__(self, player_details: List[Dict[str, str]]):
        """
        Initializes the game.
        player_details: A list of dicts, e.g., [{"id": "xyz", "name": "Alpha", "color": "#ff0000"}]
        """
        self.players = [Player(p['id'], p['name'], p['color']) for p in player_details]
        self.board = Board(self.players)
        self.turn_number = 0
        self.current_player_idx = 0
        self.game_over = False
        self.winner: Optional[Player] = None
        self.message = "Game has started!"
        random.shuffle(self.players) # Randomize turn order
        self.start_turn()

    def get_current_player(self) -> Player:
        return self.players[self.current_player_idx]

    def start_turn(self):
        """Prepares for the start of the current player's turn."""
        self.turn_number += 1
        player = self.get_current_player()
        
        # Calculate AP
        controlled_resources = self._get_controlled_resources(player)
        bonus_ap = len(controlled_resources) * RESOURCE_BONUS_AP
        player.action_points = BASE_AP_PER_TURN + bonus_ap
        
        self.message = f"{player.name}'s turn. AP: {player.action_points}"
    
    def next_turn(self):
        """Advances the game to the next player's turn."""
        if self.game_over:
            return
            
        self.current_player_idx = (self.current_player_idx + 1) % len(self.players)
        self.start_turn()

    def handle_player_action(self, player_id: str, action: Dict[str, Any]) -> bool:
        """
        Main entry point for a player performing an action.
        Returns True if the action was successful, False otherwise.
        """
        player = self.get_current_player()
        if player.id != player_id or self.game_over:
            self.message = "Not your turn or game is over."
            return False

        action_type = action.get('type')
        action_handlers = {
            'place_conduit': self._handle_place_conduit,
            'reinforce_conduit': self._handle_reinforce_conduit,
            'sabotage_conduit': self._handle_sabotage_conduit,
        }

        handler = action_handlers.get(action_type)
        if not handler:
            self.message = "Invalid action type."
            return False

        success = handler(player, action)
        if success:
            if self._check_win_condition(player):
                self.game_over = True
                self.winner = player
                self.message = f"Game Over! {player.name} has connected to the Nexus and wins!"
        
        return success

    def _handle_place_conduit(self, player: Player, action: Dict) -> bool:
        if player.action_points < COST_PLACE_CONDUIT:
            self.message = "Not enough AP to place a conduit."
            return False
        
        hex1_coord = tuple(action['hex1'])
        hex2_coord = tuple(action['hex2'])
        edge = tuple(sorted((hex1_coord, hex2_coord)))

        # Validation
        if edge in self.board.conduits:
            self.message = "A conduit already exists there."
            return False
        if hex2_coord not in self.board.get_neighbors(hex1_coord):
            self.message = "Hexes are not adjacent."
            return False
        
        # Check if placement is adjacent to player's network
        is_adjacent_to_network = False
        if player.base_hex in edge:
            is_adjacent_to_network = True
        else:
            for existing_edge in self.board.conduits:
                if self.board.conduits[existing_edge]['player_id'] == player.id:
                    if hex1_coord in existing_edge or hex2_coord in existing_edge:
                        is_adjacent_to_network = True
                        break
        
        if not is_adjacent_to_network:
            self.message = "Must place conduits adjacent to your existing network."
            return False

        # Execute action
        player.action_points -= COST_PLACE_CONDUIT
        self.board.conduits[edge] = {"player_id": player.id, "reinforced": False}
        self.message = f"{player.name} placed a conduit."
        return True

    def _handle_reinforce_conduit(self, player: Player, action: Dict) -> bool:
        if player.action_points < COST_REINFORCE_CONDUIT:
            self.message = "Not enough AP to reinforce."
            return False

        edge = tuple(sorted((tuple(action['hex1']), tuple(action['hex2']))))
        conduit = self.board.conduits.get(edge)

        if not conduit or conduit['player_id'] != player.id:
            self.message = "You can only reinforce your own conduits."
            return False
        if conduit['reinforced']:
            self.message = "Conduit is already reinforced."
            return False
            
        player.action_points -= COST_REINFORCE_CONDUIT
        conduit['reinforced'] = True
        self.message = f"{player.name} reinforced a conduit."
        return True

    def _handle_sabotage_conduit(self, player: Player, action: Dict) -> bool:
        if player.action_points < COST_SABOTAGE_CONDUIT:
            self.message = "Not enough AP to sabotage."
            return False

        edge = tuple(sorted((tuple(action['hex1']), tuple(action['hex2']))))
        conduit = self.board.conduits.get(edge)

        if not conduit or conduit['player_id'] == player.id:
            self.message = "Cannot sabotage your own or non-existent conduits."
            return False
        if conduit['reinforced']:
            self.message = "Cannot sabotage a reinforced conduit."
            return False
            
        player.action_points -= COST_SABOTAGE_CONDUIT
        del self.board.conduits[edge]
        self.message = f"{player.name} sabotaged an opponent's conduit."
        return True

    def _get_player_network(self, player: Player) -> Set[HexCoord]:
        """Gets all hexes connected by a player's conduits."""
        player_conduits = {edge for edge, data in self.board.conduits.items() if data['player_id'] == player.id}
        network_hexes = set()
        if player_conduits:
            # Add all hexes that are part of the player's conduits
            for h1, h2 in player_conduits:
                network_hexes.add(h1)
                network_hexes.add(h2)
        return network_hexes

    def _is_connected(self, player: Player, start_node: HexCoord, end_node: HexCoord) -> bool:
        """Checks if two nodes are connected in the player's network using BFS."""
        player_conduits = {edge for edge, data in self.board.conduits.items() if data['player_id'] == player.id}
        if not player_conduits:
            return False

        q = deque([start_node])
        visited = {start_node}
        
        while q:
            current_hex = q.popleft()
            if current_hex == end_node:
                return True
            
            # Find neighbors connected by player's conduits
            for neighbor in self.board.get_neighbors(current_hex):
                edge = tuple(sorted((current_hex, neighbor)))
                if edge in player_conduits and neighbor not in visited:
                    visited.add(neighbor)
                    q.append(neighbor)
        return False
        
    def _get_controlled_resources(self, player: Player) -> Set[HexCoord]:
        """Finds all resource nodes connected to a player's base."""
        controlled = set()
        resource_hexes = [h for h in self.board.hexes.values() if h.resource and h.resource != "NEXUS"]
        for res_hex in resource_hexes:
            if self._is_connected(player, player.base_hex, res_hex.coordinates):
                controlled.add(res_hex.coordinates)
        return controlled

    def _check_win_condition(self, player: Player) -> bool:
        """Checks if the player has met the win conditions."""
        nexus_hex_coord = (0, 0)
        
        # 1. Check for Nexus connection
        connected_to_nexus = self._is_connected(player, player.base_hex, nexus_hex_coord)
        if not connected_to_nexus:
            return False

        # 2. Check for resource control
        num_controlled_resources = len(self._get_controlled_resources(player))
        if num_controlled_resources < WIN_CONDITION_RESOURCES:
            return False

        return True

    def get_game_state(self) -> Dict[str, Any]:
        """Serializes the entire game state into a dictionary for the frontend."""
        return {
            "players": [
                {
                    "id": p.id,
                    "name": p.name,
                    "color": p.color,
                    "action_points": p.action_points,
                    "base_hex": p.base_hex,
                    "controlled_resources": len(self._get_controlled_resources(p)),
                } for p in self.players
            ],
            "board": {
                "radius": self.board.radius,
                "hexes": [
                    {
                        "q": h.q,
                        "r": h.r,
                        "resource": h.resource,
                        "is_base_for": h.is_base_for,
                    } for h in self.board.hexes.values()
                ],
                "conduits": [
                    {
                        "hex1": edge[0],
                        "hex2": edge[1],
                        "player_id": data["player_id"],
                        "reinforced": data["reinforced"],
                    } for edge, data in self.board.conduits.items()
                ]
            },
            "turn_number": self.turn_number,
            "current_player_id": self.get_current_player().id,
            "game_over": self.game_over,
            "winner": self.winner.name if self.winner else None,
            "message": self.message,
        }