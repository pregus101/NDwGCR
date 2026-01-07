# NDwGCR - YouTube Music Downloader

A Python-based GUI application to download music from YouTube with metadata and format conversion support.

## Features

- Download music from YouTube with title, artist, album, and genre metadata
- Convert audio to multiple formats (MP3, WAV, FLAC, AAC, OGG)
- Support for both Exportify and Tune My Music CSV formats
- Automatic cover art embedding from YouTube thumbnails
- Manual playlist creation via GUI
- Background download processing (non-blocking UI)
- Retry logic for failed downloads
- Comprehensive logging

## Installation

### Requirements
- Python 3.8+
- FFmpeg (for audio conversion)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd NDwGCR
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Install FFmpeg:
   - **macOS**: `brew install ffmpeg`
   - **Ubuntu/Debian**: `apt-get install ffmpeg`
   - **Windows**: Download from https://ffmpeg.org/download.html

## Usage

Run the application:
```bash
python NDwGCR.py
```

### Workflow

1. **Select Input File**: Choose a CSV file from Exportify or manually add songs
2. **Select Output Folder**: Choose where to save downloaded music
3. **Configure Download Options**: Select audio formats and CSV mode
4. **Start Download**: Click Download to begin background processing
5. **View Results**: Logs show progress; open download folder when complete

### CSV Format

**Exportify Format:**
- Column 1: Song Title
- Column 3: Artist
- Column 2: Album
- Column 4: Release Date
- Column 10: Genre

**Tune My Music Format:**
- Column 0: Song Title
- Column 1: Artist
- Column 2: Album
- Column 3: Release Date
- Column 4: Genre

## Project Structure

```
NDwGCR/
├── NDwGCR.py           # Main entry point
├── config.py           # Configuration management
├── ui.py              # GUI components
├── downloader.py      # Download logic
├── converter.py       # Audio format conversion
├── metadata.py        # Metadata and cover art handling
├── requirements.txt   # Python dependencies
├── custom.csv         # Default playlist file
└── README.md          # This file
```

## Architecture Improvements

### Before
- All code in a single 650+ line file
- Heavy use of global variables
- Bare exception handlers
- No separation of concerns
- UI blocking during downloads
- Repetitive FFmpeg command generation

### After
- **Modular design**: Separate concerns into dedicated modules
- **Configuration class**: Centralized settings management
- **Proper error handling**: Specific exception catching with logging
- **Background processing**: Downloads run in separate threads
- **Retry logic**: Automatic retries for failed downloads
- **DRY principle**: FFmpeg commands generated from a dictionary
- **Type hints**: Better IDE support and documentation
- **Logging**: Comprehensive logging with both file and console output

## Modules

### `config.py`
Centralized configuration management with methods to update paths, formats, and CSV mode.

### `ui.py`
Contains three main UI classes:
- `NDwGCRUI`: Main application window and logic
- `OptionsWindow`: Download format and CSV mode selection
- `CustomPlaylistWindow`: Manual song entry interface

### `downloader.py`
`MusicDownloader` class handling:
- YouTube search via `youtube-search-python`
- Audio downloading via `pytubefix`
- Metadata application
- Format conversion
- Retry logic

### `converter.py`
`AudioConverter` class for:
- FFmpeg availability checking
- Audio format conversion
- Multi-format batch processing

### `metadata.py`
`MetadataManager` class for:
- YouTube ID extraction
- Thumbnail downloading
- MP4 metadata tag application
- Cover art embedding

## Logging

Logs are written to both console and `ndwgcr.log`:
- **DEBUG**: Detailed download and conversion progress
- **INFO**: User actions and successful operations
- **ERROR**: Failed operations with error details
- **WARNING**: Non-critical issues

## TODO

- [ ] Support direct YouTube/Spotify links in CSV
- [ ] SoundCloud and Newgrounds support
- [ ] Batch retry configuration UI
- [ ] Download history tracking
- [ ] Playlist creation from Spotify/YouTube playlists

## Known Issues

- Windows file explorer opening may have limitations
- Some videos may be geographically restricted
- Very long playlists may cause memory issues (consider batching)

## Contributing

Contributions welcome! Please ensure:
- Code follows PEP 8 style guidelines
- All functions have docstrings
- Type hints are used where applicable
- Error handling is specific (no bare `except`)

## License

MIT License (or specify your license)
