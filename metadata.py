import mutagen
import pandas as pd
import os
from mutagen.id3 import ID3, TXXX, APIC
from mutagen.easyid3 import EasyID3
from mutagen.mp4 import MP4, MP4Cover
from mutagen.easymp4 import EasyMP4

# Register "yt_id" as a valid custom tag key for both MP3 (ID3) and MP4/M4A files.
# This must happen once, at import time, before any EasyID3/EasyMP4 file is touched.
EasyID3.RegisterTXXXKey("yt_id", "yt_id")
EasyMP4.RegisterTextKey("yt_id", "----:com.apple.iTunes:yt_id")


class Metadata:
    def __init__(self):
        self.song_path: str = ""
        self.song_title_csv: str = ""
        self.song_title: str = ""
        self.song_artist: str = ""
        self.song_album: str = ""
        self.song_year: str = ""
        self.song_genres: list[str] = []
        self.song_yt_id: str = ""
        self.song_album_artwork: str = ""
        self.csv_file: str = ""
        self.csv_file_type: str = ""
        self.file: pd.DataFrame = None

    def set_csv_file(self, csv_file: str, csv_file_type: str = "exptfy"):
        self.csv_file = csv_file
        self.csv_file_type = csv_file_type
        self.file = pd.read_csv(self.csv_file)

    def get_metadata(self, row_index: int = 0):
        if self.csv_file_type == "exptfy":
            row = self.file.iloc[row_index]
            self.song_title_csv = row.iloc[1]
            self.song_artist = row.iloc[3] if not pd.isna(row.iloc[3]) else "Unknown Artist"
            self.song_album = row.iloc[2]
            self.song_year = row.iloc[4]
            if pd.isna(row.iloc[10]):
                self.song_genres = []
            else:
                self.song_genres = [genre.strip() for genre in row.iloc[10].split(",")]

    def get_search_parameters(self) -> str:
        return self.song_artist + " " + self.song_title_csv

    def set_yt_id(self, yt_id: str):
        self.song_yt_id = yt_id

    def generate_yt_id_list(self, folder_path: str, formats: list[str]) -> list[str]:
        yt_id_list = []

        files = os.listdir(folder_path)
        for filename in files:
            if filename.startswith(".") or not any(filename.endswith(format) for format in formats):
                continue

            file_path = os.path.join(folder_path, filename)
            try:
                audio_file: mutagen.File = mutagen.File(file_path, easy=True)
            except (mutagen.MutagenError, OSError) as error:
                print(f"Skipping unreadable audio file {filename}: {error}")
                continue
            if audio_file is not None and "yt_id" in audio_file:
                yt_id = audio_file["yt_id"][0]
                yt_id_list.append(yt_id)
        return yt_id_list

    def apply_metadata(self, song_path: str, song_title: str, song_album_artwork: str = None):
        self.song_path = song_path
        self.song_title = song_title
        self.song_album_artwork = song_album_artwork

        # --- Simple text tags (title, artist, album, date, genre, yt_id) ---
        audio_file = mutagen.File(self.song_path, easy=True)
        if audio_file is not None:
            if audio_file.tags is None:
                audio_file.add_tags()
            audio_file["title"] = self.song_title
            audio_file["artist"] = self.song_artist
            audio_file["album"] = self.song_album
            audio_file["date"] = str(self.song_year)
            audio_file["genre"] = ", ".join(self.song_genres)
            audio_file["yt_id"] = self.song_yt_id
            audio_file.save()

        if self.song_album_artwork and os.path.exists(self.song_album_artwork):
            with open(self.song_album_artwork, "rb") as artwork_file:
                artwork_data = artwork_file.read()

            if self.song_path.lower().endswith(".mp3"):
                id3 = ID3(self.song_path)
                id3.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=artwork_data))
                id3.save(self.song_path)
            elif self.song_path.lower().endswith((".m4a", ".mp4")):
                mp4 = MP4(self.song_path)
                mp4["covr"] = [MP4Cover(artwork_data, imageformat=MP4Cover.FORMAT_JPEG)]
                mp4.save()

            os.remove(self.song_album_artwork)