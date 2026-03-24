"""Entry point for the Fanuc CNC Emulator."""

from __future__ import annotations

import sys


def main() -> None:
    """Launch the emulator GUI."""
    try:
        import tkinter  # noqa: F401 – check before heavy imports
    except ModuleNotFoundError:
        print(
            "ERROR: tkinter is not installed.\n"
            "On Linux Mint / Ubuntu, install it with:\n"
            "  sudo apt install python3-tk",
            file=sys.stderr,
        )
        sys.exit(1)

    from .ui.app import App

    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
