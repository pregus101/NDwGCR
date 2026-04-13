"""Metadata handling for audio files."""

import logging
import os
import base64
from pathlib import Path
from typing import Optional
from mutagen.mp4 import MP4, MP4Cover
from mutagen.easymp4 import EasyMP4
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, TDRC, TCON, COMM
from mutagen.oggvorbis import OggVorbis
from mutagen.flac import FLAC, Picture
from mutagen.wave import WAVE
import urllib.request
import io

logger = logging.getLogger(__name__)


class MetadataManager:
    """Handles metadata and cover art for audio files."""
    
    def __init__(self, output_path: Path, skip_cover_art: bool = False) -> None:
        """Initialize metadata manager.
        
        Args:
            output_path: Directory to save temporary thumbnail files.
            skip_cover_art: If True, skip downloading and embedding cover art (faster processing).
        """
        self.output_path: Path = output_path
        self.skip_cover_art: bool = skip_cover_art
        
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
        if not video_id:
            logger.warning("Cannot download thumbnail: video_id is empty")
            return None
        
        thumbnail_path = self.output_path / f"{video_id}.jpg"
        
        # Try high resolution first, then default
        for quality in ['maxresdefault', 'sddefault', 'hqdefault', 'default']:
            thumbnail_url = f'https://img.youtube.com/vi/{video_id}/{quality}.jpg'
            try:
                urllib.request.urlretrieve(thumbnail_url, thumbnail_path)
                logger.info(f'Thumbnail saved as {thumbnail_path} (quality: {quality})')
                return thumbnail_path
            except Exception as e:
                logger.debug(f'Failed to download {quality} thumbnail: {e}')
                
        logger.warning(f"Failed to download thumbnail for video {video_id}")
        return None
    
    def apply_metadata(self, file_path: Path, artist: str, album: str, 
                      date: str, genre: str, video_id: str, skip_cover_art: Optional[bool] = None) -> None:
        """Apply metadata to audio file and optionally embed cover art where supported.
        
        Args:
            file_path: Path to audio file.
            artist: Artist name.
            album: Album name.
            date: Release date.
            genre: Genre.
            video_id: YouTube video ID for cover art and duplicate detection.
            skip_cover_art: Optional override for cover art processing. If None, uses instance setting.
        
        Note: Cover art is supported for M4A, MP3, FLAC, and OGG. 
              WAV does not officially support embedded cover art.
        """
        skip_art = skip_cover_art if skip_cover_art is not None else self.skip_cover_art
        
        # Ensure file_path is a Path object
        file_path = Path(file_path) if not isinstance(file_path, Path) else file_path
        
        if not file_path.exists():
            logger.error(f"File not found at {file_path}")
            return
            
        logger.info(f"Applying metadata to: {file_path.name}")
        logger.debug(f"Video ID: {video_id}")
            
        # Determine file format and apply metadata accordingly
        file_ext = file_path.suffix.lower()
        
        if file_ext == '.m4a':
            self._apply_mp4_metadata(file_path, artist, album, date, genre, video_id)
        elif file_ext == '.mp3':
            self._apply_mp3_metadata(file_path, artist, album, date, genre, video_id)
        elif file_ext == '.ogg':
            self._apply_vorbis_metadata(file_path, artist, album, date, genre, video_id)
        elif file_ext == '.wav':
            # WAV doesn't support embedded cover art - only basic metadata
            self._apply_wav_metadata(file_path, artist, album, date, genre, video_id)
            logger.debug("WAV format does not support embedded cover art")
            return
        elif file_ext == '.flac':
            self._apply_flac_metadata(file_path, artist, album, date, genre, video_id)
        else:
            logger.warning(f"Unsupported audio format: {file_ext}")
            return
        
        # Download and apply cover art (except for WAV and when skipped)
        if skip_art:
            logger.debug("Skipping cover art (skip_cover_art enabled)")
            return
            
        if file_ext != '.wav':
            thumbnail_path = self.download_thumbnail(video_id)
            logger.debug(f"Thumbnail path: {thumbnail_path}")
            
            if thumbnail_path:
                logger.debug(f"Proceeding to embed cover art")
                self._embed_cover_art(file_path, thumbnail_path)
                try:
                    thumbnail_path.unlink()  # Clean up thumbnail file
                except Exception as e:
                    logger.warning(f"Failed to clean up thumbnail: {e}")
            else:
                logger.warning(f"Skipping cover art embedding - thumbnail download failed")
    
    def _apply_mp4_metadata(self, file_path: Path, artist: str, album: str,
                           date: str, genre: str, video_id: str = "") -> None:
        """Apply metadata tags to MP4 file.
        
        Args:
            file_path: Path to audio file.
            artist: Artist name.
            album: Album name.
            date: Release date.
            genre: Genre.
            video_id: YouTube video ID for duplicate detection.
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
            if video_id:
                # Store video ID in comment tag for duplicate detection
                audiofile['comment'] = [f"youtube_id:{video_id}"]
            audiofile.save()
            logger.info(f"Metadata applied successfully to: {file_path}")
        except FileNotFoundError:
            logger.error(f"File not found at {file_path}")
        except Exception as e:
            logger.error(f"Failed to apply metadata to MP4: {e}")
    
    def _apply_mp3_metadata(self, file_path: Path, artist: str, album: str,
                           date: str, genre: str, video_id: str = "") -> None:
        """Apply metadata tags to MP3 file using ID3v2.
        
        Args:
            file_path: Path to audio file.
            artist: Artist name.
            album: Album name.
            date: Release date.
            genre: Genre.
            video_id: YouTube video ID for duplicate detection.
        """
        try:
            try:
                audiofile = ID3(str(file_path))
            except:
                audiofile = ID3()
            
            if artist:
                audiofile['TPE1'] = TPE1(encoding=3, text=[artist])
            if album:
                audiofile['TALB'] = TALB(encoding=3, text=[album])
            if date:
                audiofile['TDRC'] = TDRC(encoding=3, text=[date])
            if genre:
                audiofile['TCON'] = TCON(encoding=3, text=[genre])
            if video_id:
                audiofile['COMM'] = COMM(encoding=3, lang='eng', desc='', text=[f"youtube_id:{video_id}"])
            
            audiofile.save(str(file_path), v2_version=4)
            logger.info(f"Metadata applied successfully to: {file_path}")
        except Exception as e:
            logger.error(f"Failed to apply metadata to MP3: {e}")
    
    def _apply_vorbis_metadata(self, file_path: Path, artist: str, album: str,
                              date: str, genre: str, video_id: str = "") -> None:
        """Apply metadata tags to OGG Vorbis file.
        
        Args:
            file_path: Path to audio file.
            artist: Artist name.
            album: Album name.
            date: Release date.
            genre: Genre.
            video_id: YouTube video ID for duplicate detection.
        """
        try:
            audiofile = OggVorbis(str(file_path))
            if artist:
                audiofile['artist'] = [artist]
            if album:
                audiofile['album'] = [album]
            if date:
                audiofile['date'] = [date]
            if genre:
                audiofile['genre'] = [genre]
            if video_id:
                audiofile['comment'] = [f"youtube_id:{video_id}"]
            
            audiofile.save()
            logger.info(f"Metadata applied successfully to: {file_path}")
        except Exception as e:
            logger.error(f"Failed to apply metadata to OGG: {e}")
    
    def _apply_wav_metadata(self, file_path: Path, artist: str, album: str,
                           date: str, genre: str, video_id: str = "") -> None:
        """Apply metadata tags to WAV file using ID3v2.
        
        Args:
            file_path: Path to audio file.
            artist: Artist name.
            album: Album name.
            date: Release date.
            genre: Genre.
            video_id: YouTube video ID for duplicate detection.
        """
        try:
            try:
                audiofile = ID3(str(file_path))
            except:
                audiofile = ID3()
            
            if artist:
                audiofile['TPE1'] = TPE1(encoding=3, text=[artist])
            if album:
                audiofile['TALB'] = TALB(encoding=3, text=[album])
            if date:
                audiofile['TDRC'] = TDRC(encoding=3, text=[date])
            if genre:
                audiofile['TCON'] = TCON(encoding=3, text=[genre])
            if video_id:
                audiofile['COMM'] = COMM(encoding=3, lang='eng', desc='', text=[f"youtube_id:{video_id}"])
            
            audiofile.save(str(file_path), v2_version=4)
            logger.info(f"Metadata applied successfully to: {file_path}")
        except Exception as e:
            logger.error(f"Failed to apply metadata to WAV: {e}")
    
    def _apply_flac_metadata(self, file_path: Path, artist: str, album: str,
                            date: str, genre: str, video_id: str = "") -> None:
        """Apply metadata tags to FLAC file.
        
        Args:
            file_path: Path to audio file.
            artist: Artist name.
            album: Album name.
            date: Release date.
            genre: Genre.
            video_id: YouTube video ID for duplicate detection.
        """
        try:
            audiofile = FLAC(str(file_path))
            if artist:
                audiofile['artist'] = [artist]
            if album:
                audiofile['album'] = [album]
            if date:
                audiofile['date'] = [date]
            if genre:
                audiofile['genre'] = [genre]
            if video_id:
                audiofile['comment'] = [f"youtube_id:{video_id}"]
            
            audiofile.save()
            logger.info(f"Metadata applied successfully to: {file_path}")
        except Exception as e:
            logger.error(f"Failed to apply metadata to FLAC: {e}")
    
    def get_video_id_from_file(self, file_path: Path) -> Optional[str]:
        """Extract YouTube video ID from file metadata.
        
        Args:
            file_path: Path to audio file.
            
        Returns:
            YouTube video ID or None if not found.
        """
        if not file_path.exists():
            return None
        
        file_ext = file_path.suffix.lower()
        
        try:
            if file_ext == '.m4a':
                audiofile = EasyMP4(str(file_path))
                comments = audiofile.get('comment', [])
                for comment in comments:
                    if comment.startswith('youtube_id:'):
                        return comment.replace('youtube_id:', '')
            
            elif file_ext == '.mp3':
                try:
                    audiofile = ID3(str(file_path))
                    if 'COMM' in audiofile:
                        for frame in audiofile['COMM']:
                            if hasattr(frame, 'text'):
                                for text in frame.text:
                                    if text.startswith('youtube_id:'):
                                        return text.replace('youtube_id:', '')
                except:
                    pass
            
            elif file_ext == '.ogg':
                audiofile = OggVorbis(str(file_path))
                comments = audiofile.get('comment', [])
                for comment in comments:
                    if comment.startswith('youtube_id:'):
                        return comment.replace('youtube_id:', '')
            
            elif file_ext == '.flac':
                audiofile = FLAC(str(file_path))
                comments = audiofile.get('comment', [])
                for comment in comments:
                    if comment.startswith('youtube_id:'):
                        return comment.replace('youtube_id:', '')
            
            elif file_ext == '.wav':
                # WAV: try to read from vorbis-style comments if present
                try:
                    audiofile = ID3(str(file_path))
                    if 'COMM' in audiofile:
                        for frame in audiofile['COMM']:
                            if hasattr(frame, 'text'):
                                for text in frame.text:
                                    if text.startswith('youtube_id:'):
                                        return text.replace('youtube_id:', '')
                except:
                    pass
            
            return None
        except Exception as e:
            logger.debug(f"Failed to read video ID from {file_path}: {e}")
            return None
    
    def find_file_by_video_id(self, video_id: str) -> Optional[Path]:
        """Search output directory for a file with matching video ID.
        
        Args:
            video_id: YouTube video ID to search for.
            
        Returns:
            Path to matching file or None if not found.
        """
        if not video_id:
            return None
        
        try:
            # Search all audio files in output directory
            audio_extensions = ['*.m4a', '*.mp3', '*.wav', '*.flac', '*.aac', '*.ogg']
            for ext in audio_extensions:
                for file_path in self.output_path.glob(ext):
                    file_video_id = self.get_video_id_from_file(file_path)
                    if file_video_id == video_id:
                        logger.info(f"Found existing file for video {video_id}: {file_path}")
                        return file_path
        except Exception as e:
            logger.error(f"Error searching for video ID {video_id}: {e}")
        
        return None
    
    def _embed_cover_art(self, file_path: Path, thumbnail_path: Path) -> None:
        """Embed cover art in audio file based on format.
        
        Supported formats: M4A, MP3, FLAC, OGG
        WAV is NOT supported (no official metadata container).
        
        Args:
            file_path: Path to audio file.
            thumbnail_path: Path to cover art image.
        """
        if not thumbnail_path.exists() or not file_path.exists():
            logger.error(f"File or image not found - file_path: {file_path.exists()}, thumbnail: {thumbnail_path.exists()}")
            return
        
        file_ext = file_path.suffix.lower()
        
        try:
            with open(thumbnail_path, 'rb') as f:
                image_data = f.read()
            
            logger.debug(f"Embedding cover art into {file_ext} file: {file_path.name} (image size: {len(image_data)} bytes)")
            
            if file_ext == '.m4a':
                self._embed_cover_m4a(file_path, image_data)
            
            elif file_ext == '.mp3':
                self._embed_cover_mp3(file_path, image_data)
            
            elif file_ext == '.ogg':
                self._embed_cover_vorbis(file_path, image_data)
            
            elif file_ext == '.flac':
                self._embed_cover_flac(file_path, image_data)
            
            elif file_ext == '.wav':
                logger.warning(f"Cover art is not supported for WAV files (no official metadata container)")
            
            else:
                logger.warning(f"Cover art embedding not supported for {file_ext}")
        
        except Exception as e:
            logger.error(f"Failed to embed cover art: {e}", exc_info=True)
    
    def _embed_cover_m4a(self, file_path: Path, image_data: bytes) -> None:
        """Embed cover art in MP4 file."""
        try:
            audio = MP4(str(file_path))
            cover = MP4Cover(image_data, imageformat=MP4Cover.FORMAT_JPEG)
            audio['covr'] = [cover]
            audio.save()
            logger.info(f"Cover art embedded successfully in {file_path}")
        except Exception as e:
            logger.error(f"Failed to embed cover in M4A: {e}", exc_info=True)
    
    def _embed_cover_mp3(self, file_path: Path, image_data: bytes) -> None:
        """Embed cover art in MP3 file using ID3v2."""
        try:
            try:
                audio = ID3(str(file_path))
            except:
                audio = ID3()
            
            audio['APIC'] = APIC(encoding=3, mime='image/jpeg', type=3, 
                                desc='Cover', data=image_data)
            audio.save(str(file_path), v2_version=4)
            logger.info(f"Cover art embedded successfully in {file_path}")
        except Exception as e:
            logger.error(f"Failed to embed cover in MP3: {e}", exc_info=True)
    
    def _embed_cover_vorbis(self, file_path: Path, image_data: bytes) -> None:
        """Embed cover art in OGG Vorbis file."""
        try:
            audio = OggVorbis(str(file_path))
            # OGG Vorbis uses METADATA_BLOCK_PICTURE with Picture from mutagen.flac
            picture = Picture()
            picture.data = image_data
            picture.type = 3  # Cover (front)
            picture.mime = 'image/jpeg'
            picture.width = 1280
            picture.height = 720
            picture.depth = 24
            picture.colors = 0
            
            # Encode picture data as base64
            encoded_picture = base64.b64encode(picture.write()).decode('ascii')
            audio['METADATA_BLOCK_PICTURE'] = [encoded_picture]
            audio.save()
            logger.info(f"Cover art embedded successfully in {file_path}")
        except Exception as e:
            logger.error(f"Failed to embed cover in OGG: {e}", exc_info=True)
    
    def _embed_cover_flac(self, file_path: Path, image_data: bytes) -> None:
        """Embed cover art in FLAC file."""
        try:
            audio = FLAC(str(file_path))
            picture = Picture()
            picture.data = image_data
            picture.type = 3  # Cover (front)
            picture.mime = 'image/jpeg'
            picture.width = 1280
            picture.height = 720
            picture.depth = 24
            picture.colors = 0            
            audio.add_picture(picture)
            audio.save()
            logger.info(f"Cover art embedded successfully in {file_path}")
        except Exception as e:
            logger.error(f"Failed to embed cover in FLAC: {e}")
