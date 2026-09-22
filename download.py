from youtube_search import YoutubeSearch as yt_search
from metadata import Metadata
import threading
import copy
import yt_dlp
from yt_dlp.utils import DownloadError
import requests
import subprocess
import os
import json
import re
from concurrent.futures import ThreadPoolExecutor

# Resolve relative to this script's own location, not the current working
# directory, since VS Code's launcher may run with a different cwd.
PO_TOKEN_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "po_token_cache.json")
SEARCH_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".ndwgcr_search_cache.json")


class downloader():
    def __init__(self):
        self.search_results = None
        self.row_index = 1
        self.metadata = Metadata()
        self.yt_id_list = []
        self.downloaded_ids = set()
        self.search_cache = {}
        self.output_formats = []
        self.output_folder = ""
        self.is_downloading = False
        self.po_token = None
        self.visitor_data = None
        self.download_workers = 3
        self._download_state_lock = threading.Lock()
        self._search_cache_lock = threading.Lock()
        self._in_progress_ids = set()
        self._load_po_token()

    def _load_po_token(self):
        """
        Loads a manually-generated PoToken + visitorData from cache
        (created by get_token.py). If missing, PoToken-based downloads
        will be skipped rather than prompting for input from a
        background thread, which would crash the GUI.
        """
        if os.path.exists(PO_TOKEN_CACHE_FILE):
            with open(PO_TOKEN_CACHE_FILE) as f:
                data = json.load(f)
            self.po_token = data.get("po_token")
            self.visitor_data = data.get("visitor_data")
        else:
            print(
                f"Warning: {PO_TOKEN_CACHE_FILE} not found. "
                "Run get_token.py once to generate a cached PoToken."
            )

    def start_download(self, csv_file: str, output_folder: str, csv_file_type: str = "exptfy", output_formats: list[str] = ["mp3"]):
        self.metadata.set_csv_file(csv_file, csv_file_type)
        self.row_index = 0
        self.metadata.get_metadata(self.row_index)
        self.output_formats = output_formats
        self.output_folder = output_folder
        self.yt_id_list = self.metadata.generate_yt_id_list(output_folder, output_formats)
        self.downloaded_ids = set(self.yt_id_list)
        self.search_cache = self._load_search_cache()
        self.is_downloading = True

        self.download_thread = threading.Thread(target=self.download_loop)
        self.download_thread.start()

    def _search_cache_path(self):
        return SEARCH_CACHE_FILE

    def _load_search_cache(self):
        try:
            with open(self._search_cache_path()) as cache_file:
                cache = json.load(cache_file)
            return cache if isinstance(cache, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def _save_search_cache(self):
        try:
            with open(self._search_cache_path(), "w") as cache_file:
                json.dump(self.search_cache, cache_file)
        except OSError as error:
            print(f"Could not save search cache: {error}")

    def _apply_metadata_async(self, row_metadata: Metadata, final_path: str, title: str, img_path: str | None):
        try:
            row_metadata.apply_metadata(final_path, title, img_path)
        except Exception as e:
            print(f"Metadata application failed for {title}: {e}")

    def _snapshot_metadata(self):
        return copy.deepcopy(self.metadata)

    def _safe_filename(self, title: str) -> str:
        return re.sub(r'[\\/:*?"<>|]', "_", title).strip() or "untitled"

    def _download_row(self, row_index: int, row_metadata: Metadata, search_query: str):
        with self._search_cache_lock:
            search_results = self.search_cache.get(search_query)
        if search_results is None:
            search_results = self.search_youtube(search_query)
            with self._search_cache_lock:
                self.search_cache[search_query] = search_results
                self._save_search_cache()

        if not search_results:
            return {"row_index": row_index, "search_query": search_query, "status": "no_results"}

        result = search_results[0]
        yt_id = result["id"]
        with self._download_state_lock:
            if yt_id in self.downloaded_ids or yt_id in self._in_progress_ids:
                return {
                    "row_index": row_index,
                    "search_query": search_query,
                    "yt_id": yt_id,
                    "status": "already_downloaded",
                }
            self._in_progress_ids.add(yt_id)

        title = result["title"]
        safe_title = self._safe_filename(title)
        temp_path = None
        try:
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(
                    self.output_folder, f".ndwgcr_{row_index}_{safe_title}_temp.%(ext)s"
                ),
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "noprogress": True,
            }
            if self.po_token and self.visitor_data:
                ydl_opts["extractor_args"] = {
                    "youtube": {
                        "po_token": [f"web+{self.po_token}"],
                        "visitor_data": [self.visitor_data],
                    }
                }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={yt_id}", download=True)
                temp_path = ydl.prepare_filename(info)

            row_metadata.set_yt_id(yt_id)
            return {
                "row_index": row_index,
                "search_query": search_query,
                "yt_id": yt_id,
                "title": title,
                "row_metadata": row_metadata,
                "temp_path": temp_path,
                "status": "downloaded",
            }
        except DownloadError as error:
            print(f"Skipping {yt_id} — yt-dlp error: {error}")
        except Exception as error:
            print(f"Skipping {yt_id} — unexpected error: {error}")
        finally:
            if temp_path is None:
                with self._download_state_lock:
                    self._in_progress_ids.discard(yt_id)

        return {"row_index": row_index, "search_query": search_query, "status": "failed"}

    def download_loop(self):
        total_rows = len(self.metadata.file)
        self._in_progress_ids = set()
        with ThreadPoolExecutor(max_workers=self.download_workers) as executor:
            futures = []
            for row_index in range(total_rows):
                self.metadata.get_metadata(row_index)
                row_metadata = self._snapshot_metadata()
                futures.append(
                    executor.submit(
                        self._download_row,
                        row_index,
                        row_metadata,
                        row_metadata.get_search_parameters(),
                    )
                )

            for row_index, future in enumerate(futures):
                result = future.result()
                search_query = result["search_query"]
                status = result["status"]
                if status == "downloaded":
                    yt_id = result["yt_id"]
                    title = result["title"]
                    temp_path = result["temp_path"]
                    safe_title = self._safe_filename(title)
                    final_path = os.path.join(self.output_folder, f"{safe_title}.{self.output_formats[0]}")
                    try:
                        self.convert_to_mp3(temp_path, final_path)
                        img_path = f"{self.output_folder}/{yt_id}.jpg"
                        thumbnail_ok = self.download_thumbnail(yt_id, img_path)
                        result["row_metadata"].apply_metadata(
                            final_path, title, img_path if thumbnail_ok else None
                        )
                        self.yt_id_list.append(yt_id)
                        self.downloaded_ids.add(yt_id)
                        print(f"Downloading: {search_query} (YT ID: {yt_id})")
                    except subprocess.CalledProcessError as error:
                        print(f"ffmpeg conversion failed for {yt_id}: {error}")
                    except Exception as error:
                        print(f"Finalization failed for {yt_id}: {error}")
                    finally:
                        with self._download_state_lock:
                            self._in_progress_ids.discard(yt_id)
                        try:
                            os.remove(temp_path)
                        except FileNotFoundError:
                            pass
                elif status == "already_downloaded":
                    print(f"Already downloaded: {search_query} (YT ID: {result['yt_id']})")
                elif status == "no_results":
                    print(f"No results found for: {search_query}")

                self.row_index = row_index + 1
                print(f"Progress: {self.row_index}/{total_rows}")

        with threading.Lock():
            self.is_downloading = False

    def download_thumbnail(self, yt_id: str, img_path: str) -> bool:
        for quality in ["maxresdefault", "hqdefault"]:
            img_url = f"https://img.youtube.com/vi/{yt_id}/{quality}.jpg"
            try:
                response = requests.get(img_url, timeout=10)
            except requests.RequestException as e:
                print(f"Thumbnail request failed for {yt_id}: {e}")
                continue

            # Filter out tiny placeholder/"no thumbnail" images
            if response.status_code == 200 and len(response.content) > 1000:
                with open(img_path, "wb") as handler:
                    handler.write(response.content)
                return True

        print(f"No valid thumbnail found for {yt_id}")
        return False

    def convert_to_mp3(self, input_path: str, output_path: str):
        subprocess.run(
            [
                "ffmpeg",
                "-y",  # overwrite output if it exists
                "-i", input_path,
                "-codec:a", "libmp3lame",
                "-q:a", "2",  # ~190kbps VBR, good quality
                output_path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def get_is_downloading(self) -> bool:
        with threading.Lock():
            return self.is_downloading

    def search_youtube(self, search_query: str, max_results: int = 1):
        try:
            return yt_search(search_query, max_results=max_results).to_dict()
        except Exception as error:
            print(f"YouTube search failed for {search_query}: {error}")
            return []

    def is_downloaded(self, yt_id: str) -> bool:
        return yt_id in self.yt_id_list