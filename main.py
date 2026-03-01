import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Tuple, Set, Optional
from collections import deque
from enum import Enum


class CellType(Enum):
    EMPTY = 0
    BLOCKED = 1
    PINK = 2
    YELLOW = 3
    PURPLE = 4


class GameState:
    def __init__(self):
        self.grid_size = 7
        self.grid = [
            [CellType.EMPTY for _ in range(self.grid_size)]
            for _ in range(self.grid_size)
        ]
        self.player_pos = (6, 3)  # Middle bottom (row, col)
        self.score = 0
        self.turn = 1

    def is_valid_position(self, row: int, col: int) -> bool:
        return 0 <= row < self.grid_size and 0 <= col < self.grid_size

    def is_blocked(self, row: int, col: int) -> bool:
        return self.grid[row][col] == CellType.BLOCKED

    def is_resource(self, row: int, col: int) -> bool:
        cell = self.grid[row][col]
        return cell in [CellType.PINK, CellType.YELLOW, CellType.PURPLE]

    def get_neighbors(self, row: int, col: int) -> List[Tuple[int, int]]:
        """Get all 8 adjacent positions (orthogonal + diagonal)"""
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
        """Validate a path according to game rules"""
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

        # Check color locking
        locked_color = None
        for pos in path[1:]:  # Skip start position
            cell = self.grid[pos[0]][pos[1]]
            if self.is_resource(pos[0], pos[1]):
                if locked_color is None:
                    locked_color = cell
                elif cell != locked_color:
                    return False, f"Cannot collect different colors in one turn"

        # Check no revisiting start position
        if self.player_pos in path[1:]:
            return False, "Cannot pass back through starting position"

        return True, "Valid path"

    def execute_turn(self, path: List[Tuple[int, int]]) -> int:
        """Execute a turn, collecting resources and returning points earned"""
        collected_positions = []
        points = 0

        for pos in path[1:]:  # Skip start position
            if self.is_resource(pos[0], pos[1]):
                collected_positions.append(pos)
                points += 50

        # Remove collected resources
        for pos in collected_positions:
            self.grid[pos[0]][pos[1]] = CellType.EMPTY

        # Update player position
        self.player_pos = path[-1]
        self.score += points
        self.turn += 1

        return points

    def apply_gravity(self):
        """Apply gravity to make resources fall down in columns"""
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


class PathSolver:
    def __init__(self, game_state: GameState):
        self.game_state = game_state

    def find_optimal_path(self) -> Tuple[List[Tuple[int, int]], int]:
        """Find the path that collects the most points"""
        start_pos = self.game_state.player_pos
        best_path = [start_pos]
        best_score = 0

        # Try paths for each color
        for color in [CellType.PINK, CellType.YELLOW, CellType.PURPLE]:
            path, score = self._find_best_path_for_color(start_pos, color)
            if score > best_score:
                best_score = score
                best_path = path

        return best_path, best_score

    def _find_best_path_for_color(
        self, start: Tuple[int, int], color: CellType
    ) -> Tuple[List[Tuple[int, int]], int]:
        """Find the best path collecting only the specified color using DFS"""
        best_path = [start]
        best_score = 0

        def dfs(
            current_pos: Tuple[int, int],
            visited: Set[Tuple[int, int]],
            path: List[Tuple[int, int]],
            score: int,
        ):
            nonlocal best_path, best_score

            if score > best_score:
                best_score = score
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

                cell = self.game_state.grid[neighbor[0]][neighbor[1]]

                # If it's a resource, it must match our color
                if self.game_state.is_resource(neighbor[0], neighbor[1]):
                    if cell != color:
                        continue
                    new_score = score + 50
                else:
                    new_score = score

                visited.add(neighbor)
                path.append(neighbor)
                dfs(neighbor, visited, path, new_score)
                path.pop()
                visited.remove(neighbor)

        visited = {start}
        dfs(start, visited, [start], 0)

        return best_path, best_score


class GameGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Grid Game Solver")
        self.game_state = GameState()
        self.solver = PathSolver(self.game_state)

        self.cell_size = 60
        self.mode = "setup"  # setup or play
        self.current_path = []
        self.optimal_path = []

        self.setup_ui()
        self.draw_grid()

    def setup_ui(self):
        # Control panel
        control_frame = ttk.Frame(self.root, padding="10")
        control_frame.grid(row=0, column=0, columnspan=2, sticky="ew")

        self.mode_label = ttk.Label(
            control_frame, text="Mode: SETUP", font=("Arial", 12, "bold")
        )
        self.mode_label.pack(side=tk.LEFT, padx=5)

        self.score_label = ttk.Label(
            control_frame, text="Score: 0 | Turn: 1", font=("Arial", 12)
        )
        self.score_label.pack(side=tk.LEFT, padx=20)

        ttk.Button(control_frame, text="Start Game", command=self.start_game).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(
            control_frame, text="Find Optimal Path", command=self.find_optimal
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Clear Path", command=self.clear_path).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(control_frame, text="Execute Turn", command=self.execute_turn).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(control_frame, text="Reset", command=self.reset_game).pack(
            side=tk.LEFT, padx=5
        )

        # Setup panel
        setup_frame = ttk.LabelFrame(self.root, text="Setup Controls", padding="10")
        setup_frame.grid(row=1, column=1, padx=10, pady=10, sticky="n")

        ttk.Label(setup_frame, text="Left Click:").pack(anchor="w")
        ttk.Label(setup_frame, text="  - Blocked -> Pink").pack(anchor="w")
        ttk.Label(setup_frame, text="  - Pink -> Yellow").pack(anchor="w")
        ttk.Label(setup_frame, text="  - Yellow -> Purple").pack(anchor="w")
        ttk.Label(setup_frame, text="  - Purple -> Empty").pack(anchor="w")
        ttk.Label(setup_frame, text="  - Empty -> Blocked").pack(anchor="w")
        ttk.Label(setup_frame, text="").pack()
        ttk.Label(setup_frame, text="Right Click:").pack(anchor="w")
        ttk.Label(setup_frame, text="  - Set Player Start").pack(anchor="w")

        # Canvas for grid
        canvas_frame = ttk.Frame(self.root)
        canvas_frame.grid(row=1, column=0, padx=10, pady=10)

        self.canvas = tk.Canvas(
            canvas_frame,
            width=self.cell_size * 7,
            height=self.cell_size * 7,
            bg="white",
        )
        self.canvas.pack()

        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<Button-3>", self.on_canvas_right_click)

    def draw_grid(self):
        self.canvas.delete("all")

        colors = {
            CellType.EMPTY: "white",
            CellType.BLOCKED: "gray",
            CellType.PINK: "#FF69B4",
            CellType.YELLOW: "#FFD700",
            CellType.PURPLE: "#9370DB",
        }

        # Draw cells
        for row in range(7):
            for col in range(7):
                x1 = col * self.cell_size
                y1 = row * self.cell_size
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size

                cell_type = self.game_state.grid[row][col]
                color = colors[cell_type]

                # Highlight if in optimal path
                if (row, col) in self.optimal_path:
                    self.canvas.create_rectangle(
                        x1, y1, x2, y2, fill=color, outline="lime", width=4
                    )
                else:
                    self.canvas.create_rectangle(
                        x1, y1, x2, y2, fill=color, outline="black"
                    )

                # Draw player
                if (row, col) == self.game_state.player_pos:
                    cx = (x1 + x2) / 2
                    cy = (y1 + y2) / 2
                    self.canvas.create_oval(
                        cx - 15,
                        cy - 15,
                        cx + 15,
                        cy + 15,
                        fill="red",
                        outline="darkred",
                        width=2,
                    )
                    self.canvas.create_text(
                        cx, cy, text="P", font=("Arial", 16, "bold"), fill="white"
                    )

        # Draw path lines
        if len(self.current_path) > 1:
            for i in range(len(self.current_path) - 1):
                r1, c1 = self.current_path[i]
                r2, c2 = self.current_path[i + 1]
                x1 = c1 * self.cell_size + self.cell_size / 2
                y1 = r1 * self.cell_size + self.cell_size / 2
                x2 = c2 * self.cell_size + self.cell_size / 2
                y2 = r2 * self.cell_size + self.cell_size / 2
                self.canvas.create_line(
                    x1, y1, x2, y2, fill="blue", width=3, arrow=tk.LAST
                )

    def on_canvas_click(self, event):
        col = event.x // self.cell_size
        row = event.y // self.cell_size

        if not (0 <= row < 7 and 0 <= col < 7):
            return

        if self.mode == "setup":
            # Cycle through cell types
            current = self.game_state.grid[row][col]
            cycle = [
                CellType.BLOCKED,
                CellType.PINK,
                CellType.YELLOW,
                CellType.PURPLE,
                CellType.EMPTY,
            ]
            current_idx = cycle.index(current)
            self.game_state.grid[row][col] = cycle[(current_idx + 1) % len(cycle)]
            self.draw_grid()
        elif self.mode == "play":
            # Add to path if valid
            if not self.current_path:
                if (row, col) == self.game_state.player_pos:
                    self.current_path.append((row, col))
            else:
                last_pos = self.current_path[-1]
                if (row, col) in self.game_state.get_neighbors(
                    last_pos[0], last_pos[1]
                ):
                    if (row, col) not in self.current_path or (
                        row,
                        col,
                    ) == self.current_path[-1]:
                        self.current_path.append((row, col))
            self.draw_grid()

    def on_canvas_right_click(self, event):
        col = event.x // self.cell_size
        row = event.y // self.cell_size

        if not (0 <= row < 7 and 0 <= col < 7):
            return

        if self.mode == "setup":
            self.game_state.player_pos = (row, col)
            self.draw_grid()

    def start_game(self):
        self.mode = "play"
        self.mode_label.config(text="Mode: PLAY")
        messagebox.showinfo(
            "Game Started", "Game started! Find optimal paths and execute turns."
        )

    def find_optimal(self):
        if self.mode != "play":
            messagebox.showwarning("Not in Play Mode", "Start the game first!")
            return

        path, score = self.solver.find_optimal_path()
        self.optimal_path = path
        self.current_path = path.copy()
        self.draw_grid()
        messagebox.showinfo(
            "Optimal Path", f"Found path with {score} points ({len(path) - 1} moves)"
        )

    def clear_path(self):
        self.current_path = []
        self.optimal_path = []
        self.draw_grid()

    def execute_turn(self):
        if self.mode != "play":
            messagebox.showwarning("Not in Play Mode", "Start the game first!")
            return

        if len(self.current_path) < 2:
            messagebox.showwarning("No Path", "Create a path first!")
            return

        valid, msg = self.game_state.validate_path(self.current_path)
        if not valid:
            messagebox.showerror("Invalid Path", msg)
            return

        points = self.game_state.execute_turn(self.current_path)
        self.game_state.apply_gravity()

        self.current_path = []
        self.optimal_path = []
        self.draw_grid()
        self.update_score()

        # Prompt for new resources
        self.prompt_new_resources()

    def prompt_new_resources(self):
        """Dialog to input new resources after refill"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Enter New Resources")
        dialog.geometry("400x300")

        ttk.Label(
            dialog,
            text="Enter colors for new resources that appeared:",
            font=("Arial", 12),
        ).pack(pady=10)
        ttk.Label(
            dialog, text="Format: row,col,color (e.g., 0,3,pink)", font=("Arial", 9)
        ).pack()

        text_widget = tk.Text(dialog, width=40, height=10)
        text_widget.pack(pady=10)

        def apply_resources():
            content = text_widget.get("1.0", tk.END).strip()
            if not content:
                dialog.destroy()
                return

            color_map = {
                "pink": CellType.PINK,
                "yellow": CellType.YELLOW,
                "purple": CellType.PURPLE,
            }

            for line in content.split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    parts = line.split(",")
                    row = int(parts[0].strip())
                    col = int(parts[1].strip())
                    color_name = parts[2].strip().lower()

                    if color_name in color_map:
                        self.game_state.grid[row][col] = color_map[color_name]
                except:
                    messagebox.showerror("Parse Error", f"Could not parse line: {line}")

            dialog.destroy()
            self.draw_grid()

        ttk.Button(dialog, text="Apply", command=apply_resources).pack(pady=5)
        ttk.Button(dialog, text="Skip", command=dialog.destroy).pack()

    def update_score(self):
        self.score_label.config(
            text=f"Score: {self.game_state.score} | Turn: {self.game_state.turn}"
        )

    def reset_game(self):
        self.game_state = GameState()
        self.solver = PathSolver(self.game_state)
        self.mode = "setup"
        self.mode_label.config(text="Mode: SETUP")
        self.current_path = []
        self.optimal_path = []
        self.update_score()
        self.draw_grid()


def main():
    root = tk.Tk()
    app = GameGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
