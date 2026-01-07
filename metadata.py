"""Metadata handling for audio files."""

import logging
import os
from pathlib import Path
from typing import Optional
from mutagen.mp4 import MP4, MP4Cover
from mutagen.easymp4 import EasyMP4
import urllib.request

logger = logging.getLogger(__name__)


class MetadataManager:
    """Handles metadata and cover art for audio files."""
    
    def __init__(self, output_path: Path):
        """Initialize metadata manager.
        
        Args:
            output_path: Directory to save temporary thumbnail files.
        """
        self.output_path = output_path
        
    def get_youtube_id(self, url: str, ignore_playlist: bool = True) -> Optional[str]:
        """Extract video ID from YouTube URL.
        
        Args:
            url: YouTube URL.
            ignore_playlist: Whether to ignore playlist parameters.
            
        Returns:
            YouTube video ID or None.
        """
        from urllib.parse import urlparse, parse_qs
        
        try:
            if 'youtu.be' in url:
                path = urlparse(url).path
                return path.lstrip('/')
            elif 'youtube.com' in url:
                query = urlparse(url).query
                if query:
                    query_params = parse_qs(query)
                    if 'v' in query_params:
                        video_id = query_params['v'][0]
                        if ignore_playlist and '&list=' in url:
                            return video_id.split('&')[0]
                        return video_id
        except Exception as e:
            logger.error(f"Failed to extract YouTube ID: {e}")
            
        return None
    
    def download_thumbnail(self, video_id: str) -> Optional[Path]:
        """Download YouTube thumbnail.
        
        Args:
            video_id: YouTube video ID.
            
        Returns:
            Path to downloaded thumbnail or None.
        """
        thumbnail_path = self.output_path / f"{video_id}.jpg"
        
        # Try high resolution first, then default
        for quality in ['maxresdefault', 'default']:
            thumbnail_url = f'https://img.youtube.com/vi/{video_id}/{quality}.jpg'
            try:
                urllib.request.urlretrieve(thumbnail_url, thumbnail_path)
                logger.info(f'Thumbnail saved as {thumbnail_path}')
                return thumbnail_path
            except Exception as e:
                logger.warning(f'Failed to download {quality} thumbnail: {e}')
                
        logger.error(f"Failed to download thumbnail for video {video_id}")
        return None
    
    def apply_metadata(self, file_path: Path, artist: str, album: str, 
                      date: str, genre: str, video_id: str) -> None:
        """Apply metadata to audio file and embed cover art.
        
        Args:
            file_path: Path to audio file.
            artist: Artist name.
            album: Album name.
            date: Release date.
            genre: Genre.
            video_id: YouTube video ID for cover art.
        """
        # Ensure file_path is a Path object
        file_path = Path(file_path) if not isinstance(file_path, Path) else file_path
        
        if not file_path.exists():
            logger.error(f"File not found at {file_path}")
            return
            
        logger.info(f"Applying metadata to: {file_path.name}")
            
        # Download thumbnail first
        thumbnail_path = self.download_thumbnail(video_id)
        
        # Apply basic metadata to MP4
        self._apply_mp4_metadata(file_path, artist, album, date, genre)
        
        # Apply cover art if thumbnail was downloaded
        if thumbnail_path:
            self._embed_cover_art(file_path, thumbnail_path)
            try:
                thumbnail_path.unlink()  # Clean up thumbnail file
            except Exception as e:
                logger.warning(f"Failed to clean up thumbnail: {e}")
    
    def _apply_mp4_metadata(self, file_path: Path, artist: str, album: str,
                           date: str, genre: str) -> None:
        """Apply metadata tags to MP4 file.
        
        Args:
            file_path: Path to audio file.
            artist: Artist name.
            album: Album name.
            date: Release date.
            genre: Genre.
        """
        try:
            audiofile = EasyMP4(str(file_path))
            if artist:
                audiofile['artist'] = [artist]
            if album:
                audiofile['album'] = [album]
            if date:
                audiofile['date'] = [date]
            if genre:
                audiofile['genre'] = [genre]
            audiofile.save()
            logger.info(f"Metadata applied successfully to: {file_path}")
        except FileNotFoundError:
            logger.error(f"File not found at {file_path}")
        except Exception as e:
            logger.error(f"Failed to apply metadata: {e}")
    
    def _embed_cover_art(self, file_path: Path, thumbnail_path: Path) -> None:
        """Embed cover art in MP4 file.
        
        Args:
            file_path: Path to audio file.
            thumbnail_path: Path to cover art image.
        """
        try:
            audio = MP4(str(file_path))
            with open(thumbnail_path, 'rb') as f:
                image_data = f.read()
            
            cover = MP4Cover(image_data, imageformat=MP4Cover.FORMAT_JPEG)
            audio['covr'] = [cover]
            audio.save()
            logger.info(f"Cover art embedded successfully in {file_path}")
        except FileNotFoundError:
            logger.error(f"File or image not found")
        except Exception as e:
            logger.error(f"Failed to embed cover art: {e}")
