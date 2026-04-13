"""Configuration and settings management for NDwGCR."""

import os
from pathlib import Path
from platformdirs import user_music_dir
from typing import List


class Config:
    """Centralized configuration management."""
    
    def __init__(self) -> None:
        """Initialize configuration with default values."""
        self.app_path: Path = Path(__file__).parent
        self.output_path: Path = Path(user_music_dir())
        self.input_path: Path = self.app_path / "custom.csv"
        self.csv_mode: str = "exportify"  # "exportify", "tune_my_music", or "native"
        self.download_formats: List[str] = ["m4a"]
        self.max_retries: int = 3
        self.retry_delay: int = 2  # seconds
        self.quality_preset: str = "high"  # "maximum", "high", "medium", or "fast"
        self.skip_cover_art: bool = False  # Skip cover art embedding for faster processing
        self.max_concurrent_workers: int = 6  # Downloads: More threads = faster, but may hit YouTube rate limits
        self.max_format_conversion_workers: int = 3  # Format conversions
        
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
        """Set CSV reading mode (exportify, tune_my_music, or native)."""
        if mode in ("exportify", "tune_my_music", "native"):
            self.csv_mode = mode
            
    def ensure_output_path_exists(self) -> None:
        """Create output directory if it doesn't exist."""
        self.output_path.mkdir(parents=True, exist_ok=True)


# Global config instance
config = Config()
