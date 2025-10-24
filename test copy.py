import subprocess

command = [
        'ffmpeg',
        '-i', "/Users/presian/Music/usedcvnt, abyssal.angel - yours forever.m4a",
        '-acodec', 'libmp3lame',
        '-q:a', '0',
        "/Users/presian/Music/usedcvnt, abyssal.angel - yours forever.mp3"
    ]
        
subprocess.run(command, check=True, capture_output=True, text=True)