"""Pathfinding solver for finding optimal game moves."""

from typing import List, Tuple, Set, Optional
from src.models import CellType, RESOURCE_TYPES, GameConfig
from src.game import GameState


class PathSolver:
    """Solves for the best path to take in the current game state."""

    LOOKAHEAD_WEIGHT = 0.35
    HARVEST_CAP_BONUS = 40
    HARVEST_EARLY_USE_PENALTY = 40
    MAX_JELLY_PLACEMENT_SAMPLES = 10

    def __init__(self, game_state: GameState):
        self.game_state = game_state

    def find_optimal_path(self) -> Tuple[str, List[Tuple[int, int]], int, int]:
        """
        Find the best turn-start action (path move or harvest).

        Returns:
            (action, path, points_earned, resources_count)
            action is either "path" or "harvest"
        """
        start_pos = self.game_state.player_pos
        candidates: List[Tuple[str, List[Tuple[int, int]], int, int, float]] = []

        # Path candidates (one per locked color), evaluated with one-turn lookahead.
        for color in RESOURCE_TYPES:
            path, score, resources = self._find_best_path_for_color(start_pos, color)
            next_turn_score = self._estimate_next_turn_after_path(path)
            utility = score + (self.LOOKAHEAD_WEIGHT * next_turn_score)
            candidates.append(("path", path, score, resources, utility))

        # Harvest candidate, also evaluated with one-turn lookahead.
        self.game_state.refresh_harvest_charges()
        harvest_score = 0
        harvest_resources = 0
        if self.game_state.harvest_charges > 0:
            _, harvest_resources = self.game_state.get_most_abundant_resource()
            harvest_score = harvest_resources * 50
        if self.game_state.harvest_charges > 0 and harvest_resources > 0:
            next_turn_score = self._estimate_next_turn_after_harvest()
            harvest_utility = harvest_score + (self.LOOKAHEAD_WEIGHT * next_turn_score)

            if self.game_state.harvest_charges >= GameConfig.MAX_HARVEST_CHARGES:
                harvest_utility += self.HARVEST_CAP_BONUS
            else:
                harvest_utility -= self.HARVEST_EARLY_USE_PENALTY

            candidates.append(
                (
                    "harvest",
                    [start_pos],
                    harvest_score,
                    harvest_resources,
                    harvest_utility,
                )
            )

        if not candidates:
            return "path", [start_pos], 0, 0

        # Maximize long-term utility; tie-break by immediate score then resources.
        best = max(candidates, key=lambda c: (c[4], c[2], c[3]))
        return best[0], best[1], best[2], best[3]

    @staticmethod
    def _best_immediate_score(state: GameState) -> int:
        """Compute the best immediate score (no lookahead) for a given state."""
        solver = PathSolver(state)
        start_pos = state.player_pos
        best_score = 0

        for color in RESOURCE_TYPES:
            _, score, _ = solver._find_best_path_for_color(start_pos, color)
            if score > best_score:
                best_score = score

        state.refresh_harvest_charges()
        if state.harvest_charges > 0:
            _, harvest_resources = state.get_most_abundant_resource()
            best_score = max(best_score, harvest_resources * 50)

        return best_score

    def _estimate_next_turn_after_path(self, path: List[Tuple[int, int]]) -> float:
        """
        Simulate taking `path`, then estimate next-turn potential.

        If a jelly is spawned (10+ resources collected), its future position is uncertain;
        model this by evaluating possible jelly placements along the path and averaging.
        """
        if len(path) < 2:
            return 0.0

        sim_state = self.game_state.copy()
        _, _, jelly_pending = sim_state.execute_turn(path)

        if not jelly_pending:
            sim_state.apply_gravity()
            return float(self._best_immediate_score(sim_state))

        # Model uncertain jelly placement across path tiles (excluding start and endpoint).
        possible_positions: List[Tuple[int, int]] = []
        seen: Set[Tuple[int, int]] = set()
        for pos in path[1:-1]:
            if pos == sim_state.player_pos:
                continue
            if sim_state.grid[pos[0]][pos[1]] != CellType.EMPTY:
                continue
            if pos in seen:
                continue
            seen.add(pos)
            possible_positions.append(pos)

        if not possible_positions:
            sim_state.apply_gravity()
            return float(self._best_immediate_score(sim_state))

        sampled_positions = self._sample_positions(
            possible_positions, self.MAX_JELLY_PLACEMENT_SAMPLES
        )

        branch_scores: List[int] = []
        for pos in sampled_positions:
            branch = sim_state.copy()
            branch.grid[pos[0]][pos[1]] = CellType.JELLY
            branch.jellies.add(pos)
            branch.apply_gravity()
            branch_scores.append(self._best_immediate_score(branch))

        mean_score = sum(branch_scores) / len(branch_scores)
        conservative_score = min(branch_scores)
        return (0.7 * mean_score) + (0.3 * conservative_score)

    def _estimate_next_turn_after_harvest(self) -> float:
        """Simulate harvest now, then estimate next-turn immediate potential."""
        sim_state = self.game_state.copy()
        points, _, _ = sim_state.execute_harvest()
        if points <= 0:
            return 0.0
        sim_state.apply_gravity()
        return float(self._best_immediate_score(sim_state))

    @staticmethod
    def _sample_positions(
        positions: List[Tuple[int, int]], max_samples: int
    ) -> List[Tuple[int, int]]:
        """Return evenly spread samples from `positions` (deterministic)."""
        if len(positions) <= max_samples:
            return positions

        # Evenly sample indices from [0, len(positions)-1].
        last = len(positions) - 1
        sampled: List[Tuple[int, int]] = []
        for i in range(max_samples):
            idx = round((i * last) / (max_samples - 1))
            sampled.append(positions[idx])
        return sampled

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
