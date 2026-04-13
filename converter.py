"""Audio format conversion utilities."""

import logging
import subprocess
from pathlib import Path
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


# FFmpeg command templates for different formats with quality presets
FFMPEG_COMMANDS: Dict[str, Dict[str, List[str]]] = {
    'mp3': {
        'maximum': [
            'ffmpeg', '-i', '{input}',
            '-acodec', 'libmp3lame',
            '-q:a', '0',  # Highest quality VBR
            '-lowpass', '20.5',  # Maximize Nyquist frequency
            '-ar', '48000',  # MP3 spec max is 48kHz (cannot exceed this)
            '-b:a', '320k',  # Maximum MP3 bitrate (320kbps)
            '{output}'
        ],
        'high': [
            'ffmpeg', '-i', '{input}',
            '-acodec', 'libmp3lame',
            '-q:a', '0',  # Highest quality VBR
            '-ar', '48000',
            '{output}'
        ],
        'medium': [
            'ffmpeg', '-i', '{input}',
            '-acodec', 'libmp3lame',
            '-q:a', '2',  # Medium quality VBR (faster)
            '-ar', '44100',
            '{output}'
        ],
        'fast': [
            'ffmpeg', '-i', '{input}',
            '-acodec', 'libmp3lame',
            '-b:a', '192k',  # Fixed bitrate (2x faster)
            '-ar', '44100',
            '{output}'
        ]
    },
    'wav': {
        'maximum': [
            'ffmpeg', '-i', '{input}',
            '-acodec', 'pcm_s32le',  # 32-bit PCM (highest precision)
            '-ar', '96000',  # 96kHz sample rate (professional quality)
            '-ac', '2',
            '{output}'
        ],
        'high': [
            'ffmpeg', '-i', '{input}',
            '-acodec', 'pcm_s24le',
            '-ar', '48000',
            '-ac', '2',
            '{output}'
        ],
        'medium': [
            'ffmpeg', '-i', '{input}',
            '-acodec', 'pcm_s16le',
            '-ar', '44100',
            '-ac', '2',
            '{output}'
        ],
        'fast': [
            'ffmpeg', '-i', '{input}',
            '-acodec', 'pcm_s16le',
            '-ar', '32000',  # Lower sample rate
            '-ac', '1',  # Mono
            '{output}'
        ]
    },
    'flac': {
        'maximum': [
            'ffmpeg', '-i', '{input}',
            '-c:a', 'flac',
            '-compression_level', '8',  # Using 8 as max (level 12 requires FLAC 1.4.2+)
            '-ar', '96000',  # 96kHz professional quality
            '{output}'
        ],
        'high': [
            'ffmpeg', '-i', '{input}',
            '-c:a', 'flac',
            '-compression_level', '8',
            '-ar', '48000',
            '{output}'
        ],
        'medium': [
            'ffmpeg', '-i', '{input}',
            '-c:a', 'flac',
            '-compression_level', '4',  # Faster compression
            '-ar', '44100',
            '{output}'
        ],
        'fast': [
            'ffmpeg', '-i', '{input}',
            '-c:a', 'flac',
            '-compression_level', '0',  # No compression (10x faster)
            '-ar', '44100',
            '{output}'
        ]
    },
    'aac': {
        'maximum': [
            'ffmpeg', '-i', '{input}',
            '-c:a', 'aac',
            '-q:a', '0.1',  # Highest AAC quality
            '-ar', '96000',  # 96kHz professional sample rate
            '{output}'
        ],
        'high': [
            'ffmpeg', '-i', '{input}',
            '-c:a', 'aac',
            '-q:a', '2',
            '-ar', '48000',
            '{output}'
        ],
        'medium': [
            'ffmpeg', '-i', '{input}',
            '-c:a', 'aac',
            '-b:a', '128k',  # Fixed bitrate (faster)
            '-ar', '44100',
            '{output}'
        ],
        'fast': [
            'ffmpeg', '-i', '{input}',
            '-c:a', 'aac',
            '-b:a', '96k',  # Lower bitrate (faster)
            '-ar', '32000',  # Lower sample rate
            '{output}'
        ]
    },
    'ogg': {
        'maximum': [
            'ffmpeg', '-i', '{input}',
            '-c:a', 'libvorbis',
            '-q:a', '9',  # Maximum standard Vorbis quality (q:a 10 may not be supported on all FFmpeg versions)
            '-ar', '96000',  # 96kHz professional quality
            '{output}'
        ],
        'high': [
            'ffmpeg', '-i', '{input}',
            '-c:a', 'libvorbis',
            '-q:a', '9',
            '-ar', '48000',
            '{output}'
        ],
        'medium': [
            'ffmpeg', '-i', '{input}',
            '-c:a', 'libvorbis',
            '-q:a', '5',  # Medium quality (faster)
            '-ar', '44100',
            '{output}'
        ],
        'fast': [
            'ffmpeg', '-i', '{input}',
            '-c:a', 'libvorbis',
            '-q:a', '1',  # Low quality (fastest)
            '-ar', '32000',  # Lower sample rate
            '{output}'
        ]
    }
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
    def convert_audio(input_path: Path, output_format: str, quality: str = 'high') -> bool:
        """Convert audio file to specified format.
        
        Args:
            input_path: Path to input audio file.
            output_format: Desired output format (mp3, wav, flac, aac, ogg).
            quality: Quality preset ('maximum' for best quality, 'high', 'medium', or 'fast').
            
        Returns:
            True if conversion successful, False otherwise.
        
        Note:
            MP3 format is limited to 48kHz maximum due to MP3 specification, not software.
            For 96kHz audio, use FLAC, WAV, or OGG formats instead.
        """
        if not input_path.exists():
            logger.error(f"Input file not found: {input_path}")
            return False
        
        if output_format not in FFMPEG_COMMANDS:
            logger.error(f"Unsupported format: {output_format}")
            return False
        
        if quality not in FFMPEG_COMMANDS[output_format]:
            logger.warning(f"Quality preset '{quality}' not available for {output_format}, using 'high'")
            quality = 'high'
        
        logger.debug(f"Converting to {output_format} with '{quality}' quality preset")
        
        output_path = input_path.with_suffix(f".{output_format}")
        
        # If output already exists, delete it to ensure we re-convert with the new quality settings
        if output_path.exists():
            logger.info(f"Existing {output_format.upper()} file found, re-converting with '{quality}' quality preset")
            try:
                output_path.unlink()
            except Exception as e:
                logger.warning(f"Could not delete existing file {output_path}: {e}")
                return False
        
        # Build FFmpeg command
        command = [
            part.format(input=str(input_path), output=str(output_path))
            for part in FFMPEG_COMMANDS[output_format][quality]
        ]
        
        try:
            result = subprocess.run(command, check=False, capture_output=True, text=True)
            
            if result.returncode != 0:
                # If maximum quality fails, retry with 'high' as fallback
                if quality == 'maximum':
                    logger.warning(f"Conversion with 'maximum' quality preset failed for {output_format}, falling back to 'high' preset")
                    logger.debug(f"FFmpeg error: {result.stderr}")
                    # Retry with 'high' quality
                    return AudioConverter.convert_audio(input_path, output_format, 'high')
                else:
                    logger.error(f"Conversion failed with return code {result.returncode}")
                    logger.debug(f"FFmpeg stderr: {result.stderr}")
                    return False
            
            logger.info(f"Successfully converted '{input_path}' to '{output_path}' ({quality} quality)")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Conversion failed: {e}")
            if e.stdout:
                logger.error(f"FFmpeg stdout: {e.stdout}")
            if e.stderr:
                logger.error(f"FFmpeg stderr: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during conversion: {e}", exc_info=True)
            return False
    
    @staticmethod
    def convert_to_formats(input_path: Path, formats: List[str], quality: str = 'high', max_workers: int = None) -> List[Path]:
        """Convert audio to multiple formats in parallel.
        
        Args:
            input_path: Path to input audio file.
            formats: List of output formats.
            quality: Quality preset ('maximum', 'high', 'medium', or 'fast'). Use 'maximum' for best quality.
            max_workers: Maximum number of concurrent conversions (default 3, None uses config default).
            
        Returns:
            List of successfully created output file paths.
        
        Quality Presets:
            - 'maximum': Absolute best quality for each format (96kHz, max bitrates/compression)
              * MP3: Limited to 48kHz due to MP3 spec (not a software limitation)
              * WAV: 32-bit, 96kHz
              * FLAC: Compression 8, 96kHz
              * OGG: Quality 9, 96kHz
              * AAC: Quality 0.1, 96kHz
            - 'high': Excellent quality (48kHz, maximum codec settings) - default
            - 'medium': Balanced (44.1kHz, moderate settings) 
            - 'fast': Maximum speed (32-44.1kHz, minimal compression/lower bitrates) - 2-3x faster
        """
        
        successful_outputs = []
        
        # Default to 3 if not specified
        if max_workers is None:
            max_workers = 3
        
        # Separate m4a (no conversion) from formats that need conversion
        needs_conversion = [fmt for fmt in formats if fmt != 'm4a']
        
        if input_path.exists() and 'm4a' in formats:
            successful_outputs.append(input_path)
        
        # Parallelize format conversions using ThreadPoolExecutor
        if needs_conversion:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit conversion tasks
                future_to_format = {
                    executor.submit(AudioConverter.convert_audio, input_path, fmt, quality): fmt
                    for fmt in needs_conversion
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_format):
                    fmt = future_to_format[future]
                    try:
                        if future.result():
                            successful_outputs.append(input_path.with_suffix(f".{fmt}"))
                            logger.info(f"Format {fmt.upper()} conversion completed successfully")
                        else:
                            logger.warning(f"Format {fmt.upper()} conversion failed")
                    except Exception as e:
                        logger.error(f"Exception during {fmt.upper()} conversion: {e}", exc_info=True)
        
        # Remove original m4a if not in desired formats
        if 'm4a' not in formats and input_path.exists():
            try:
                input_path.unlink()
                logger.info(f"Removed original m4a file: {input_path}")
            except Exception as e:
                logger.warning(f"Failed to remove original file: {e}")
        
        return successful_outputs
