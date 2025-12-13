import tkinter as tk
from tkinter import filedialog
import threading
import time
from pydub import AudioSegment, effects
import pygame
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class AppState:
    IDLE = "idle" # No song loaded or stopped
    LOADED = "loaded" # Song loaded, ready to play
    PLAYING = "playing" # Currently playing
    PAUSED = "paused" # Paused
    STOPPED = "stopped" # Stopped after playing

class PracticeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Guitar with your guitar app")

        # Initialize pygame mixer
        pygame.mixer.init()

        # State machine
        self.state = AppState.IDLE

        # Audio
        self.audio = None
        self.play_obj = None
        self.playing = False
        self.current_pos_ms = 0  # Track current playback position
        self.start_ms = 0
        self.end_ms = None
        self.speed_percent = 100
        self.pending_speed = 100
        self.tempo = 1.0
        self.volume = 0.0
        self.clock = pygame.time.Clock()
        self.sound = None
        self.channel = None

        # Waveform
        self.fig, self.ax = plt.subplots(figsize=(6, 2))
        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.canvas.mpl_connect("button_press_event", self.on_click)

        # Controls
        self.load_btn = tk.Button(root, text="Load MP3", command=self.load_file)
        self.load_btn.pack(pady=5)

        self.clear_btn = tk.Button(root, text="Clear", command=self.clear_song)
        self.clear_btn.pack(pady=5)

        # Time display label
        self.time_label = tk.Label(root, text="0:00 / 0:00", font=("Arial", 10))
        self.time_label.pack(pady=5)
        self.time_label.pack(pady=5)

        # Progress scale
        self.progress_scale = tk.Scale(root, from_=0, to=0, orient="horizontal", 
                                       showvalue=0, label="Progress", command=self.on_scale_change)
        self.progress_scale.pack(fill="x")

        self.speed_scale = tk.Scale(root, from_=50, to=160, resolution=1,
                                    orient="horizontal", label="Speed (%)", command=self.on_speed_drag)
        self.speed_scale.bind("<ButtonRelease-1>", self.on_speed_commit)
        self.speed_scale.set(100)
        self.speed_scale.pack(fill="x")

        self.volume_scale = tk.Scale(root, from_=0, to=40, resolution=1,
                                     orient="horizontal", label="Volume (dB)", command=self.update_volume)
        self.volume_scale.set(0)
        self.volume_scale.pack(fill="x")

        self.play_btn = tk.Button(root, text="Play", command=self.play_audio)
        self.play_btn.pack(pady=5)

        self.pause_btn = tk.Button(root, text="Pause", command=self.pause_audio)
        self.pause_btn.pack(pady=5)

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

        self.update_ui_state()

    def format_time(self, ms):
        """Convert milliseconds to MM:SS format"""
        minutes = ms // 60000
        seconds = (ms % 60000) // 1000
        millis = ms % 1000
        return f"{minutes}:{seconds:02d}:{millis:03d}"

    def update_time_label(self):
        """Update the time display label"""
        if self.end_ms is None:
            total = "0:00:000"
        else:
            total = self.format_time(self.end_ms)
        current = self.format_time(self.current_pos_ms)
        self.time_label.config(text=f"{current} / {total}")

    def set_state(self, new_state):
        self.state = new_state
        self.update_ui_state()

    def update_ui_state(self):
        # Enable/disable buttons based on state
        if self.state == AppState.IDLE:
            self.play_btn.config(state="disabled")
            self.pause_btn.config(state="disabled")
            self.stop_btn.config(state="disabled")
            self.clear_btn.config(state="disabled")
        elif self.state == AppState.LOADED:
            self.play_btn.config(state="normal")
            self.pause_btn.config(state="disabled")
            self.stop_btn.config(state="disabled")
            self.clear_btn.config(state="normal")
        elif self.state == AppState.PLAYING:
            self.play_btn.config(state="disabled")
            self.pause_btn.config(state="normal")
            self.stop_btn.config(state="normal")
            self.clear_btn.config(state="disabled")
        elif self.state == AppState.PAUSED:
            self.play_btn.config(state="normal")
            self.pause_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.clear_btn.config(state="disabled")
        elif self.state == AppState.STOPPED:
            self.play_btn.config(state="normal")
            self.pause_btn.config(state="disabled")
            self.stop_btn.config(state="disabled")
            self.clear_btn.config(state="normal")

    def load_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("MP3 files", "*.mp3")])
        if file_path:
            self.audio = AudioSegment.from_mp3(file_path)
            self.end_ms = len(self.audio)
            self.start_ms = 0
            self.current_pos_ms = 0
            self.progress_scale.config(to=self.end_ms)
            self.update_time_label()
            self.plot_waveform()
            self.set_state(AppState.LOADED)
        else:
            # print on gui with ("No file selected")
            self.set_state(AppState.IDLE)

    def get_mixer_args(self):
        return {
            "frequency": int(self.audio.frame_rate * self.speed_percent / 100),
            "size": -16,
            "channels": self.audio.channels,
            "buffer": 4096
        }
    
    def clear_song(self):
        self.stop_audio()
        self.audio = None
        self.ax.clear()
        self.canvas.draw()
        self.start_ms = 0
        self.end_ms = None
        self.current_pos_ms = 0
        self.update_time_label()
        self.set_state(AppState.IDLE)

    def plot_waveform(self):
        if self.audio is None:
            self.ax.clear()
            self.canvas.draw()
            return
        samples = np.array(self.audio.get_array_of_samples())
        if self.audio.channels == 2:
            samples = samples.reshape((-1, 2))
            samples = samples.mean(axis=1)
        times = np.linspace(0, len(samples) / self.audio.frame_rate, num=len(samples))
        self.ax.clear()
        self.ax.plot(times, samples, color="blue")
        self.ax.set_xlim([0, times[-1]])
        self.ax.set_title("Waveform")
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

    def move_to_timestamp(self, val):
        if self.audio is None:
            return
        pos_ms = int(float(val))
        self.pos_ms = pos_ms
        self.draw_markers()

    def on_scale_change(self, val):
        if self.audio is None or self.state == AppState.PLAYING or self.updating_scale:
            return

        self.current_pos_ms = int(val)
        self.start_ms = self.current_pos_ms
        self.update_time_label()


    def on_speed_drag(self, val):
        self.pending_speed = int(val)

    def on_speed_commit(self, event):
        if self.audio is None:
            return

        self.speed_percent = self.pending_speed

        if self.state == AppState.PLAYING:
            self.restart_playback()
    
    def restart_playback(self):
        pygame.mixer.stop()

        elapsed = int((time.time() - self.play_start_time) * 1000)
        self.current_pos_ms = min(self.start_ms + elapsed, self.end_ms)
        self.start_ms = self.current_pos_ms

        self.play_audio()


    def update_speed(self, val):
        self.speed = float(val) / 100.0
        if self.state == AppState.PLAYING:
            # pause and restart playback at new speed
            self.pause_audio()
            self.playing = False
            if self.channel:
                self.channel.stop()
            
            self.play_audio()

        if self.state in [AppState.LOADED, AppState.PAUSED, AppState.STOPPED]:
            self.playing = False
            if self.channel:
                self.channel.stop()

            self.play_audio()

    def update_volume(self, val):
        self.volume = float(val)

    def get_processed_segment(self):
        if self.audio is None:
            return None

        if self.end_ms is None:
            self.end_ms = len(self.audio)

        seg = self.audio[self.start_ms:self.end_ms]

        # Speed (frame rate change)
        if self.speed_percent != 100:
            seg = seg._spawn(seg.raw_data, overrides={
                "frame_rate": int(seg.frame_rate * self.speed_percent / 100)
            }).set_frame_rate(seg.frame_rate)

        # Volume
        seg += self.volume

        return seg

    def play_audio(self):
        if self.audio is None:
            return

        pygame.mixer.quit()
        pygame.mixer.init(**self.get_mixer_args())

        seg = self.get_processed_segment()
        if seg is None:
            return

        wav = seg.export(format="wav")
        self.sound = pygame.mixer.Sound(wav)
        self.channel = self.sound.play()

        self.play_start_time = time.time()
        self.playing = True
        self.set_state(AppState.PLAYING)

        self.start_ui_timer()


    def pause_audio(self):
        if self.state == AppState.PLAYING:
            pygame.mixer.pause()
            self.playing = False

            elapsed = int((time.time() - self.play_start_time) * 1000)
            self.current_pos_ms = min(self.start_ms + elapsed, self.end_ms)
            self.start_ms = self.current_pos_ms

            self.set_state(AppState.PAUSED)
            self.update_time_label()


    def stop_audio(self):
        pygame.mixer.stop()
        self.playing = False

        self.current_pos_ms = 0
        self.start_ms = 0
        self.progress_scale.set(0)
        self.speed_scale.set(100)
        self.update_time_label()

        self.set_state(AppState.STOPPED)


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
        
        # Export to bytes for pygame mixer
        sound_data = click_audio.export(format="wav")
        click_sound = pygame.mixer.Sound(sound_data)
        
        while self.metronome_on:
            click_sound.play()
            bpm = self.bpm_scale.get()
            time.sleep(60.0 / bpm)

    def start_ui_timer(self):
        if self.state != AppState.PLAYING:
            return

        elapsed = int((time.time() - self.play_start_time) * 1000)
        self.current_pos_ms = min(self.start_ms + elapsed, self.end_ms)

        self.updating_scale = True
        self.progress_scale.set(self.current_pos_ms)
        self.updating_scale = False

        self.update_time_label()

        if self.channel and self.channel.get_busy():
            self.root.after(50, self.start_ui_timer)
        else:
            self.stop_audio()


if __name__ == "__main__":
    root = tk.Tk()
    app = PracticeApp(root)
    root.mainloop()
