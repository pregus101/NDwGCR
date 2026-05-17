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
        self._progress_lock = threading.Lock()
        self._id_cache: Dict[str, Optional[Path]] = {}  # video_id -> path (None = download in progress)
        self._id_cache_lock = threading.Lock()
        self._build_id_cache()

    def _build_id_cache(self) -> None:
        """Scan the output directory once at startup to index all existing video IDs."""
        count = 0
        audio_extensions = ['*.m4a', '*.mp3', '*.wav', '*.flac', '*.aac', '*.ogg']
        for ext in audio_extensions:
            for file_path in self.config.output_path.glob(ext):
                video_id = self.metadata_manager.get_video_id_from_file(file_path)
                if video_id:
                    self._id_cache[video_id] = file_path
                    count += 1
        logger.info(f"Cache built: {count} previously downloaded tracks indexed")
    
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
            Path to existing file, or None if not found (or download in progress).
        """
        if not video_id:
            return None
        with self._id_cache_lock:
            return self._id_cache.get(video_id)  # None if in-progress or missing

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
                url = video_data.get('link')
                if url:  # skip results where the library returned None for the URL
                    videos.append({
                        'url': url,
                        'title': video_data.get('title') or 'Unknown'
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
        # Extract video ID first — pure URL string parse, zero network cost
        video_id: str = self.metadata_manager.get_youtube_id(url) or ""
        logger.debug(f"Extracted video ID: '{video_id}' from URL: {url}")

        cached: Optional[Path] = None
        missing_formats: List[str] = []
        if video_id:
            with self._id_cache_lock:
                if video_id in self._id_cache:
                    cached = self._id_cache[video_id]
                    if cached is None:
                        # None sentinel means another thread is downloading this right now
                        logger.debug(f"Download already in progress for {video_id}, skipping")
                        return None
                    missing_formats = [
                        fmt for fmt in formats
                        if not cached.with_suffix(f'.{fmt}').exists()
                    ]
                else:
                    self._id_cache[video_id] = None  # Reserve slot — blocks other threads from re-downloading

        # Cache hit — check if all desired formats are already on disk
        if cached is not None:
            if not missing_formats:
                logger.info(f"File already exists (all formats present), skipping: {cached.name}")
                return cached
            # Some formats are missing (e.g. a previous conversion failed) — convert without re-downloading
            logger.info(f"File cached but missing formats {missing_formats}, converting: {cached.name}")
            if cached.exists():
                all_ok = True
                for fmt in missing_formats:
                    if AudioConverter.convert_audio(cached, fmt, quality=self.config.quality_preset):
                        converted = cached.with_suffix(f'.{fmt}')
                        self.metadata_manager.apply_metadata(converted, artist, album, date, genre, video_id)
                    else:
                        all_ok = False
                # Remove the source file if it's not a desired format and all conversions succeeded
                source_fmt = cached.suffix.lstrip('.')
                if all_ok and source_fmt not in formats:
                    try:
                        cached.unlink()
                        logger.info(f"Removed source file after conversion: {cached.name}")
                    except Exception as e:
                        logger.warning(f"Failed to remove source file {cached}: {e}")
            else:
                logger.warning(f"Cached path no longer on disk: {cached}")
            return cached

        if not video_id:
            logger.warning(f"Failed to extract video ID from URL: {url}")

        try:
            yt = YouTube(url)

            stream = yt.streams.filter(only_audio=True, file_extension='mp4').order_by('abr').desc().first()

            if not stream:
                logger.error(f"No mp4 audio stream available for {url}")
                return None

            logger.info(f"Downloading: {yt.title}")
            logger.info(f"Audio quality: {stream.abr} (highest available, mp4 format)")
            downloaded_dir = stream.download(str(self.config.output_path))
            download_path = Path(downloaded_dir)

            if download_path.is_dir():
                audio_files = list(download_path.glob('*.m4a')) or list(download_path.glob('*.mp4'))
                if not audio_files:
                    logger.error(f"No audio file found in {download_path}")
                    return None
                download_path = audio_files[0]

            logger.info(f"Downloaded to: {download_path}")

            title: str = yt.title
            # Replace characters that are illegal in filenames on macOS/Linux
            safe_title = title.replace('/', '∕').replace('\0', '')
            title_path: Path = self.config.output_path / f"{safe_title}.m4a"

            if download_path != title_path:
                download_path.rename(title_path)
                download_path = title_path
                logger.info(f"Renamed to: {download_path}")

            # Apply metadata to the original m4a (stores video_id for future cache rebuilds)
            logger.debug(f"Applying metadata with video_id='{video_id}'")
            self.metadata_manager.apply_metadata(
                download_path, artist, album, date, genre, video_id
            )

            # Convert to desired formats and apply metadata to each converted file
            if formats and formats != ['m4a']:
                converted_files = AudioConverter.convert_to_formats(
                    download_path,
                    formats,
                    quality=self.config.quality_preset,
                    max_workers=self.config.max_format_conversion_workers
                )

                for converted_file in converted_files:
                    if converted_file != download_path:
                        logger.debug(f"Applying metadata to converted file: {converted_file}")
                        self.metadata_manager.apply_metadata(
                            converted_file, artist, album, date, genre, video_id
                        )

            # Update cache so subsequent calls in this session skip immediately
            if video_id:
                with self._id_cache_lock:
                    self._id_cache[video_id] = download_path

            return download_path

        except Exception as e:
            # Release the reservation so retries (and other threads) can proceed
            if video_id:
                with self._id_cache_lock:
                    if self._id_cache.get(video_id) is None:
                        del self._id_cache[video_id]

            logger.error(f"Download failed (attempt {retry_count + 1}): {e}")

            # Don't retry errors that will never succeed regardless of how many attempts
            error_str = str(e).lower()
            permanent = any(phrase in error_str for phrase in (
                'age restricted', 'private video', 'video unavailable',
                'this video is not available', 'no such file or directory',
            ))
            if not permanent and retry_count < self.config.max_retries:
                logger.info(f"Retrying download in {self.config.retry_delay}s...")
                time.sleep(self.config.retry_delay)
                return self.download(url, artist, album, date, genre, formats, retry_count + 1)
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
        # Rebuild cache with the current output path — user may have changed it since init
        with self._id_cache_lock:
            self._id_cache.clear()
        self._build_id_cache()

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
                
                # Build search query — replace ';' separators (multi-artist) with spaces
                title: str = song.get('title', '') or ''
                artist: str = (song.get('artist', '') or '').replace(';', ' ')
                search_query: str = f"{title} {artist}".strip()
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
