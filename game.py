"""Core game state and mechanics."""

from typing import List, Tuple, Set, Optional
import random

from models import CellType, GameConfig, RESOURCE_TYPES


class GameState:
    """Manages the game board, player position, score, and turn logic."""

    def __init__(self):
        self.grid_size = GameConfig.GRID_SIZE
        self.grid: List[List[CellType]] = [
            [CellType.EMPTY for _ in range(self.grid_size)]
            for _ in range(self.grid_size)
        ]
        self.player_pos = GameConfig.PLAYER_START_POS
        self.score = 0
        self.turn = 1
        self.jellies: Set[Tuple[int, int]] = set()  # Track jelly positions

    def is_valid_position(self, row: int, col: int) -> bool:
        """Check if position is within grid bounds."""
        return 0 <= row < self.grid_size and 0 <= col < self.grid_size

    def is_blocked(self, row: int, col: int) -> bool:
        """Check if a cell is blocked."""
        return self.grid[row][col] == CellType.BLOCKED

    def is_resource(self, row: int, col: int) -> bool:
        """Check if a cell contains a standard resource (not jelly, not empty/blocked)."""
        cell = self.grid[row][col]
        return cell in RESOURCE_TYPES

    def is_jelly(self, row: int, col: int) -> bool:
        """Check if a cell contains a rainbow jelly."""
        return self.grid[row][col] == CellType.JELLY

    def get_neighbors(self, row: int, col: int) -> List[Tuple[int, int]]:
        """Get all 8 adjacent positions (orthogonal + diagonal)."""
        neighbors = []
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                new_row, new_col = row + dr, col + dc
                if self.is_valid_position(new_row, new_col):
                    neighbors.append((new_row, new_col))
        return neighbors

    def validate_path(self, path: List[Tuple[int, int]]) -> Tuple[bool, str]:
        """
        Validate a path according to game rules.

        Rules:
        - At least 2 positions
        - Starts at player position
        - Consecutive positions are neighbors (8-connected)
        - No blocked cells in path
        - Cannot revisit tiles (except endpoint staying same)
        - Color-locking: all resources in a path must be same color,
          UNLESS a rainbow jelly is encountered, which unlocks for next move
        """
        if not path or len(path) < 2:
            return False, "Path must have at least 2 positions"

        if path[0] != self.player_pos:
            return False, "Path must start at player position"

        # Check path connectivity
        for i in range(len(path) - 1):
            if path[i + 1] not in self.get_neighbors(path[i][0], path[i][1]):
                return False, f"Path not connected at step {i + 1}"

        # Check no blocked cells
        for pos in path[1:]:  # Skip start position
            if self.is_blocked(pos[0], pos[1]):
                return False, f"Path goes through blocked cell at {pos}"

        # Check no revisiting tiles (except staying at same endpoint)
        visited = set()
        for i, pos in enumerate(path):
            if (
                pos in visited and i < len(path) - 1
            ):  # Can end on a tile, just not revisit
                return False, f"Cannot revisit tile at {pos}"
            visited.add(pos)

        # Check color locking with jelly support
        locked_color: Optional[CellType] = None
        for pos in path[1:]:  # Skip start position
            cell = self.grid[pos[0]][pos[1]]

            if self.is_jelly(pos[0], pos[1]):
                # Rainbow jelly unlocks color for next move
                locked_color = None
                continue

            if self.is_resource(pos[0], pos[1]):
                if locked_color is None:
                    locked_color = cell
                elif cell != locked_color:
                    return (
                        False,
                        f"Cannot collect different colors in one turn (unless separated by jelly)",
                    )

        # Check no revisiting start position
        if self.player_pos in path[1:]:
            return False, "Cannot pass back through starting position"

        return True, "Valid path"

    def execute_turn(self, path: List[Tuple[int, int]]) -> Tuple[int, int]:
        """
        Execute a turn, collecting resources and returning (points_earned, resources_collected).

        Only standard resources count toward points and collected count.
        Jellies do not contribute to these counts.

        Returns:
            (points_earned, resources_collected_count)
        """
        collected_positions = []
        resources_count = 0
        points = 0

        for pos in path[1:]:  # Skip start position
            if self.is_resource(pos[0], pos[1]):
                collected_positions.append(pos)
                resources_count += 1
                points += 50
            elif self.is_jelly(pos[0], pos[1]):
                # Jelly is collected but doesn't count for points/resources
                collected_positions.append(pos)
                self.jellies.discard(pos)

        # Remove collected resources and jellies
        for pos in collected_positions:
            self.grid[pos[0]][pos[1]] = CellType.EMPTY

        # Update player position
        self.player_pos = path[-1]
        self.score += points
        self.turn += 1

        # Check if we collected 10+ resources; if so, spawn a jelly
        if resources_count >= GameConfig.RESOURCES_FOR_JELLY:
            self._spawn_jelly(collected_positions)

        return points, resources_count

    def _spawn_jelly(self, cleared_positions: List[Tuple[int, int]]) -> None:
        """
        Spawn a rainbow jelly in a random cleared position.

        Args:
            cleared_positions: List of positions where resources were collected
        """
        if not cleared_positions:
            return

        # Choose a random cleared position
        spawn_pos = random.choice(cleared_positions)
        self.grid[spawn_pos[0]][spawn_pos[1]] = CellType.JELLY
        self.jellies.add(spawn_pos)

    def apply_gravity(self) -> None:
        """Apply gravity to make resources fall down in columns."""
        for col in range(self.grid_size):
            # Collect non-blocked, non-empty cells from bottom to top
            stable_cells = []
            for row in range(self.grid_size - 1, -1, -1):
                cell = self.grid[row][col]
                if cell != CellType.BLOCKED and cell != CellType.EMPTY:
                    stable_cells.append(cell)

            # Clear the column (except blocked cells)
            for row in range(self.grid_size):
                if self.grid[row][col] != CellType.BLOCKED:
                    self.grid[row][col] = CellType.EMPTY

            # Place stable cells from bottom up
            row = self.grid_size - 1
            for cell in stable_cells:
                # Find next available spot from bottom
                while row >= 0 and self.grid[row][col] != CellType.EMPTY:
                    row -= 1
                if row >= 0:
                    self.grid[row][col] = cell
                    row -= 1

    def copy(self) -> "GameState":
        """Create a deep copy of the game state (for solver simulations)."""
        new_state = GameState()
        new_state.grid = [row[:] for row in self.grid]
        new_state.player_pos = self.player_pos
        new_state.score = self.score
        new_state.turn = self.turn
        new_state.jellies = self.jellies.copy()
        return new_state
