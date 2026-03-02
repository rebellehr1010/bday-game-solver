"""Pathfinding solver for finding optimal game moves."""

import time
from typing import Dict, List, Tuple, Set, Optional
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
        self._neighbors_by_index = self._build_neighbor_index_table()
        self._immediate_score_cache: Dict[Tuple, int] = {}
        self._solver_start_time: Optional[float] = None
        self._nodes_checked = 0

    def _build_neighbor_index_table(self) -> Dict[int, List[int]]:
        """Precompute neighbor indices for each board index."""
        size = self.game_state.grid_size
        table: Dict[int, List[int]] = {}
        for row in range(size):
            for col in range(size):
                idx = (row * size) + col
                neighbors: List[int] = []
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        nr = row + dr
                        nc = col + dc
                        if 0 <= nr < size and 0 <= nc < size:
                            neighbors.append((nr * size) + nc)
                table[idx] = neighbors
        return table

    def _state_cache_key(self, state: GameState) -> Tuple:
        """Build a deterministic hashable key for immediate-score cache."""
        flat_grid: List[int] = []
        for row in state.grid:
            for cell in row:
                flat_grid.append(cell.value)
        return (
            tuple(flat_grid),
            state.player_pos,
            state.total_normal_resources_collected,
            state.harvest_uses,
            state.pending_chests,
            state.total_materials_for_chest,
        )

    def find_optimal_path(self) -> Tuple[str, List[Tuple[int, int]], int, int]:
        """
        Find the best turn-start action (path move or harvest).

        Returns:
            (action, path, points_earned, resources_count)
            action is either "path" or "harvest"
        """
        self._solver_start_time = time.time()
        self._nodes_checked = 0
        self._immediate_score_cache = {}
        start_pos = self.game_state.player_pos
        candidates: List[Tuple[str, List[Tuple[int, int]], int, int, float]] = []

        print(f"\n[Solver] Starting path search...")

        # Path candidates (one per locked color), evaluated with one-turn lookahead.
        for color in RESOURCE_TYPES:
            path, score, resources = self._find_best_path_for_color(start_pos, color)
            next_turn_score = self._estimate_next_turn_after_path(path)
            utility = score + (self.LOOKAHEAD_WEIGHT * next_turn_score)
            candidates.append(("path", path, score, resources, utility))
            elapsed = time.time() - self._solver_start_time
            print(
                f"[Solver] Checked {color.name}: score={score}, utility={utility:.2f}"
                f" | Elapsed: {elapsed:.2f}s | Nodes: {self._nodes_checked}"
            )

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
            elapsed = time.time() - self._solver_start_time
            print(f"[Solver] No candidates found. Time: {elapsed:.2f}s")
            return "path", [start_pos], 0, 0

        # Maximize long-term utility; tie-break by immediate score then resources.
        best = max(candidates, key=lambda c: (c[4], c[2], c[3]))
        elapsed = time.time() - self._solver_start_time
        print(
            f"[Solver] BEST: {best[0].upper()} utility={best[4]:.2f} score={best[2]} "
            f"| Total time: {elapsed:.2f}s | Total nodes: {self._nodes_checked}\n"
        )
        return best[0], best[1], best[2], best[3]

    def _best_immediate_score(self, state: GameState) -> int:
        """Compute the best immediate score (no lookahead) for a given state."""
        key = self._state_cache_key(state)
        cached = self._immediate_score_cache.get(key)
        if cached is not None:
            return cached

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

        self._immediate_score_cache[key] = best_score
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
        _, _, jelly_pending, chest_pending = sim_state.execute_turn(path)

        if not jelly_pending and chest_pending <= 0:
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

            occupied = set()
            if jelly_pending:
                branch.grid[pos[0]][pos[1]] = CellType.JELLY
                branch.jellies.add(pos)
                occupied.add(pos)

            if chest_pending > 0:
                chest_positions = [p for p in sampled_positions if p not in occupied]
                for chest_pos in chest_positions[:chest_pending]:
                    branch.grid[chest_pos[0]][chest_pos[1]] = CellType.CHEST
                    branch.chests.add(chest_pos)

            branch.apply_gravity()
            branch_scores.append(self._best_immediate_score(branch))

        mean_score = sum(branch_scores) / len(branch_scores)
        conservative_score = min(branch_scores)
        return (0.7 * mean_score) + (0.3 * conservative_score)

    def _estimate_next_turn_after_harvest(self) -> float:
        """Simulate harvest now, then estimate next-turn immediate potential."""
        sim_state = self.game_state.copy()
        points, _, _, chest_pending = sim_state.execute_harvest()
        if points <= 0:
            return 0.0
        if chest_pending <= 0:
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
        size = self.game_state.grid_size
        grid = self.game_state.grid
        start_idx = (start[0] * size) + start[1]

        best_path_idx = [start_idx]
        best_score = 0
        best_resources = 0

        resource_types = set(RESOURCE_TYPES)

        total_resources = 0
        total_chests = 0
        for row in range(size):
            for col in range(size):
                if (row, col) == start:
                    continue
                cell = grid[row][col]
                if cell in resource_types:
                    total_resources += 1
                elif cell == CellType.CHEST:
                    total_chests += 1

        def better_candidate(score: int, resources: int) -> bool:
            is_better = (score > best_score) or (
                score == best_score and resources > best_resources
            )
            if is_better and self._solver_start_time is not None:
                elapsed = time.time() - self._solver_start_time
                print(
                    f"  [Update] New best for {color.name}: score={score} resources={resources} "
                    f"| {elapsed:.2f}s elapsed | {self._nodes_checked} nodes"
                )
            return is_better

        seen_states: Set[Tuple[int, int, int]] = set()

        def dfs(
            current_idx: int,
            visited_mask: int,
            path_idx: List[int],
            score: int,
            resources: int,
            chests: int,
            locked_color: Optional[CellType],
            rem_resources: int,
            rem_chests: int,
        ) -> None:
            nonlocal best_path_idx, best_score, best_resources
            self._nodes_checked += 1

            if better_candidate(score, resources):
                best_score = score
                best_resources = resources
                best_path_idx = path_idx.copy()

            locked_value = -1 if locked_color is None else locked_color.value
            state_key = (current_idx, visited_mask, locked_value)
            if state_key in seen_states:
                return
            seen_states.add(state_key)

            max_total_resources = resources + rem_resources
            max_total_chests = max(
                0, (max_total_resources // GameConfig.CHEST_COST_RESOURCES) - chests
            )
            chest_gain_cap = min(rem_chests, max_total_chests)
            optimistic_score = (
                score
                + (rem_resources * 50)
                + (chest_gain_cap * GameConfig.CHEST_SCORE_BONUS)
            )

            if optimistic_score < best_score:
                return
            if optimistic_score == best_score and max_total_resources <= best_resources:
                return

            chest_moves: List[int] = []
            resource_moves: List[int] = []
            jelly_moves: List[int] = []
            empty_moves: List[int] = []

            for neighbor_idx in self._neighbors_by_index[current_idx]:
                if neighbor_idx == start_idx:
                    continue
                if (visited_mask >> neighbor_idx) & 1:
                    continue

                row = neighbor_idx // size
                col = neighbor_idx % size
                cell = grid[row][col]

                if cell == CellType.BLOCKED:
                    continue

                if cell == CellType.CHEST:
                    chest_moves.append(neighbor_idx)
                elif cell in resource_types:
                    if locked_color is not None and cell != locked_color:
                        continue
                    resource_moves.append(neighbor_idx)
                elif cell == CellType.JELLY:
                    jelly_moves.append(neighbor_idx)
                else:
                    empty_moves.append(neighbor_idx)

            ordered_moves = chest_moves + resource_moves + jelly_moves + empty_moves

            for neighbor_idx in ordered_moves:
                row = neighbor_idx // size
                col = neighbor_idx % size
                cell = grid[row][col]

                next_score = score
                next_resources = resources
                next_chests = chests
                next_locked = locked_color
                next_rem_resources = rem_resources
                next_rem_chests = rem_chests

                if cell == CellType.CHEST:
                    effective_resources = resources - (
                        chests * GameConfig.CHEST_COST_RESOURCES
                    )
                    if effective_resources < GameConfig.CHEST_COST_RESOURCES:
                        continue
                    next_score += GameConfig.CHEST_SCORE_BONUS
                    next_chests += 1
                    next_rem_chests -= 1
                elif cell in resource_types:
                    next_score += 50
                    next_resources += 1
                    next_rem_resources -= 1
                    if locked_color is None:
                        next_locked = cell
                elif cell == CellType.JELLY:
                    next_locked = None

                next_visited = visited_mask | (1 << neighbor_idx)
                path_idx.append(neighbor_idx)
                dfs(
                    neighbor_idx,
                    next_visited,
                    path_idx,
                    next_score,
                    next_resources,
                    next_chests,
                    next_locked,
                    next_rem_resources,
                    next_rem_chests,
                )
                path_idx.pop()

        dfs(
            start_idx,
            (1 << start_idx),
            [start_idx],
            0,
            0,
            0,
            color,
            total_resources,
            total_chests,
        )
        elapsed = time.time() - (self._solver_start_time or time.time())
        print(
            f"  [Search] DFS complete for {color.name}: best_score={best_score} "
            f"best_resources={best_resources} | {elapsed:.2f}s"
        )

        best_path: List[Tuple[int, int]] = []
        for idx in best_path_idx:
            best_path.append((idx // size, idx % size))

        return best_path, best_score, best_resources
