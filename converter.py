"""Audio format conversion utilities."""

import logging
import subprocess
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


# FFmpeg command templates for different formats with high quality settings
FFMPEG_COMMANDS: Dict[str, List[str]] = {
    'mp3': [
        'ffmpeg', '-i', '{input}',
        '-acodec', 'libmp3lame',
        '-q:a', '0',  # Highest quality VBR
        '-ar', '48000',  # 48kHz sample rate (maximum for MP3)
        '{output}'
    ],
    'wav': [
        'ffmpeg', '-i', '{input}',
        '-acodec', 'pcm_s24le',  # 24-bit PCM for higher quality
        '-ar', '48000',  # 48kHz sample rate
        '-ac', '2',
        '{output}'
    ],
    'flac': [
        'ffmpeg', '-i', '{input}',
        '-c:a', 'flac',
        '-sample_fmt', 's24',  # 24-bit FLAC
        '-compression_level', '8',  # Maximum compression while maintaining quality
        '-ar', '48000',  # 48kHz sample rate
        '{output}'
    ],
    'aac': [
        'ffmpeg', '-i', '{input}',
        '-c:a', 'aac',
        '-q:a', '2',  # High quality AAC
        '-ar', '48000',  # 48kHz sample rate
        '{output}'
    ],
    'ogg': [
        'ffmpeg', '-i', '{input}',
        '-c:a', 'libvorbis',
        '-qscale:a', '10',  # Highest quality VBR (0-10 scale)
        '-ar', '48000',  # 48kHz sample rate
        '{output}'
    ]
}


class AudioConverter:
    """Handles audio format conversion using FFmpeg."""
    
    @staticmethod
    def check_ffmpeg_installed() -> bool:
        """Check if FFmpeg is installed and accessible.
        
        Returns:
            True if FFmpeg is available, False otherwise.
        """
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            logger.error("FFmpeg not found. Please install FFmpeg and add it to PATH.")
            return False
    
    @staticmethod
    def convert_audio(input_path: Path, output_format: str) -> bool:
        """Convert audio file to specified format.
        
        Args:
            input_path: Path to input audio file.
            output_format: Desired output format (mp3, wav, flac, aac, ogg).
            
        Returns:
            True if conversion successful, False otherwise.
        """
        if not input_path.exists():
            logger.error(f"Input file not found: {input_path}")
            return False
        
        if output_format not in FFMPEG_COMMANDS:
            logger.error(f"Unsupported format: {output_format}")
            return False
        
        output_path = input_path.with_suffix(f".{output_format}")
        
        # Skip if output already exists
        if output_path.exists():
            logger.info(f"Output file already exists, skipping: {output_path}")
            return True
        
        # Build FFmpeg command
        command = [
            part.format(input=str(input_path), output=str(output_path))
            for part in FFMPEG_COMMANDS[output_format]
        ]
        
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
            logger.info(f"Successfully converted '{input_path}' to '{output_path}'")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Conversion failed: {e}")
            if e.stdout:
                logger.error(f"FFmpeg stdout: {e.stdout}")
            if e.stderr:
                logger.error(f"FFmpeg stderr: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during conversion: {e}")
            return False
    
    @staticmethod
    def convert_to_formats(input_path: Path, formats: List[str]) -> List[Path]:
        """Convert audio to multiple formats.
        
        Args:
            input_path: Path to input audio file.
            formats: List of output formats.
            
        Returns:
            List of successfully created output file paths.
        """
        
        successful_outputs = []
        
        for fmt in formats:
            if fmt == 'm4a':
                # Original format, no conversion needed
                if input_path.exists():
                    successful_outputs.append(input_path)
                continue
            
            if AudioConverter.convert_audio(input_path, fmt):
                successful_outputs.append(input_path.with_suffix(f".{fmt}"))
        
        # Remove original m4a if not in desired formats
        if 'm4a' not in formats and input_path.exists():
            try:
                input_path.unlink()
                logger.info(f"Removed original m4a file: {input_path}")
            except Exception as e:
                logger.warning(f"Failed to remove original file: {e}")
        
        return successful_outputs
