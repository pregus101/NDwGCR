import tkinter as tk
from tkinter import filedialog
from download import downloader
import platformdirs


class main:
    def __init__(self):
        self.downloader = downloader()
        self.output_formats = ["mp3"]
        self.output_folder = platformdirs.user_music_dir()
        self.csv_file = ""
        self.csv_file_type = "exptfy"

    def select_csv_file(self):
        self.csv_file = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if self.csv_file:
            print(f"Selected CSV file: {self.csv_file}")

    def select_output_folder(self):
        self.output_folder = filedialog.askdirectory()
        if self.output_folder:
            print(f"Selected output folder: {self.output_folder}")

    def start_download(self):
        if self.csv_file and self.output_folder:
            self.downloader.start_download(self.csv_file, self.output_folder, self.csv_file_type, self.output_formats)
        else:
            print("Please select a CSV file and an output folder before starting the download.")


if __name__ == "__main__":
    # Create an instance of the downloader class

    app = main()

    screen = tk.Tk()
    screen.geometry("400x200")
    screen.title("NDwGCR")

    # Create buttons for selecting CSV file, output folder, and starting the download
    select_csv_button = tk.Button(screen, text="Select CSV File", command=app.select_csv_file)
    select_csv_button.pack(pady=10)

    select_output_button = tk.Button(screen, text="Select Output Folder", command=app.select_output_folder)
    select_output_button.pack(pady=10)

    start_download_button = tk.Button(screen, text="Start Download", command=app.start_download)
    start_download_button.pack(pady=10)

    screen.mainloop()  # Keep the GUI running until the user closes it