import tkinter as tk
from tkinter import filedialog
import threading
import time
from pydub import AudioSegment, effects
from pydub.playback import _play_with_simpleaudio
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class PracticeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Guitar Practice App")

        # Audio
        self.audio = None
        self.play_obj = None
        self.playing = False
        self.start_ms = 0
        self.end_ms = None
        self.speed = 1.0
        self.tempo = 1.0
        self.volume = 0.0

        # Waveform
        self.fig, self.ax = plt.subplots(figsize=(6, 2))
        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.canvas.mpl_connect("button_press_event", self.on_click)

        # Controls
        self.load_btn = tk.Button(root, text="Load MP3", command=self.load_file)
        self.load_btn.pack(pady=5)

        self.speed_scale = tk.Scale(root, from_=0.5, to=2.0, resolution=0.1,
                                    orient="horizontal", label="Speed (Pitch+Tempo)", command=self.update_speed)
        self.speed_scale.set(1.0)
        self.speed_scale.pack(fill="x")

        self.tempo_scale = tk.Scale(root, from_=0.5, to=2.0, resolution=0.1,
                                    orient="horizontal", label="Tempo (%100 = Normal)", command=self.update_tempo)
        self.tempo_scale.set(1.0)
        self.tempo_scale.pack(fill="x")

        self.volume_scale = tk.Scale(root, from_=-20, to=10, resolution=1,
                                     orient="horizontal", label="Volume (dB)", command=self.update_volume)
        self.volume_scale.set(0)
        self.volume_scale.pack(fill="x")

        self.play_btn = tk.Button(root, text="Play", command=self.play_audio)
        self.play_btn.pack(pady=5)

        self.stop_btn = tk.Button(root, text="Stop", command=self.stop_audio)
        self.stop_btn.pack(pady=5)

        # Metronome
        self.bpm_scale = tk.Scale(root, from_=40, to=240, resolution=1,
                                  orient="horizontal", label="Metronome BPM")
        self.bpm_scale.set(120)
        self.bpm_scale.pack(fill="x")

        self.metro_btn = tk.Button(root, text="Start Metronome", command=self.toggle_metronome)
        self.metro_btn.pack(pady=5)

        self.metronome_on = False

    def load_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("MP3 files", "*.mp3")])
        if file_path:
            self.audio = AudioSegment.from_mp3(file_path)
            self.end_ms = len(self.audio)
            self.plot_waveform()

    def plot_waveform(self):
        samples = np.array(self.audio.get_array_of_samples())
        if self.audio.channels == 2:
            samples = samples.reshape((-1, 2))
            samples = samples.mean(axis=1)
        times = np.linspace(0, len(samples) / self.audio.frame_rate, num=len(samples))
        self.ax.clear()
        self.ax.plot(times, samples, color="blue")
        self.ax.set_xlim([0, times[-1]])
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Amplitude")
        self.canvas.draw()

    def on_click(self, event):
        if self.audio is None or event.xdata is None:
            return
        pos_ms = int(event.xdata * 1000)
        if self.start_ms == 0 or (self.start_ms is not None and self.end_ms is not None):
            self.start_ms = pos_ms
            self.end_ms = None
        else:
            self.end_ms = pos_ms
        self.draw_markers()

    def draw_markers(self):
        self.ax.clear()
        samples = np.array(self.audio.get_array_of_samples())
        if self.audio.channels == 2:
            samples = samples.reshape((-1, 2))
            samples = samples.mean(axis=1)
        times = np.linspace(0, len(samples) / self.audio.frame_rate, num=len(samples))
        self.ax.plot(times, samples, color="blue")
        if self.start_ms:
            self.ax.axvline(self.start_ms/1000, color="green", linestyle="--")
        if self.end_ms:
            self.ax.axvline(self.end_ms/1000, color="red", linestyle="--")
        self.ax.set_xlim([0, times[-1]])
        self.canvas.draw()

    def update_speed(self, val):
        self.speed = float(val)

    def update_tempo(self, val):
        self.tempo = float(val)

    def update_volume(self, val):
        self.volume = float(val)

    def get_processed_segment(self):
        if self.audio is None:
            return None

        if self.end_ms is None:
            self.end_ms = len(self.audio)

        seg = self.audio[self.start_ms:self.end_ms]

        # Apply speed (affects pitch + tempo)
        seg = seg._spawn(seg.raw_data, overrides={
            "frame_rate": int(seg.frame_rate * self.speed)
        }).set_frame_rate(seg.frame_rate)

        # Apply tempo (time-stretch without pitch change)
        if self.tempo != 1.0:
            seg = effects.speedup(seg, playback_speed=self.tempo)

        # Apply volume
        seg += self.volume

        return seg

    def play_audio(self):
        if self.audio is None:
            return

        def play_loop():
            self.playing = True
            while self.playing:
                seg = self.get_processed_segment()
                if seg is None:
                    break
                self.play_obj = _play_with_simpleaudio(seg)
                self.play_obj.wait_done()

        threading.Thread(target=play_loop, daemon=True).start()

    def stop_audio(self):
        self.playing = False
        if self.play_obj:
            self.play_obj.stop()

    def toggle_metronome(self):
        if not self.metronome_on:
            self.metronome_on = True
            self.metro_btn.config(text="Stop Metronome")
            threading.Thread(target=self.metronome_loop, daemon=True).start()
        else:
            self.metronome_on = False
            self.metro_btn.config(text="Start Metronome")

    def metronome_loop(self):
        # Simple tick using numpy-generated click
        sample_rate = 44100
        click = (np.sin(2*np.pi*np.arange(int(0.05*sample_rate))*1000/sample_rate)*32767).astype(np.int16)
        click_audio = AudioSegment(click.tobytes(), frame_rate=sample_rate, sample_width=2, channels=1)
        while self.metronome_on:
            _play_with_simpleaudio(click_audio)
            bpm = self.bpm_scale.get()
            time.sleep(60.0 / bpm)

if __name__ == "__main__":
    root = tk.Tk()
    app = PracticeApp(root)
    root.mainloop()
