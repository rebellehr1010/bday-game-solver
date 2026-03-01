"""Birthday Game Solver - Main entry point."""

import sys
import os

# Add parent directory to path so we can import src package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
from src.ui import GameGUI


def main():
    """Launch the game application."""
    root = tk.Tk()
    app = GameGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
