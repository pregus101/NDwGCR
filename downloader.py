"""Music download and search functionality."""

import logging
import time
from pathlib import Path
from typing import List, Dict, Optional

from youtubesearchpython import VideosSearch
from pytubefix import YouTube

from config import Config
from converter import AudioConverter
from metadata import MetadataManager

logger = logging.getLogger(__name__)


class MusicDownloader:
    """Handles searching for and downloading music from YouTube."""
    
    def __init__(self, config: Config):
        """Initialize downloader with configuration.
        
        Args:
            config: Configuration object.
        """
        self.config = config
        self.metadata_manager = MetadataManager(config.output_path)
        self.config.ensure_output_path_exists()
    
    def search(self, query: str, max_results: int = 1) -> List[Dict[str, str]]:
        """Search for music videos on YouTube.
        
        Args:
            query: Search query (song and artist).
            max_results: Maximum number of results to return.
            
        Returns:
            List of video dictionaries with 'url' and 'title' keys.
        """
        try:
            searcher = VideosSearch(query, max_results)
            results = searcher.result()
            
            videos = []
            for video_data in results.get('result', []):
                videos.append({
                    'url': video_data['link'],
                    'title': video_data.get('title', 'Unknown')
                })
            return videos
        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}")
            return []
    
    def download(self, url: str, artist: str, album: str, 
                date: str, genre: str, formats: List[str], 
                retry_count: int = 0) -> Optional[Path]:
        """Download and process a music video.
        
        Args:
            url: YouTube video URL.
            artist: Artist name.
            album: Album name.
            date: Release date.
            genre: Genre.
            formats: Desired output formats.
            retry_count: Current retry attempt.
            
        Returns:
            Path to downloaded file or None if failed.
        """
        try:
            yt = YouTube(url)
            # Get the highest quality audio stream available (maximizes sample rate/bitrate)
            stream = yt.streams.filter(only_audio=True).first()
            
            if not stream:
                logger.error(f"No audio stream available for {url}")
                return None
            
            logger.info(f"Downloading: {yt.title}")
            logger.info(f"Audio quality: {stream.abr} (highest available)")
            # stream.download() creates a subdirectory, so get the full file path
            downloaded_dir = stream.download(str(self.config.output_path))
            # Find the actual audio file in the downloaded directory
            download_path = Path(downloaded_dir)
            
            # Handle case where file is in a subdirectory
            if download_path.is_dir():
                # Find the audio file in the directory
                audio_files = list(download_path.glob('*.m4a')) or list(download_path.glob('*.mp4'))
                if not audio_files:
                    logger.error(f"No audio file found in {download_path}")
                    return None
                download_path = audio_files[0]
            
            logger.info(f"Downloaded to: {download_path}")
            
            # Extract video ID for metadata
            video_id = self.metadata_manager.get_youtube_id(url)
            
            # Apply metadata
            self.metadata_manager.apply_metadata(
                download_path, artist, album, date, genre, video_id or ""
            )
            
            # Convert to desired formats
            if formats and formats != ['m4a']:
                AudioConverter.convert_to_formats(download_path, formats)
            
            return download_path
            
        except Exception as e:
            logger.error(f"Download failed (attempt {retry_count + 1}): {e}")
            
            # Retry logic
            if retry_count < self.config.max_retries:
                logger.info(f"Retrying download in {self.config.retry_delay}s...")
                time.sleep(self.config.retry_delay)
                return self.download(url, artist, album, date, genre, 
                                    formats, retry_count + 1)
            return None
    
    def download_playlist(self, songs: List[Dict], 
                         on_progress: Optional[callable] = None,
                         on_error: Optional[callable] = None) -> List[Path]:
        """Download a playlist of songs.
        
        Args:
            songs: List of song dictionaries with keys: title, artist, album, date, genre.
            on_progress: Callback function(current, total, song_info) for progress updates.
            on_error: Callback function(error_message) for error handling.
            
        Returns:
            List of successfully downloaded file paths.
        """
        downloaded_files = []
        total_songs = len(songs)
        
        for index, song in enumerate(songs, 1):
            try:
                if on_progress:
                    on_progress(index, total_songs, song)
                
                # Search for the song
                search_query = f"{song.get('title', '')} {song.get('artist', '')}"
                results = self.search(search_query)
                
                if not results:
                    error_msg = f"No results found for: {search_query}"
                    logger.warning(error_msg)
                    if on_error:
                        on_error(error_msg)
                    continue
                
                # Download the first result
                for result in results:
                    file_path = self.download(
                        result['url'],
                        song.get('artist', ''),
                        song.get('album', ''),
                        song.get('date', ''),
                        song.get('genre', ''),
                        self.config.download_formats
                    )
                    
                    if file_path:
                        downloaded_files.append(file_path)
                        break
                        
            except Exception as e:
                error_msg = f"Failed to process song {index}/{total_songs}: {e}"
                logger.error(error_msg)
                if on_error:
                    on_error(error_msg)
        
        return downloaded_files
