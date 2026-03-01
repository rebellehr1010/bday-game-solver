"""GUI implementation with hotbar below the grid."""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Tuple, Optional

from models import CellType, GameConfig, HOTBAR_ITEMS, CELL_COLORS, Hotbar
from game import GameState
from solver import PathSolver

RAINBOW_STRIPE_COLORS = [
    "#FF0000",
    "#FF7F00",
    "#FFFF00",
    "#00FF00",
    "#0000FF",
    "#4B0082",
    "#9400D3",
]


class GameGUI:
    """Main GUI window managing game display and user interaction."""

    def __init__(self, root):
        self.root = root
        self.root.title("Birthday Game Solver")

        self.game_state = GameState()
        self.solver = PathSolver(self.game_state)
        self.hotbar = Hotbar()

        self.cell_size = GameConfig.CELL_SIZE
        self.mode = "placement"  # placement, play, place_jelly, game_over
        self.current_path: List[Tuple[int, int]] = []
        self.optimal_path: List[Tuple[int, int]] = []
        self.optimal_action: Optional[str] = None
        self.blocked_locked = False
        self.game_over = False

        self._setup_ui()
        self._draw_grid()
        self._enter_placement_mode(initial=True)
        self._update_score()

    def _setup_ui(self) -> None:
        """Initialize all UI components."""
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.columnconfigure(1, weight=1)

        # Left panel for stats and buttons
        left_panel = ttk.Frame(main_frame)
        left_panel.grid(row=0, column=0, sticky="ns")

        self.score_label = ttk.Label(left_panel, text="Score: 0", font=("Arial", 12))
        self.score_label.grid(row=0, column=0, sticky="w", pady=(0, 5))

        self.turn_label = ttk.Label(left_panel, text="Turn: 1", font=("Arial", 12))
        self.turn_label.grid(row=1, column=0, sticky="w", pady=(0, 5))

        self.harvest_label = ttk.Label(
            left_panel, text="Harvest: 0", font=("Arial", 12)
        )
        self.harvest_label.grid(row=2, column=0, sticky="w", pady=(0, 5))

        self.normal_collected_label = ttk.Label(
            left_panel, text="Normal Collected: 0", font=("Arial", 12)
        )
        self.normal_collected_label.grid(row=3, column=0, sticky="w", pady=(0, 10))

        self.optimal_label = ttk.Label(
            left_panel, text="Optimal: --", font=("Arial", 11), wraplength=180
        )
        self.optimal_label.grid(row=4, column=0, sticky="w", pady=(0, 10))

        self.execute_turn_button = ttk.Button(
            left_panel, text="Execute Turn", command=self._execute_turn
        )
        self.execute_turn_button.grid(row=5, column=0, sticky="ew", pady=(0, 5))

        self.finish_placement_button = ttk.Button(
            left_panel, text="Finish Placement", command=self._finish_placement
        )
        self.finish_placement_button.grid(row=6, column=0, sticky="ew", pady=(0, 5))

        # Right panel for board and hotbar
        right_panel = ttk.Frame(main_frame)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        canvas_frame = ttk.Frame(right_panel)
        canvas_frame.pack(side=tk.TOP, padx=10, pady=10)

        self.canvas = tk.Canvas(
            canvas_frame,
            width=self.cell_size * GameConfig.GRID_SIZE,
            height=self.cell_size * GameConfig.GRID_SIZE,
            bg="white",
        )
        self.canvas.pack()

        self.canvas.bind("<Button-1>", self._on_canvas_click)

        # Hotbar frame on bottom
        self._create_hotbar_panel(right_panel)

    def _create_hotbar_panel(self, parent) -> None:
        """Create the bottom hotbar panel with controls."""
        hotbar_panel = ttk.Frame(parent)
        hotbar_panel.pack(side=tk.TOP, padx=10, pady=10, fill=tk.X)

        # Hotbar label
        self.hotbar_label = ttk.Label(
            hotbar_panel, text="Hotbar", font=("Arial", 11, "bold")
        )
        self.hotbar_label.pack(anchor="w", pady=(0, 5))

        # Hotbar buttons frame
        self.hotbar_frame = ttk.Frame(hotbar_panel)
        self.hotbar_frame.pack(anchor="w", fill=tk.X, pady=(0, 5))

        self._create_hotbar_buttons()

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

    def _set_hotbar_allowed_items(self, allowed_items: Optional[set]) -> None:
        """Enable only the allowed hotbar items (or all if None)."""
        for item, btn in self.hotbar_buttons.items():
            if allowed_items is None or item in allowed_items:
                btn.config(state=tk.NORMAL)
            else:
                btn.config(state=tk.DISABLED)

        if allowed_items is not None:
            selected = self.hotbar.get_selected()
            if selected not in allowed_items:
                next_item = None
                for item in HOTBAR_ITEMS:
                    if item in allowed_items:
                        next_item = item
                        break
                if next_item is not None:
                    self.hotbar.select(next_item)
                    self._highlight_selected_hotbar()

    def _select_hotbar_item(self, item: CellType) -> None:
        """Handle hotbar item selection."""
        if self.mode == "placement":
            self.hotbar.select(item)
            self._highlight_selected_hotbar()
        elif self.mode == "place_jelly" and item == CellType.JELLY:
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

                if cell_type == CellType.JELLY:
                    stripe_height = (y2 - y1) / len(RAINBOW_STRIPE_COLORS)
                    for idx, color in enumerate(RAINBOW_STRIPE_COLORS):
                        sy1 = y1 + idx * stripe_height
                        sy2 = y1 + (idx + 1) * stripe_height
                        self.canvas.create_rectangle(
                            x1, sy1, x2, sy2, fill=color, outline=""
                        )
                else:
                    self.canvas.create_rectangle(
                        x1,
                        y1,
                        x2,
                        y2,
                        fill=hex_color,
                        outline="",
                        width=0,
                    )

                self.canvas.create_rectangle(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill="",
                    outline=outline_color,
                    width=outline_width,
                )

                # Draw icon
                if icon and cell_type != CellType.JELLY:
                    cx = (x1 + x2) / 2
                    cy = (y1 + y2) / 2
                    self.canvas.create_text(
                        cx, cy - 10, text=icon, font=("Arial", 12), fill="black"
                    )

                # Draw player marker
                if (row, col) == self.game_state.player_pos:
                    self.canvas.create_rectangle(
                        x1,
                        y1,
                        x2,
                        y2,
                        fill="red",
                        outline="darkred",
                        width=2,
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

        if self.mode == "placement":
            if (row, col) == self.game_state.player_pos:
                messagebox.showwarning(
                    "Invalid Placement", "Cannot place items on the player tile."
                )
                return
            if (
                self.blocked_locked
                and self.game_state.grid[row][col] == CellType.BLOCKED
            ):
                messagebox.showwarning(
                    "Locked Tile", "Blocked tiles are locked after initial placement."
                )
                return

            selected = self.hotbar.get_selected()
            if self.blocked_locked and selected == CellType.BLOCKED:
                messagebox.showwarning(
                    "Blocked Locked", "Blocked tiles can only be placed initially."
                )
                return

            if self.game_state.grid[row][col] == CellType.JELLY:
                self.game_state.jellies.discard((row, col))
            self.game_state.grid[row][col] = selected
            if selected == CellType.JELLY:
                self.game_state.jellies.add((row, col))
            self._draw_grid()

        elif self.mode == "place_jelly":
            self._place_jelly_at(row, col)

    def _execute_turn(self) -> None:
        """Execute the current path as a turn."""
        if self.mode != "play" or self.game_over:
            return

        if self.optimal_action is None:
            messagebox.showwarning("No Move", "No optimal move is available.")
            return

        if self.optimal_action == "harvest":
            self.game_state.refresh_harvest_charges()
            if self.game_state.harvest_charges <= 0:
                messagebox.showwarning("No Charges", "No harvest charges available.")
                return
            self.game_state.execute_harvest()
            self.game_state.apply_gravity()
            self._draw_grid()
            self._update_score()
            self._enter_placement_mode(initial=False)
            return

        if len(self.optimal_path) < 2:
            messagebox.showwarning("No Path", "No optimal path is available.")
            return

        valid, msg = self.game_state.validate_path(self.optimal_path)
        if not valid:
            messagebox.showerror("Invalid Path", msg)
            return

        self.current_path = self.optimal_path.copy()
        points, resources, jelly_pending = self.game_state.execute_turn(
            self.current_path
        )

        self.current_path = []
        self.optimal_path = []
        self._draw_grid()
        self._update_score()

        if self.game_state.turn > GameConfig.MAX_TURNS:
            self._end_game()
            return

        if jelly_pending:
            messagebox.showinfo(
                "Turn Executed",
                f"Points: {points}\nResources: {resources}\n"
                "Place the rainbow jelly before gravity applies.",
            )
            self._enter_jelly_placement()
        else:
            messagebox.showinfo(
                "Turn Executed", f"Points: {points}\nResources: {resources}"
            )
            self.game_state.apply_gravity()
            self._draw_grid()
            self._enter_placement_mode(initial=False)

    def _enter_placement_mode(self, initial: bool) -> None:
        """Switch to resource placement mode with hotbar."""
        if self.game_over:
            return
        self.mode = "placement"
        if initial:
            self.blocked_locked = False
        else:
            self.blocked_locked = True

        if not self.hotbar_frame.winfo_viewable():
            self.hotbar_frame.pack(anchor="w", fill=tk.X, pady=(0, 5))

        allowed_items = set(HOTBAR_ITEMS)
        if self.blocked_locked and CellType.BLOCKED in allowed_items:
            allowed_items.remove(CellType.BLOCKED)
        self._set_hotbar_allowed_items(allowed_items)

        self.finish_placement_button.config(state=tk.NORMAL)
        self.execute_turn_button.config(state=tk.DISABLED)
        self.optimal_action = None
        self.optimal_path = []
        self.current_path = []
        self.optimal_label.config(text="Optimal: --")
        self._draw_grid()

    def _finish_placement(self) -> None:
        """Validate the board and start the next turn."""
        if self.mode != "placement" or self.game_over:
            return
        if not self.game_state.is_board_filled():
            messagebox.showwarning(
                "Incomplete Board",
                "All tiles must be filled with resources or blocked tiles.",
            )
            return

        self.blocked_locked = True
        self.mode = "play"
        self.finish_placement_button.config(state=tk.DISABLED)
        self.execute_turn_button.config(state=tk.NORMAL)
        self.hotbar_frame.pack_forget()
        self._compute_optimal_move()

    def _enter_jelly_placement(self) -> None:
        """Switch to jelly placement mode before gravity."""
        self.mode = "place_jelly"
        if not self.hotbar_frame.winfo_viewable():
            self.hotbar_frame.pack(anchor="w", fill=tk.X, pady=(0, 5))
        self.hotbar.select(CellType.JELLY)
        self._highlight_selected_hotbar()
        self._set_hotbar_allowed_items({CellType.JELLY})
        self.finish_placement_button.config(state=tk.DISABLED)
        self.execute_turn_button.config(state=tk.DISABLED)

    def _place_jelly_at(self, row: int, col: int) -> None:
        """Place the pending jelly, apply gravity, then enter post-turn placement."""
        if (row, col) == self.game_state.player_pos:
            messagebox.showwarning(
                "Invalid Placement", "Cannot place jelly on the player tile."
            )
            return
        if self.game_state.grid[row][col] != CellType.EMPTY:
            messagebox.showwarning(
                "Invalid Placement", "Jelly must be placed on an empty tile."
            )
            return

        self.game_state.grid[row][col] = CellType.JELLY
        self.game_state.jellies.add((row, col))
        self.game_state.apply_gravity()
        self._draw_grid()
        self._enter_placement_mode(initial=False)

    def _compute_optimal_move(self) -> None:
        """Compute and display the optimal move for the current board."""
        if self.game_over:
            return

        action, path, score, resources = self.solver.find_optimal_path()
        self.optimal_action = action
        if action == "harvest":
            self.optimal_path = []
            self.current_path = []
            self.optimal_label.config(
                text=(f"Optimal: HARVEST\nPoints: {score}\nResources: {resources}")
            )
            self._draw_grid()
            return

        self.optimal_path = path
        self.current_path = path.copy()
        self.optimal_label.config(
            text=(f"Optimal: PATH\nPoints: {score}\nResources: {resources}")
        )
        self._draw_grid()

    def _end_game(self) -> None:
        """End the game after the final turn."""
        self.game_over = True
        self.mode = "game_over"
        self.execute_turn_button.config(state=tk.DISABLED)
        self.finish_placement_button.config(state=tk.DISABLED)
        self._set_hotbar_allowed_items(set())
        self.hotbar_frame.pack_forget()
        self.optimal_label.config(text="Optimal: --")
        messagebox.showinfo("Game Over", f"Final score: {self.game_state.score}")

    def _update_score(self) -> None:
        """Update the score display label."""
        display_turn = min(self.game_state.turn, GameConfig.MAX_TURNS)
        self.score_label.config(text=f"Score: {self.game_state.score}")
        self.turn_label.config(text=f"Turn: {display_turn}")
        self.harvest_label.config(text=f"Harvest: {self.game_state.harvest_charges}")
        self.normal_collected_label.config(
            text=(
                f"Normal Collected: {self.game_state.total_normal_resources_collected}"
            )
        )
