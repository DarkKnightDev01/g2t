"""Tkinter GUI for the g2t audio-to-notes converter."""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from g2t.audio_loader import load_audio, normalize_audio, trim_silence
from g2t.pitch_detector import (
    detect_pitches, detect_onsets, estimate_tempo, segment_notes,
    separate_harmonic,
)
from g2t.note_converter import quantize_notes
from g2t.guitar_tab import notes_to_tab
from g2t.midi_generator import create_midi_file
from g2t.sheet_music import create_sheet_music
from g2t.player import MidiPlayer, ALL_EXTENSIONS, GP_EXTENSIONS, MIDI_EXTENSIONS


class G2TApp:
    """Main application window."""

    def __init__(self, root):
        self.root = root
        self.root.title("g2t — Audio to Notes Converter")
        self.root.geometry("960x720")
        self.root.minsize(800, 600)

        # State
        self.audio_path = tk.StringVar()
        self.instrument_var = tk.StringVar(value="Guitar")
        self.tempo_var = tk.StringVar(value="auto")
        self.status_var = tk.StringVar(value="Ready")
        self.detected_notes = []
        self.detected_tempo = 120.0

        # Player state
        self._player = MidiPlayer(on_stop=self._on_playback_stopped)
        self._player_path = tk.StringVar()
        self._player_pos_var = tk.StringVar(value="0:00")
        self._player_poll_id = None

        self._build_ui()

    def _on_close(self):
        """Clean up player resources before closing the window."""
        if self._player_poll_id is not None:
            try:
                self.root.after_cancel(self._player_poll_id)
            except Exception:
                pass
        self._player.close()
        self.root.destroy()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        # Top frame: file selection
        top = ttk.LabelFrame(self.root, text="Audio Input", padding=10)
        top.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Label(top, text="File:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(top, textvariable=self.audio_path, width=60).grid(
            row=0, column=1, padx=5, sticky=tk.EW
        )
        ttk.Button(top, text="Browse…", command=self._browse_file).grid(
            row=0, column=2
        )
        top.columnconfigure(1, weight=1)

        # Options frame
        opts = ttk.LabelFrame(self.root, text="Options", padding=10)
        opts.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(opts, text="Instrument:").grid(row=0, column=0, sticky=tk.W)
        inst_combo = ttk.Combobox(
            opts, textvariable=self.instrument_var,
            values=["Guitar", "Piano", "Vocals / Other"],
            state="readonly", width=20
        )
        inst_combo.grid(row=0, column=1, padx=5, sticky=tk.W)

        ttk.Label(opts, text="Tempo (BPM):").grid(row=0, column=2, padx=(20, 0),
                                                    sticky=tk.W)
        ttk.Entry(opts, textvariable=self.tempo_var, width=10).grid(
            row=0, column=3, padx=5, sticky=tk.W
        )
        ttk.Label(opts, text='("auto" to detect)').grid(
            row=0, column=4, sticky=tk.W
        )

        # Action buttons
        btn_frame = ttk.Frame(self.root, padding=(10, 5))
        btn_frame.pack(fill=tk.X)

        self.analyze_btn = ttk.Button(
            btn_frame, text="▶  Analyze Audio", command=self._start_analysis
        )
        self.analyze_btn.pack(side=tk.LEFT)

        self.export_tab_btn = ttk.Button(
            btn_frame, text="Export Guitar Tab",
            command=self._export_tab, state=tk.DISABLED
        )
        self.export_tab_btn.pack(side=tk.LEFT, padx=5)

        self.export_midi_btn = ttk.Button(
            btn_frame, text="Export MIDI",
            command=self._export_midi, state=tk.DISABLED
        )
        self.export_midi_btn.pack(side=tk.LEFT, padx=5)

        self.export_sheet_btn = ttk.Button(
            btn_frame, text="Export Sheet Music (MusicXML)",
            command=self._export_sheet, state=tk.DISABLED
        )
        self.export_sheet_btn.pack(side=tk.LEFT, padx=5)

        # Progress bar
        self.progress = ttk.Progressbar(
            self.root, mode='indeterminate', length=200
        )
        self.progress.pack(fill=tk.X, padx=10, pady=2)

        # Results notebook
        nb = ttk.Notebook(self.root)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        # Tab: Guitar Tab
        tab_frame = ttk.Frame(nb)
        nb.add(tab_frame, text="Guitar Tab")
        self.tab_text = scrolledtext.ScrolledText(
            tab_frame, wrap=tk.NONE, font=("Courier", 11)
        )
        self.tab_text.pack(fill=tk.BOTH, expand=True)

        # Tab: Notes list
        notes_frame = ttk.Frame(nb)
        nb.add(notes_frame, text="Detected Notes")
        self.notes_text = scrolledtext.ScrolledText(
            notes_frame, wrap=tk.NONE, font=("Courier", 10)
        )
        self.notes_text.pack(fill=tk.BOTH, expand=True)

        # Tab: Info
        info_frame = ttk.Frame(nb)
        nb.add(info_frame, text="Info")
        self.info_text = scrolledtext.ScrolledText(
            info_frame, wrap=tk.WORD, font=("TkDefaultFont", 10)
        )
        self.info_text.pack(fill=tk.BOTH, expand=True)

        # Tab: Player
        player_frame = ttk.Frame(nb)
        nb.add(player_frame, text="Player")
        self._build_player_tab(player_frame)

        # Status bar
        status_bar = ttk.Label(
            self.root, textvariable=self.status_var, relief=tk.SUNKEN,
            anchor=tk.W, padding=3
        )
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_player_tab(self, parent):
        """Build the interactive MIDI / Guitar Pro player UI."""
        outer = ttk.LabelFrame(parent, text="MIDI / Guitar Pro Player",
                               padding=12)
        outer.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # File row
        file_row = ttk.Frame(outer)
        file_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(file_row, text="File:").pack(side=tk.LEFT)
        ttk.Entry(file_row, textvariable=self._player_path,
                  width=55).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(file_row, text="Browse…",
                   command=self._player_browse).pack(side=tk.LEFT)
        ttk.Button(file_row, text="Load",
                   command=self._player_load).pack(side=tk.LEFT, padx=(4, 0))

        # Controls row
        ctrl_row = ttk.Frame(outer)
        ctrl_row.pack(pady=4)

        self._play_btn = ttk.Button(ctrl_row, text="▶  Play",
                                    command=self._player_play, width=10)
        self._play_btn.pack(side=tk.LEFT, padx=4)

        self._pause_btn = ttk.Button(ctrl_row, text="⏸  Pause",
                                     command=self._player_pause, width=10,
                                     state=tk.DISABLED)
        self._pause_btn.pack(side=tk.LEFT, padx=4)

        self._stop_btn = ttk.Button(ctrl_row, text="⏹  Stop",
                                    command=self._player_stop, width=10,
                                    state=tk.DISABLED)
        self._stop_btn.pack(side=tk.LEFT, padx=4)

        # Volume
        vol_row = ttk.Frame(outer)
        vol_row.pack(pady=4)
        ttk.Label(vol_row, text="Volume:").pack(side=tk.LEFT)
        self._vol_var = tk.DoubleVar(value=1.0)
        vol_slider = ttk.Scale(vol_row, from_=0.0, to=1.0,
                               orient=tk.HORIZONTAL, length=150,
                               variable=self._vol_var,
                               command=self._player_set_volume)
        vol_slider.pack(side=tk.LEFT, padx=6)

        # Position label
        pos_row = ttk.Frame(outer)
        pos_row.pack(pady=2)
        ttk.Label(pos_row, text="Position:").pack(side=tk.LEFT)
        ttk.Label(pos_row, textvariable=self._player_pos_var,
                  font=("Courier", 10)).pack(side=tk.LEFT, padx=6)

        # Status label
        self._player_status_var = tk.StringVar(value="No file loaded.")
        ttk.Label(outer, textvariable=self._player_status_var,
                  foreground="#555555").pack(pady=(8, 0))

    # -------------------------------------------------------------- Actions
    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="Select audio file",
            filetypes=[
                ("Audio files", "*.wav *.mp3 *.flac *.ogg *.aac *.m4a"),
                ("All files", "*.*"),
            ]
        )
        if path:
            self.audio_path.set(path)

    def _start_analysis(self):
        path = self.audio_path.get().strip()
        if not path or not os.path.isfile(path):
            messagebox.showerror("Error", "Please select a valid audio file.")
            return

        self.analyze_btn.config(state=tk.DISABLED)
        self.progress.start(10)
        self.status_var.set("Analyzing…")
        threading.Thread(target=self._run_analysis, args=(path,),
                         daemon=True).start()

    def _run_analysis(self, path):
        try:
            self._log_status("Loading audio…")
            y, sr = load_audio(path)
            y = normalize_audio(y)
            y = trim_silence(y, sr)

            # Determine instrument-specific frequency range
            instrument = self.instrument_var.get()
            if instrument == "Guitar":
                fmin, fmax = 70.0, 1400.0
            elif instrument == "Piano":
                fmin, fmax = 27.5, 4186.0
            else:
                fmin, fmax = 50.0, 2000.0

            # Separate harmonic content to improve pitch detection accuracy.
            # The harmonic component contains sustained tones while transients
            # (pick attacks, drum hits) go to the percussive component.
            self._log_status("Separating harmonic content…")
            y_harmonic = separate_harmonic(y)

            self._log_status("Detecting pitches (pYIN)…")
            f0, voiced, probs = detect_pitches(y_harmonic, sr,
                                               fmin=fmin, fmax=fmax)

            # Detect onsets on the original (full) signal so that transients
            # are still captured for note boundary placement.
            self._log_status("Detecting onsets…")
            onsets = detect_onsets(y, sr)

            # Tempo
            tempo_str = self.tempo_var.get().strip().lower()
            if tempo_str == "auto" or tempo_str == "":
                self._log_status("Estimating tempo…")
                self.detected_tempo = estimate_tempo(y, sr)
            else:
                try:
                    self.detected_tempo = float(tempo_str)
                except ValueError:
                    self.detected_tempo = 120.0

            self._log_status("Segmenting notes…")
            raw_notes = segment_notes(f0, voiced, onsets, sr,
                                      voiced_probs=probs)

            self._log_status("Quantizing to semitones…")
            self.detected_notes = quantize_notes(raw_notes)

            # Generate guitar tab
            self._log_status("Generating guitar tab…")
            tab = notes_to_tab(self.detected_notes, tempo=self.detected_tempo)

            # Display results
            self.root.after(0, self._display_results, tab)

        except Exception as exc:
            self.root.after(
                0, lambda: messagebox.showerror("Analysis Error", str(exc))
            )
        finally:
            self.root.after(0, self._analysis_done)

    def _display_results(self, tab):
        # Guitar tab
        self.tab_text.delete('1.0', tk.END)
        self.tab_text.insert(tk.END, tab)

        # Notes list
        self.notes_text.delete('1.0', tk.END)
        header = f"{'#':<5} {'Note':<6} {'MIDI':<5} {'Start':>7} {'End':>7} {'Cents':>7} {'Conf':>6}\n"
        self.notes_text.insert(tk.END, header)
        self.notes_text.insert(tk.END, "-" * 50 + "\n")
        for i, n in enumerate(self.detected_notes, 1):
            line = (f"{i:<5} {n['note_name']:<6} {n['midi']:<5} "
                    f"{n['start']:7.3f} {n['end']:7.3f} "
                    f"{n['cents_off']:+7.1f} {n['confidence']:6.2f}\n")
            self.notes_text.insert(tk.END, line)

        # Info
        self.info_text.delete('1.0', tk.END)
        self.info_text.insert(tk.END, f"Detected tempo: {self.detected_tempo:.1f} BPM\n")
        self.info_text.insert(tk.END, f"Total notes detected: {len(self.detected_notes)}\n")
        self.info_text.insert(tk.END, f"Instrument: {self.instrument_var.get()}\n")
        if self.detected_notes:
            dur = self.detected_notes[-1]['end']
            self.info_text.insert(tk.END, f"Duration: {dur:.2f} s\n")

    def _analysis_done(self):
        self.progress.stop()
        self.analyze_btn.config(state=tk.NORMAL)
        if self.detected_notes:
            self.export_tab_btn.config(state=tk.NORMAL)
            self.export_midi_btn.config(state=tk.NORMAL)
            self.export_sheet_btn.config(state=tk.NORMAL)
            self.status_var.set(
                f"Done — {len(self.detected_notes)} notes detected at "
                f"{self.detected_tempo:.0f} BPM"
            )
        else:
            self.status_var.set("No notes detected.")

    def _log_status(self, msg):
        self.root.after(0, lambda: self.status_var.set(msg))

    # ------------------------------------------------------------ Exports
    def _export_tab(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Save Guitar Tab"
        )
        if not path:
            return
        tab = notes_to_tab(self.detected_notes, tempo=self.detected_tempo)
        with open(path, 'w') as f:
            f.write(tab)
        self.status_var.set(f"Tab saved to {path}")

    def _export_midi(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".mid",
            filetypes=[("MIDI files", "*.mid *.midi"), ("All files", "*.*")],
            title="Save MIDI"
        )
        if not path:
            return

        instrument = self.instrument_var.get()
        if instrument == "Guitar":
            gm_name = "Acoustic Guitar (nylon)"
        elif instrument == "Piano":
            gm_name = "Acoustic Grand Piano"
        else:
            gm_name = "Acoustic Grand Piano"

        create_midi_file(
            self.detected_notes, path,
            instrument_name=gm_name, tempo=self.detected_tempo
        )
        self.status_var.set(f"MIDI saved to {path}")

    def _export_sheet(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".musicxml",
            filetypes=[
                ("MusicXML files", "*.musicxml *.xml"),
                ("All files", "*.*"),
            ],
            title="Save Sheet Music"
        )
        if not path:
            return
        create_sheet_music(
            self.detected_notes, path, tempo=self.detected_tempo
        )
        self.status_var.set(f"Sheet music saved to {path}")

    # ------------------------------------------------------------ Player
    def _player_browse(self):
        ext_list = " ".join(f"*{e}" for e in sorted(ALL_EXTENSIONS))
        path = filedialog.askopenfilename(
            title="Select MIDI or Guitar Pro file",
            filetypes=[
                ("MIDI / Guitar Pro files", ext_list),
                ("MIDI files", "*.mid *.midi"),
                ("Guitar Pro files", "*.gp *.gp3 *.gp4 *.gp5 *.gpx *.gp7"),
                ("All files", "*.*"),
            ]
        )
        if path:
            self._player_path.set(path)

    def _player_load(self):
        path = self._player_path.get().strip()
        if not path or not os.path.isfile(path):
            messagebox.showerror("Player Error",
                                 "Please select a valid MIDI or GP file.")
            return
        try:
            self._player.load(path)
            fname = os.path.basename(path)
            self._player_status_var.set(f"Loaded: {fname}")
            self._play_btn.config(state=tk.NORMAL)
            self._pause_btn.config(state=tk.DISABLED)
            self._stop_btn.config(state=tk.DISABLED)
            self._player_pos_var.set("0:00")
        except Exception as exc:
            messagebox.showerror("Player Error", str(exc))

    def _player_play(self):
        try:
            self._player.play()
            self._player_status_var.set("Playing…")
            self._pause_btn.config(state=tk.NORMAL)
            self._stop_btn.config(state=tk.NORMAL)
            self._play_btn.config(text="↺  Restart")
            self._poll_player_position()
        except Exception as exc:
            messagebox.showerror("Player Error", str(exc))

    def _player_pause(self):
        if self._player.is_paused():
            self._player.resume()
            self._player_status_var.set("Playing…")
            self._pause_btn.config(text="⏸  Pause")
            self._poll_player_position()
        else:
            self._player.pause()
            self._player_status_var.set("Paused.")
            self._pause_btn.config(text="▶  Resume")

    def _player_stop(self):
        self._player.stop()
        self._player_status_var.set("Stopped.")
        self._play_btn.config(text="▶  Play")
        self._pause_btn.config(state=tk.DISABLED, text="⏸  Pause")
        self._stop_btn.config(state=tk.DISABLED)
        self._player_pos_var.set("0:00")
        if self._player_poll_id is not None:
            self.root.after_cancel(self._player_poll_id)
            self._player_poll_id = None

    def _on_playback_stopped(self):
        """Called from the MidiPlayer background thread when playback ends."""
        self.root.after(0, self._player_stop)

    def _poll_player_position(self):
        """Update the position label while the player is active."""
        if self._player_poll_id is not None:
            self.root.after_cancel(self._player_poll_id)
        if self._player.is_playing():
            secs = self._player.get_position()
            mins = int(secs) // 60
            sec = int(secs) % 60
            self._player_pos_var.set(f"{mins}:{sec:02d}")
            self._player_poll_id = self.root.after(250, self._poll_player_position)
        else:
            self._player_poll_id = None

    def _player_set_volume(self, value):
        try:
            self._player.set_volume(float(value))
        except Exception:
            pass


def main():
    """Launch the g2t GUI application."""
    root = tk.Tk()
    G2TApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
