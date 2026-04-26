"""
CHRONOS//FOCUS — Cyberpunk Pomodoro Timer
  25min STUDY -> 5min BREAK
  Persistent daily log at ~/.nexus_focus_log.json
  Python 3.8+ / stdlib only

[v1.1 changes]
  * Removed: mini ring in right panel (caused duplicate timer at small sizes)
  * Removed: _on_resize layout-switching logic (no longer needed)
  * Removed: AMBIENT_MSGS noise generator (it was unused in v1.0)
  * Added:   responsive timer ring that scales with center panel size
  * Added:   minsize on the center column so it can never collapse
  * Added:   keyboard shortcuts: Space (play/pause), R (reset), S (skip), P (pin)
  * Added:   system bell on phase change (subtle audio cue)
  * Kept:    every other feature — color config, pin/topmost, persistence,
             history, log, status bar, auto-save, date rollover, flash effect
"""

import tkinter as tk
from tkinter import colorchooser
import json
import math
import time
from datetime import datetime, timedelta
from pathlib import Path


WORK_SEC = 25 * 60
BREAK_SEC = 5 * 60
LOG_FILE = Path.home() / ".nexus_focus_log.json"


DEFAULT_COLORS = {
    "bg":     "#08001a",
    "panel":  "#0e0625",
    "border": "#2a1450",
    "lit":    "#9d4dff",
    "text":   "#e6e0ff",
    "muted":  "#6a5090",
    "work":   "#ff2e88",
    "break":  "#00f0ff",
    "accent": "#b829ff",
    "ok":     "#00ffaa",
}


class ChronosFocus(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("CHRONOS//FOCUS")

        self.colors = dict(DEFAULT_COLORS)
        self.phase = "work"
        self.remaining = WORK_SEC
        self.running = False
        self.cycles_today = 0
        self.total_seconds = self._load_today_total()
        self.session_start = time.time()
        self.topmost = False
        self.settings_win = None
        self._tick_after = None
        self._log_count = 0
        self._ring_w = 0
        self._ring_h = 0

        self._wbinds = []
        self._cibinds = []

        self.configure(bg=self.colors["bg"])
        self._apply_window_size()
        # 全要素が同時に見える最小サイズ
        self.minsize(820, 600)

        self._build_ui()
        self._render()
        self._refresh_history()

        self._log("SYS  :: CHRONOS online", "ok")
        self._log(f"DAT  :: today {self._fmt_hms(self.total_seconds)}", "info")

        self._uptime_loop()
        self._autosave_loop()

        # キーボードショートカット
        self.bind("<space>", lambda e: self._toggle())
        self.bind("<Key-r>", lambda e: self._reset())
        self.bind("<Key-R>", lambda e: self._reset())
        self.bind("<Key-s>", lambda e: self._skip())
        self.bind("<Key-S>", lambda e: self._skip())
        self.bind("<Key-p>", lambda e: self._toggle_topmost())
        self.bind("<Key-P>", lambda e: self._toggle_topmost())

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Color helpers ──────────────────────────────────────
    def _reg(self, widget, **role_map):
        for opt, key in role_map.items():
            try:
                widget.config(**{opt: self.colors[key]})
            except Exception:
                pass
            self._wbinds.append((widget, opt, key))
        return widget

    def _reg_item(self, canvas, item_id, **role_map):
        for opt, key in role_map.items():
            try:
                canvas.itemconfig(item_id, **{opt: self.colors[key]})
            except Exception:
                pass
            self._cibinds.append((canvas, item_id, opt, key))
        return item_id

    # ── Window ─────────────────────────────────────────────
    def _apply_window_size(self):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = max(920, sw // 2)
        h = max(620, int(sh * 0.62))
        x = max(0, (sw - w) // 2)
        y = max(40, (sh - h) // 3)
        self.geometry(f"{w}x{h}+{x}+{y}")

    @staticmethod
    def _fmt_hms(secs):
        secs = int(secs)
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    # ── Persistence ────────────────────────────────────────
    def _load_today_total(self):
        try:
            if LOG_FILE.exists():
                data = json.loads(LOG_FILE.read_text(encoding="utf-8"))
                today = datetime.now().strftime("%Y-%m-%d")
                return int(data.get(today, 0))
        except Exception:
            pass
        return 0

    def _save_today_total(self):
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            data = {}
            if LOG_FILE.exists():
                try:
                    raw = json.loads(LOG_FILE.read_text(encoding="utf-8"))
                    if isinstance(raw, dict):
                        data = raw
                except Exception:
                    data = {}
            data[today] = int(self.total_seconds)
            LOG_FILE.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _load_history(self):
        try:
            if LOG_FILE.exists():
                d = json.loads(LOG_FILE.read_text(encoding="utf-8"))
                if isinstance(d, dict):
                    return d
        except Exception:
            pass
        return {}

    # ── Build UI ───────────────────────────────────────────
    def _build_ui(self):
        self._build_header()
        self._build_footer()

        main = tk.Frame(self)
        self._reg(main, bg="bg")
        main.pack(side="top", fill="both", expand=True, padx=10, pady=(2, 4))
        # ★ 中央列にも minsize を指定 → どんなに小さくしても消えない
        main.columnconfigure(0, minsize=200, weight=0)
        main.columnconfigure(1, minsize=320, weight=1)
        main.columnconfigure(2, minsize=240, weight=0)
        main.rowconfigure(0, weight=1)

        self.left_panel = self._make_panel(main)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        self._build_left(self.left_panel)

        self.center_panel = self._make_panel(main)
        self.center_panel.grid(row=0, column=1, sticky="nsew", padx=4)
        self._build_center(self.center_panel)

        self.right_panel = self._make_panel(main)
        self.right_panel.grid(row=0, column=2, sticky="nsew", padx=(4, 0))
        self._build_right(self.right_panel)

    def _make_panel(self, parent):
        f = tk.Frame(parent, highlightthickness=1)
        self._reg(f, bg="panel", highlightbackground="border")
        return f

    def _hsep(self, parent, padx=14, pady=4):
        f = tk.Frame(parent, height=1)
        self._reg(f, bg="border")
        f.pack(fill="x", padx=padx, pady=pady)
        return f

    def _build_header(self):
        hbar = tk.Frame(self, height=42)
        self._reg(hbar, bg="bg")
        hbar.pack(side="top", fill="x", padx=10, pady=(8, 2))
        hbar.pack_propagate(False)

        tf = tk.Frame(hbar)
        self._reg(tf, bg="bg")
        tf.pack(side="left", fill="y")

        d = tk.Label(tf, text="◆", font=("Consolas", 13, "bold"))
        self._reg(d, bg="bg", fg="work")
        d.pack(side="left", padx=(0, 6))

        for txt, role in [("CHRONOS", "text"), ("//", "accent"), ("FOCUS", "work")]:
            l = tk.Label(tf, text=txt, font=("Consolas", 14, "bold"))
            self._reg(l, bg="bg", fg=role)
            l.pack(side="left")

        tag = tk.Label(tf, text="  v1.1 / control_room", font=("Consolas", 8))
        self._reg(tag, bg="bg", fg="muted")
        tag.pack(side="left", padx=(8, 0))

        rf = tk.Frame(hbar)
        self._reg(rf, bg="bg")
        rf.pack(side="right", fill="y")

        self.btn_topmost = tk.Button(
            rf, text="◇ PIN", font=("Consolas", 9),
            relief="flat", bd=0, cursor="hand2",
            command=self._toggle_topmost,
        )
        self._reg(self.btn_topmost, bg="bg", fg="muted",
                  activebackground="panel", activeforeground="accent")
        self.btn_topmost.pack(side="right", padx=(8, 0))

        self.btn_settings = tk.Button(
            rf, text="⚙ CFG", font=("Consolas", 9),
            relief="flat", bd=0, cursor="hand2",
            command=self._open_settings,
        )
        self._reg(self.btn_settings, bg="bg", fg="muted",
                  activebackground="panel", activeforeground="accent")
        self.btn_settings.pack(side="right", padx=(8, 0))

        self.lbl_uptime = tk.Label(rf, text="UPTIME 00:00:00", font=("Consolas", 9))
        self._reg(self.lbl_uptime, bg="bg", fg="break")
        self.lbl_uptime.pack(side="right", padx=8)

        sep = tk.Frame(self, height=1)
        self._reg(sep, bg="border")
        sep.pack(side="top", fill="x", padx=10)

    def _build_footer(self):
        sep = tk.Frame(self, height=1)
        self._reg(sep, bg="border")
        sep.pack(side="bottom", fill="x", padx=10)

        f = tk.Frame(self, height=24)
        self._reg(f, bg="bg")
        f.pack(side="bottom", fill="x", padx=10, pady=(2, 6))
        f.pack_propagate(False)

        self.lbl_status = tk.Label(f, text="● STANDBY", font=("Consolas", 8))
        self._reg(self.lbl_status, bg="bg", fg="muted")
        self.lbl_status.pack(side="left")

        # キーボードショートカットのヒント
        hint = tk.Label(
            f, text="[SPACE] PLAY  [R] RESET  [S] SKIP  [P] PIN",
            font=("Consolas", 7))
        self._reg(hint, bg="bg", fg="muted")
        hint.pack(side="left", padx=12)

        self.lbl_clock = tk.Label(f, text="", font=("Consolas", 8))
        self._reg(self.lbl_clock, bg="bg", fg="muted")
        self.lbl_clock.pack(side="right")

    def _build_left(self, f):
        h = tk.Frame(f)
        self._reg(h, bg="panel")
        h.pack(fill="x", padx=14, pady=(14, 0))

        hl = tk.Label(h, text="▮ SYSTEM", font=("Consolas", 9, "bold"))
        self._reg(hl, bg="panel", fg="accent")
        hl.pack(anchor="w")

        self._hsep(f)

        l = tk.Label(f, text="PHASE", font=("Consolas", 7))
        self._reg(l, bg="panel", fg="muted")
        l.pack(anchor="w", padx=14, pady=(8, 2))

        self.lbl_phase = tk.Label(f, text="STUDY", font=("Consolas", 22, "bold"))
        self._reg(self.lbl_phase, bg="panel", fg="work")
        self.lbl_phase.pack(anchor="w", padx=14, pady=(0, 8))

        self.prog_canvas = tk.Canvas(f, height=4, highlightthickness=0)
        self._reg(self.prog_canvas, bg="panel")
        self.prog_canvas.pack(fill="x", padx=14, pady=(0, 16))
        self.prog_bg = self.prog_canvas.create_rectangle(0, 0, 0, 4, outline="")
        self._reg_item(self.prog_canvas, self.prog_bg, fill="border")
        self.prog_fg = self.prog_canvas.create_rectangle(0, 0, 0, 4, outline="")
        self._reg_item(self.prog_canvas, self.prog_fg, fill="work")

        l = tk.Label(f, text="CYCLES TODAY", font=("Consolas", 7))
        self._reg(l, bg="panel", fg="muted")
        l.pack(anchor="w", padx=14, pady=(0, 2))

        self.lbl_cycles = tk.Label(f, text="00", font=("Consolas", 20, "bold"))
        self._reg(self.lbl_cycles, bg="panel", fg="text")
        self.lbl_cycles.pack(anchor="w", padx=14, pady=(0, 12))

        l = tk.Label(f, text="STUDY TIME", font=("Consolas", 7))
        self._reg(l, bg="panel", fg="muted")
        l.pack(anchor="w", padx=14, pady=(0, 2))

        self.lbl_total = tk.Label(f, text="00:00:00", font=("Consolas", 16, "bold"))
        self._reg(self.lbl_total, bg="panel", fg="ok")
        self.lbl_total.pack(anchor="w", padx=14, pady=(0, 2))

        l = tk.Label(f, text="(BREAK EXCLUDED)", font=("Consolas", 6))
        self._reg(l, bg="panel", fg="muted")
        l.pack(anchor="w", padx=14, pady=(0, 12))

        self._hsep(f)

        l = tk.Label(f, text="NEXT", font=("Consolas", 7))
        self._reg(l, bg="panel", fg="muted")
        l.pack(anchor="w", padx=14, pady=(8, 2))

        self.lbl_next = tk.Label(f, text="-> BREAK 05:00", font=("Consolas", 9))
        self._reg(self.lbl_next, bg="panel", fg="break")
        self.lbl_next.pack(anchor="w", padx=14, pady=(0, 8))

    def _build_center(self, f):
        # ヘッダー
        top = tk.Frame(f)
        self._reg(top, bg="panel")
        top.pack(side="top", fill="x", padx=14, pady=(14, 0))

        hl = tk.Label(top, text="▮ TIMER CORE", font=("Consolas", 9, "bold"))
        self._reg(hl, bg="panel", fg="accent")
        hl.pack(side="left")

        self.lbl_session = tk.Label(top, text="SESSION 01", font=("Consolas", 8))
        self._reg(self.lbl_session, bg="panel", fg="muted")
        self.lbl_session.pack(side="right")

        self._hsep(f)

        # コントロール（下に固定）
        ctrl = tk.Frame(f)
        self._reg(ctrl, bg="panel")
        ctrl.pack(side="bottom", pady=(0, 18))

        bs_kw = dict(font=("Consolas", 11), bd=0, relief="flat",
                     cursor="hand2", width=4, height=2)

        self.btn_reset = tk.Button(ctrl, text="↺", command=self._reset, **bs_kw)
        self._reg(self.btn_reset, bg="bg", fg="text",
                  activebackground="border", activeforeground="text")
        self.btn_reset.pack(side="left", padx=8)

        self.btn_play = tk.Button(
            ctrl, text="▶",
            font=("Consolas", 14, "bold"), bd=0, relief="flat",
            cursor="hand2", width=5, height=2, command=self._toggle,
        )
        self._reg(self.btn_play, bg="bg", fg="work",
                  activebackground="border", activeforeground="work")
        self.btn_play.pack(side="left", padx=8)

        self.btn_skip = tk.Button(ctrl, text="⏭", command=self._skip, **bs_kw)
        self._reg(self.btn_skip, bg="bg", fg="text",
                  activebackground="border", activeforeground="text")
        self.btn_skip.pack(side="left", padx=8)

        # ★ レスポンシブなリングキャンバス（残った領域を全部使う）
        self.ring_canvas = tk.Canvas(f, highlightthickness=0)
        self._reg(self.ring_canvas, bg="panel")
        self.ring_canvas.pack(side="top", fill="both", expand=True,
                              padx=10, pady=(4, 0))
        self.ring_canvas.bind("<Configure>", self._on_ring_resize)

    def _on_ring_resize(self, event):
        if event.width == self._ring_w and event.height == self._ring_h:
            return
        self._ring_w = event.width
        self._ring_h = event.height
        self._draw_ring()

    def _draw_ring(self):
        c = self.ring_canvas
        c.delete("all")
        cw = c.winfo_width()
        ch = c.winfo_height()
        if cw < 60 or ch < 60:
            return

        size = min(cw, ch) - 16
        if size < 120:
            size = 120
        cx = cw // 2
        cy = ch // 2
        r = size // 2

        is_work = self.phase == "work"
        col = self.colors["work"] if is_work else self.colors["break"]
        total = WORK_SEC if is_work else BREAK_SEC
        ratio = self.remaining / total if total else 0

        # 外周リング
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      width=1, outline=self.colors["border"])

        # 内側の背景リング
        m = max(10, int(size * 0.07))
        c.create_oval(cx - r + m, cy - r + m, cx + r - m, cy + r - m,
                      width=2, outline=self.colors["border"])

        # 進捗アーク
        if ratio > 0:
            c.create_arc(cx - r + m, cy - r + m, cx + r - m, cy + r - m,
                         start=90, extent=-360 * ratio,
                         width=3, style="arc", outline=col)

        # 時計の目盛り（12個）
        tick_outer = r - max(14, int(size * 0.085))
        tick_inner = r - max(20, int(size * 0.12))
        for i in range(12):
            ang = math.radians(i * 30 - 90)
            x1 = cx + tick_inner * math.cos(ang)
            y1 = cy + tick_inner * math.sin(ang)
            x2 = cx + tick_outer * math.cos(ang)
            y2 = cy + tick_outer * math.sin(ang)
            c.create_line(x1, y1, x2, y2, width=1,
                          fill=self.colors["border"])

        # 中央のテキスト（フォントもサイズに応じてスケール）
        font_size = max(20, int(size * 0.18))
        sub_size = max(8, int(size * 0.04))
        mm, ss = divmod(self.remaining, 60)
        c.create_text(cx, cy - max(2, font_size // 10),
                      text=f"{mm:02d}:{ss:02d}",
                      font=("Consolas", font_size, "bold"), fill=col)
        c.create_text(cx, cy + font_size // 2 + max(8, sub_size + 4),
                      text="STUDY MODE" if is_work else "BREAK MODE",
                      font=("Consolas", sub_size), fill=self.colors["muted"])

    def _build_right(self, f):
        # ヘッダー
        h = tk.Frame(f)
        self._reg(h, bg="panel")
        h.pack(fill="x", padx=14, pady=(14, 0))

        hl = tk.Label(h, text="▮ SYS_LOG", font=("Consolas", 9, "bold"))
        self._reg(hl, bg="panel", fg="accent")
        hl.pack(side="left")

        self.lbl_log_count = tk.Label(h, text="0", font=("Consolas", 8))
        self._reg(self.lbl_log_count, bg="panel", fg="muted")
        self.lbl_log_count.pack(side="right")

        self._hsep(f)

        # ヒストリー（上）
        l = tk.Label(f, text="◆ HISTORY (7d)", font=("Consolas", 8, "bold"))
        self._reg(l, bg="panel", fg="accent")
        l.pack(anchor="w", padx=14, pady=(8, 4))

        self.history_frame = tk.Frame(f)
        self._reg(self.history_frame, bg="panel")
        self.history_frame.pack(fill="x", padx=14, pady=(0, 8))

        self._hsep(f)

        # ログエリア（残り全部を埋める）
        self.log_frame = tk.Frame(f)
        self._reg(self.log_frame, bg="bg")
        self.log_frame.pack(fill="both", expand=True, padx=14, pady=(8, 12))

        self.log_text = tk.Text(
            self.log_frame, font=("Consolas", 8),
            wrap="none", bd=0, padx=6, pady=6, highlightthickness=0)
        self._reg(self.log_text, bg="bg", fg="muted",
                  insertbackground="muted")
        self.log_text.pack(fill="both", expand=True)
        self._refresh_log_tags()
        self.log_text.configure(state="disabled")

    def _refresh_log_tags(self):
        try:
            self.log_text.tag_configure("info",  foreground=self.colors["muted"])
            self.log_text.tag_configure("event", foreground=self.colors["work"])
            self.log_text.tag_configure("ok",    foreground=self.colors["ok"])
            self.log_text.tag_configure("break", foreground=self.colors["break"])
        except Exception:
            pass

    # ── History ────────────────────────────────────────────
    def _refresh_history(self):
        for w in self.history_frame.winfo_children():
            w.destroy()
        data = self._load_history()
        today = datetime.now()
        for i in range(7):
            d = today - timedelta(days=i)
            key = d.strftime("%Y-%m-%d")
            secs = int(data.get(key, 0))
            if i == 0:
                secs = self.total_seconds
            label = "TODAY" if i == 0 else d.strftime("%m-%d")
            self._history_row(self.history_frame, label, secs, i == 0)

    def _history_row(self, parent, label, secs, is_today):
        row = tk.Frame(parent)
        self._reg(row, bg="panel")
        row.pack(fill="x", pady=1)

        col_role = "work" if is_today else "muted"
        l = tk.Label(row, text=label, font=("Consolas", 8), width=7, anchor="w")
        self._reg(l, bg="panel", fg=col_role)
        l.pack(side="left")

        max_secs = max(8 * 3600, int(self.total_seconds * 1.2))
        ratio = min(secs / max_secs, 1.0) if max_secs else 0

        bar_w = 70
        bar = tk.Canvas(row, height=6, width=bar_w, highlightthickness=0)
        self._reg(bar, bg="bg")
        bar.pack(side="left", padx=4)

        b1 = bar.create_rectangle(0, 1, bar_w, 5, outline="")
        self._reg_item(bar, b1, fill="border")
        if ratio > 0:
            b2 = bar.create_rectangle(0, 1, max(2, bar_w * ratio), 5, outline="")
            self._reg_item(bar, b2, fill=col_role)

        h, rem = divmod(secs, 3600)
        m, _ = divmod(rem, 60)
        l = tk.Label(row, text=f"{h:02d}:{m:02d}", font=("Consolas", 8))
        self._reg(l, bg="panel", fg=col_role)
        l.pack(side="right")

    # ── Render ─────────────────────────────────────────────
    def _render(self):
        is_work = self.phase == "work"
        col = self.colors["work"] if is_work else self.colors["break"]
        total = WORK_SEC if is_work else BREAK_SEC
        ratio = self.remaining / total if total else 0

        # メインリング再描画
        self._draw_ring()

        self.lbl_phase.config(text="STUDY" if is_work else "BREAK", fg=col)
        self.btn_play.config(fg=col, activeforeground=col)
        self.lbl_cycles.config(text=f"{self.cycles_today:02d}")
        self.lbl_total.config(text=self._fmt_hms(self.total_seconds))

        if is_work:
            self.lbl_next.config(text="-> BREAK 05:00", fg=self.colors["break"])
        else:
            self.lbl_next.config(text="-> STUDY 25:00", fg=self.colors["work"])

        self.lbl_session.config(text=f"SESSION {(self.cycles_today + 1):02d}")

        # プログレスバー
        self.prog_canvas.update_idletasks()
        w = max(self.prog_canvas.winfo_width(), 1)
        self.prog_canvas.coords(self.prog_bg, 0, 0, w, 4)
        self.prog_canvas.coords(self.prog_fg, 0, 0, w * (1 - ratio), 4)
        self.prog_canvas.itemconfig(self.prog_fg, fill=col)

    # ── Timing ─────────────────────────────────────────────
    def _tick(self):
        self._tick_after = None
        if not self.running:
            return
        if self.remaining > 0:
            self.remaining -= 1
            if self.phase == "work":
                self.total_seconds += 1
            self._render()
            self._tick_after = self.after(1000, self._tick)
        else:
            self._phase_end()

    def _phase_end(self):
        # フェーズ切り替え時のシステムベル
        try:
            self.bell()
        except Exception:
            pass

        if self.phase == "work":
            self.cycles_today += 1
            self._save_today_total()
            self._refresh_history()
            self._log(f"EVT  :: study_complete cycle={self.cycles_today}", "ok")
            self.phase = "break"
            self.remaining = BREAK_SEC
            self.lbl_status.config(text="● BREAK MODE", fg=self.colors["break"])
        else:
            self._log("EVT  :: break_complete", "break")
            self.phase = "work"
            self.remaining = WORK_SEC
            self.lbl_status.config(text="● STUDY MODE", fg=self.colors["work"])
        self._flash()
        self._render()
        self._tick_after = self.after(1000, self._tick)

    def _toggle(self):
        if self.running:
            self.running = False
            if self._tick_after is not None:
                try:
                    self.after_cancel(self._tick_after)
                except Exception:
                    pass
                self._tick_after = None
            self.btn_play.config(text="▶")
            self.lbl_status.config(text="● PAUSED", fg=self.colors["muted"])
            self._log("CTRL :: pause", "info")
        else:
            self.running = True
            self.btn_play.config(text="❚❚")
            phase_col = (self.colors["work"] if self.phase == "work"
                         else self.colors["break"])
            phase_name = "STUDY MODE" if self.phase == "work" else "BREAK MODE"
            self.lbl_status.config(text=f"● {phase_name}", fg=phase_col)
            self._log(f"CTRL :: start phase={self.phase}",
                      "event" if self.phase == "work" else "break")
            if self._tick_after is None:
                self._tick_after = self.after(1000, self._tick)

    def _reset(self):
        if self._tick_after is not None:
            try:
                self.after_cancel(self._tick_after)
            except Exception:
                pass
            self._tick_after = None
        self.running = False
        self.phase = "work"
        self.remaining = WORK_SEC
        self.btn_play.config(text="▶")
        self.lbl_status.config(text="● STANDBY", fg=self.colors["muted"])
        self._log("CTRL :: reset", "info")
        self._render()

    def _skip(self):
        self.remaining = 1
        self._log(f"CTRL :: skip phase={self.phase}", "info")
        self._render()

    def _flash(self):
        c = (self.colors["break"] if self.phase == "break"
             else self.colors["work"])
        prev = self.colors["bg"]
        self.configure(bg=c)
        self.after(80, lambda: self.configure(bg=prev))

    # ── Side loops ─────────────────────────────────────────
    def _uptime_loop(self):
        try:
            elapsed = int(time.time() - self.session_start)
            h, rem = divmod(elapsed, 3600)
            m, s = divmod(rem, 60)
            self.lbl_uptime.config(text=f"UPTIME {h:02d}:{m:02d}:{s:02d}")
            self.lbl_clock.config(text=time.strftime("%Y-%m-%d  %H:%M:%S"))
        except Exception:
            return
        self.after(1000, self._uptime_loop)

    def _autosave_loop(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if not hasattr(self, "_current_date"):
            self._current_date = today
        if today != self._current_date:
            self._save_today_total()
            self._current_date = today
            self.total_seconds = 0
            self._refresh_history()
            self._log("SYS  :: date change detected. reset.", "ok")
        self._save_today_total()
        self.after(30000, self._autosave_loop)

    # ── Log ────────────────────────────────────────────────
    def _log(self, msg, tag="info"):
        try:
            self.log_text.configure(state="normal")
            ts = time.strftime("%H:%M:%S")
            self.log_text.insert("end", f"[{ts}] {msg}\n", tag)
            lines = int(self.log_text.index("end-1c").split(".")[0])
            if lines > 250:
                self.log_text.delete("1.0", f"{lines - 180}.0")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
            self._log_count += 1
            self.lbl_log_count.config(text=str(self._log_count))
        except Exception:
            pass

    # ── Topmost / close ────────────────────────────────────
    def _toggle_topmost(self):
        self.topmost = not self.topmost
        self.attributes("-topmost", self.topmost)
        if self.topmost:
            self.btn_topmost.config(text="◆ PIN", fg=self.colors["work"])
            self._log("CTRL :: pinned topmost", "ok")
        else:
            self.btn_topmost.config(text="◇ PIN", fg=self.colors["muted"])
            self._log("CTRL :: unpinned", "info")

    def _on_close(self):
        try:
            self._save_today_total()
        except Exception:
            pass
        self.destroy()

    # ── Settings ───────────────────────────────────────────
    def _open_settings(self):
        if self.settings_win is not None:
            try:
                if self.settings_win.winfo_exists():
                    self.settings_win.lift()
                    return
            except Exception:
                pass

        win = tk.Toplevel(self)
        self.settings_win = win
        win.title("◆ CHRONOS//CONFIG")
        win.configure(bg=self.colors["bg"])
        win.resizable(False, False)
        win.geometry("380x540")
        win.transient(self)

        tk.Label(win, text="◆ COLOR_CONFIG", font=("Consolas", 11, "bold"),
                 bg=self.colors["bg"], fg=self.colors["work"]).pack(pady=(20, 4))
        tk.Label(win, text="── modify visual parameters ──", font=("Consolas", 8),
                 bg=self.colors["bg"], fg=self.colors["muted"]).pack(pady=(0, 14))

        items = [
            ("bg",     "BACKGROUND"),
            ("panel",  "PANEL"),
            ("border", "BORDER"),
            ("lit",    "BORDER+"),
            ("text",   "TEXT"),
            ("muted",  "TEXT_DIM"),
            ("work",   "STUDY_COL"),
            ("break",  "BREAK_COL"),
            ("accent", "ACCENT"),
            ("ok",     "STATUS_OK"),
        ]

        body = tk.Frame(win, bg=self.colors["bg"])
        body.pack(padx=24, fill="x")

        self._cbtn = {}
        for key, lbl in items:
            row = tk.Frame(body, bg=self.colors["bg"])
            row.pack(fill="x", pady=3)

            tk.Label(row, text=lbl, font=("Consolas", 9),
                     bg=self.colors["bg"], fg=self.colors["text"],
                     width=11, anchor="w").pack(side="left")

            sw = tk.Button(
                row, bg=self.colors[key], width=4, height=1,
                relief="flat", bd=1, cursor="hand2",
                highlightbackground=self.colors["border"],
                command=lambda k=key: self._pick_color(k),
            )
            sw.pack(side="left", padx=(8, 0))

            vl = tk.Label(row, text=self.colors[key], font=("Consolas", 8),
                          bg=self.colors["bg"], fg=self.colors["muted"],
                          width=10, anchor="w")
            vl.pack(side="left", padx=8)
            sw._vl = vl
            self._cbtn[key] = sw

        tk.Frame(win, bg=self.colors["border"], height=1).pack(
            fill="x", padx=24, pady=(20, 12))

        bf = tk.Frame(win, bg=self.colors["bg"])
        bf.pack()

        tk.Button(bf, text="⟲ DEFAULTS", font=("Consolas", 9),
                  bg=self.colors["bg"], fg=self.colors["muted"],
                  activebackground=self.colors["panel"],
                  activeforeground=self.colors["text"],
                  relief="flat", bd=0, cursor="hand2",
                  command=self._reset_colors).pack(side="left", padx=8)

        tk.Button(bf, text="✕ CLOSE", font=("Consolas", 9),
                  bg=self.colors["bg"], fg=self.colors["text"],
                  activebackground=self.colors["panel"],
                  activeforeground=self.colors["work"],
                  relief="flat", bd=0, cursor="hand2",
                  command=win.destroy).pack(side="left", padx=8)

    def _pick_color(self, key):
        result = colorchooser.askcolor(
            color=self.colors[key], title=f"{key} color",
            parent=self.settings_win)
        if result and result[1]:
            self.colors[key] = result[1]
            btn = self._cbtn[key]
            btn.config(bg=result[1])
            btn._vl.config(text=result[1])
            self._apply_colors()

    def _reset_colors(self):
        self.colors = dict(DEFAULT_COLORS)
        if hasattr(self, "_cbtn"):
            for key, btn in self._cbtn.items():
                btn.config(bg=self.colors[key])
                btn._vl.config(text=self.colors[key])
        self._apply_colors()

    def _apply_colors(self):
        self.configure(bg=self.colors["bg"])
        for w, opt, key in self._wbinds:
            try:
                w.config(**{opt: self.colors[key]})
            except Exception:
                pass
        for c, iid, opt, key in self._cibinds:
            try:
                c.itemconfig(iid, **{opt: self.colors[key]})
            except Exception:
                pass
        self._refresh_log_tags()
        if self.topmost:
            self.btn_topmost.config(fg=self.colors["work"])
        self._render()


if __name__ == "__main__":
    app = ChronosFocus()
    app.mainloop()
