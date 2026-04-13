"""Music download and search functionality."""

import logging
import time
from pathlib import Path
from typing import List, Dict, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

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
        self.metadata_manager = MetadataManager(config.output_path, skip_cover_art=config.skip_cover_art)
        self.config.ensure_output_path_exists()
        self._progress_lock = threading.Lock()  # Thread-safe progress updates
    
    def _get_canonical_filename(self, title: str, artist: str, album: str) -> str:
        """Generate a canonical filename from metadata.
        
        Args:
            title: Song title.
            artist: Artist name.
            album: Album name.
            
        Returns:
            Canonical filename without extension.
        """
        # Create a safe filename from metadata
        safe_chars = lambda s: "".join(c if c.isalnum() or c in (' ', '-', '_') else '' for c in s).strip()
        parts = [p for p in [safe_chars(artist), safe_chars(album), safe_chars(title)] if p]
        return " - ".join(parts) if parts else "unknown"
    
    def file_already_exists_by_video_id(self, video_id: str) -> Optional[Path]:
        """Check if a file with the given video ID already exists.
        
        Args:
            video_id: YouTube video ID to check.
            
        Returns:
            Path to existing file or None if not found.
        """
        if not video_id:
            return None
        
        return self.metadata_manager.find_file_by_video_id(video_id)

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
            
            # Extract video ID early for duplicate checking
            video_id: str = self.metadata_manager.get_youtube_id(url) or ""
            logger.debug(f"Extracted video ID: '{video_id}' from URL: {url}")
            
            # Check if file already exists by video ID
            if video_id:
                existing_file: Optional[Path] = self.file_already_exists_by_video_id(video_id)
                if existing_file:
                    logger.info(f"File already exists, skipping: {yt.title}")
                    return existing_file
            else:
                logger.warning(f"Failed to extract video ID from URL: {url}")
            
            # Get the highest quality audio stream available (maximizes sample rate/bitrate)
            # Filter for mp4 audio to ensure m4a format, not webm
            stream = yt.streams.filter(only_audio=True, file_extension='mp4').order_by('abr').desc().first()
            
            if not stream:
                logger.error(f"No mp4 audio stream available for {url}")
                return None
            
            logger.info(f"Downloading: {yt.title}")
            logger.info(f"Audio quality: {stream.abr} (highest available, mp4 format)")
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
            
            # Rename to use YouTube title directly (original behavior)
            title: str = yt.title
            title_path: Path = self.config.output_path / f"{title}.m4a"
            
            # Only rename if not already the title-based name
            if download_path != title_path:
                download_path.rename(title_path)
                download_path = title_path
                logger.info(f"Renamed to: {download_path}")
            
            # Apply metadata (includes video ID for future duplicate detection)
            logger.debug(f"Applying metadata with video_id='{video_id}'")
            self.metadata_manager.apply_metadata(
                download_path, artist, album, date, genre, video_id
            )
            
            # Convert to desired formats
            if formats and formats != ['m4a']:
                converted_files = AudioConverter.convert_to_formats(
                    download_path, 
                    formats, 
                    quality=self.config.quality_preset,
                    max_workers=self.config.max_format_conversion_workers
                )
                
                # Apply metadata to each converted file
                for converted_file in converted_files:
                    if converted_file != download_path:  # Skip the original m4a
                        logger.debug(f"Applying metadata to converted file: {converted_file}")
                        self.metadata_manager.apply_metadata(
                            converted_file, artist, album, date, genre, video_id
                        )
            
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
    
    def download_playlist(self, songs: List[Dict[str, str]], 
                         on_progress: Optional[Callable[[int, int, Dict[str, str]], None]] = None,
                         on_error: Optional[Callable[[str], None]] = None) -> List[Path]:
        """Download a playlist of songs using parallel threads.
        
        Args:
            songs: List of song dictionaries with keys: title, artist, album, date, genre.
            on_progress: Callback function(current, total, song_info) for progress updates.
            on_error: Callback function(error_message) for error handling.
            
        Returns:
            List of successfully downloaded file paths.
        """
        downloaded_files: List[Path] = []
        total_songs: int = len(songs)
        completed_count: int = 0
        
        # Use configurable concurrent downloads
        # Higher numbers = faster but YouTube may rate limit (6-8 recommended, max 10)
        max_workers: int = min(self.config.max_concurrent_workers, total_songs)
        
        def download_song(index: int, song: Dict[str, str]) -> Optional[Path]:
            """Helper function to download a single song.
            
            Args:
                index: Song index for progress reporting.
                song: Song dictionary.
                
            Returns:
                Path to downloaded file or None if failed.
            """
            try:
                nonlocal completed_count
                
                # Search for the song
                search_query: str = f"{song.get('title', '')} {song.get('artist', '')}"
                results: List[Dict[str, str]] = self.search(search_query)
                
                if not results:
                    error_msg: str = f"No results found for: {search_query}"
                    logger.warning(error_msg)
                    with self._progress_lock:
                        completed_count += 1
                        if on_progress:
                            on_progress(completed_count, total_songs, song)
                        if on_error:
                            on_error(error_msg)
                    return None
                
                # Download the first result
                file_path: Optional[Path] = None
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
                        break
                
                # Update progress in thread-safe manner
                with self._progress_lock:
                    completed_count += 1
                    if on_progress:
                        on_progress(completed_count, total_songs, song)
                
                return file_path
                        
            except Exception as e:
                error_msg: str = f"Failed to process song: {e}"
                logger.error(error_msg)
                with self._progress_lock:
                    completed_count += 1
                    if on_progress:
                        on_progress(completed_count, total_songs, song)
                    if on_error:
                        on_error(error_msg)
                return None
        
        # Download songs in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all download tasks
            futures = {
                executor.submit(download_song, index, song): (index, song)
                for index, song in enumerate(songs, 1)
            }
            
            # Collect completed downloads
            for future in as_completed(futures):
                try:
                    result: Optional[Path] = future.result()
                    if result:
                        downloaded_files.append(result)
                except Exception as e:
                    logger.error(f"Unexpected error in download thread: {e}")
        
        return downloaded_files
