import os
import subprocess
import threading
import logging
import csv
from io import BytesIO
from typing import Self
import webbrowser

# Why do we have this and import tkinter as tk?
# TODO: Remove extra imports
from tkinter import *
from tkinter import filedialog
from tkinter import ttk
import tkinter as tk
from tkinter import scrolledtext

from bs4 import BeautifulSoup
import urllib.request
from urllib.parse import urlparse, parse_qs

from youtubesearchpython import VideosSearch
from pytubefix import YouTube
import yt_dlp

from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC, error
from mutagen.easymp4 import EasyMP4

from platformdirs import user_music_dir

# Sets default output path
output_path = user_music_dir()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

#Sets default options
global mp3_download
mp3_download = True

class OnlineMusicEntry():

    # TODO: Work on better source identification.
    source: int

    def __init__(self):
        self.is_downloaded = False
        
    @staticmethod
    def create_from_youtube_ID(ID) -> Self:
        pass

    @staticmethod
    def create_from_spotify_ID(ID) -> Self:
        pass

    def download(self, path: str) -> None:
        # ...
        self.is_downloaded = True
        return

    def convert_m4a_to_mp3(self) -> None:
        pass

    def apply_metadata(self) -> None:
        pass

    def _apply_youtube_metadata(self) -> None:
        pass

    def _apply_spotify_metadata(self) -> None:
        pass

class ListOfMusicEntries():
    
    def __init__(self):
        self.entry_list: list[OnlineMusicEntry] = []

    # Appends a single online music entry or multiple if the url is a playlist or single video
    def smart_append_from_url(self, path):
        pass

    def smart_append_from_cvs(self, path):
        pass

    def download_all(self, path: str):
        for entry in self.entry_list:
            try:
                entry.download(path)
            except Exception as e:
                error_out(f"Exception downloading file: {e}")

class Downloader():
    def __init__(self):

        screen.update()

        #Gets project path
        self.appPath = os.path.dirname(os.path.abspath(__file__))
        self.layout = []

        #Gets playlist length
        with open(input_path, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                self.song_count = sum(1 for row in reader)
        self.song_count -=1

        
        # Retrieves song data then searches for them

        with open(input_path, 'r') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')

            next(csv_reader)

            #initates loading bar
            progress_bar.config(maximum=self.song_count)
            progress_bar['value']=0

            self.progress_of_bar = 0 

            for song in csv_reader:

                # Tell you what song it is on and how many you have left
                self.progress_of_bar +=1
                out_data = song[1] + ' by ' + song[3] + ' ' + str(self.progress_of_bar) + '/' + str(self.song_count) + '\n'
                info_out(out_data)

                # Gets the download url then downloads and converts it.
                self.download_and_meta_url = self.search(song[1]+' '+song[3])
                for element in self.download_and_meta_url:
                    self.download(output_path, element['url'], song[3], song[2], song[4], song[10])

                # updates loading bar
                progress_bar['value']+=1

                # updates screen
                screen.update()

    # Finds the url based off of the song name and artist
    def search(self, term):
        searcher = VideosSearch(term, 1)
        result = searcher.result()

        video = []
        for video_data in result['result']:
            video.append({
                "url": video_data['link'],
            })
        return video

    # Downloads the music if it can't it will skip it
    # This will also apply the meta data to the file
    def download(self, path, url, artist, album, date, genre):
        yt = YouTube(url)

        # tries to download the music. Raises an exception if it can't
        try:
            stream = yt.streams.filter(only_audio=True).first()
            convertin = stream.download(path) # Optional: specify download path
            convertout = convertin[:-3] + 'mp3'

            if mp3_download:
                self.convert_m4a_mp3(convertin, convertout)

                # attempts to apply metadata
                self.apply_metadata_mp3(convertout, convertin, artist, album, date, genre, self.get_youtube_id(url))
            
            else:
                self.apply_metadata_m4a(convertin, artist, album, date, genre, self.get_youtube_id(url))

        except:
            error_out("Content can't be downloaded")

    # Converts the .m4a to .mp3 also applies thumbnail
    # TODO: Class seperation
    def convert_m4a_mp3(self, file, path):
    # Applies thumbnail
    # Why?
        try:
            audio = MP3(self.old_path, ID3=ID3)

            #reads image
            with open(self.full_image_path, "rb") as f:
                image_data = f.read()
                audio.tags.add(
                    APIC(
                        encoding=3,  # UTF-8
                        mime='image/jpeg',
                        type=3,  # 3 is for Front Cover
                        desc='Cover',
                        data=image_data
                    )
                )
            audio.save()
            logger.info(f"Cover image embedded into {path}")
            os.remove(self.full_image_path)
        except:
            logger.error('Adding cover failed')

        if not os.path.exists(file):
            error_out(f"Input file '{file}' not found.\n")
            return
        if not os.path.isfile(path):
            try:
                command = [
                    'ffmpeg',
                    '-i', file,
                    '-acodec', 'libmp3lame',
                    '-q:a', '0',
                    path
                ]
                    
                subprocess.run(command, check=True, capture_output=True, text=True)
                info_out(f"Successfully converted '{file}' to '{path}'\n")
            except subprocess.CalledProcessError as e:
                error_out(f"Conversion failed: {e}\n")
                info_out(f"FFmpeg output: {e.stdout}\n")
                error_out(f"FFmpeg: {e.stderr}\n")
            except FileNotFoundError:
                error_out("FFmpeg not found. Please ensure FFmpeg is installed and in your system's PATH. \n")
        else:
            info_out('File already exists skipping.\n')

        os.remove(file)

        self.old_path=path

    # Applies the meta data
    def apply_metadata_mp3(self, path, path_mp3, artist, album, date, genre, video_id):
        # Gets the thumbnail image
        try:
            thumbnail_url = f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg'
            try:
                self.full_image_path = output_path + '/' + video_id + '.jpg'
                urllib.request.urlretrieve(thumbnail_url, self.full_image_path)
                logger.info(f'Thumbnail saved as', self.full_image_path)
            except Exception as e:
                logger.error(f'downloading thumbnail failed: {e}')
        except:
            thumbnail_url = f'https://img.youtube.com/vi/{video_id}/default.jpg'
            try:
                self.full_image_path = output_path + '/' + video_id + '.jpg'
                urllib.request.urlretrieve(thumbnail_url, self.full_image_path)
                logger.info(f'Thumbnail saved as', self.full_image_path)
            except Exception as e:
                logger.error(f'downloading thumbnail failed: {e}')

        try:
            # Load the MP3 file with EasyID3
            audio = MP3(path, ID3=EasyID3)

            # Modifies tags
            audio['artist'] = [artist]
            audio['album'] = [album]
            audio['date'] = [date]
            audio['genre'] = [genre] 

            # Save the changes
            audio.save()
            logger.debug("Metadata updated successfully!")

        except Exception as e:
            logger.error(f"{e}")

    def apply_metadata_m4a(self, path, artist, album, date, genre, video_id):
        try:
            thumbnail_url = f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg'
            try:
                self.full_image_path = output_path + '/' + video_id + '.jpg'
                urllib.request.urlretrieve(thumbnail_url, self.full_image_path)
                logger.info(f'Thumbnail saved as', self.full_image_path)
            except Exception as e:
                logger.error(f'downloading thumbnail failed: {e}')
        except:
            thumbnail_url = f'https://img.youtube.com/vi/{video_id}/default.jpg'
            try:
                self.full_image_path = output_path + '/' + video_id + '.jpg'
                urllib.request.urlretrieve(thumbnail_url, self.full_image_path)
                logger.info(f'Thumbnail saved as', self.full_image_path)
            except Exception as e:
                logger.error(f'downloading thumbnail failed: {e}')

        try:
            audiofile = EasyMP4(path)

            audiofile['artist'] = [artist]
            audiofile['album'] = [album]
            audiofile['date'] = [date]
            audiofile['genre'] = [genre]

            audiofile.save()
            info_out(f"Metadata applied successfully to: {path}")
        except FileNotFoundError:
            error_out(f"File not found at {path}")
        except Exception as e:
            error_out(f"An error occurred: {e}")

        try:
            audio = MP4(path)

            # Read the image data
            with open(self.full_image_path, 'rb') as f:
                image_data = f.read()

            # Sets image format
            image_format = MP4Cover.FORMAT_JPEG

            # Create an MP4Cover object
            cover = MP4Cover(image_data, imageformat=image_format)

            # Assign the cover art to the 'covr' tag
            audio['covr'] = [cover]

            # Save the changes to the M4A file
            audio.save()
            info_out(f"Cover art successfully embedded into '{path}'")

        except FileNotFoundError:
            error_out(f"File not found. Check paths for '{path}' or '{self.full_image_path}'.")
        except Exception as e:
            error_out(f"An error occurred: {e}")

        os.remove(self.full_image_path)

    # Gets video id for the thumbnail image
    def get_youtube_id(self, url, ignore_playlist=True):
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
                        # Strip any playlist parameters
                        return video_id.split('&')[0]
                    return video_id
        return None

# Getting the output file from the user
def get_out_path():
    global output_path
    output_path = filedialog.askdirectory()
    if output_path:
        info_out('Folder selected\n')
    else:
        output_path = user_music_dir()
        info_out('Using default path\n')

# Getting the path to the input CSV file
def get_in_path():
    global input_path
    input_path = filedialog.askopenfilename()
    if input_path:
        info_out('File selected\n')
    else:
        error_out('No file selected\n')

# Function for the mp3 option download
def mp3_m4a_option():
    global mp3_download
    mp3_download = not(mp3_download)
    print(mp3_download)
    mp3_option_button.config(text=str(mp3_download))
    screen.update()

# Opens the options window (TODO)
global options_window
options_window = ''

def open_options_window():

    print("test")

    global options_window

    try:
        if 'normal' != options_window.state():
            options_window = Toplevel(screen)
            options_window.title("Options window")
            options_window.configure(bg="black")

            mp3_option_button = Button(options_window, text=str(mp3_download), fg = "violet", highlightbackground = "black", command = [mp3_m4a_option, open_options_window])
            mp3_option_button.pack()

        else:
            mp3_download.config(text=str(mp3_download))
                                
            options_window.update()

    except:
        options_window = Toplevel(screen)
        options_window.title("Options window")
        options_window.configure(bg="black")

        mp3_option_button = Button(options_window, text=str(mp3_download), fg = "violet", highlightbackground = "black", command = [mp3_m4a_option, open_options_window])
        mp3_option_button.pack()

def open_download_folder():
    
    # Tries opening the folder in a new finder window on mac
    if not os.path.isdir(output_path):
        error_out(f"Folder '{output_path}' does not exist.")
        return

    try:
        subprocess.run(["open", output_path], check=True)
        info_out(f"Opened folder '{output_path}' in Finder.")
    except:

        # If it fails to open the folder in finder it will try to open the folder using Explorer on Windows
        try:
            webbrowser.open(output_path)
            info_out(f"Opened folder '{output_path}' in Finder.")
        except:
            error_out("Unable to open download path.")

def info_out(message: str):
    logger.info(message)
    text_output_area.insert(tk.END, message + "\n")
    text_output_area.see(tk.END) # Auto-scroll to the end
    
def error_out(message: str):
    logger.error(message)
    text_output_area.insert(tk.END, "[ERROR]: " + message + "\n")
    text_output_area.see(tk.END) # Auto-scroll to the end

def warn_out(message: str):
    logger.warning(message)
    text_output_area.insert(tk.END, "[WARNING]: " + message + "\n")
    text_output_area.see(tk.END) # Auto-scroll to the end



if __name__ == "__main__":

    # Defining the screen
    screen = Tk()
    screen.title("New spotify downloader")

    # Setting Screen Size
    screen.geometry("540x740")

    # Ensuring text stays centered
    screen.grid_columnconfigure(0, weight=1)  

    # Making the background black
    screen.configure(bg="black")

    # Writing the inital text
    inital_text = Label(text="Welcome\nplease select your CSV file from exportify and output folder", fg = 'violet', bg = 'black')
    inital_text.grid(row=0)

    # Button that opens the option windows (TODO)
    # options_window_open_button = Button(text='Options', fg = "violet", highlightbackground = "black", command = open_options_window)
    # options_window_open_button.grid(row=5)

    # Label explaining what the bottom button does.
    download_as_mp3_label = Label(text="Download as mp3:", fg = 'violet', bg = 'black')
    download_as_mp3_label.grid(row=5)

    # Option button for downloading as and m4a or mp3
    mp3_option_button = Button(text=str(mp3_download), fg = "violet", highlightbackground = "black", command = mp3_m4a_option, relief="sunken")
    mp3_option_button.grid(row=6)

    # Button that opens download folder
    open_download = Button(text="Open download folder", fg = "violet", highlightbackground = "black", command = open_download_folder)
    open_download.grid(row=7)

    # Defines the progress bar
    progress_bar_look = ttk.Style()
    progress_bar_look.theme_use('clam')
    progress_bar_look.configure("violet.Horizontal.TProgressbar", foreground='black', background='violet', highlightbackground = "black")
    progress_bar = ttk.Progressbar(screen,orient=HORIZONTAL, style='violet.Horizontal.TProgressbar', length=300,mode="determinate",takefocus=True)
    progress_bar.grid(row=8)

    # Initializing data output gui
    text_output_area = tk.Text(screen, wrap='word', height=40, width=65)
    text_output_area.grid(row=9,column=0)

    scrollbar = tk.Scrollbar(screen, command=text_output_area.yview)
    scrollbar.grid(row=9,column=1)
    text_output_area.config(yscrollcommand=scrollbar.set)

    # Getting the input file from the user
    get_input = Button(text = "Select input file", fg = "violet", highlightbackground = "black", command = get_in_path)
    get_input.grid(row=2)


    # Drawing the select path button
    download_path_button = Button(text = "Select output folder", fg = "violet", highlightbackground = "black", command = get_out_path)
    download_path_button.grid(row=3)

    # Drawing the download button
    download_button = Button(text = "Download", fg = "violet", highlightbackground = "black", command = Downloader)
    download_button.grid(row=4)

    # Main screen loop
    screen.mainloop()