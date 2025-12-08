import os
import subprocess
import logging
import csv
import pandas as pd
from io import BytesIO
from typing import Self
import webbrowser

# Why do we have this and import tkinter as tk?
# TODO: Remove extra imports
from tkinter import *
from tkinter import filedialog
from tkinter import ttk
import tkinter as tk

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

# Clears the custom playlist csv and sets the default csv file to be the custom playlist one
with open(os.path.dirname(os.path.abspath(__file__))+"/custom.csv", "r+", encoding='utf-8') as f:
    f.truncate(0)
    writer = csv.writer(f)
    writer.writerow(["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24"])

global custom_playlist
input_path = os.path.dirname(os.path.abspath(__file__))+"/custom.csv"

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

        with open(input_path, 'r', encoding='utf-8') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')

            next(csv_reader)

            #initates loading bar
            progress_bar.config(maximum=self.song_count)
            progress_bar['value']=0

            self.progress_of_bar = 0 
            
            for song in csv_reader:
                try:
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
                except:
                    error_out("Failed to read song data")
                
            progress_bar['value']+=1

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
            path_to_og = stream.download(path) # Optional: specify download path

            print(path_to_og)

            # Applies meta_data
            self.apply_metadata(path_to_og, artist, album, date, genre, self.get_youtube_id(url))

            # Will convert the files based on the options selected 
            self.converter(path_to_og)


        except:
            error_out("Content can't be downloaded")

    # Converts the .m4a to .mp3 also applies thumbnail
    # TODO: Class seperation

    def converter(self, path):

        global download_options

        extensions = []

        command = ''

        try:
            for index in download_options.curselection():
                extensions.append(download_options.get(index))
        except:
            extensions = ['m4a']
        
        if extensions != []:
            try:
                for extend in extensions:
                    if extend == 'mp3':

                        out_file = path[:-3] + 'mp3'

                        if not os.path.exists(path):
                            error_out(f"Input file '{path}' not found.\n")
                            return
                        if not os.path.isfile(out_file):
                            command = [
                                'ffmpeg',
                                '-i', path,
                                '-acodec', 'libmp3lame',
                                '-q:a', '0',
                                out_file
                            ]

                        else:
                            info_out('File already exists skipping.\n')

                    if extend == 'wav':

                        out_file = path[:-3] + "wav"

                        if not os.path.exists(path):
                            error_out(f"Input file '{path}' not found.\n")
                            return
                        if not os.path.isfile(out_file):
                            command = [
                                'ffmpeg',
                                '-i', path,
                                '-acodec', 'pcm_s16le',
                                '-ar', '44800', "-ac", "2",
                                out_file
                            ]

                        else:
                            info_out('File already exists skipping.\n')

                    if extend == "flac":
                        out_file = path[:-3] + "flac"

                        if not os.path.exists(path):
                            error_out(f"Input file '{path}' not found.\n")
                            return
                        if not os.path.isfile(out_file):
                            command = [
                                'ffmpeg',
                                '-i', path,
                                '-c:a', 'flac', 
                                '-sample_fmt', 's32',
                                out_file
                            ]

                    if extend == "AAC":
                        out_file = path[:-3] + "AAC"

                        if not os.path.exists(path):
                            error_out(f"Input file '{path}' not found.\n")
                            return
                        if not os.path.isfile(out_file):
                            command = [
                                'ffmpeg',
                                '-i', path, 
                                '-c:a', 'aac',
                                out_file
                            ]

                    if extend == "OGG":
                        out_file = path[:-3] + "ogg"

                        if not os.path.exists(path):
                            error_out(f"Input file '{path}' not found.\n")
                            return
                        if not os.path.isfile(out_file):
                            command = [ 'ffmpeg', '-i', path, '-c:a', 'libvorbis', '-qscale:a', '5', out_file]

                    if command != "":
                        try:
                            subprocess.run(command, check=True, capture_output=True, text=True)
                            info_out(f"Successfully converted '{path}' to '{out_file}'\n")
                        except subprocess.CalledProcessError as e:
                            error_out(f"Conversion failed: {e}\n")
                            info_out(f"FFmpeg output: {e.stdout}\n")
                            error_out(f"FFmpeg: {e.stderr}\n")
                        except FileNotFoundError:
                            error_out("FFmpeg not found. Please ensure FFmpeg is installed and in your system's PATH. \n")

            except:
                error_out("Failed to convert to selected format")

            if 'm4a' not in extensions:
                    os.remove(path)

    # Applies metadata
    def apply_metadata(self, path, artist, album, date, genre, video_id):
        thumbnail_url = f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg'
        try:
            self.full_image_path = output_path + '/' + video_id + '.jpg'
            urllib.request.urlretrieve(thumbnail_url, self.full_image_path)
            logger.info(f'Thumbnail saved as', self.full_image_path)
        except Exception as e:
            logger.error(f'downloading thumbnail failed: {e}')

            thumbnail_url = f'https://img.youtube.com/vi/{video_id}/default.jpg'
            try:
                self.full_image_path = output_path + '/' + video_id + '.jpg'
                urllib.request.urlretrieve(thumbnail_url, self.full_image_path)
                logger.info(f'Thumbnail saved as', self.full_image_path)
            except Exception as e:
                logger.error(f'downloading low res thumbnail failed: {e}')
    

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
        error_out('No file selected using defualt csv (manual add)\n')
        input_path = os.path.dirname(os.path.abspath(__file__))+"/custom.csv"

# Opens the options window (TODO)
def open_options_window():
    global download_options

    options_menu_window = tk.Toplevel(screen)
    options_menu_window.title("Options window")

    options_menu_window.configure(bg="black")

    options_menu_window.geometry("500x500")

    download_options_Label = Label(options_menu_window, text="Please select the format you want the songs downloaded in", fg = 'violet', bg = 'black')
    download_options_Label.pack()

    download_options = tk.Listbox(options_menu_window, height=10, width=40, selectmode="multiple")
    download_options.pack(pady=10)

    download_options.insert(tk.END, "m4a")
    download_options.insert(tk.END, "mp3")
    download_options.insert(tk.END, "wav")
    download_options.insert(tk.END, "flac")
    download_options.insert(tk.END, "AAC")
    download_options.insert(tk.END, "OGG")

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

class Custom_Playlist_Window():
    def __init__(self):
        
        # Initializes the lists for this window
        self.song_list_length = 0
        self.song_entries = []
        self.artist_entries = []
        self.album_entries = []
        self.genre_entries = []
        self.date_entries = []
        self.remove_buttons = []

        # [TODO] Test if I really need to have this external frame (I don't think I do)
        custom_playlist_screen = tk.Toplevel(screen)
        custom_playlist_screen.title("Custom playlist window")
        custom_playlist_screen.geometry("500x500")

        custom_playlist_screen.configure(bg="black")

        custom_list_frame = Frame(custom_playlist_screen)
        custom_list_frame.pack(fill="both", expand=True)

        scroll_list_canvas = Canvas(custom_list_frame, borderwidth=0, background="black")
        scroll_list_canvas.pack(side="left", fill="both", expand=True)

        list_scrollbar = Scrollbar(custom_list_frame, orient="vertical", command=scroll_list_canvas.yview)
        list_scrollbar.pack(side="right", fill="y")

        scroll_list_canvas.config(yscrollcommand=list_scrollbar.set)

        self.interior_list_frame = Frame(scroll_list_canvas)
        scroll_list_canvas.create_window((0,0), window=self.interior_list_frame, anchor="nw")

        # Centers the text and other stuff. (Applies weight to all relevant columns)
        for i in range(7):
            self.interior_list_frame.grid_columnconfigure(i, weight=1)
        self.interior_list_frame.grid_columnconfigure(7, weight=1)

        custom_explain_label = Label(self.interior_list_frame, text="Please input the name, artist, album, genre,\n and date released.\n If you don't know all this info\n just leave the box blank", justify=tk.CENTER)
        custom_explain_label.grid(row=0, column=0, columnspan=5, sticky="n")
        
        custom_song = Label(self.interior_list_frame, text="Song Name")
        custom_song.grid(row=1, column=0)

        custom_artist = Label(self.interior_list_frame, text="Artist")
        custom_artist.grid(row=1, column=1)

        custom_album = Label(self.interior_list_frame, text="Album")
        custom_album.grid(row=1, column=2)

        custom_genre = Label(self.interior_list_frame, text="Genre")
        custom_genre.grid(row=1, column=3)
        
        custom_date = Label(self.interior_list_frame, text="Date")
        custom_date.grid(row=1, column=4)

        self.add_button = Button(self.interior_list_frame, text="Add", command= self.add)
        self.add_button.grid(row=self.song_list_length+2, column=0, columnspan=5, sticky="s")

        self.save_button = Button(self.interior_list_frame, text="Save", command = self.save)
        self.save_button.grid(row=self.song_list_length+3, column=0, columnspan=5, sticky="s")

    def add(self):
        self.song_entries.append(Entry(self.interior_list_frame))
        self.artist_entries.append(Entry(self.interior_list_frame))
        self.album_entries.append(Entry(self.interior_list_frame))
        self.genre_entries.append(Entry(self.interior_list_frame))
        self.date_entries.append(Entry(self.interior_list_frame))
        self.remove_buttons.append(Button(self.interior_list_frame ,text="Remove", command=self.remove))

        self.song_entries[self.song_list_length].grid(row=self.song_list_length+2, column=0)
        self.artist_entries[self.song_list_length].grid(row=self.song_list_length+2, column=1)
        self.album_entries[self.song_list_length].grid(row=self.song_list_length+2, column=2)
        self.genre_entries[self.song_list_length].grid(row=self.song_list_length+2, column=3)
        self.date_entries[self.song_list_length].grid(row=self.song_list_length+2, column=4)
        self.remove_buttons[self.song_list_length].grid(row=self.song_list_length+2, column=5)

        self.song_list_length += 1

        self.add_button.grid(row=self.song_list_length+2, sticky="s")
        self.save_button.grid(row=self.song_list_length+3, column=0, columnspan=5, sticky="s")

    def remove(self):
        self.song_list_length -= 1
        self.add_button.grid(row=self.song_list_length+2)

        self.song_entries[self.song_list_length].destroy()
        self.song_entries.remove(self.song_entries[self.song_list_length])

        self.artist_entries[self.song_list_length].destroy()
        self.artist_entries.remove(self.artist_entries[self.song_list_length])

        self.album_entries[self.song_list_length].destroy()
        self.album_entries.remove(self.album_entries[self.song_list_length])

        self.genre_entries[self.song_list_length].destroy()
        self.genre_entries.remove(self.genre_entries[self.song_list_length])

        self.date_entries[self.song_list_length].destroy()
        self.date_entries.remove(self.date_entries[self.song_list_length])

        self.remove_buttons[self.song_list_length].destroy()
        self.remove_buttons.remove(self.remove_buttons[self.song_list_length])

    def save(self):
        self.songs = []
        self.artists = []
        self.albums = []
        self.genres = []
        self.dates = []

        for song_entry in self.song_entries:
            self.songs.append(song_entry.get())

        for artist_entry in self.artist_entries:
            self.artists.append(artist_entry.get())

        for album_entry in self.album_entries:
            self.albums.append(album_entry.get())

        for genre_entry in self.genre_entries:
            self.genres.append(genre_entry.get())

        for date_entry in self.date_entries:
            self.dates.append(date_entry.get())

        custom_csv = pd.read_csv(os.path.dirname(os.path.abspath(__file__))+"/custom.csv")
        for i in range(self.song_list_length):
            custom_csv.loc[i, 1] = self.songs[i]
            print(custom_csv)
        custom_csv.to_csv(os.path.dirname(os.path.abspath(__file__))+"/custom.csv")

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
    inital_text = Label(text="Welcome\nplease select your CSV file from exportify\n or press manual add and select output folder", fg = 'violet', bg = 'black')
    inital_text.grid(row=0)

    # Label explaining what the bottom button does.
    # download_as_mp3_label = Label(text="Download as mp3:", fg = 'violet', bg = 'black')
    # download_as_mp3_label.grid(row=5)

    # Option button for downloading as and m4a or mp3
    mp3_option_button = Button(text="Open the options window", fg = "violet", highlightbackground = "black", command = open_options_window) #, relief="sunken"
    mp3_option_button.grid(row=6)

    # Button that opens download folder
    open_download = Button(text="Open download folder", fg = "violet", highlightbackground = "black", command = open_download_folder)
    open_download.grid(row=7)

    # Defines the progress bar
    progress_bar_look = ttk.Style()
    progress_bar_look.theme_use('clam')
    progress_bar_look.configure("violet.Horizontal.TProgressbar", foreground='black', background='violet', highlightbackground = "black")
    progress_bar = ttk.Progressbar(screen,orient=HORIZONTAL, style='violet.Horizontal.TProgressbar', length=300,mode="determinate",takefocus=True)
    progress_bar.grid(row=9)

    # Initializing data output gui
    text_output_area = tk.Text(screen, wrap='word', height=20, width=65)
    text_output_area.grid(row=10,column=0)

    scrollbar = tk.Scrollbar(screen, command=text_output_area.yview)
    scrollbar.grid(row=10,column=1)
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

    open_window_button = Button(text = "Manual Add", fg = "violet", highlightbackground = "black", command = Custom_Playlist_Window)
    open_window_button.grid(row=8)

    # Main screen loop
    screen.mainloop()