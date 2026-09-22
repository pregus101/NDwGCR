from pytubefix import YouTube
import os
import yt_dlp

def download_subtitles_with_ytdlp(url, language='en', output_path='./', video_title=''):
    # Try to download subtitles, with fallback to auto-generated captions
    ydl_opts = {
        'writesubtitles': True,  # Download subtitles
        'writeautosub': True,  # Download automatic subtitles as fallback
        'subtitleslangs': [language, 'en', ''],  # Try requested language, then English, then any available
        'skip_download': True, # Skip the video download
        'subtitle_format': 'srt', # Specify format
        'outtmpl': os.path.join(output_path, video_title if video_title else '%(title)s') + '.%(ext)s', # Output template with extension
        'quiet': False, # Show output to debug subtitle download
        'no_warnings': False,
        'verbose': True, # Add verbose output
    }

    print(f"📥 Downloading subtitles to: {ydl_opts['outtmpl']}")
    print(f"📝 Trying languages: {language}, en, or any available")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            print(f"✅ Subtitle download completed.")
            # List files in output folder to verify
            if os.path.exists(output_path):
                print(f"📂 Files in {output_path}:")
                for file in os.listdir(output_path):
                    print(f"   - {file}")

    except Exception as e:
        print(f"❌ An error occurred during subtitle download: {e}")
        import traceback
        traceback.print_exc()


print("To exit this program please press ctrl-c")


while True:
    link = input("Please enter the link of the video you want to download: ")
    yt = YouTube(link)

    # Create folder named after the video
    video_title = yt.title
    # Remove invalid characters from folder name
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in invalid_chars:
        video_title = video_title.replace(char, '')
    
    output_folder = os.path.join(os.getcwd(), video_title)
    os.makedirs(output_folder, exist_ok=True)

    # Download highest quality video stream
    try:
        video_stream = yt.streams.filter(adaptive=True, file_extension='mp4', res='1080p').first() # Adjust res as needed
    except:
        video_stream = yt.streams.filter(adaptive=True, file_extension='mp4', res='720p').first() # Adjust res as needed
    path_old = video_stream.download(output_folder)

    video_path = path_old[:-3] + "_video.mp4"

    os.rename(path_old, video_path)

    # Download highest quality audio stream
    audio_stream = yt.streams.filter(only_audio=True, file_extension='mp4').first()
    audio_path_old = audio_stream.download(output_folder)

    audio_path = audio_path_old[:-4] + "_audio.m4a"

    os.rename(audio_path_old, audio_path)

    # Merges the files
    import subprocess
    subprocess.run(['ffmpeg', '-i', video_path, '-i', audio_path, '-c:v', 'copy', '-c:a', 'aac', path_old])

    os.remove(video_path)
    os.remove(audio_path)

    download_subtitles_with_ytdlp(link, "ja", output_folder, video_title)

    print("Successful")

