"""Offline OCR - desktop GUI (Tkinter, no internet needed)."""
import multiprocessing
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from batch import MAX_IMAGES, run_batch
from ocr_engine import Options

IMG_EXT = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Offline OCR - Bengali & English, Equations, Graphs")
        self.geometry("860x640")
        self.minsize(760, 560)
        self.files: list[str] = []
        self.q: queue.Queue = queue.Queue()
        self.cancel = threading.Event()
        self.worker = None
        self.out_dir = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Documents"))
        self.math_mode = tk.StringVar(value="Auto-detect equations")
        self.lang = tk.StringVar(value="Bengali + English")
        self.graphs = tk.BooleanVar(value=True)
        self.want_docx = tk.BooleanVar(value=True)
        self.want_txt = tk.BooleanVar(value=True)
        self._build()
        self.after(100, self._poll)

    # ---------------- UI ----------------
    def _build(self):
        pad = {"padx": 8, "pady": 4}
        top = ttk.Frame(self)
        top.pack(fill="both", expand=True, **pad)

        bar = ttk.Frame(top)
        bar.pack(fill="x")
        ttk.Button(bar, text="Add images...", command=self.add_files).pack(side="left")
        ttk.Button(bar, text="Add folder...", command=self.add_folder).pack(side="left", padx=4)
        ttk.Button(bar, text="Remove selected", command=self.remove_sel).pack(side="left")
        ttk.Button(bar, text="Clear", command=self.clear).pack(side="left", padx=4)
        self.count = ttk.Label(bar, text=f"0 / {MAX_IMAGES} images")
        self.count.pack(side="right")

        lf = ttk.Frame(top)
        lf.pack(fill="both", expand=True, pady=4)
        self.listbox = tk.Listbox(lf, selectmode="extended", height=10)
        sb = ttk.Scrollbar(lf, command=self.listbox.yview)
        self.listbox.config(yscrollcommand=sb.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        opt = ttk.LabelFrame(top, text="Options")
        opt.pack(fill="x", pady=4)
        ttk.Label(opt, text="Text language:").grid(row=0, column=0, sticky="w", **pad)
        ttk.Combobox(opt, textvariable=self.lang, state="readonly", width=22,
                     values=["Bengali + English", "Bengali only", "English only"]
                     ).grid(row=0, column=1, sticky="w", **pad)
        ttk.Label(opt, text="Equations:").grid(row=0, column=2, sticky="w", **pad)
        ttk.Combobox(opt, textvariable=self.math_mode, state="readonly", width=34,
                     values=["Auto-detect equations", "Whole image is ONE equation", "Off (text only)"]
                     ).grid(row=0, column=3, sticky="w", **pad)
        ttk.Checkbutton(opt, text="Extract graphs/charts as PNG", variable=self.graphs
                        ).grid(row=1, column=0, columnspan=2, sticky="w", **pad)
        ttk.Checkbutton(opt, text="Word document (.docx)", variable=self.want_docx
                        ).grid(row=1, column=2, sticky="w", **pad)
        ttk.Checkbutton(opt, text="Plain text (.txt)", variable=self.want_txt
                        ).grid(row=1, column=3, sticky="w", **pad)

        of = ttk.Frame(top)
        of.pack(fill="x")
        ttk.Label(of, text="Save to:").pack(side="left")
        ttk.Entry(of, textvariable=self.out_dir).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(of, text="Browse...", command=self.pick_out).pack(side="left")

        run = ttk.Frame(top)
        run.pack(fill="x", pady=6)
        self.start_btn = ttk.Button(run, text="Start OCR", command=self.start)
        self.start_btn.pack(side="left")
        self.cancel_btn = ttk.Button(run, text="Cancel", command=self.cancel.set, state="disabled")
        self.cancel_btn.pack(side="left", padx=6)
        self.open_btn = ttk.Button(run, text="Open output folder", command=self.open_out, state="disabled")
        self.open_btn.pack(side="left")
        self.prog = ttk.Progressbar(run, mode="determinate")
        self.prog.pack(side="left", fill="x", expand=True, padx=8)

        self.log = tk.Text(top, height=9, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)
        self.last_out = ""

    # ---------------- file list ----------------
    def _refresh(self):
        self.listbox.delete(0, "end")
        for f in self.files:
            self.listbox.insert("end", os.path.basename(f))
        self.count.config(text=f"{len(self.files)} / {MAX_IMAGES} images")

    def _add(self, paths):
        room = MAX_IMAGES - len(self.files)
        new = [p for p in paths if p not in self.files]
        if len(new) > room:
            messagebox.showwarning("Limit", f"Only {MAX_IMAGES} images allowed per batch. "
                                            f"Added the first {room}.")
            new = new[:room]
        self.files += new
        self._refresh()

    def add_files(self):
        ps = filedialog.askopenfilenames(title="Select images", filetypes=[
            ("Images", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp"), ("All files", "*.*")])
        self._add(sorted(ps))

    def add_folder(self):
        d = filedialog.askdirectory(title="Select folder of images")
        if d:
            self._add(sorted(os.path.join(d, f) for f in os.listdir(d)
                             if f.lower().endswith(IMG_EXT)))

    def remove_sel(self):
        for i in reversed(self.listbox.curselection()):
            del self.files[i]
        self._refresh()

    def clear(self):
        self.files = []
        self._refresh()

    def pick_out(self):
        d = filedialog.askdirectory(title="Output folder")
        if d:
            self.out_dir.set(d)

    def open_out(self):
        if self.last_out and os.path.isdir(self.last_out):
            os.startfile(self.last_out) if os.name == "nt" else None

    # ---------------- run ----------------
    def _log(self, msg):
        self.q.put(("log", msg))

    def start(self):
        if not self.files:
            messagebox.showinfo("No images", "Add some images first.")
            return
        if not (self.want_docx.get() or self.want_txt.get()):
            messagebox.showinfo("Output", "Choose at least one output format.")
            return
        lang = {"Bengali + English": "ben+eng", "Bengali only": "ben", "English only": "eng"}[self.lang.get()]
        mm = {"Auto-detect equations": "auto", "Whole image is ONE equation": "whole",
              "Off (text only)": "off"}[self.math_mode.get()]
        opts = Options(lang=lang, math_mode=mm, graphs=self.graphs.get())
        self.cancel.clear()
        self.start_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.open_btn.config(state="disabled")
        self.prog.config(maximum=len(self.files), value=0)

        def work():
            try:
                out = run_batch(list(self.files), self.out_dir.get(), opts,
                                self.want_docx.get(), self.want_txt.get(),
                                progress=lambda i, n: self.q.put(("prog", i)),
                                log=self._log, cancel=self.cancel)
                self.q.put(("done", out))
            except Exception as e:
                self.q.put(("error", str(e)))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def _poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "log":
                    self.log.config(state="normal")
                    self.log.insert("end", val + "\n")
                    self.log.see("end")
                    self.log.config(state="disabled")
                elif kind == "prog":
                    self.prog.config(value=val)
                elif kind in ("done", "error"):
                    self.start_btn.config(state="normal")
                    self.cancel_btn.config(state="disabled")
                    if kind == "done":
                        self.last_out = val
                        self.open_btn.config(state="normal")
                        self._log(f"Saved to: {val}")
                        messagebox.showinfo("Finished", f"Output saved to:\n{val}")
                    else:
                        messagebox.showerror("Error", val)
        except queue.Empty:
            pass
        self.after(100, self._poll)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    if "--selftest" in sys.argv:
        from selftest import run
        run()
    App().mainloop()
