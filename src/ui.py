"""GUI implementation with hotbar below the grid."""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Tuple, Optional, Dict
import os
from PIL import Image, ImageTk, ImageOps

from src.models import CellType, GameConfig, HOTBAR_ITEMS, CELL_COLORS, Hotbar
from src.game import GameState
from src.solver import PathSolver

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
        self.mode = "placement"  # placement, play, place_bonus, game_over
        self.current_path: List[Tuple[int, int]] = []
        self.optimal_path: List[Tuple[int, int]] = []
        self.optimal_action: Optional[str] = None
        self.blocked_locked = False
        self.game_over = False
        self.pending_jelly = False
        self.pending_chests = 0

        # Load images
        self._load_images()

        self._setup_ui()
        self._draw_grid()
        self._enter_placement_mode(initial=True)
        self._update_score()

    def _load_images(self) -> None:
        """Load all tile images and create greyscale versions."""
        assets_dir = os.path.join(os.path.dirname(__file__), "assets")

        # Mapping from CellType to filename
        image_map = {
            CellType.BLOCKED: "blocked.jpg",
            CellType.LIGHT_BLUE: "light_blue.jpg",
            CellType.YELLOW: "yellow.jpg",
            CellType.PINK: "pink.jpg",
            CellType.PURPLE: "purple.jpg",
            CellType.BRIGHT_PINK: "light_pink.jpg",
            CellType.DARK_BLUE: "dark_blue.jpg",
            CellType.JELLY: "rainbow.jpg",
            CellType.CHEST: "lucky_chest.jpg",
        }

        self.tile_images: Dict[CellType, ImageTk.PhotoImage] = {}
        self.tile_images_grey: Dict[CellType, ImageTk.PhotoImage] = {}
        self.tile_images_canvas: Dict[CellType, ImageTk.PhotoImage] = {}

        size = (self.cell_size, self.cell_size)

        for cell_type, filename in image_map.items():
            path = os.path.join(assets_dir, filename)
            img = Image.open(path)

            # Resize for hotbar buttons and canvas (60x60)
            img_resized = img.resize(size, Image.Resampling.LANCZOS)
            self.tile_images[cell_type] = ImageTk.PhotoImage(img_resized)
            self.tile_images_canvas[cell_type] = ImageTk.PhotoImage(img_resized)

            # Create greyscale version for disabled buttons
            img_grey = ImageOps.grayscale(img_resized)
            img_grey_rgb = Image.new("RGB", img_grey.size)
            img_grey_rgb.paste(img_grey)
            self.tile_images_grey[cell_type] = ImageTk.PhotoImage(img_grey_rgb)

        # Load player image (slightly smaller to fit within gridlines)
        player_path = os.path.join(assets_dir, "player.jpg")
        player_size = (
            self.cell_size - 4,
            self.cell_size - 4,
        )  # 4px smaller for gridline padding
        try:
            player_img = Image.open(player_path).resize(
                player_size, Image.Resampling.LANCZOS
            )
            self.player_image = ImageTk.PhotoImage(player_img)
        except Exception as e:
            print(f"Warning: Could not load player.jpg: {e}")
            # Create a simple red square as fallback
            player_img = Image.new("RGB", player_size, "red")
            self.player_image = ImageTk.PhotoImage(player_img)

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

        self.chest_pending_label = ttk.Label(
            left_panel, text="Chests Pending: 0", font=("Arial", 12)
        )
        self.chest_pending_label.grid(row=4, column=0, sticky="w", pady=(0, 5))

        self.chest_progress_label = ttk.Label(
            left_panel, text="Chest Progress: 0/30", font=("Arial", 12)
        )
        self.chest_progress_label.grid(row=5, column=0, sticky="w", pady=(0, 10))

        self.execute_turn_button = ttk.Button(
            left_panel, text="Execute Turn", command=self._execute_turn
        )
        self.execute_turn_button.grid(row=6, column=0, sticky="ew", pady=(0, 5))

        self.finish_placement_button = ttk.Button(
            left_panel, text="Finish Placement", command=self._finish_placement
        )
        self.finish_placement_button.grid(row=7, column=0, sticky="ew", pady=(0, 5))

        self.optimal_label = ttk.Label(
            left_panel, text="Optimal: --", font=("Arial", 11), wraplength=180
        )
        self.optimal_label.grid(row=9, column=0, sticky="w", pady=(10, 0))

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
        """Create the bottom hotbar panel with controls (always visible)."""
        hotbar_panel = ttk.Frame(parent)
        hotbar_panel.pack(side=tk.TOP, padx=10, pady=10, fill=tk.X)

        # Hotbar label
        self.hotbar_label = ttk.Label(
            hotbar_panel, text="Hotbar", font=("Arial", 11, "bold")
        )
        self.hotbar_label.pack(anchor="w", pady=(0, 5))

        # Hotbar buttons frame - 2 rows
        self.hotbar_frame = ttk.Frame(hotbar_panel)
        self.hotbar_frame.pack(anchor="w", fill=tk.X, pady=(0, 5))

        self._create_hotbar_buttons()

    def _create_hotbar_buttons(self) -> None:
        """Create hotbar buttons: blocked/jelly on left, gap, then 2x3 grid of resources."""
        self.hotbar_buttons = {}

        # Left column: BLOCKED and JELLY stacked vertically
        left_frame = ttk.Frame(self.hotbar_frame)
        left_frame.pack(side=tk.LEFT, padx=(0, 2))

        btn_blocked = tk.Button(
            left_frame,
            image=self.tile_images[CellType.BLOCKED],
            relief=tk.RAISED,
            borderwidth=2,
            command=lambda: self._select_hotbar_item(CellType.BLOCKED),
        )
        btn_blocked.pack(side=tk.TOP, padx=2, pady=2)
        self.hotbar_buttons[CellType.BLOCKED] = btn_blocked

        btn_jelly = tk.Button(
            left_frame,
            image=self.tile_images[CellType.JELLY],
            relief=tk.RAISED,
            borderwidth=2,
            command=lambda: self._select_hotbar_item(CellType.JELLY),
        )
        btn_jelly.pack(side=tk.TOP, padx=2, pady=2)
        self.hotbar_buttons[CellType.JELLY] = btn_jelly

        btn_chest = tk.Button(
            left_frame,
            image=self.tile_images[CellType.CHEST],
            relief=tk.RAISED,
            borderwidth=2,
            command=lambda: self._select_hotbar_item(CellType.CHEST),
        )
        btn_chest.pack(side=tk.TOP, padx=2, pady=2)
        self.hotbar_buttons[CellType.CHEST] = btn_chest

        # Spacer column (empty gap)
        spacer_frame = ttk.Frame(self.hotbar_frame, width=20)
        spacer_frame.pack(side=tk.LEFT)

        # Right side: 2x3 grid of resources
        right_frame = ttk.Frame(self.hotbar_frame)
        right_frame.pack(side=tk.LEFT)

        # Top row: YELLOW, PINK, PURPLE
        row1_frame = ttk.Frame(right_frame)
        row1_frame.pack(side=tk.TOP)

        row1_items = [CellType.YELLOW, CellType.PINK, CellType.PURPLE]
        for item in row1_items:
            btn = tk.Button(
                row1_frame,
                image=self.tile_images[item],
                relief=tk.RAISED,
                borderwidth=2,
                command=lambda cell=item: self._select_hotbar_item(cell),
            )
            btn.pack(side=tk.LEFT, padx=2, pady=2)
            self.hotbar_buttons[item] = btn

        # Bottom row: LIGHT_BLUE, BRIGHT_PINK, DARK_BLUE
        row2_frame = ttk.Frame(right_frame)
        row2_frame.pack(side=tk.TOP)

        row2_items = [CellType.LIGHT_BLUE, CellType.BRIGHT_PINK, CellType.DARK_BLUE]
        for item in row2_items:
            btn = tk.Button(
                row2_frame,
                image=self.tile_images[item],
                relief=tk.RAISED,
                borderwidth=2,
                command=lambda cell=item: self._select_hotbar_item(cell),
            )
            btn.pack(side=tk.LEFT, padx=2, pady=2)
            self.hotbar_buttons[item] = btn

        # Highlight the initially selected item
        self._highlight_selected_hotbar()

    def _set_hotbar_allowed_items(self, allowed_items: Optional[set]) -> None:
        """Enable only the allowed hotbar items (or all if None), using greyscale for disabled."""
        for item, btn in self.hotbar_buttons.items():
            if allowed_items is None or item in allowed_items:
                btn.config(state=tk.NORMAL, image=self.tile_images[item])
            else:
                btn.config(state=tk.DISABLED, image=self.tile_images_grey[item])

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
        elif self.mode == "place_bonus" and item in {CellType.JELLY, CellType.CHEST}:
            self.hotbar.select(item)
            self._highlight_selected_hotbar()

    def _highlight_selected_hotbar(self) -> None:
        """Highlight the currently selected hotbar item."""
        for item, btn in self.hotbar_buttons.items():
            if item == self.hotbar.get_selected():
                btn.config(relief=tk.SUNKEN, borderwidth=4)
            else:
                btn.config(relief=tk.RAISED, borderwidth=2)

    def _draw_grid(self) -> None:
        """Redraw the grid display using images."""
        self.canvas.delete("all")

        # Draw cells
        for row in range(GameConfig.GRID_SIZE):
            for col in range(GameConfig.GRID_SIZE):
                x1 = col * self.cell_size
                y1 = row * self.cell_size
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size

                cell_type = self.game_state.grid[row][col]

                # Draw tile image (if not empty)
                if cell_type != CellType.EMPTY:
                    self.canvas.create_image(
                        x1, y1, image=self.tile_images_canvas[cell_type], anchor=tk.NW
                    )
                else:
                    # Draw empty cell as white rectangle
                    self.canvas.create_rectangle(
                        x1, y1, x2, y2, fill="white", outline=""
                    )

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
                    fill="",
                    outline=outline_color,
                    width=outline_width,
                )

                # Draw player marker
                if (row, col) == self.game_state.player_pos:
                    # Inset by 2 pixels to fit within gridlines
                    self.canvas.create_image(
                        x1 + 2, y1 + 2, image=self.player_image, anchor=tk.NW
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
            if self.game_state.grid[row][col] == CellType.CHEST:
                self.game_state.chests.discard((row, col))
            self.game_state.grid[row][col] = selected
            if selected == CellType.JELLY:
                self.game_state.jellies.add((row, col))
            if selected == CellType.CHEST:
                self.game_state.chests.add((row, col))
            self._draw_grid()

        elif self.mode == "place_bonus":
            self._place_bonus_at(row, col)

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
            _, _, _, chest_pending = self.game_state.execute_harvest()
            self._draw_grid()
            if chest_pending > 0:
                self._enter_bonus_placement(False, chest_pending)
            else:
                self.game_state.apply_gravity()
                self._draw_grid()
                self._enter_placement_mode(initial=False)
            self._update_score()
            return

        if len(self.optimal_path) < 2:
            messagebox.showwarning("No Path", "No optimal path is available.")
            return

        valid, msg = self.game_state.validate_path(self.optimal_path)
        if not valid:
            messagebox.showerror("Invalid Path", msg)
            return

        self.current_path = self.optimal_path.copy()
        _, _, jelly_pending, chest_pending = self.game_state.execute_turn(
            self.current_path
        )

        self.current_path = []
        self.optimal_path = []
        self._draw_grid()
        self._update_score()

        if self.game_state.turn > GameConfig.MAX_TURNS:
            self._end_game()
            return

        if jelly_pending or chest_pending > 0:
            self._enter_bonus_placement(jelly_pending, chest_pending)
        else:
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

        # Hotbar is always visible, just update allowed items
        allowed_items = set(HOTBAR_ITEMS)
        if self.blocked_locked and CellType.BLOCKED in allowed_items:
            allowed_items.remove(CellType.BLOCKED)
        if CellType.JELLY in allowed_items:
            allowed_items.remove(CellType.JELLY)
        if self.game_state.pending_chests <= 0 and CellType.CHEST in allowed_items:
            allowed_items.remove(CellType.CHEST)
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

        is_initial_placement = not self.blocked_locked
        if is_initial_placement:
            chest_count = 0
            for row in range(GameConfig.GRID_SIZE):
                for col in range(GameConfig.GRID_SIZE):
                    if (row, col) == self.game_state.player_pos:
                        continue
                    if self.game_state.grid[row][col] == CellType.CHEST:
                        chest_count += 1

            if chest_count != 1:
                messagebox.showwarning(
                    "Chest Required",
                    "Initial setup must contain exactly one lucky chest.",
                )
                return

            # Consume the initial chest requirement now that exactly one is placed.
            if self.game_state.pending_chests > 0:
                self.game_state.pending_chests -= 1
                self._update_score()

        self.blocked_locked = True
        self.mode = "play"
        self.finish_placement_button.config(state=tk.DISABLED)
        self.execute_turn_button.config(state=tk.NORMAL)
        # Hotbar stays visible but disabled
        self._set_hotbar_allowed_items(set())
        if self.game_state.pending_chests > 0:
            self._enter_bonus_placement(False, self.game_state.pending_chests)
        else:
            self._compute_optimal_move()

    def _enter_bonus_placement(self, jelly_pending: bool, chest_pending: int) -> None:
        """Switch to bonus placement mode (jelly and/or chest) before gravity."""
        self.mode = "place_bonus"
        self.pending_jelly = jelly_pending
        self.pending_chests = chest_pending

        allowed_items = set()
        if self.pending_jelly:
            allowed_items.add(CellType.JELLY)
        if self.pending_chests > 0:
            allowed_items.add(CellType.CHEST)

        if CellType.JELLY in allowed_items:
            self.hotbar.select(CellType.JELLY)
        elif CellType.CHEST in allowed_items:
            self.hotbar.select(CellType.CHEST)

        self._highlight_selected_hotbar()
        self._set_hotbar_allowed_items(allowed_items)
        self.finish_placement_button.config(state=tk.DISABLED)
        self.execute_turn_button.config(state=tk.DISABLED)

    def _place_bonus_at(self, row: int, col: int) -> None:
        """Place a pending jelly or chest, then apply gravity when all are placed."""
        if (row, col) == self.game_state.player_pos:
            messagebox.showwarning(
                "Invalid Placement", "Cannot place bonus tiles on the player tile."
            )
            return
        if self.game_state.grid[row][col] != CellType.EMPTY:
            messagebox.showwarning(
                "Invalid Placement", "Bonus tiles must be placed on an empty tile."
            )
            return

        selected = self.hotbar.get_selected()
        if selected == CellType.JELLY:
            self.game_state.grid[row][col] = CellType.JELLY
            self.game_state.jellies.add((row, col))
            self.pending_jelly = False
        elif selected == CellType.CHEST:
            self.game_state.grid[row][col] = CellType.CHEST
            self.game_state.chests.add((row, col))
            if self.pending_chests > 0:
                self.pending_chests -= 1

        self.game_state.pending_chests = self.pending_chests

        if self.pending_jelly or self.pending_chests > 0:
            self._enter_bonus_placement(self.pending_jelly, self.pending_chests)
            self._draw_grid()
            return

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
        # Hotbar stays visible but all disabled
        self._set_hotbar_allowed_items(set())
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
        self.chest_pending_label.config(
            text=f"Chests Pending: {self.game_state.pending_chests}"
        )
        progress = (
            self.game_state.total_materials_for_chest % GameConfig.RESOURCES_FOR_CHEST
        )
        self.chest_progress_label.config(
            text=(f"Chest Progress: {progress}/{GameConfig.RESOURCES_FOR_CHEST}")
        )
