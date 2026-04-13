"""NDwGCR - Download music from YouTube with metadata."""

import logging
import tkinter as tk

from ui import NDwGCRUI

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ndwgcr.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    """Entry point for the application."""
    root = tk.Tk()
    app = NDwGCRUI(root) # type: ignore
    root.mainloop()


if __name__ == "__main__":
    main()
