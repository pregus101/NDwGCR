import csv
import os
from bs4 import BeautifulSoup
import urllib.request
from youtubesearchpython import VideosSearch
from pytubefix import YouTube
import subprocess
from tkinter import *
from tkinter import filedialog
from platformdirs import user_music_dir
from tkinter import ttk
import tkinter as tk
from tkinter import scrolledtext
import yt_dlp
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3
from mutagen.mp4 import MP4, MP4Tags

#Sets default output path
output_path = user_music_dir()

class Downloader():

    def __init__(self):
        #updates screen
        screen.update_idletasks()
        screen.after(25)

        #Gets project path
        self.appPath = os.path.dirname(os.path.abspath(__file__))
        self.layout = []

        #Gets playlist length
        with open(input_path, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                self.song_count = sum(1 for row in reader)
        self.song_count -=1

        
        #Retrieves song data then searches for them

        with open(input_path, 'r') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')

            next(csv_reader)

            #initates loading bar
            progress_bar.config(maximum=self.song_count)
            progress_bar['value']=0

            self.progress_of_bar = 0 

            for song in csv_reader:

                #Tell you what song it is on and how many you have left
                self.progress_of_bar +=1
                out_data = song[1] + ' by ' + song[3] + ' ' + str(self.progress_of_bar) + '/' + str(self.song_count) + '\n'
                output_and_scroll(out_data)

                #Gets the download url then downloads and converts it.
                self.download_and_meta_url = self.search(song[1]+' '+song[3])
                for element in self.download_and_meta_url:
                    self.download(output_path, element['url'], song[3], song[2], song[4], song[10])

                #updates loading bar
                progress_bar['value']+=1

                #updates screen
                screen.update_idletasks()
                screen.after(25)

    #Finds the url based off of the song name and artist
    def search(self, term):
        searcher = VideosSearch(term, 1)
        result = searcher.result()

        video = []
        for video_data in result['result']:
            video.append({
                "url": video_data['link'],
            })
        return video

    #Downloads the music if it can't it will skip it This will also apply the meta data to the file
    def download(self, path, url, artist, album, date, genre):
        yt = YouTube(url)

        #tries to download the music. Returns error if you it can't
        try:
            stream = yt.streams.filter(only_audio=True).first()
            convertin = stream.download(path) # Optional: specify download path
            convertout = convertin[:-3]+'mp3'
            self.convert_m4a_mp3(convertin, convertout)

            #attempts to apply metadata
            self.apply_metadata(convertout, artist, album, date, genre)

        except:
            output_and_scroll( "Error, content can't be downloaded")

    #Converts the .m4a to .mp3
    def convert_m4a_mp3(self, file, path):
        if not os.path.exists(file):
            output_and_scroll(f"Error: Input file '{file}' not found.\n")
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
                output_and_scroll(f"Successfully converted '{file}' to '{path}'\n")
            except subprocess.CalledProcessError as e:
                output_and_scroll(f"Error during conversion: {e}\n")
                output_and_scroll(f"FFmpeg output: {e.stdout}\n")
                output_and_scroll(f"FFmpeg error: {e.stderr}\n")
            except FileNotFoundError:
                output_and_scroll("Error: FFmpeg not found. Please ensure FFmpeg is installed and in your system's PATH. \n")
        else:
            output_and_scroll('File already exists skipping.\n')

        os.remove(file)

    #applies the meta data
    def apply_metadata(self, path, artist, album, date, genre):
        try:
            # Load the MP3 file with EasyID3
            audio = MP3(path, ID3=EasyID3)

            # Print current title (if exists)
            print(f"Original Title: {audio.get('title', ['N/A'])[0]}")

            # Modifies tags
            audio['artist'] = [artist]
            audio['album'] = [album]
            audio['date'] = [date]
            audio['genre'] = [genre] 

            # Save the changes
            audio.save()
            print("Metadata updated successfully!")

        except Exception as e:
            print(f"An error occurred: {e}")


# defining the screen
screen = Tk()
screen.title("New spotify downloader")

#Setting Screen Size
screen.geometry("540x740")

#Ensuring text stays centered
screen.grid_columnconfigure(0, weight=1)  

#Making the background black
screen.configure(bg="black")

#Writing the inital text
inital_text = Label(text="Welcome\nplease select your CSV file and output folder", fg = 'violet', bg = 'black')
inital_text.grid(row=0)

#Getting the output file from the user
def get_out_path():
    global output_path
    output_path = filedialog.askdirectory()
    if output_path:
        output_and_scroll('Folder selected\n')
    else:
        output_path = user_music_dir()
        output_and_scroll('Using default path\n')

def get_in_path():
    global input_path
    input_path = filedialog.askopenfilename()
    if input_path:
        output_and_scroll('file selected\n')
    else:
        output_and_scroll('error no file selected\n')

#defines the progress bar
progress_bar_look = ttk.Style()
progress_bar_look.theme_use('clam')
progress_bar_look.configure("violet.Horizontal.TProgressbar", foreground='black', background='violet', highlightbackground = "black")
progress_bar = ttk.Progressbar(screen,orient=HORIZONTAL, style='violet.Horizontal.TProgressbar', length=300,mode="determinate",takefocus=True)
progress_bar.grid(row=5)

# #initializing data output gui
text_output_area = tk.Text(screen, wrap='word', height=40, width=65)
text_output_area.grid(row=6,column=0)

scrollbar = tk.Scrollbar(screen, command=text_output_area.yview)
scrollbar.grid(row=6,column=1)
text_output_area.config(yscrollcommand=scrollbar.set)


def output_and_scroll(message):
    text_output_area.insert(tk.END, message + "\n")
    text_output_area.see(tk.END) # Auto-scroll to the end

#Getting the input file from the user
get_input = Button(text = "Select input file", fg = "violet", highlightbackground = "black", command = get_in_path)
get_input.grid(row=2)


#Drawing the select path button
download_path_button = Button(text = "Select output folder", fg = "violet", highlightbackground = "black", command = get_out_path)
download_path_button.grid(row=3)

#Drawing the download button
download_button = Button(text = "Download", fg = "violet", highlightbackground = "black", command = Downloader)
download_button.grid(row=4)

#Main screen loop
screen.mainloop()
