import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
import subprocess
import threading
import os
import shutil
import re

# ─── Theme ────────────────────────────────────────────────────────────────────
BG      = "#0d0f14"
PANEL   = "#141720"
PANEL2  = "#1a1e2a"
BORDER  = "#1e2330"
ACCENT  = "#e8622a"
ACCENT2 = "#f0a05a"
TEXT    = "#e8e8e8"
SUBTEXT = "#7a8099"
SUCCESS = "#3ecf8e"
WARNING = "#f0c040"
ERROR   = "#e85050"


def make_btn(parent, text, cmd, small=False, danger=False, accent=False):
    fg = ERROR if danger else (SUCCESS if accent else ACCENT)
    bg = "#1a0f0f" if danger else ("#0f1a12" if accent else "#1a1208")
    f  = ("Consolas", 9) if small else ("Consolas", 10, "bold")
    b  = tk.Button(parent, text=text, command=cmd, font=f,
                   fg=fg, bg=bg, activeforeground=TEXT,
                   activebackground=BORDER, relief="flat", bd=0,
                   cursor="hand2", highlightthickness=1,
                   highlightbackground=fg, padx=8, pady=4 if small else 6)
    b.bind("<Enter>", lambda e: b.config(bg=fg, fg=BG))
    b.bind("<Leave>", lambda e: b.config(bg=bg, fg=fg))
    return b


def make_section(parent, title, pady_top=14):
    f = tk.Frame(parent, bg=BG)
    f.pack(fill="x", padx=24, pady=(pady_top, 4))
    tk.Label(f, text=title, font=("Consolas", 10, "bold"),
             fg=ACCENT, bg=BG).pack(side="left")
    tk.Frame(f, bg=BORDER, height=1).pack(
        side="left", fill="x", expand=True, padx=10)


def make_entry_row(parent, label, var, browse_cb=None, lw=14):
    row = tk.Frame(parent, bg=BG)
    row.pack(fill="x", padx=24, pady=5)
    tk.Label(row, text=label, width=lw, anchor="w",
             font=("Consolas", 10), fg=SUBTEXT, bg=BG).pack(side="left")
    e = tk.Entry(row, textvariable=var, font=("Consolas", 10),
                 bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat",
                 bd=0, highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ACCENT)
    e.pack(side="left", fill="x", expand=True, ipady=5,
           padx=(0, 6 if browse_cb else 0))
    if browse_cb:
        make_btn(row, "Browse", browse_cb, small=True).pack(side="left")


def make_log(parent):
    frame = tk.Frame(parent, bg=PANEL, padx=2, pady=2,
                     highlightthickness=1, highlightbackground=BORDER)
    frame.pack(fill="both", expand=True, padx=24, pady=(0, 16))
    log = tk.Text(frame, font=("Consolas", 9), bg=PANEL, fg=TEXT,
                  insertbackground=TEXT, relief="flat", height=12,
                  state="disabled", wrap="word")
    sb = tk.Scrollbar(frame, command=log.yview)
    log.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    log.pack(fill="both", expand=True, padx=6, pady=4)
    for tag, col in [("ok", SUCCESS), ("err", ERROR),
                     ("warn", WARNING), ("head", ACCENT2)]:
        log.tag_configure(tag, foreground=col)
    return log


def scrollable(parent):
    canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
    sb     = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    canvas.pack(fill="both", expand=True)
    inner  = tk.Frame(canvas, bg=BG)
    wid    = canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>",
               lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>",
                lambda e: canvas.itemconfig(wid, width=e.width))
    inner.bind_all("<MouseWheel>",
                   lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
    return inner


# ═══════════════════════════════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Transparent Video Maker  v2")
        self.configure(bg=BG)
        self.minsize(740, 780)
        self.geometry("800x920")

        self.running = False
        self.proc    = None

        # ── Pipeline vars ──────────────────────────────────────────────────
        self.video_path   = tk.StringVar()
        self.output_dir   = tk.StringVar()
        self.framerate    = tk.StringVar(value="30")
        self.crf          = tk.IntVar(value=25)
        self.out_format   = tk.StringVar(value="webm")
        self.remove_mode  = tk.StringVar(value="chroma")
        self.chroma_color = tk.StringVar(value="#00ff00")
        self.chroma_sim   = tk.DoubleVar(value=0.10)
        self.chroma_blend = tk.DoubleVar(value=0.05)
        self.rembg_model  = tk.StringVar(value="u2net")
        self.keep_frames  = tk.BooleanVar(value=False)

        # ── Frames→Video vars ──────────────────────────────────────────────
        self.fv_folder  = tk.StringVar()
        self.fv_output  = tk.StringVar()
        self.fv_fps     = tk.StringVar(value="30")
        self.fv_crf     = tk.IntVar(value=25)
        self.fv_format  = tk.StringVar(value="webm")
        self.fv_pattern = tk.StringVar(value="frame%04d.png")

        self._build_ui()

    # ── Header + tab bar ──────────────────────────────────────────────────────
    def _build_ui(self):
        hdr = tk.Frame(self, bg=BG, pady=14)
        hdr.pack(fill="x", padx=24)
        tk.Label(hdr, text="◈  TRANSPARENT VIDEO MAKER",
                 font=("Consolas", 16, "bold"), fg=ACCENT, bg=BG).pack(side="left")
        tk.Label(hdr, text="ffmpeg + rembg",
                 font=("Consolas", 9), fg=SUBTEXT, bg=BG).pack(side="left", padx=12)
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=24)

        tab_bar = tk.Frame(self, bg=BG)
        tab_bar.pack(fill="x", padx=24, pady=(8, 0))
        self.tab_btns = []
        for i, lbl in enumerate(["  Full Pipeline  ", "  Frames → Video  "]):
            b = tk.Button(tab_bar, text=lbl,
                          font=("Consolas", 10, "bold"),
                          fg=SUBTEXT, bg=PANEL, relief="flat",
                          bd=0, padx=10, pady=6, cursor="hand2",
                          command=lambda i=i: self._switch_tab(i))
            b.pack(side="left", padx=(0, 4))
            self.tab_btns.append(b)

        self.content = tk.Frame(self, bg=BG)
        self.content.pack(fill="both", expand=True)

        self.pane_pipe = self._build_pipeline_pane()
        self.pane_fv   = self._build_fv_pane()
        self._switch_tab(0)

    def _switch_tab(self, idx):
        self.pane_pipe.pack_forget()
        self.pane_fv.pack_forget()
        [self.pane_pipe, self.pane_fv][idx].pack(fill="both", expand=True)
        for i, b in enumerate(self.tab_btns):
            if i == idx:
                b.config(fg=ACCENT, bg=PANEL2,
                         highlightthickness=1, highlightbackground=ACCENT)
            else:
                b.config(fg=SUBTEXT, bg=PANEL, highlightthickness=0)

    # ═══════════════════════════════════════════════════════════════════════════
    #  TAB 1 — Full Pipeline
    # ═══════════════════════════════════════════════════════════════════════════
    def _build_pipeline_pane(self):
        outer = tk.Frame(self.content, bg=BG)
        inner = scrollable(outer)
        P = {"padx": 24, "pady": 5}

        # 01 Input / Output
        make_section(inner, "01 — INPUT & OUTPUT")
        make_entry_row(inner, "Video file:",    self.video_path,  self._browse_video)
        make_entry_row(inner, "Output folder:", self.output_dir,  self._browse_output)

        # 02 Frame extraction
        make_section(inner, "02 — FRAME EXTRACTION  (ffmpeg)")
        fps_row = tk.Frame(inner, bg=BG)
        fps_row.pack(fill="x", **P)
        tk.Label(fps_row, text="Source FPS:", width=14, anchor="w",
                 font=("Consolas", 10), fg=SUBTEXT, bg=BG).pack(side="left")
        for v in ["24", "25", "30", "60"]:
            tk.Radiobutton(fps_row, text=v, variable=self.framerate, value=v,
                           font=("Consolas", 10), fg=TEXT, bg=BG,
                           selectcolor=PANEL, activebackground=BG,
                           activeforeground=ACCENT, relief="flat"
                           ).pack(side="left", padx=5)
        tk.Label(fps_row, text="custom →", font=("Consolas", 9),
                 fg=SUBTEXT, bg=BG).pack(side="left", padx=6)
        tk.Entry(fps_row, textvariable=self.framerate, width=5,
                 font=("Consolas", 10), bg=PANEL, fg=TEXT, insertbackground=TEXT,
                 relief="flat", highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ACCENT
                 ).pack(side="left", ipady=4)

        # 03 Background removal
        make_section(inner, "03 — BACKGROUND REMOVAL")

        mode_row = tk.Frame(inner, bg=BG)
        mode_row.pack(fill="x", **P)
        tk.Label(mode_row, text="Method:", width=14, anchor="w",
                 font=("Consolas", 10), fg=SUBTEXT, bg=BG).pack(side="left")
        for val, lbl in [("chroma", "Chroma Key  (solid color bg — RECOMMENDED)"),
                         ("ai",     "AI Model  (rembg — complex/unknown bg)")]:
            tk.Radiobutton(mode_row, text=f"  {lbl}",
                           variable=self.remove_mode, value=val,
                           font=("Consolas", 10), fg=TEXT, bg=BG,
                           selectcolor=PANEL, activebackground=BG,
                           activeforeground=ACCENT, relief="flat",
                           command=self._toggle_mode
                           ).pack(side="left", padx=10)

        # Chroma sub-panel
        self.chroma_panel = tk.Frame(inner, bg=PANEL2,
                                     highlightthickness=1,
                                     highlightbackground=BORDER)
        self.chroma_panel.pack(fill="x", padx=32, pady=(2, 2))

        # color row
        cr1 = tk.Frame(self.chroma_panel, bg=PANEL2)
        cr1.pack(fill="x", padx=12, pady=(8, 4))
        tk.Label(cr1, text="Background color:", width=18, anchor="w",
                 font=("Consolas", 10), fg=SUBTEXT, bg=PANEL2).pack(side="left")
        self.color_swatch = tk.Label(cr1, width=4, bg=self.chroma_color.get(),
                                     highlightthickness=1,
                                     highlightbackground=BORDER)
        self.color_swatch.pack(side="left", ipady=8, padx=(0, 6))
        tk.Entry(cr1, textvariable=self.chroma_color, width=10,
                 font=("Consolas", 10), bg=PANEL, fg=TEXT, insertbackground=TEXT,
                 relief="flat", highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ACCENT
                 ).pack(side="left", ipady=4, padx=(0, 6))
        make_btn(cr1, "Pick color", self._pick_color, small=True).pack(side="left", padx=4)
        tk.Label(cr1, text="  Presets:", font=("Consolas", 8),
                 fg=SUBTEXT, bg=PANEL2).pack(side="left")
        for name, col in [("Green",  "#00ff00"), ("Blue",  "#0000ff"),
                          ("Black",  "#000000"), ("White", "#ffffff")]:
            tk.Button(cr1, text=name, font=("Consolas", 8), fg=SUBTEXT,
                      bg=PANEL, relief="flat", cursor="hand2", padx=5, pady=2,
                      command=lambda c=col: self._set_color(c)
                      ).pack(side="left", padx=2)

        # similarity slider
        cr2 = tk.Frame(self.chroma_panel, bg=PANEL2)
        cr2.pack(fill="x", padx=12, pady=2)
        tk.Label(cr2, text="Similarity:", width=18, anchor="w",
                 font=("Consolas", 10), fg=SUBTEXT, bg=PANEL2).pack(side="left")
        tk.Scale(cr2, variable=self.chroma_sim, from_=0.01, to=0.50,
                 resolution=0.01, orient="horizontal", length=210,
                 bg=PANEL2, fg=TEXT, troughcolor=BG, highlightthickness=0,
                 activebackground=ACCENT, font=("Consolas", 8), sliderlength=14
                 ).pack(side="left", padx=(0, 8))
        tk.Label(cr2, text="How broadly to match the background color",
                 font=("Consolas", 8), fg=SUBTEXT, bg=PANEL2).pack(side="left")

        # blend slider
        cr3 = tk.Frame(self.chroma_panel, bg=PANEL2)
        cr3.pack(fill="x", padx=12, pady=(2, 8))
        tk.Label(cr3, text="Edge blend:", width=18, anchor="w",
                 font=("Consolas", 10), fg=SUBTEXT, bg=PANEL2).pack(side="left")
        tk.Scale(cr3, variable=self.chroma_blend, from_=0.0, to=0.30,
                 resolution=0.01, orient="horizontal", length=210,
                 bg=PANEL2, fg=TEXT, troughcolor=BG, highlightthickness=0,
                 activebackground=ACCENT, font=("Consolas", 8), sliderlength=14
                 ).pack(side="left", padx=(0, 8))
        tk.Label(cr3, text="Soften jagged edges (raise if outline looks harsh)",
                 font=("Consolas", 8), fg=SUBTEXT, bg=PANEL2).pack(side="left")

        # AI sub-panel
        self.ai_panel = tk.Frame(inner, bg=PANEL2,
                                  highlightthickness=1,
                                  highlightbackground=BORDER)
        mf = tk.Frame(self.ai_panel, bg=PANEL2)
        mf.pack(fill="x", padx=12, pady=8)
        for val, lbl in [
            ("u2net",            "u2net            — general purpose"),
            ("u2net_human_seg",  "u2net_human_seg  — people & characters"),
            ("isnet-general-use","isnet-general-use — sharper edges, slower"),
            ("silueta",          "silueta          — fast, simple backgrounds"),
        ]:
            tk.Radiobutton(mf, text=f"  {lbl}",
                           variable=self.rembg_model, value=val,
                           font=("Consolas", 9), fg=TEXT, bg=PANEL2,
                           anchor="w", selectcolor=PANEL,
                           activebackground=PANEL2, activeforeground=ACCENT,
                           relief="flat").pack(fill="x", pady=1)

        self._toggle_mode()

        # 04 Encode
        make_section(inner, "04 — VIDEO RE-ENCODE  (ffmpeg)")
        fmt_row = tk.Frame(inner, bg=BG)
        fmt_row.pack(fill="x", **P)
        tk.Label(fmt_row, text="Output format:", width=14, anchor="w",
                 font=("Consolas", 10), fg=SUBTEXT, bg=BG).pack(side="left")
        for val, lbl in [("webm", "WebM/VP9  — web, OBS, most editors"),
                         ("mov",  "MOV/ProRes 4444  — editing master")]:
            tk.Radiobutton(fmt_row, text=f"  {lbl}", variable=self.out_format,
                           value=val, font=("Consolas", 9), fg=TEXT, bg=BG,
                           selectcolor=PANEL, activebackground=BG,
                           activeforeground=ACCENT, relief="flat"
                           ).pack(side="left", padx=8)
        crf_row = tk.Frame(inner, bg=BG)
        crf_row.pack(fill="x", **P)
        tk.Label(crf_row, text="Quality (CRF):", width=14, anchor="w",
                 font=("Consolas", 10), fg=SUBTEXT, bg=BG).pack(side="left")
        tk.Scale(crf_row, variable=self.crf, from_=0, to=63,
                 orient="horizontal", length=230, bg=PANEL, fg=TEXT,
                 troughcolor=BG, highlightthickness=0, activebackground=ACCENT,
                 font=("Consolas", 8), sliderlength=14
                 ).pack(side="left", padx=(0, 8))
        tk.Label(crf_row, text="0 = best quality / largest file",
                 font=("Consolas", 8), fg=SUBTEXT, bg=BG).pack(side="left")
        kf_row = tk.Frame(inner, bg=BG)
        kf_row.pack(fill="x", **P)
        tk.Checkbutton(kf_row,
                       text="  Keep temporary frame folders after processing",
                       variable=self.keep_frames,
                       font=("Consolas", 9), fg=SUBTEXT, bg=BG,
                       selectcolor=PANEL, activebackground=BG,
                       activeforeground=TEXT, relief="flat").pack(side="left")

        # Controls
        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", padx=24, pady=10)
        ctrl = tk.Frame(inner, bg=BG)
        ctrl.pack(fill="x", padx=24, pady=4)
        self.run_btn = make_btn(ctrl, "▶  RUN FULL PIPELINE",
                                self._run_pipeline)
        self.run_btn.pack(side="left", ipadx=14, ipady=6)
        self.stop_btn = make_btn(ctrl, "■  STOP", self._stop, danger=True)
        self.stop_btn.pack(side="left", padx=8, ipadx=8, ipady=6)
        self.stop_btn.config(state="disabled")
        make_btn(ctrl, "Check tools", self._check_tools,
                 small=True).pack(side="right")

        # Step indicators
        sf = tk.Frame(inner, bg=BG)
        sf.pack(fill="x", padx=24, pady=(8, 4))
        self.pipe_steps = []
        for i, name in enumerate(["Extract Frames", "Remove BG", "Encode Video"]):
            f2 = tk.Frame(sf, bg=PANEL, padx=10, pady=8,
                          highlightthickness=1, highlightbackground=BORDER)
            f2.pack(side="left", fill="x", expand=True, padx=3)
            tk.Label(f2, text=f"STEP {i+1}", font=("Consolas", 8),
                     fg=SUBTEXT, bg=PANEL).pack(anchor="w")
            lbl = tk.Label(f2, text=name, font=("Consolas", 10, "bold"),
                           fg=SUBTEXT, bg=PANEL)
            lbl.pack(anchor="w")
            dot = tk.Label(f2, text="●  idle", font=("Consolas", 9),
                           fg=SUBTEXT, bg=PANEL)
            dot.pack(anchor="w")
            self.pipe_steps.append((f2, lbl, dot))

        pb = tk.Frame(inner, bg=BG)
        pb.pack(fill="x", padx=24, pady=(4, 0))
        s = ttk.Style(); s.theme_use("default")
        s.configure("A.Horizontal.TProgressbar",
                    troughcolor=PANEL, bordercolor=BORDER,
                    background=ACCENT, lightcolor=ACCENT2, darkcolor=ACCENT)
        self.pipe_pb = ttk.Progressbar(pb, style="A.Horizontal.TProgressbar",
                                       mode="indeterminate")
        self.pipe_pb.pack(fill="x")

        make_section(inner, "LOG", pady_top=8)
        self.pipe_log = make_log(inner)
        self._wlog(self.pipe_log,
                   "Ready. Select your video and click  ▶ RUN FULL PIPELINE.\n",
                   "head")
        return outer

    # ═══════════════════════════════════════════════════════════════════════════
    #  TAB 2 — Frames → Video
    # ═══════════════════════════════════════════════════════════════════════════
    def _build_fv_pane(self):
        outer = tk.Frame(self.content, bg=BG)

        info = tk.Frame(outer, bg=PANEL2,
                        highlightthickness=1, highlightbackground=BORDER)
        info.pack(fill="x", padx=24, pady=(12, 0))
        tk.Label(info,
                 text="  Use this tab when you already have a folder of transparent PNG frames\n"
                      "  (e.g. manually edited in Photoshop or another tool) and just need\n"
                      "  them stitched into a transparent video.",
                 font=("Consolas", 9), fg=SUBTEXT, bg=PANEL2, justify="left"
                 ).pack(padx=10, pady=8, anchor="w")

        make_section(outer, "FRAMES FOLDER & OUTPUT")
        make_entry_row(outer, "Frames folder:", self.fv_folder,
                       self._fv_browse_folder)
        make_entry_row(outer, "Output folder:", self.fv_output,
                       self._fv_browse_output)

        make_section(outer, "FRAME FILENAME PATTERN")
        pat_row = tk.Frame(outer, bg=BG)
        pat_row.pack(fill="x", padx=24, pady=5)
        tk.Label(pat_row, text="Pattern:", width=14, anchor="w",
                 font=("Consolas", 10), fg=SUBTEXT, bg=BG).pack(side="left")
        tk.Entry(pat_row, textvariable=self.fv_pattern, width=20,
                 font=("Consolas", 10), bg=PANEL, fg=TEXT, insertbackground=TEXT,
                 relief="flat", highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ACCENT
                 ).pack(side="left", ipady=5, padx=(0, 8))
        make_btn(pat_row, "Auto-detect", self._fv_autodetect,
                 small=True).pack(side="left")
        tk.Label(pat_row, text="  e.g.  frame%04d.png   img%03d.png",
                 font=("Consolas", 8), fg=SUBTEXT, bg=BG).pack(side="left", padx=6)

        make_section(outer, "OUTPUT SETTINGS")
        fps_row = tk.Frame(outer, bg=BG)
        fps_row.pack(fill="x", padx=24, pady=5)
        tk.Label(fps_row, text="Framerate:", width=14, anchor="w",
                 font=("Consolas", 10), fg=SUBTEXT, bg=BG).pack(side="left")
        for v in ["24", "25", "30", "60"]:
            tk.Radiobutton(fps_row, text=v, variable=self.fv_fps, value=v,
                           font=("Consolas", 10), fg=TEXT, bg=BG,
                           selectcolor=PANEL, activebackground=BG,
                           activeforeground=ACCENT, relief="flat"
                           ).pack(side="left", padx=5)
        tk.Label(fps_row, text="custom →", font=("Consolas", 9),
                 fg=SUBTEXT, bg=BG).pack(side="left", padx=6)
        tk.Entry(fps_row, textvariable=self.fv_fps, width=5,
                 font=("Consolas", 10), bg=PANEL, fg=TEXT, insertbackground=TEXT,
                 relief="flat", highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ACCENT
                 ).pack(side="left", ipady=4)

        fmt_row = tk.Frame(outer, bg=BG)
        fmt_row.pack(fill="x", padx=24, pady=5)
        tk.Label(fmt_row, text="Output format:", width=14, anchor="w",
                 font=("Consolas", 10), fg=SUBTEXT, bg=BG).pack(side="left")
        for val, lbl in [("webm", "WebM/VP9  — web, OBS, most editors"),
                         ("mov",  "MOV/ProRes 4444  — editing master")]:
            tk.Radiobutton(fmt_row, text=f"  {lbl}",
                           variable=self.fv_format, value=val,
                           font=("Consolas", 9), fg=TEXT, bg=BG,
                           selectcolor=PANEL, activebackground=BG,
                           activeforeground=ACCENT, relief="flat"
                           ).pack(side="left", padx=8)

        crf_row = tk.Frame(outer, bg=BG)
        crf_row.pack(fill="x", padx=24, pady=5)
        tk.Label(crf_row, text="Quality (CRF):", width=14, anchor="w",
                 font=("Consolas", 10), fg=SUBTEXT, bg=BG).pack(side="left")
        tk.Scale(crf_row, variable=self.fv_crf, from_=0, to=63,
                 orient="horizontal", length=230, bg=PANEL, fg=TEXT,
                 troughcolor=BG, highlightthickness=0, activebackground=ACCENT,
                 font=("Consolas", 8), sliderlength=14
                 ).pack(side="left", padx=(0, 8))
        tk.Label(crf_row, text="0 = best quality / largest file",
                 font=("Consolas", 8), fg=SUBTEXT, bg=BG).pack(side="left")

        tk.Frame(outer, bg=BORDER, height=1).pack(fill="x", padx=24, pady=10)
        ctrl = tk.Frame(outer, bg=BG)
        ctrl.pack(fill="x", padx=24, pady=4)
        self.fv_run_btn = make_btn(ctrl, "▶  ENCODE VIDEO FROM FRAMES",
                                   self._run_fv, accent=True)
        self.fv_run_btn.pack(side="left", ipadx=14, ipady=6)
        self.fv_stop_btn = make_btn(ctrl, "■  STOP", self._stop, danger=True)
        self.fv_stop_btn.pack(side="left", padx=8, ipadx=8, ipady=6)
        self.fv_stop_btn.config(state="disabled")

        pb2 = tk.Frame(outer, bg=BG)
        pb2.pack(fill="x", padx=24, pady=(8, 0))
        self.fv_pb = ttk.Progressbar(pb2, style="A.Horizontal.TProgressbar",
                                     mode="indeterminate")
        self.fv_pb.pack(fill="x")

        make_section(outer, "LOG", pady_top=8)
        self.fv_log = make_log(outer)
        self._wlog(self.fv_log,
                   "Select a folder of transparent PNG frames, then click "
                   "▶ ENCODE VIDEO FROM FRAMES.\n", "head")
        return outer

    # ── Chroma helpers ────────────────────────────────────────────────────────
    def _toggle_mode(self):
        if self.remove_mode.get() == "chroma":
            self.chroma_panel.pack(fill="x", padx=32, pady=(2, 4))
            self.ai_panel.pack_forget()
        else:
            self.ai_panel.pack(fill="x", padx=32, pady=(2, 4))
            self.chroma_panel.pack_forget()

    def _pick_color(self):
        col = colorchooser.askcolor(color=self.chroma_color.get(),
                                    title="Pick background color")[1]
        if col:
            self._set_color(col)

    def _set_color(self, col):
        self.chroma_color.set(col)
        self.color_swatch.config(bg=col)

    # ── Browse callbacks ──────────────────────────────────────────────────────
    def _browse_video(self):
        p = filedialog.askopenfilename(
            title="Select video",
            filetypes=[("Video files", "*.mp4 *.mov *.avi *.webm *.mkv"),
                       ("All files", "*.*")])
        if p:
            self.video_path.set(p)
            if not self.output_dir.get():
                self.output_dir.set(os.path.dirname(p))

    def _browse_output(self):
        p = filedialog.askdirectory(title="Select output folder")
        if p: self.output_dir.set(p)

    def _fv_browse_folder(self):
        p = filedialog.askdirectory(title="Select frames folder")
        if p:
            self.fv_folder.set(p)
            if not self.fv_output.get():
                self.fv_output.set(os.path.dirname(p))
            self._fv_autodetect()

    def _fv_browse_output(self):
        p = filedialog.askdirectory(title="Select output folder")
        if p: self.fv_output.set(p)

    def _fv_autodetect(self):
        folder = self.fv_folder.get()
        if not folder or not os.path.isdir(folder):
            return
        pngs = sorted([f for f in os.listdir(folder)
                       if f.lower().endswith(".png")])
        if not pngs:
            self._wlog(self.fv_log, "  No PNG files found in that folder.\n", "warn")
            return
        m = re.match(r'^([a-zA-Z_\-]+)(\d+)\.png$', pngs[0])
        if m:
            prefix = m.group(1)
            width  = len(m.group(2))
            pat    = f"{prefix}%0{width}d.png"
            self.fv_pattern.set(pat)
            self._wlog(self.fv_log,
                       f"  Auto-detected pattern: {pat}  ({len(pngs)} frames)\n",
                       "ok")
        else:
            self._wlog(self.fv_log,
                       f"  Could not auto-detect pattern.\n"
                       f"  First file: {pngs[0]} — set pattern manually.\n",
                       "warn")

    # ── Tool check ────────────────────────────────────────────────────────────
    def _check_tools(self):
        self._wlog(self.pipe_log,
                   "\n─── Tool Check ─────────────────────────────────\n", "head")
        for tool, cmd in [("ffmpeg", ["ffmpeg", "-version"]),
                          ("rembg",  ["rembg",  "--help"])]:
            try:
                subprocess.run(cmd, capture_output=True, timeout=8)
                self._wlog(self.pipe_log, f"  ✓  {tool} found\n", "ok")
            except FileNotFoundError:
                self._wlog(self.pipe_log, f"  ✗  {tool} NOT found\n", "err")
        self._wlog(self.pipe_log,
                   "\n  Missing something?\n"
                   "  • ffmpeg → https://www.gyan.dev/ffmpeg/builds/\n"
                   "  • rembg  → pip install rembg[cli]\n\n", "warn")

    # ── Log helper ────────────────────────────────────────────────────────────
    def _wlog(self, widget, msg, tag=None):
        widget.configure(state="normal")
        widget.insert("end", msg, tag) if tag else widget.insert("end", msg)
        widget.see("end")
        widget.configure(state="disabled")
        self.update_idletasks()

    # ── Step indicator ────────────────────────────────────────────────────────
    def _set_step(self, idx, state):
        STATES = {
            "idle":    (SUBTEXT, SUBTEXT, "●  idle"),
            "running": (TEXT,    ACCENT2, "◌  running…"),
            "done":    (TEXT,    SUCCESS, "✓  done"),
            "error":   (TEXT,    ERROR,   "✗  error"),
        }
        f, lbl, dot = self.pipe_steps[idx]
        nc, dc, dt  = STATES[state]
        lbl.config(fg=nc)
        dot.config(fg=dc, text=dt)
        hl = {"running": ACCENT, "done": SUCCESS,
              "error": ERROR}.get(state, BORDER)
        f.config(highlightbackground=hl)

    def _step_ui(self, idx, state):
        self.after(0, lambda: self._set_step(idx, state))

    # ── Run command ───────────────────────────────────────────────────────────
    def _run_cmd(self, cmd, log):
        self._wlog(log, f"  $ {' '.join(cmd)}\n")
        try:
            self.proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace")
            for line in self.proc.stdout:
                s = line.rstrip()
                if s:
                    self._wlog(log, f"    {s}\n")
            self.proc.wait()
            return self.proc.returncode == 0
        except FileNotFoundError as e:
            self._wlog(log, f"  Command not found: {e}\n", "err")
            return False

    # ── Encode helper (shared) ────────────────────────────────────────────────
    def _encode(self, frames_dir, fps, crf, fmt, outfile, log, pattern="frame%04d.png"):
        inp = os.path.join(frames_dir, pattern)
        if fmt == "webm":
            cmd = ["ffmpeg", "-y", "-framerate", fps, "-i", inp,
                   "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
                   "-crf", str(crf), "-b:v", "0", outfile]
        else:
            cmd = ["ffmpeg", "-y", "-framerate", fps, "-i", inp,
                   "-c:v", "prores_ks", "-profile:v", "4444",
                   "-pix_fmt", "yuva444p10le", outfile]
        return self._run_cmd(cmd, log)

    # ═══════════════════════════════════════════════════════════════════════════
    #  PIPELINE RUN
    # ═══════════════════════════════════════════════════════════════════════════
    def _run_pipeline(self):
        video  = self.video_path.get().strip()
        outdir = self.output_dir.get().strip() or os.path.dirname(video)
        if not video or not os.path.isfile(video):
            messagebox.showerror("No video", "Please select a valid video file.")
            return
        self.run_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.running = True
        self.pipe_pb.start(12)
        for i in range(3): self._set_step(i, "idle")
        threading.Thread(target=self._pipeline_thread,
                         args=(video, outdir), daemon=True).start()

    def _pipeline_thread(self, video, outdir):
        log = self.pipe_log
        try:
            base   = os.path.splitext(os.path.basename(video))[0]
            frames = os.path.join(outdir, f"{base}_frames")
            transp = os.path.join(outdir, f"{base}_transparent")
            fps    = self.framerate.get() or "30"
            os.makedirs(frames, exist_ok=True)

            # Step 1
            self._step_ui(0, "running")
            self._wlog(log, f"\n▶  STEP 1 — Extracting frames…\n", "head")
            ok = self._run_cmd(
                ["ffmpeg", "-y", "-i", video, "-pix_fmt", "rgba",
                 os.path.join(frames, "frame%04d.png")], log)
            if not ok:
                self._step_ui(0, "error"); return
            self._step_ui(0, "done")
            n = len([f for f in os.listdir(frames) if f.endswith(".png")])
            self._wlog(log, f"  → {n} frames extracted\n", "ok")

            # Step 2
            self._step_ui(1, "running")
            mode = self.remove_mode.get()
            if mode == "chroma":
                self._wlog(log, "\n▶  STEP 2 — Chroma key removal…\n", "head")
                os.makedirs(transp, exist_ok=True)
                hex_col  = self.chroma_color.get().lstrip("#")
                color_str = f"0x{hex_col.upper()}"
                sim      = round(self.chroma_sim.get(), 3)
                blend    = round(self.chroma_blend.get(), 3)
                self._wlog(log, f"  Color: #{hex_col.upper()}  "
                                 f"Similarity: {sim}  Blend: {blend}\n")
                vf  = f"chromakey={color_str}:{sim}:{blend}"
                ok  = self._run_cmd([
                    "ffmpeg", "-y",
                    "-i", os.path.join(frames, "frame%04d.png"),
                    "-vf", vf,
                    "-pix_fmt", "yuva420p",
                    os.path.join(transp, "frame%04d.png")
                ], log)
            else:
                os.makedirs(transp, exist_ok=True)
                self._wlog(log, f"\n▶  STEP 2 — AI removal "
                                 f"({self.rembg_model.get()})…\n", "head")
                cmd = ["rembg", "p"]
                if self.rembg_model.get() != "u2net":
                    cmd += ["-m", self.rembg_model.get()]
                cmd += [frames, transp]
                ok = self._run_cmd(cmd, log)
            if not ok:
                self._step_ui(1, "error"); return
            self._step_ui(1, "done")

            # Step 3
            self._step_ui(2, "running")
            outfile = os.path.join(outdir,
                                   f"{base}_transparent.{self.out_format.get()}")
            self._wlog(log, f"\n▶  STEP 3 — Encoding {self.out_format.get()}…\n",
                       "head")
            ok = self._encode(transp, fps, self.crf.get(),
                              self.out_format.get(), outfile, log)
            if not ok:
                self._step_ui(2, "error"); return
            self._step_ui(2, "done")

            if not self.keep_frames.get():
                shutil.rmtree(frames, ignore_errors=True)
                shutil.rmtree(transp, ignore_errors=True)
                self._wlog(log, "  → Temp folders removed.\n")

            self._wlog(log, f"\n✓  ALL DONE!  →  {outfile}\n\n", "ok")
        except Exception as ex:
            self._wlog(log, f"\n  Unexpected error: {ex}\n", "err")
        finally:
            self.after(0, self._pipe_done)

    def _pipe_done(self):
        self.running = False
        self.pipe_pb.stop()
        self.run_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    # ═══════════════════════════════════════════════════════════════════════════
    #  FRAMES → VIDEO RUN
    # ═══════════════════════════════════════════════════════════════════════════
    def _run_fv(self):
        folder = self.fv_folder.get().strip()
        outdir = self.fv_output.get().strip() or os.path.dirname(folder)
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("No folder", "Please select a folder of PNG frames.")
            return
        self.fv_run_btn.config(state="disabled")
        self.fv_stop_btn.config(state="normal")
        self.running = True
        self.fv_pb.start(12)
        threading.Thread(target=self._fv_thread,
                         args=(folder, outdir), daemon=True).start()

    def _fv_thread(self, folder, outdir):
        log = self.fv_log
        try:
            fps     = self.fv_fps.get() or "30"
            crf     = self.fv_crf.get()
            fmt     = self.fv_format.get()
            pattern = self.fv_pattern.get().strip() or "frame%04d.png"
            name    = os.path.basename(folder.rstrip("/\\"))
            outfile = os.path.join(outdir, f"{name}_video.{fmt}")
            self._wlog(log,
                       f"\n▶  Encoding from: {folder}\n"
                       f"   Pattern: {pattern}   FPS: {fps}   "
                       f"CRF: {crf}   Format: {fmt}\n", "head")
            ok = self._encode(folder, fps, crf, fmt, outfile, log,
                              pattern=pattern)
            if ok:
                self._wlog(log, f"\n✓  DONE!  →  {outfile}\n\n", "ok")
            else:
                self._wlog(log, "\n  Encoding failed — check log above.\n", "err")
        except Exception as ex:
            self._wlog(log, f"\n  Error: {ex}\n", "err")
        finally:
            self.after(0, self._fv_done)

    def _fv_done(self):
        self.running = False
        self.fv_pb.stop()
        self.fv_run_btn.config(state="normal")
        self.fv_stop_btn.config(state="disabled")

    # ── Stop ──────────────────────────────────────────────────────────────────
    def _stop(self):
        if self.proc:
            self.proc.terminate()
        self._pipe_done()
        self._fv_done()
        self._wlog(self.pipe_log, "\n  ■  Stopped by user.\n", "warn")


if __name__ == "__main__":
    App().mainloop()
