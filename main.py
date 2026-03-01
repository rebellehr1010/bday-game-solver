"""Birthday Game Solver - Main entry point."""

import tkinter as tk
from ui import GameGUI


def main():
    """Launch the game application."""
    root = tk.Tk()
    app = GameGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
