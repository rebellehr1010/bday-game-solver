"""Pathfinding solver for finding optimal game moves."""

from typing import List, Tuple, Set, Optional
from models import CellType, RESOURCE_TYPES
from game import GameState


class PathSolver:
    """Solves for the best path to take in the current game state."""

    def __init__(self, game_state: GameState):
        self.game_state = game_state

    def find_optimal_path(self) -> Tuple[List[Tuple[int, int]], int, int]:
        """
        Find the path that collects the most points.

        Returns:
            (path, points_earned, resources_count)
        """
        start_pos = self.game_state.player_pos
        best_path = [start_pos]
        best_score = 0
        best_resources = 0

        # Try paths for each resource color
        for color in RESOURCE_TYPES:
            path, score, resources = self._find_best_path_for_color(start_pos, color)
            if score > best_score:
                best_score = score
                best_path = path
                best_resources = resources

        return best_path, best_score, best_resources

    def _find_best_path_for_color(
        self, start: Tuple[int, int], color: CellType
    ) -> Tuple[List[Tuple[int, int]], int, int]:
        """
        Find the best path collecting only the specified color using DFS.

        The path can include jellies, which unlock color changes for the next move.

        Returns:
            (path, points_earned, resources_count)
        """
        best_path = [start]
        best_score = 0
        best_resources = 0

        def dfs(
            current_pos: Tuple[int, int],
            visited: Set[Tuple[int, int]],
            path: List[Tuple[int, int]],
            score: int,
            resources: int,
            locked_color: Optional[CellType],
        ):
            nonlocal best_path, best_score, best_resources

            if score > best_score or (
                score == best_score and resources > best_resources
            ):
                best_score = score
                best_resources = resources
                best_path = path.copy()

            # Try all neighbors
            for neighbor in self.game_state.get_neighbors(
                current_pos[0], current_pos[1]
            ):
                if neighbor in visited:
                    continue
                if neighbor == start:  # Can't revisit start
                    continue
                if self.game_state.is_blocked(neighbor[0], neighbor[1]):
                    continue

                # Check jelly
                if self.game_state.is_jelly(neighbor[0], neighbor[1]):
                    # Jelly doesn't contribute points but unlocks color
                    visited.add(neighbor)
                    path.append(neighbor)
                    dfs(neighbor, visited, path, score, resources, None)
                    path.pop()
                    visited.remove(neighbor)
                    continue

                # Check resource
                cell = self.game_state.grid[neighbor[0]][neighbor[1]]
                if self.game_state.is_resource(neighbor[0], neighbor[1]):
                    # Must match current locked color (if any)
                    if locked_color is not None and cell != locked_color:
                        continue

                    new_score = score + 50
                    new_resources = resources + 1
                    new_locked_color = (
                        locked_color if locked_color is not None else cell
                    )
                else:
                    # Empty space
                    new_score = score
                    new_resources = resources
                    new_locked_color = locked_color

                visited.add(neighbor)
                path.append(neighbor)
                dfs(neighbor, visited, path, new_score, new_resources, new_locked_color)
                path.pop()
                visited.remove(neighbor)

        visited = {start}
        dfs(start, visited, [start], 0, 0, color)

        return best_path, best_score, best_resources
