"""GUI implementation with hotbar and grid rendering."""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Tuple, Optional

from models import CellType, GameConfig, HOTBAR_ITEMS, CELL_COLORS, Hotbar
from game import GameState
from solver import PathSolver


class GameGUI:
    """Main GUI window managing game display and user interaction."""

    def __init__(self, root):
        self.root = root
        self.root.title("Birthday Game Solver")

        self.game_state = GameState()
        self.solver = PathSolver(self.game_state)
        self.hotbar = Hotbar()

        self.cell_size = GameConfig.CELL_SIZE
        self.mode = "setup"  # setup or play
        self.current_path: List[Tuple[int, int]] = []
        self.optimal_path: List[Tuple[int, int]] = []

        self._setup_ui()
        self._draw_grid()

    def _setup_ui(self) -> None:
        """Initialize all UI components."""
        # Control panel (top)
        self._create_control_panel()

        # Main content frame
        content_frame = ttk.Frame(self.root)
        content_frame.grid(row=1, column=0, columnspan=2, sticky="nsew")

        # Canvas on left
        canvas_frame = ttk.Frame(content_frame)
        canvas_frame.pack(side=tk.LEFT, padx=10, pady=10)

        self.canvas = tk.Canvas(
            canvas_frame,
            width=self.cell_size * GameConfig.GRID_SIZE,
            height=self.cell_size * GameConfig.GRID_SIZE,
            bg="white",
        )
        self.canvas.pack()

        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Button-3>", self._on_canvas_right_click)

        # Info panel on right
        self._create_info_panel(content_frame)

    def _create_control_panel(self) -> None:
        """Create the top control panel with mode indicator and buttons."""
        control_frame = ttk.Frame(self.root, padding="10")
        control_frame.grid(row=0, column=0, columnspan=2, sticky="ew")

        # Mode indicator
        self.mode_label = ttk.Label(
            control_frame, text="Mode: SETUP", font=("Arial", 12, "bold")
        )
        self.mode_label.pack(side=tk.LEFT, padx=5)

        # Score display
        self.score_label = ttk.Label(
            control_frame, text="Score: 0 | Turn: 1", font=("Arial", 12)
        )
        self.score_label.pack(side=tk.LEFT, padx=20)

        # Buttons
        ttk.Button(control_frame, text="Start Game", command=self._start_game).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(
            control_frame, text="Find Optimal Path", command=self._find_optimal
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Clear Path", command=self._clear_path).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(control_frame, text="Execute Turn", command=self._execute_turn).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(control_frame, text="Reset", command=self._reset_game).pack(
            side=tk.LEFT, padx=5
        )

    def _create_info_panel(self, parent) -> None:
        """Create the right-side info panel with hotbar and instructions."""
        info_frame = ttk.Frame(parent)
        info_frame.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.BOTH, expand=True)

        # Hotbar frame
        hotbar_label = ttk.Label(
            info_frame, text="Hotbar (Setup Mode)", font=("Arial", 11, "bold")
        )
        hotbar_label.pack(anchor="w", pady=(0, 5))

        self.hotbar_frame = ttk.Frame(info_frame)
        self.hotbar_frame.pack(anchor="w", fill=tk.X, pady=(0, 10))

        self._create_hotbar_buttons()

        # Instructions
        instructions_label = ttk.Label(
            info_frame, text="Instructions", font=("Arial", 11, "bold")
        )
        instructions_label.pack(anchor="w", pady=(10, 5))

        instructions_text = """
SETUP MODE:
- Click hotbar to select a tile type
- Click grid to place selected tile
- Right-click to set player start
- Click "Start Game" when ready

PLAY MODE:
- Click grid cells to build path
- Right-click to set player position
- "Find Optimal Path" to see best move
- "Execute Turn" to perform action
        """

        ttk.Label(info_frame, text=instructions_text, justify=tk.LEFT).pack(
            anchor="w", pady=(0, 10)
        )

    def _create_hotbar_buttons(self) -> None:
        """Create hotbar buttons for all cell types."""
        self.hotbar_buttons = {}

        for item in HOTBAR_ITEMS:
            hex_color, icon = CELL_COLORS[item]
            button_text = f"{item.name}\n{icon}" if icon else item.name

            btn = tk.Button(
                self.hotbar_frame,
                text=button_text,
                width=12,
                height=2,
                bg=hex_color,
                relief=tk.RAISED,
                command=lambda cell=item: self._select_hotbar_item(cell),
            )
            btn.pack(side=tk.LEFT, padx=2, pady=2)
            self.hotbar_buttons[item] = btn

        # Highlight the initially selected item
        self._highlight_selected_hotbar()

    def _select_hotbar_item(self, item: CellType) -> None:
        """Handle hotbar item selection."""
        if self.mode == "setup":
            self.hotbar.select(item)
            self._highlight_selected_hotbar()

    def _highlight_selected_hotbar(self) -> None:
        """Highlight the currently selected hotbar item."""
        for item, btn in self.hotbar_buttons.items():
            if item == self.hotbar.get_selected():
                btn.config(relief=tk.SUNKEN, width=12)
            else:
                btn.config(relief=tk.RAISED, width=12)

    def _draw_grid(self) -> None:
        """Redraw the grid display."""
        self.canvas.delete("all")

        # Draw cells
        for row in range(GameConfig.GRID_SIZE):
            for col in range(GameConfig.GRID_SIZE):
                x1 = col * self.cell_size
                y1 = row * self.cell_size
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size

                cell_type = self.game_state.grid[row][col]
                hex_color, icon = CELL_COLORS[cell_type]

                # Highlight if in optimal path
                outline_color = "lime"
                outline_width = 4
                if (row, col) not in self.optimal_path:
                    outline_color = "black"
                    outline_width = 1

                self.canvas.create_rectangle(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill=hex_color,
                    outline=outline_color,
                    width=outline_width,
                )

                # Draw icon
                if icon:
                    cx = (x1 + x2) / 2
                    cy = (y1 + y2) / 2
                    self.canvas.create_text(
                        cx, cy - 10, text=icon, font=("Arial", 12), fill="black"
                    )

                # Draw player marker
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

        # Draw current path
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

    def _on_canvas_click(self, event) -> None:
        """Handle left-click on canvas."""
        col = event.x // self.cell_size
        row = event.y // self.cell_size

        if not (0 <= row < GameConfig.GRID_SIZE and 0 <= col < GameConfig.GRID_SIZE):
            return

        if self.mode == "setup":
            # Place selected hotbar item
            selected = self.hotbar.get_selected()
            self.game_state.grid[row][col] = selected
            if selected == CellType.JELLY:
                self.game_state.jellies.add((row, col))
            self._draw_grid()

        elif self.mode == "play":
            # Build path
            if not self.current_path:
                if (row, col) == self.game_state.player_pos:
                    self.current_path.append((row, col))
            else:
                last_pos = self.current_path[-1]
                if (row, col) in self.game_state.get_neighbors(
                    last_pos[0], last_pos[1]
                ):
                    # Check if it's a new position or extending the path
                    if (row, col) not in self.current_path or (row, col) == last_pos:
                        self.current_path.append((row, col))

            self._draw_grid()

    def _on_canvas_right_click(self, event) -> None:
        """Handle right-click on canvas."""
        col = event.x // self.cell_size
        row = event.y // self.cell_size

        if not (0 <= row < GameConfig.GRID_SIZE and 0 <= col < GameConfig.GRID_SIZE):
            return

        if self.mode == "setup":
            self.game_state.player_pos = (row, col)
            self._draw_grid()
        elif self.mode == "play":
            # Allow repositioning in play mode for testing
            self.game_state.player_pos = (row, col)
            self.current_path = [(row, col)]
            self._draw_grid()

    def _start_game(self) -> None:
        """Start the game and switch to play mode."""
        self.mode = "play"
        self.mode_label.config(text="Mode: PLAY")
        self.hotbar_frame.pack_forget()  # Hide hotbar in play mode
        messagebox.showinfo(
            "Game Started", "Game started! Find paths and execute turns."
        )

    def _find_optimal(self) -> None:
        """Find and display the optimal path."""
        if self.mode != "play":
            messagebox.showwarning("Not in Play Mode", "Start the game first!")
            return

        path, score, resources = self.solver.find_optimal_path()
        self.optimal_path = path
        self.current_path = path.copy()
        self._draw_grid()
        messagebox.showinfo(
            "Optimal Path",
            f"Found path with {score} points ({resources} resources, {len(path) - 1} moves)",
        )

    def _clear_path(self) -> None:
        """Clear the current and optimal paths."""
        self.current_path = []
        self.optimal_path = []
        self._draw_grid()

    def _execute_turn(self) -> None:
        """Execute the current path as a turn."""
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

        points, resources = self.game_state.execute_turn(self.current_path)
        self.game_state.apply_gravity()

        # Show execution result
        jelly_msg = ""
        if resources >= GameConfig.RESOURCES_FOR_JELLY:
            jelly_msg = f"\n[Rainbow Jelly spawned! 10+ resources collected]"

        messagebox.showinfo(
            "Turn Executed", f"Points: {points}\nResources: {resources}{jelly_msg}"
        )

        self.current_path = []
        self.optimal_path = []
        self._draw_grid()
        self._update_score()

        # Prompt for new resources
        self._prompt_new_resources()

    def _prompt_new_resources(self) -> None:
        """Dialog to input new resources that appear after gravity."""
        dialog = tk.Toplevel(self.root)
        dialog.title("New Resources")
        dialog.geometry("400x300")

        ttk.Label(
            dialog,
            text="Enter new resources (format: row,col,LIGHT_BLUE|YELLOW|etc)",
            font=("Arial", 10),
        ).pack(pady=10)

        text_widget = tk.Text(dialog, width=40, height=10)
        text_widget.pack(pady=10, padx=10)

        def apply_resources():
            content = text_widget.get("1.0", tk.END).strip()
            if not content:
                dialog.destroy()
                return

            for line in content.split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    parts = line.split(",")
                    row = int(parts[0].strip())
                    col = int(parts[1].strip())
                    color_name = parts[2].strip()

                    # Convert name to CellType
                    try:
                        cell_type = CellType[color_name]
                        self.game_state.grid[row][col] = cell_type
                        if cell_type == CellType.JELLY:
                            self.game_state.jellies.add((row, col))
                    except KeyError:
                        messagebox.showerror(
                            "Invalid Color", f"Unknown color: {color_name}"
                        )
                        return
                except Exception as e:
                    messagebox.showerror("Parse Error", f"Could not parse line: {line}")
                    return

            dialog.destroy()
            self._draw_grid()

        ttk.Button(dialog, text="Apply", command=apply_resources).pack(pady=5)
        ttk.Button(dialog, text="Skip", command=dialog.destroy).pack(pady=5)

    def _update_score(self) -> None:
        """Update the score display label."""
        self.score_label.config(
            text=f"Score: {self.game_state.score} | Turn: {self.game_state.turn}"
        )

    def _reset_game(self) -> None:
        """Reset the game to initial state."""
        self.game_state = GameState()
        self.solver = PathSolver(self.game_state)
        self.hotbar = Hotbar()
        self.mode = "setup"
        self.mode_label.config(text="Mode: SETUP")
        self.current_path = []
        self.optimal_path = []
        self._update_score()

        # Show hotbar again
        if not self.hotbar_frame.winfo_viewable():
            self.hotbar_frame.pack(anchor="w", fill=tk.X, pady=(0, 10))

        self._draw_grid()
