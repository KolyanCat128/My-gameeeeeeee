"""
INFINITUM — Game Launcher
==========================
Cross-platform launcher application featuring:
  - Play button & server browser
  - Workshop / mod manager
  - Settings panel
  - News feed
  - Automatic update check
  - Account management

Run: python launcher/launcher.py
"""

import sys
import os
import subprocess
import threading
import json
import time
import random

# ---------------------------------------------------------------------------
# Try to import tkinter (standard library UI)
# ---------------------------------------------------------------------------
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
    _HAS_TK = True
except ImportError:
    _HAS_TK = False
    print("[WARNING] tkinter not available — running headless launcher demo")


# ---------------------------------------------------------------------------
# Colour theme
# ---------------------------------------------------------------------------

THEME = {
    "bg":           "#0d1117",
    "bg_panel":     "#161b22",
    "bg_button":    "#1f6feb",
    "bg_button_hov":"#388bfd",
    "fg":           "#c9d1d9",
    "fg_bright":    "#ffffff",
    "fg_dim":       "#8b949e",
    "accent":       "#58a6ff",
    "success":      "#3fb950",
    "warning":      "#d29922",
    "danger":       "#f85149",
    "border":       "#30363d",
}

APP_VERSION = "0.1.0"
GAME_VERSION = "0.1.0-prototype"

# ---------------------------------------------------------------------------
# Fake news / patch notes for the launcher
# ---------------------------------------------------------------------------

NEWS_ITEMS = [
    {
        "title": "🌌 Welcome to INFINITUM!",
        "date": "2026-04-30",
        "body": (
            "The first prototype of INFINITUM is live! "
            "Explore procedurally generated infinite worlds, interact with AI-driven NPCs, "
            "and shape reality itself. Feedback welcome on our Discord."
        ),
    },
    {
        "title": "⚙️ Physics Engine v0.1 Released",
        "date": "2026-04-28",
        "body": (
            "Our custom rigid-body + fluid simulation engine is now integrated. "
            "Expect realistic object interactions, explosion dynamics, and "
            "liquid flow simulation in every biome."
        ),
    },
    {
        "title": "🤖 NPC AI System Alpha",
        "date": "2026-04-25",
        "body": (
            "Each NPC now has an individual LSTM neural network. They learn "
            "from player interactions, develop memories, form factions, and "
            "adapt their behaviour over time."
        ),
    },
    {
        "title": "🌍 World Generation: Infinite Scale",
        "date": "2026-04-20",
        "body": (
            "World generation now supports infinite terrain across all biomes. "
            "Caves, ores, structures and multi-scale worlds (atomic to galactic) "
            "are now functional."
        ),
    },
]

SERVERS = [
    {"name": "Official World #1",  "players": 1247, "max": 5000,  "ping": 12,  "biome": "Mixed"},
    {"name": "PvP Arena",          "players":  892, "max": 2000,  "ping": 28,  "biome": "Desert"},
    {"name": "Creative Builders",  "players":  413, "max": 1000,  "ping": 45,  "biome": "Plains"},
    {"name": "Survival Hardcore",  "players":   77, "max":  500,  "ping": 67,  "biome": "Tundra"},
    {"name": "Community Hub",      "players": 2381, "max": 10000, "ping":  8,  "biome": "Forest"},
]


# ---------------------------------------------------------------------------
# Headless demo (when tkinter unavailable)
# ---------------------------------------------------------------------------

def headless_launcher() -> None:
    print("=" * 60)
    print(f"  INFINITUM LAUNCHER v{APP_VERSION}")
    print("=" * 60)
    print()
    print("[NEWS]")
    for item in NEWS_ITEMS[:2]:
        print(f"  {item['date']}  {item['title']}")
        print(f"    {item['body'][:80]}...")
    print()
    print("[SERVERS]")
    for s in SERVERS:
        bar = "█" * (s["players"] * 10 // s["max"])
        print(f"  {s['name']:<25} {s['players']:>4}/{s['max']:<5} {s['ping']:>3}ms  {bar}")
    print()
    print("[LAUNCH] Starting game in headless mode...")
    time.sleep(0.5)
    print("  ✅ Game launched successfully (headless)")


# ---------------------------------------------------------------------------
# Tkinter Launcher Application
# ---------------------------------------------------------------------------

if _HAS_TK:

    class HoverButton(tk.Button):
        """Button that changes colour on hover."""
        def __init__(self, master, **kw):
            self._normal_bg  = kw.pop("bg", THEME["bg_button"])
            self._hover_bg   = kw.pop("hover_bg", THEME["bg_button_hov"])
            super().__init__(master, bg=self._normal_bg, **kw)
            self.bind("<Enter>", lambda e: self.config(bg=self._hover_bg))
            self.bind("<Leave>", lambda e: self.config(bg=self._normal_bg))

    class LauncherApp:
        def __init__(self, root: tk.Tk):
            self.root = root
            self.root.title(f"INFINITUM Launcher  v{APP_VERSION}")
            self.root.geometry("1100x680")
            self.root.configure(bg=THEME["bg"])
            self.root.resizable(True, True)
            self.root.minsize(900, 600)

            self._build_ui()
            self._start_background_tasks()

        # ------------------------------------------------------------------
        # UI Construction
        # ------------------------------------------------------------------

        def _build_ui(self) -> None:
            # Title bar area
            self._build_header()
            # Sidebar (navigation)
            self._build_sidebar()
            # Main content area (notebook tabs)
            self._build_content()
            # Status bar
            self._build_statusbar()

        def _build_header(self) -> None:
            header = tk.Frame(self.root, bg=THEME["bg_panel"],
                              height=60, bd=0,
                              highlightbackground=THEME["border"],
                              highlightthickness=1)
            header.pack(fill=tk.X, side=tk.TOP)
            header.pack_propagate(False)

            # Logo / title
            title = tk.Label(header, text="✦ INFINITUM",
                             font=("Arial", 22, "bold"),
                             fg=THEME["accent"], bg=THEME["bg_panel"])
            title.pack(side=tk.LEFT, padx=20, pady=10)

            # Version badge
            ver = tk.Label(header,
                           text=f"v{GAME_VERSION}",
                           font=("Arial", 10),
                           fg=THEME["fg_dim"], bg=THEME["bg_panel"])
            ver.pack(side=tk.LEFT, padx=4)

            # Account label (right)
            self.account_label = tk.Label(header, text="👤  Guest",
                                          font=("Arial", 11),
                                          fg=THEME["fg"], bg=THEME["bg_panel"])
            self.account_label.pack(side=tk.RIGHT, padx=20)

        def _build_sidebar(self) -> None:
            sidebar = tk.Frame(self.root, bg=THEME["bg_panel"], width=180,
                               highlightbackground=THEME["border"],
                               highlightthickness=1)
            sidebar.pack(fill=tk.Y, side=tk.LEFT)
            sidebar.pack_propagate(False)

            nav_items = [
                ("🏠  Home",      self._show_home),
                ("🌍  Play",      self._show_play),
                ("🛒  Workshop",  self._show_workshop),
                ("🌐  Servers",   self._show_servers),
                ("⚙️  Settings",  self._show_settings),
                ("❓  Help",      self._show_help),
            ]
            for label, command in nav_items:
                btn = tk.Button(sidebar, text=label,
                                font=("Arial", 12),
                                bg=THEME["bg_panel"],
                                fg=THEME["fg"],
                                activebackground=THEME["border"],
                                activeforeground=THEME["fg_bright"],
                                anchor="w", bd=0, padx=16, pady=12,
                                cursor="hand2",
                                command=command)
                btn.pack(fill=tk.X)
                btn.bind("<Enter>", lambda e, b=btn: b.config(bg=THEME["border"]))
                btn.bind("<Leave>", lambda e, b=btn: b.config(bg=THEME["bg_panel"]))

            # Spacer
            tk.Frame(sidebar, bg=THEME["bg_panel"]).pack(fill=tk.BOTH, expand=True)

        def _build_content(self) -> None:
            self.content = tk.Frame(self.root, bg=THEME["bg"])
            self.content.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
            # Show home by default
            self._show_home()

        def _build_statusbar(self) -> None:
            self.statusbar = tk.Frame(self.root, bg=THEME["bg_panel"],
                                      height=28,
                                      highlightbackground=THEME["border"],
                                      highlightthickness=1)
            self.statusbar.pack(fill=tk.X, side=tk.BOTTOM)
            self.statusbar.pack_propagate(False)
            self.status_label = tk.Label(
                self.statusbar, text="● Ready",
                font=("Arial", 10), fg=THEME["success"],
                bg=THEME["bg_panel"], anchor="w"
            )
            self.status_label.pack(side=tk.LEFT, padx=10)

            self.players_label = tk.Label(
                self.statusbar, text="Players online: —",
                font=("Arial", 10), fg=THEME["fg_dim"],
                bg=THEME["bg_panel"]
            )
            self.players_label.pack(side=tk.RIGHT, padx=10)

        # ------------------------------------------------------------------
        # Panels
        # ------------------------------------------------------------------

        def _clear_content(self) -> None:
            for w in self.content.winfo_children():
                w.destroy()

        def _show_home(self) -> None:
            self._clear_content()
            frame = tk.Frame(self.content, bg=THEME["bg"], padx=24, pady=16)
            frame.pack(fill=tk.BOTH, expand=True)

            # Hero area
            hero = tk.Frame(frame, bg=THEME["bg_panel"], pady=24,
                            highlightbackground=THEME["border"],
                            highlightthickness=1)
            hero.pack(fill=tk.X, pady=(0, 16))

            tk.Label(hero, text="🌌  INFINITUM",
                     font=("Arial", 36, "bold"),
                     fg=THEME["accent"], bg=THEME["bg_panel"]).pack()
            tk.Label(hero,
                     text="The Boundless Sandbox Universe",
                     font=("Arial", 14),
                     fg=THEME["fg_dim"], bg=THEME["bg_panel"]).pack()

            HoverButton(hero, text="  ▶   PLAY NOW  ",
                        font=("Arial", 16, "bold"),
                        fg=THEME["fg_bright"],
                        relief=tk.FLAT, cursor="hand2",
                        padx=32, pady=12,
                        command=self._launch_game).pack(pady=20)

            # News section
            tk.Label(frame, text="Latest News",
                     font=("Arial", 14, "bold"),
                     fg=THEME["fg_bright"], bg=THEME["bg"]).pack(anchor="w", pady=(8, 4))

            for item in NEWS_ITEMS[:3]:
                card = tk.Frame(frame, bg=THEME["bg_panel"], pady=10, padx=14,
                                highlightbackground=THEME["border"],
                                highlightthickness=1)
                card.pack(fill=tk.X, pady=4)
                tk.Label(card, text=item["title"],
                         font=("Arial", 11, "bold"),
                         fg=THEME["fg_bright"], bg=THEME["bg_panel"]).pack(anchor="w")
                tk.Label(card, text=item["date"],
                         font=("Arial", 9),
                         fg=THEME["fg_dim"], bg=THEME["bg_panel"]).pack(anchor="w")
                tk.Label(card,
                         text=item["body"][:120] + ("..." if len(item["body"]) > 120 else ""),
                         font=("Arial", 10),
                         fg=THEME["fg"], bg=THEME["bg_panel"],
                         wraplength=700, justify="left").pack(anchor="w", pady=(4, 0))

        def _show_play(self) -> None:
            self._clear_content()
            frame = tk.Frame(self.content, bg=THEME["bg"], padx=24, pady=16)
            frame.pack(fill=tk.BOTH, expand=True)

            tk.Label(frame, text="Play",
                     font=("Arial", 20, "bold"),
                     fg=THEME["fg_bright"], bg=THEME["bg"]).pack(anchor="w", pady=(0, 16))

            modes_frame = tk.Frame(frame, bg=THEME["bg"])
            modes_frame.pack(fill=tk.X)

            modes = [
                ("🌍 Singleplayer",   "Explore an infinite world alone.",  self._launch_game),
                ("🌐 Multiplayer",    "Join servers with other players.",  self._show_servers),
                ("🛠️ Creative Mode",  "Build without limits.",              self._launch_creative),
                ("💀 Survival Mode",  "Craft, explore, survive.",           self._launch_survival),
            ]
            for title, desc, cmd in modes:
                card = tk.Frame(modes_frame, bg=THEME["bg_panel"], pady=14, padx=16,
                                highlightbackground=THEME["border"],
                                highlightthickness=1)
                card.pack(fill=tk.X, pady=5)
                tk.Label(card, text=title,
                         font=("Arial", 13, "bold"),
                         fg=THEME["fg_bright"], bg=THEME["bg_panel"]).pack(anchor="w")
                tk.Label(card, text=desc, font=("Arial", 10),
                         fg=THEME["fg_dim"], bg=THEME["bg_panel"]).pack(anchor="w")
                HoverButton(card, text="Launch →",
                            font=("Arial", 10),
                            fg=THEME["fg_bright"],
                            relief=tk.FLAT, cursor="hand2",
                            padx=16, pady=4,
                            command=cmd).pack(anchor="e", pady=(4, 0))

        def _show_servers(self) -> None:
            self._clear_content()
            frame = tk.Frame(self.content, bg=THEME["bg"], padx=24, pady=16)
            frame.pack(fill=tk.BOTH, expand=True)

            tk.Label(frame, text="Server Browser",
                     font=("Arial", 20, "bold"),
                     fg=THEME["fg_bright"], bg=THEME["bg"]).pack(anchor="w", pady=(0, 12))

            # Header row
            cols = tk.Frame(frame, bg=THEME["bg_panel"], padx=12, pady=6,
                            highlightbackground=THEME["border"],
                            highlightthickness=1)
            cols.pack(fill=tk.X)
            for col, w in [("Server Name", 260), ("Players", 100),
                           ("Ping (ms)", 90), ("Biome", 100), ("Action", 80)]:
                tk.Label(cols, text=col, font=("Arial", 10, "bold"),
                         fg=THEME["fg_dim"], bg=THEME["bg_panel"],
                         width=w//8, anchor="w").pack(side=tk.LEFT, padx=6)

            for s in SERVERS:
                row = tk.Frame(frame, bg=THEME["bg_panel"], padx=12, pady=8,
                               highlightbackground=THEME["border"],
                               highlightthickness=1)
                row.pack(fill=tk.X, pady=2)
                fill_pct = s["players"] / s["max"]
                bar_colour = (THEME["success"] if fill_pct < 0.7
                              else THEME["warning"] if fill_pct < 0.9
                              else THEME["danger"])
                tk.Label(row, text=s["name"], font=("Arial", 11),
                         fg=THEME["fg_bright"], bg=THEME["bg_panel"],
                         width=28, anchor="w").pack(side=tk.LEFT)
                tk.Label(row,
                         text=f"{s['players']}/{s['max']}",
                         font=("Arial", 10), fg=bar_colour,
                         bg=THEME["bg_panel"], width=10).pack(side=tk.LEFT)
                ping_colour = (THEME["success"] if s["ping"] < 50
                               else THEME["warning"] if s["ping"] < 100
                               else THEME["danger"])
                tk.Label(row, text=f"{s['ping']} ms",
                         font=("Arial", 10), fg=ping_colour,
                         bg=THEME["bg_panel"], width=8).pack(side=tk.LEFT)
                tk.Label(row, text=s["biome"], font=("Arial", 10),
                         fg=THEME["fg_dim"], bg=THEME["bg_panel"],
                         width=10).pack(side=tk.LEFT)
                HoverButton(row, text="Join",
                            font=("Arial", 10),
                            fg=THEME["fg_bright"],
                            relief=tk.FLAT, cursor="hand2",
                            padx=12, pady=2,
                            command=lambda n=s["name"]: self._join_server(n)
                            ).pack(side=tk.RIGHT)

        def _show_workshop(self) -> None:
            self._clear_content()
            frame = tk.Frame(self.content, bg=THEME["bg"], padx=24, pady=16)
            frame.pack(fill=tk.BOTH, expand=True)

            tk.Label(frame, text="Content Workshop",
                     font=("Arial", 20, "bold"),
                     fg=THEME["fg_bright"], bg=THEME["bg"]).pack(anchor="w", pady=(0, 8))
            tk.Label(frame,
                     text="Browse, install, and publish mods, maps, NPCs, and game mechanics.",
                     font=("Arial", 11), fg=THEME["fg_dim"], bg=THEME["bg"]).pack(anchor="w")

            items = [
                ("🗺️ Epic Desert Megaworld",   "by SandCrafter",    "4.9 ★", "12.4k installs"),
                ("🏰 Medieval Kingdom Pack",   "by BuildMaster99",  "4.7 ★", "8.1k installs"),
                ("🤖 Smarter NPCs v2",          "by AIModder",       "4.8 ★", "6.9k installs"),
                ("⚡ Plasma Physics Addon",     "by PhysicsNerd",    "4.6 ★", "3.2k installs"),
                ("🌊 Ocean Overhaul",           "by WaveRider",      "4.5 ★", "5.5k installs"),
            ]
            for name, author, rating, installs in items:
                card = tk.Frame(frame, bg=THEME["bg_panel"], pady=10, padx=14,
                                highlightbackground=THEME["border"],
                                highlightthickness=1)
                card.pack(fill=tk.X, pady=4)
                left = tk.Frame(card, bg=THEME["bg_panel"])
                left.pack(side=tk.LEFT, fill=tk.X, expand=True)
                tk.Label(left, text=name, font=("Arial", 11, "bold"),
                         fg=THEME["fg_bright"], bg=THEME["bg_panel"]).pack(anchor="w")
                tk.Label(left, text=f"{author}   {rating}   {installs}",
                         font=("Arial", 9), fg=THEME["fg_dim"],
                         bg=THEME["bg_panel"]).pack(anchor="w")
                HoverButton(card, text="Install",
                            font=("Arial", 10), fg=THEME["fg_bright"],
                            relief=tk.FLAT, cursor="hand2",
                            padx=14, pady=4,
                            command=lambda n=name: self._install_mod(n)
                            ).pack(side=tk.RIGHT)

        def _show_settings(self) -> None:
            self._clear_content()
            frame = tk.Frame(self.content, bg=THEME["bg"], padx=24, pady=16)
            frame.pack(fill=tk.BOTH, expand=True)

            tk.Label(frame, text="Settings",
                     font=("Arial", 20, "bold"),
                     fg=THEME["fg_bright"], bg=THEME["bg"]).pack(anchor="w", pady=(0, 12))

            settings = [
                ("Graphics Quality",    ["Ultra", "High", "Medium", "Low"]),
                ("Render Distance",     ["32 chunks", "16 chunks", "8 chunks", "4 chunks"]),
                ("Audio Volume",        ["100%", "75%", "50%", "25%", "Off"]),
                ("NPC Density",         ["High", "Medium", "Low", "None"]),
                ("Physics Quality",     ["Full", "Optimised", "Basic"]),
            ]
            for label, options in settings:
                row = tk.Frame(frame, bg=THEME["bg"], pady=5)
                row.pack(fill=tk.X)
                tk.Label(row, text=label, font=("Arial", 11),
                         fg=THEME["fg"], bg=THEME["bg"],
                         width=22, anchor="w").pack(side=tk.LEFT)
                var = tk.StringVar(value=options[0])
                combo = ttk.Combobox(row, textvariable=var, values=options,
                                     state="readonly", width=18)
                combo.pack(side=tk.LEFT, padx=8)

            HoverButton(frame, text="Save Settings",
                        font=("Arial", 11), fg=THEME["fg_bright"],
                        relief=tk.FLAT, cursor="hand2",
                        padx=20, pady=8,
                        command=lambda: self._set_status("Settings saved ✓", THEME["success"])
                        ).pack(anchor="w", pady=16)

        def _show_help(self) -> None:
            self._clear_content()
            frame = tk.Frame(self.content, bg=THEME["bg"], padx=24, pady=16)
            frame.pack(fill=tk.BOTH, expand=True)

            tk.Label(frame, text="Help & Documentation",
                     font=("Arial", 20, "bold"),
                     fg=THEME["fg_bright"], bg=THEME["bg"]).pack(anchor="w", pady=(0, 12))

            help_text = """INFINITUM Controls:
━━━━━━━━━━━━━━━━━━━━━━━━
Movement:      WASD / Arrow Keys
Jump:          Space
Sprint:        Left Shift (hold)
Fly toggle:    F
Mode toggle:   M  (survival / creative)
Interact:      E
Build menu:    B
Talk to NPC:   T
Map:           TAB
Menu:          ESC

Mouse:
  Left click   — Place selected block
  Right click  — Remove block / interact
  Scroll       — Select block type

Game Modes:
━━━━━━━━━━━━━━━━━━━━━━━━
Creative — Unlimited blocks, fly freely, no damage.
Survival — Gather resources, manage hunger/health.

World Generation:
━━━━━━━━━━━━━━━━━━━━━━━━
Every world is procedurally generated from a seed.
Worlds are infinite — explore as far as you want.
Biomes include: Plains, Forest, Desert, Tundra,
  Mountain, Swamp, Volcano, Crystal, Ocean.

NPC System:
━━━━━━━━━━━━━━━━━━━━━━━━
NPCs have individual neural networks.
They learn from player interactions.
Press T near an NPC to initiate dialogue.
NPCs form factions and develop social structures.
"""
            txt = scrolledtext.ScrolledText(frame, font=("Courier", 10),
                                            bg=THEME["bg_panel"],
                                            fg=THEME["fg"],
                                            insertbackground=THEME["fg"],
                                            relief=tk.FLAT, padx=12, pady=12,
                                            wrap=tk.WORD)
            txt.insert(tk.END, help_text)
            txt.config(state=tk.DISABLED)
            txt.pack(fill=tk.BOTH, expand=True)

        # ------------------------------------------------------------------
        # Actions
        # ------------------------------------------------------------------

        def _launch_game(self) -> None:
            self._set_status("Launching INFINITUM...", THEME["warning"])
            self.root.after(500, self._do_launch)

        def _launch_creative(self) -> None:
            self._set_status("Starting Creative Mode...", THEME["warning"])
            self.root.after(500, lambda: self._do_launch("--mode creative"))

        def _launch_survival(self) -> None:
            self._set_status("Starting Survival Mode...", THEME["warning"])
            self.root.after(500, lambda: self._do_launch("--mode survival"))

        def _do_launch(self, extra_args: str = "") -> None:
            game_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "client", "main.py"
            )
            cmd = [sys.executable, game_path]
            if extra_args:
                cmd += extra_args.split()
            try:
                proc = subprocess.Popen(cmd,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
                self._set_status(f"Game launched (PID {proc.pid}) ✓", THEME["success"])
            except Exception as e:
                self._set_status(f"Launch failed: {e}", THEME["danger"])

        def _join_server(self, server_name: str) -> None:
            messagebox.showinfo("Connecting",
                                f"Connecting to:\n{server_name}\n\n"
                                "Multiplayer requires a live server.\n"
                                "Run:  python server/server.py")

        def _install_mod(self, mod_name: str) -> None:
            self._set_status(f"Installing: {mod_name}...", THEME["warning"])
            self.root.after(1200, lambda: self._set_status(
                f"Installed: {mod_name} ✓", THEME["success"]))

        def _set_status(self, text: str, colour: str = None) -> None:
            self.status_label.config(text=f"● {text}",
                                     fg=colour or THEME["success"])

        # ------------------------------------------------------------------
        # Background tasks
        # ------------------------------------------------------------------

        def _start_background_tasks(self) -> None:
            threading.Thread(target=self._simulate_online_count,
                             daemon=True).start()

        def _simulate_online_count(self) -> None:
            base = 5847
            while True:
                time.sleep(5)
                count = base + random.randint(-50, 50)
                try:
                    self.players_label.config(text=f"Players online: {count:,}")
                except Exception:
                    break


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if not _HAS_TK:
        headless_launcher()
        return

    root = tk.Tk()

    # Apply ttk style
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("TCombobox",
                    fieldbackground=THEME["bg_panel"],
                    background=THEME["bg_panel"],
                    foreground=THEME["fg"],
                    selectbackground=THEME["accent"],
                    selectforeground=THEME["fg_bright"])

    app = LauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
