# Movies Downloader & Subtitles CLI

A terminal-based assistant for discovering movies, fetching subtitles, and organizing your local library. Built for speed, automation, and Plex/Kodi compatibility.

![App Screenshot](assets/SLogo.jpeg)


![Version](https://img.shields.io/badge/version-1.1-blue) ![Platform](https://img.shields.io/badge/platform-Windows-lightgrey) ![License](https://img.shields.io/badge/license-MIT-green)

---

## Features

- **Cross-Tracker Search** — Find content across **YTS and EZTV** for maximum availability.
- **Advanced Search** — Find content by title, genre, actor, or director via TMDb integration.
- **Automatic Subtitles** — Fetches and matches Arabic, English, or Russian subtitles to your exact release using the OpenSubtitles API.
- **Torrent Client Integration** — Opens magnet links directly in qBittorrent or uTorrent.
- **Library Cleanup** — Flattens nested folders, renames files to a clean Plex/Kodi format, and removes junk files (`.txt`, `.url`, `.nfo`, etc.).
- **Dark Premium Theme** — Eye-friendly, 60%-brightness dark UI rendered entirely in the terminal.

---

## Requirements

- Python 3.9+
- qBittorrent or uTorrent
- A free [OpenSubtitles](https://www.opensubtitles.com/en/consumers) account (for subtitle search)
- A free [TMDb](https://www.themoviedb.org/signup) account (for actor/director search)

---

## Installation

**1. Clone the repository**

```bash
git clone https://github.com/5t46/MSCLI.git
cd MSCLI
```

**2. Run the installer**

Double-click `install.bat`. This creates a virtual environment and installs all dependencies from `requirements.txt` automatically.

**3. Launch the app**

```bash
python main.py
```

---

## First-Run Setup

On the first launch, a **Setup Wizard** will guide you through:

1. **API Keys** — You will be prompted to paste your OpenSubtitles and TMDb API keys. Input is masked for security.
2. **Library Folder** — A folder picker dialog opens so you can choose where downloaded movies are stored.

### Getting your API keys

**OpenSubtitles (subtitles)**
1. Go to [opensubtitles.com/en/consumers](https://www.opensubtitles.com/en/consumers) and sign up.
2. Create a new consumer app (any name works, e.g. `MovieScript`).
3. Copy the generated **API Key**.

**TMDb (actor/director search)**
1. Go to [themoviedb.org/signup](https://www.themoviedb.org/signup) and create an account.
2. Navigate to **Settings > API** and request a Developer key.
3. Copy your **API Read Access Token**.

---

## Usage

```
1. Search for a Movie      → Enter a title, genre, actor, or director name
2. Select Quality          → Choose 720p, 1080p, or 4K
3. Subtitle Download       → Best-matching subtitle is fetched automatically
4. Open in Client          → Select qBittorrent or uTorrent to begin download
5. CleanUP                 → After download completes, press ENTER to organize files
```

---

## Settings

| Option | Description |
|---|---|
| Change YTS Mirror | Switch to a working YTS URL (e.g. `yts.mx`, `yts.bz`) |
| API Keys | Update stored credentials at any time |
| Library Folder | Change the default save location |

To change the YTS mirror: **Settings (5) > Change YTS Mirror (4)**.

---

## Project Structure

### 📂 Root Directory
*   **`run_app.bat`** — Primary launcher. Validates environment, activates venv, and starts the app.
*   **`main.py`** — Application entry point. Manages UI, menus, and high-level logic.
*   **`install.bat`** — Automated installer. Handles Git/Python detection, venv creation, and repository cloning.
*   **`requirements.txt`** — List of required Python libraries (InquirerPy, requests, etc.).
*   **`assets/`** — Project media, including `Main.png` for documentation.
*   **`config/`** — Stores `config.json` containing saved user API keys and preferences.
*   **`logs/`** — Stores `app.log` for runtime tracking and error debugging.

### 📦 Modules (`modules/`)
*   **`opensubtitles_api.py`** — OpenSubtitles.com integration for fetching `.srt` files.
*   **`tmdb_api.py`** — TMDb integration for movie metadata, plot summaries, and cast info.
*   **`yts_api.py`** — YTS search engine integration for movie lists and magnet links.
*   **`yts_subs_api.py`** — Alternative subtitle source (YTS-Subs) for high-accuracy matching.
*   **`torrent_formatter.py`** — Intelligent cleanup engine for Plex/Kodi-compatible file organization.
*   **`utils.py`** — Shared helper functions, UI styling (gradients), and system utilities.
*   **`__init__.py`** — Python package initializer for the modules directory.

---

## Troubleshooting

**YTS mirror is unreachable**
Go to Settings > Change YTS Mirror and enter a working URL.

**Subtitles not found**
Ensure your OpenSubtitles API key is valid and your daily request quota has not been exceeded (free tier allows 5 downloads/day).

**Torrent client not opening**
Confirm the client is installed and its path is registered in your system's `PATH` environment variable.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

*Author: Star — Version 1.1.*
