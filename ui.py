"""GUI components and interface for NDwGCR."""

import logging
import csv
import threading
from pathlib import Path
from typing import List, Dict, Callable, Optional

import pandas as pd
import tkinter as tk
from tkinter import filedialog, ttk, Frame, Canvas, Scrollbar, Label, Button, Entry, Text
import webbrowser
import subprocess

from config import Config
from downloader import MusicDownloader
from converter import AudioConverter

logger = logging.getLogger(__name__)


class NDwGCRUI:
    """Main GUI for NDwGCR application."""
    
    def __init__(self, root: tk.Tk):
        """Initialize the UI.
        
        Args:
            root: Tkinter root window.
        """
        self.root = root
        self.config = Config()
        self.downloader = MusicDownloader(self.config)
        self.download_thread: Optional[threading.Thread] = None
        
        self._setup_window()
        self._create_widgets()
        self._initialize_csv()
    
    def _setup_window(self) -> None:
        """Configure main window."""
        self.root.title("NDwGCR - Music Downloader")
        self.root.geometry("540x740")
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(7, weight=4)
        self.root.configure(bg="black")
    
    def _create_widgets(self) -> None:
        """Create all UI widgets."""
        # Title
        title = Label(
            self.root,
            text="Welcome\nSelect your CSV file or use Manual Add\nto build a custom playlist",
            fg='violet', bg='black', font=("Arial", 10)
        )
        title.grid(row=0, pady=10)
        
        # File selection buttons
        get_input_btn = Button(
            self.root, text="Select Input File", fg="violet",
            highlightbackground="black", command=self._get_input_path
        )
        get_input_btn.grid(row=1, pady=5)
        
        output_btn = Button(
            self.root, text="Select Output Folder", fg="violet",
            highlightbackground="black", command=self._get_output_path
        )
        output_btn.grid(row=2, pady=5)
        
        # Options and control buttons
        options_btn = Button(
            self.root, text="Download Options", fg="violet",
            highlightbackground="black", command=self._open_options_window
        )
        options_btn.grid(row=3, pady=5)
        
        download_btn = Button(
            self.root, text="Download", fg="violet",
            highlightbackground="black", command=self._start_download
        )
        download_btn.grid(row=4, pady=5, padx=10)
        
        manual_add_btn = Button(
            self.root, text="Manual Add", fg="violet",
            highlightbackground="black", command=lambda: CustomPlaylistWindow(self.root, self.config)
        )
        manual_add_btn.grid(row=5, pady=5)
        
        # Progress bar
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(
            "violet.Horizontal.TProgressbar",
            foreground='black', background='violet'
        )
        self.progress_bar = ttk.Progressbar(
            self.root, orient="horizontal",
            style='violet.Horizontal.TProgressbar', length=300
        )
        self.progress_bar.grid(row=6, pady=10)
        
        # Output text area
        self.text_output = Text(
            self.root, wrap='word', height=20, width=65,
            bg='black', fg='violet'
        )
        self.text_output.grid(row=7, column=0, padx=5, pady=5, sticky="nsew")
        
        scrollbar = tk.Scrollbar(self.root, command=self.text_output.yview)
        scrollbar.grid(row=7, column=1, sticky="nsw")
        self.text_output.config(yscrollcommand=scrollbar.set)
        
        # Bottom buttons
        open_folder_btn = Button(
            self.root, text="Open Download Folder", fg="violet",
            highlightbackground="black", command=self._open_download_folder
        )
        open_folder_btn.grid(row=8, pady=5)
    
    def _initialize_csv(self) -> None:
        """Initialize the custom CSV file."""
        csv_path = self.config.app_path / "custom.csv"
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                # Check if file has content
                reader = csv.reader(f)
                rows = list(reader)
                if len(rows) <= 1:  # Only header or empty
                    self._write_empty_csv(csv_path)
        except FileNotFoundError:
            self._write_empty_csv(csv_path)
    
    def _write_empty_csv(self, csv_path: Path) -> None:
        """Create empty CSV file with headers."""
        headers = [str(i) for i in range(24)]
        try:
            with open(csv_path, 'w', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
            logger.info(f"Initialized CSV at {csv_path}")
        except Exception as e:
            self._log_error(f"Failed to initialize CSV: {e}")
    
    def _get_input_path(self) -> None:
        """Let user select input CSV file."""
        path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if path:
            self.config.set_input_path(path)
            self._log_info("Input file selected")
        else:
            self._log_info("Using default custom.csv")
    
    def _get_output_path(self) -> None:
        """Let user select output directory."""
        path = filedialog.askdirectory()
        if path:
            self.config.set_output_path(path)
            self._log_info("Output folder selected")
        else:
            self._log_info("Using default music directory")
    
    def _open_options_window(self) -> None:
        """Open download options window."""
        OptionsWindow(self.root, self.config)
    
    def _open_download_folder(self) -> None:
        """Open the download folder in file explorer."""
        output_path = str(self.config.output_path)
        
        if not Path(output_path).is_dir():
            self._log_error(f"Folder does not exist: {output_path}")
            return
        
        try:
            subprocess.run(["open", output_path], check=True)
            self._log_info(f"Opened folder in Finder")
        except (FileNotFoundError, subprocess.CalledProcessError):
            try:
                webbrowser.open(output_path)
                self._log_info("Opened folder in browser")
            except Exception as e:
                self._log_error(f"Unable to open download folder: {e}")
    
    def _start_download(self) -> None:
        """Start downloading in a background thread."""
        if self.download_thread and self.download_thread.is_alive():
            self._log_error("Download already in progress")
            return
        
        if not AudioConverter.check_ffmpeg_installed():
            self._log_error("FFmpeg is required but not installed")
            return
        
        self.download_thread = threading.Thread(target=self._perform_download)
        self.download_thread.daemon = True
        self.download_thread.start()
    
    def _perform_download(self) -> None:
        """Execute the download process."""
        try:
            songs = self._read_csv_file()
            if not songs:
                self._log_error("No songs found in CSV file")
                return
            
            self._log_info(f"Starting download of {len(songs)} songs...")
            self.progress_bar.config(maximum=len(songs))
            self.progress_bar['value'] = 0
            
            def progress_callback(current: int, total: int, song_info: Dict) -> None:
                self.progress_bar['value'] = current
                song_name = song_info.get('title', 'Unknown')
                artist_name = song_info.get('artist', 'Unknown')
                self._log_info(
                    f"Downloading: {song_name} by {artist_name} ({current}/{total})"
                )
                self.root.update()
            
            def error_callback(error_msg: str) -> None:
                self._log_error(error_msg)
            
            self.downloader.download_playlist(
                songs,
                on_progress=progress_callback,
                on_error=error_callback
            )
            
            self._log_info("Download complete!")
            
        except Exception as e:
            self._log_error(f"Download failed: {e}")
            logger.exception("Download error:")
    
    def _read_csv_file(self) -> List[Dict]:
        """Read songs from CSV file.
        
        Returns:
            List of song dictionaries.
        """
        songs = []
        try:
            with open(self.config.input_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                
                for row in reader:
                    if not row or all(not cell.strip() for cell in row):
                        continue
                    
                    if self.config.csv_mode == "exportify":
                        # Exportify format: title, artist, album, date, genre
                        songs.append({
                            'title': row[1] if len(row) > 1 else '',
                            'artist': row[3] if len(row) > 3 else '',
                            'album': row[2] if len(row) > 2 else '',
                            'date': row[4] if len(row) > 4 else '',
                            'genre': row[10] if len(row) > 10 else ''
                        })
                    else:
                        # Tune My Music format: title, artist, album, date, genre
                        songs.append({
                            'title': row[0] if len(row) > 0 else '',
                            'artist': row[1] if len(row) > 1 else '',
                            'album': row[2] if len(row) > 2 else '',
                            'date': row[3] if len(row) > 3 else '',
                            'genre': row[4] if len(row) > 4 else ''
                        })
                
                return [s for s in songs if s.get('title') and s.get('artist')]
                
        except FileNotFoundError:
            self._log_error(f"CSV file not found: {self.config.input_path}")
        except Exception as e:
            self._log_error(f"Error reading CSV file: {e}")
        
        return []
    
    def _log_info(self, message: str) -> None:
        """Log info message."""
        logger.info(message)
        self.text_output.insert(tk.END, message + "\n")
        self.text_output.see(tk.END)
    
    def _log_error(self, message: str) -> None:
        """Log error message."""
        logger.error(message)
        self.text_output.insert(tk.END, f"[ERROR]: {message}\n")
        self.text_output.see(tk.END)


class OptionsWindow:
    """Download options dialog."""
    
    def __init__(self, parent: tk.Tk, config: Config):
        """Initialize options window.
        
        Args:
            parent: Parent window.
            config: Configuration object.
        """
        self.config = config
        
        self.window = tk.Toplevel(parent)
        self.window.title("Download Options")
        self.window.geometry("500x300")
        self.window.configure(bg="black")
        
        # Format selection
        Label(
            self.window, text="Select output formats",
            fg='violet', bg='black', font=("Arial", 10)
        ).pack(pady=10)
        
        self.format_listbox = tk.Listbox(
            self.window, height=6, width=40,
            selectmode="multiple", bg='black', fg='violet'
        )
        self.format_listbox.pack(pady=5)
        
        for fmt in ['m4a', 'mp3', 'wav', 'flac', 'aac', 'ogg']:
            self.format_listbox.insert(tk.END, fmt)
        
        # CSV mode selection
        Label(
            self.window, text="CSV Reading Mode",
            fg='violet', bg='black', font=("Arial", 10)
        ).pack(pady=10)
        
        self.mode_var = tk.StringVar(value=self.config.csv_mode)
        
        tk.Radiobutton(
            self.window, text="Exportify", variable=self.mode_var,
            value="exportify", bg='black', fg='violet'
        ).pack()
        
        tk.Radiobutton(
            self.window, text="Tune My Music", variable=self.mode_var,
            value="tune_my_music", bg='black', fg='violet'
        ).pack()
        
        # Save button
        Button(
            self.window, text="Save", fg="violet",
            highlightbackground="black", command=self._save_options
        ).pack(pady=10)
    
    def _save_options(self) -> None:
        """Save selected options."""
        selected_indices = self.format_listbox.curselection()
        formats = [self.format_listbox.get(i) for i in selected_indices]
        
        self.config.set_download_formats(formats or ['m4a'])
        self.config.set_csv_mode(self.mode_var.get())
        
        self.window.destroy()


class CustomPlaylistWindow:
    """Window for manually adding songs to a playlist."""
    
    def __init__(self, parent: tk.Tk, config: Config):
        """Initialize custom playlist window.
        
        Args:
            parent: Parent window.
            config: Configuration object.
        """
        self.config = config
        self.song_entries: List[Dict[str, tk.Entry]] = []
        
        self.window = tk.Toplevel(parent)
        self.window.title("Custom Playlist")
        self.window.geometry("700x600")
        self.window.configure(bg="black")
        
        # Scrollable frame
        main_frame = Frame(self.window)
        main_frame.pack(fill="both", expand=True)
        
        canvas = Canvas(main_frame, bg="black", highlightthickness=0)
        canvas.pack(side="left", fill="both", expand=True)
        
        scrollbar = Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollbar.pack(side="right", fill="y")
        
        canvas.config(yscrollcommand=scrollbar.set)
        
        self.inner_frame = Frame(canvas, bg="black")
        canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")
        
        # Instructions
        Label(
            self.inner_frame, text="Add songs (leave blank fields empty if unknown)",
            fg='violet', bg='black'
        ).pack(pady=10)
        
        # Headers
        header_frame = Frame(self.inner_frame, bg="black")
        header_frame.pack(fill="x", padx=10)
        
        for header in ["Song Name", "Artist", "Album", "Genre", "Date"]:
            Label(header_frame, text=header, fg='violet', bg='black',
                 width=12).pack(side="left", padx=5)
        
        self.entries_frame = Frame(self.inner_frame, bg="black")
        self.entries_frame.pack(fill="both", expand=True, padx=10)
        
        # Buttons
        button_frame = Frame(self.inner_frame, bg="black")
        button_frame.pack(pady=10)
        
        Button(button_frame, text="Add Row", fg="violet",
              highlightbackground="black", command=self._add_row).pack(side="left", padx=5)
        Button(button_frame, text="Save", fg="violet",
              highlightbackground="black", command=self._save_playlist).pack(side="left", padx=5)
        
        # Initial row
        self._add_row()
    
    def _add_row(self) -> None:
        """Add a new song entry row."""
        row_frame = Frame(self.entries_frame, bg="black")
        row_frame.pack(fill="x", pady=5)
        
        entries = {
            'title': tk.Entry(row_frame, width=12),
            'artist': tk.Entry(row_frame, width=12),
            'album': tk.Entry(row_frame, width=12),
            'genre': tk.Entry(row_frame, width=12),
            'date': tk.Entry(row_frame, width=12)
        }
        
        for entry in entries.values():
            entry.pack(side="left", padx=5)
        
        self.song_entries.append(entries)
    
    def _save_playlist(self) -> None:
        """Save playlist to CSV file."""
        try:
            csv_path = self.config.input_path
            
            with open(csv_path, 'w', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([str(i) for i in range(24)])
                
                for entry_dict in self.song_entries:
                    title = entry_dict['title'].get().strip()
                    artist = entry_dict['artist'].get().strip()
                    album = entry_dict['album'].get().strip()
                    genre = entry_dict['genre'].get().strip()
                    date = entry_dict['date'].get().strip()
                    
                    if title and artist:  # Only save if title and artist present
                        row = [''] * 24
                        row[1] = title
                        row[3] = artist
                        row[2] = album
                        row[10] = genre
                        row[4] = date
                        writer.writerow(row)
            
            logger.info(f"Playlist saved to {csv_path}")
            self.window.destroy()
            
        except Exception as e:
            logger.error(f"Failed to save playlist: {e}")
