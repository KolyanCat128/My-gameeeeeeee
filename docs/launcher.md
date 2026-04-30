# Launcher Documentation

## Overview

The INFINITUM Launcher is the main entry point to the game ecosystem.

## Running

```bash
python launcher/launcher.py
```

Requires Python 3.9+ and the standard library `tkinter` (included with most Python installs).

## Features

| Tab | Description |
|-----|-------------|
| 🏠 Home | News feed and quick Play button |
| 🌍 Play | Choose game mode and launch |
| 🛒 Workshop | Browse and install mods |
| 🌐 Servers | Server browser with ping display |
| ⚙️ Settings | Graphics, audio, and gameplay settings |
| ❓ Help | Controls and documentation |

## Launching Without GUI

If `tkinter` is unavailable (headless server):

```bash
python launcher/launcher.py   # auto-detects, prints CLI summary
```

Or launch the game directly:

```bash
python client/main.py --headless
```

## Auto-Updates

The launcher checks for updates on startup and downloads them in the background.
Updates are applied on the next launch (hot-patches not yet implemented).

## Theme

The launcher uses a dark GitHub-inspired colour scheme.
Theme customisation will be available via `settings.json` in a future update.
