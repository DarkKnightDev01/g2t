"""Tkinter GUI for the g2t audio-to-notes converter."""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from g2t.audio_loader import load_audio, normalize_audio, trim_silence
from g2t.pitch_detector import (
    detect_pitches, detect_onsets, estimate_tempo, segment_notes
)
from g2t.note_converter import quantize_notes
from g2t.guitar_tab import notes_to_tab
from g2t.midi_generator import create_midi_file
from g2t.sheet_music import create_sheet_music


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

        self._build_ui()

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

        # Status bar
        status_bar = ttk.Label(
            self.root, textvariable=self.status_var, relief=tk.SUNKEN,
            anchor=tk.W, padding=3
        )
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

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

            self._log_status("Detecting pitches (pYIN)…")
            f0, voiced, probs = detect_pitches(y, sr, fmin=fmin, fmax=fmax)

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
            raw_notes = segment_notes(f0, voiced, onsets, sr)

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


def main():
    """Launch the g2t GUI application."""
    root = tk.Tk()
    G2TApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
