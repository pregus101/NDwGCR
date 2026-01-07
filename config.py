"""Configuration and settings management for NDwGCR."""

import os
from pathlib import Path
from platformdirs import user_music_dir
from typing import List


class Config:
    """Centralized configuration management."""
    
    def __init__(self):
        """Initialize configuration with default values."""
        self.app_path = Path(__file__).parent
        self.output_path = Path(user_music_dir())
        self.input_path = self.app_path / "custom.csv"
        self.csv_mode = "exportify"  # "exportify" or "tune_my_music"
        self.download_formats: List[str] = ["m4a"]
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        
    def set_output_path(self, path: str) -> None:
        """Set custom output path."""
        if path:
            self.output_path = Path(path)
            
    def set_input_path(self, path: str) -> None:
        """Set custom input CSV path."""
        if path:
            self.input_path = Path(path)
            
    def set_download_formats(self, formats: List[str]) -> None:
        """Set desired output formats."""
        self.download_formats = formats if formats else ["m4a"]
        
    def set_csv_mode(self, mode: str) -> None:
        """Set CSV reading mode (exportify or tune_my_music)."""
        if mode in ("exportify", "tune_my_music"):
            self.csv_mode = mode
            
    def ensure_output_path_exists(self) -> None:
        """Create output directory if it doesn't exist."""
        self.output_path.mkdir(parents=True, exist_ok=True)


# Global config instance
config = Config()
