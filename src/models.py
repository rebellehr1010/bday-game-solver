"""Data models and enums for the birthday game solver."""

from enum import Enum
from typing import Tuple


class CellType(Enum):
    """Represents the type of content in a grid cell."""

    EMPTY = 0
    BLOCKED = 1
    LIGHT_BLUE = 2  # Fish icon: <
    YELLOW = 3  # Paint palette: /\
    PINK = 4  # Rectangle: []
    PURPLE = 5  # Bow: /\_
    BRIGHT_PINK = 6  # 4-petal flower: +
    DARK_BLUE = 7  # Heart: <3
    JELLY = 8  # Rainbow jelly: o


# Color display properties: (hex_color, icon_symbol)
CELL_COLORS = {
    CellType.EMPTY: ("white", ""),
    CellType.BLOCKED: ("gray", ""),
    CellType.LIGHT_BLUE: ("#87CEEB", "<"),  # Sky blue
    CellType.YELLOW: ("#FFD700", "/\\"),  # Gold
    CellType.PINK: ("#FF6B9D", "[]"),  # Reddish pink
    CellType.PURPLE: ("#9370DB", "/\\_"),  # Medium purple
    CellType.BRIGHT_PINK: ("#FF1493", "+"),  # Deep pink
    CellType.DARK_BLUE: ("#00008B", "<3"),  # Dark blue
    CellType.JELLY: ("#FFB6C1", "o"),  # Light pink for rainbow jelly
}

# Standard resources (excludes JELLY, EMPTY, BLOCKED)
RESOURCE_TYPES = [
    CellType.LIGHT_BLUE,
    CellType.YELLOW,
    CellType.PINK,
    CellType.PURPLE,
    CellType.BRIGHT_PINK,
    CellType.DARK_BLUE,
]

# Hotbar items in order (for UI display)
HOTBAR_ITEMS = [
    CellType.BLOCKED,
    CellType.EMPTY,
    CellType.LIGHT_BLUE,
    CellType.YELLOW,
    CellType.PINK,
    CellType.PURPLE,
    CellType.BRIGHT_PINK,
    CellType.DARK_BLUE,
    CellType.JELLY,
]


class GameConfig:
    """Configuration constants for the game."""

    GRID_SIZE = 7
    PLAYER_START_POS = (6, 3)  # Middle bottom (row, col)
    CELL_SIZE = 60
    RESOURCES_FOR_JELLY = 10  # Resources needed per turn to spawn jelly


class Hotbar:
    """Represents the selection hotbar for setup mode."""

    def __init__(self):
        self.selected_item = CellType.BLOCKED

    def select(self, item: CellType) -> None:
        """Select an item from the hotbar."""
        if item in HOTBAR_ITEMS:
            self.selected_item = item

    def get_selected(self) -> CellType:
        """Get the currently selected item."""
        return self.selected_item
