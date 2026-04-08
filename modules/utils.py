import os
import re
import json
import time
import logging
import shutil
from pathlib import Path
from requests.exceptions import RequestException
import questionary
from rich.panel import Panel
from rich.align import Align
from rich.rule import Rule
from rich.table import Table
from rich.style import Style
from modules.console import (
    console, C_PRIMARY, C_SECONDARY, C_SUCCESS, C_WARNING, C_ERROR, 
    C_TEXT_PRI, C_TEXT_SEC, C_BORDER
)

CONFIG_FILE = './config/config.json'

def show_header(subtitle="Movie Downloader  v5.19.5"):
    """Professional MCLI Header."""
    console.clear()
    header_content = f"[#00D7FF bold]M C L I[/]\n[#8A8A8A]{subtitle}[/]"
    console.print(Align.center(Panel(
        header_content,
        border_style="#3A3A3A",
        padding=(0, 2),
        width=44
    )))
    console.print(Rule(style="#3A3A3A"))

def get_questionary_style():
    """Custom Questionary Style."""
    return questionary.Style([
        ("qmark",        "fg:#AF87FF bold"),
        ("question",     "fg:#FFFFFF bold"),
        ("answer",       "fg:#00D7FF bold"),
        ("pointer",      "fg:#00D7FF bold"),
        ("highlighted",  "fg:#00D7FF bold"),
        ("selected",     "fg:#5FD75F"),
        ("separator",    "fg:#3A3A3A"),
        ("instruction",  "fg:#8A8A8A"),
    ])

def setup_logging():
    log_file = Path('./logs/app.log')
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # Set the stream handler to WARNING so the CLI isn't cluttered with DEBUG/INFO, 
    # but the log file contains everything.
    for handler in logging.root.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
            handler.setLevel(logging.WARNING)

def sanitize_filename(filename):
    """Removes invalid characters for Windows filenames and strips tags."""
    # Remove tags like YIFY, BRRip, x264, etc. case-insensitively
    tags = [r'\byify\b', r'\bbrrip\b', r'\bx264\b', r'\b1080p\b', r'\b720p\b', r'\b2160p\b', r'\bweb-dl\b', r'\bbluray\b']
    for tag in tags:
        filename = re.sub(tag, '', filename, flags=re.IGNORECASE)
    
    # Remove invalid characters and dots
    filename = re.sub(r'[<>:"/\\|?\*\.]', ' ', filename)
    
    # Collapse multiple spaces
    filename = re.sub(r'\s+', ' ', filename).strip()
    return filename

def get_gradient_text(text, start_rgb, end_rgb):
    """Generates an ANSI RGB gradient for the given text."""
    # Deprecated in favor of Rich, but kept for logic compatibility
    return f"[#00D7FF]{text}[/]"

def draw_detail_card(title, info_dict, color_code="#00D7FF"):
    """Draws a professional Rich detail card."""
    table = Table(show_header=False, box=None, padding=(0, 1))
    for key, value in info_dict.items():
        if value:
            table.add_row(f"[#8A8A8A]{key}:[/]", f"[#FFFFFF]{value}[/]")
    
    console.print(Panel(
        table,
        title=f"[#AF87FF]{title}[/]",
        border_style="#3A3A3A",
        expand=False
    ))

def _bdecode(data):
    """Robust minimal bencode decoder (recursive)."""
    def decode_item(idx):
        if idx >= len(data): return None, idx
        char = data[idx:idx+1]
        if char == b'i': # Integer: i[digits]e
            idx += 1
            end = data.find(b'e', idx)
            return int(data[idx:end]), end + 1
        elif char == b'l': # List: l[items]e
            idx += 1
            res = []
            while data[idx:idx+1] != b'e' and idx < len(data):
                item, idx = decode_item(idx)
                res.append(item)
            return res, idx + 1
        elif char == b'd': # Dict: d[key][val]e
            idx += 1
            res = {}
            while data[idx:idx+1] != b'e' and idx < len(data):
                key_raw, idx = decode_item(idx)
                if not key_raw: break
                val, idx = decode_item(idx)
                res[key_raw.decode('utf-8', errors='ignore')] = val
            return res, idx + 1
        elif char.isdigit(): # String: [len]:[data]
            end = data.find(b':', idx)
            length = int(data[idx:end])
            s_start = end + 1
            return data[s_start:s_start+length], s_start+length
        return None, idx
    try:
        res, _ = decode_item(0)
        return res
    except:
        return None

def extract_filename_from_torrent(torrent_path):
    """
    Robustly extracts the actual movie filename from a .torrent file using a bencode decoder.
    Finds the largest file entry with a video extension (.mp4, .mkv, .avi).
    """
    try:
        with open(torrent_path, 'rb') as f:
            data = _bdecode(f.read())
            if not data: return None
            
            info = data.get('info', {})
            video_exts = ('.mp4', '.mkv', '.avi', '.mov', '.wmv')
            
            # 1. Multi-file torrent check
            if 'files' in info:
                best_file = None
                max_size = 0
                for f in info['files']:
                    # path is a list of segments
                    path_segments = [p.decode('utf-8', errors='ignore') if isinstance(p, bytes) else p for p in f.get('path', [])]
                    if not path_segments: continue
                    
                    filename = path_segments[-1]
                    if any(filename.lower().endswith(ext) for ext in video_exts):
                        size = f.get('length', 0)
                        if size > max_size:
                            max_size = size
                            best_file = filename
                if best_file: return best_file
            
            # 2. Single-file torrent check
            name = info.get('name')
            if isinstance(name, bytes):
                name = name.decode('utf-8', errors='ignore')
            
            if name and any(name.lower().endswith(ext) for ext in video_exts):
                return name
    except Exception as e:
        logging.getLogger(__name__).debug(f"Bencode extraction failed: {e}")
    return None

def load_config():
    """Load config.json from project root."""
    config_path = Path('./config/config.json')
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.getLogger(__name__).error(f"Error reading config: {e}")
    return {}

def save_config(key, value):
    """Save a key-value pair to config.json."""
    config = load_config()
    config[key] = value
    try:
        with open('./config/config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        logging.getLogger(__name__).error(f"Error writing config: {e}")

def save_config_full(config):
    """Save the entire config dictionary to config.json."""
    try:
        with open('./config/config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        logging.getLogger(__name__).error(f"Error writing full config: {e}")

def bencode_decode(data):
    """Simple Bencode decoder for parsing .torrent files."""
    def decode_item(index):
        char = data[index:index+1]
        if char == b'i': # Integer
            index += 1
            end = data.find(b'e', index)
            return int(data[index:end]), end + 1
        elif char == b'l': # List
            index += 1
            res = []
            while data[index:index+1] != b'e':
                val, index = decode_item(index)
                res.append(val)
            return res, index + 1
        elif char == b'd': # Dictionary
            index += 1
            res = {}
            while data[index:index+1] != b'e':
                key, index = decode_item(index)
                val, index = decode_item(index)
                res[key.decode('utf-8', 'ignore')] = val
            return res, index + 1
        elif char.isdigit(): # String
            colon = data.find(b':', index)
            length = int(data[index:colon])
            start = colon + 1
            end = start + length
            return data[start:end], end
        raise ValueError("Invalid bencode data")
    
    try:
        return decode_item(0)[0]
    except Exception:
        return None

def extract_original_filename_from_torrent(torrent_path):
    """
    Reads a .torrent file and returns the name of the main video file inside.
    This is the 'True Name' used for perfect subtitle sync.
    """
    try:
        with open(torrent_path, 'rb') as f:
            data = f.read()
        
        decoded = bencode_decode(data)
        if not decoded or 'info' not in decoded:
            return None
            
        info = decoded['info']
        
        # Multi-file torrent
        if 'files' in info:
            video_files = []
            video_exts = {b'.mp4', b'.mkv', b'.avi', b'.mov'}
            for f_info in info['files']:
                path_parts = f_info.get('path', [])
                if path_parts:
                    last_part = path_parts[-1]
                    ext = os.path.splitext(last_part)[1].lower()
                    if ext in video_exts:
                        video_files.append({
                            'name': last_part.decode('utf-8', 'ignore'),
                            'length': f_info.get('length', 0)
                        })
            if video_files:
                # Return the largest video file name
                video_files.sort(key=lambda x: x['length'], reverse=True)
                return video_files[0]['name']
        
        # Single-file torrent
        elif 'name' in info:
            return info['name'].decode('utf-8', 'ignore')
            
        return None
    except Exception as e:
        logging.getLogger(__name__).error(f"Error extracting filename from {torrent_path}: {e}")
        return None

def load_movie_metadata(movie_dir):
    """Loads movie details from .yts_meta.json if it exists."""
    meta_path = Path(movie_dir) / ".yts_meta.json"
    if meta_path.exists():
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.getLogger(__name__).error(f"Error loading metadata from {meta_path}: {e}")
    return None

def save_movie_metadata(movie_dir, metadata):
    """
    Saves movie details to a hidden .yts_meta.json file.
    Includes full_release_title for perfect sync later.
    """
    movie_dir_path = Path(movie_dir)
    meta_path = movie_dir_path / ".yts_meta.json"
    
    try:
        # On Windows, if the file is already hidden, 'open(..., "w")' fails with Permission Denied.
        # We must remove the hidden attribute first.
        if os.name == 'nt' and meta_path.exists():
            import ctypes
            # 0x80 is FILE_ATTRIBUTE_NORMAL
            ctypes.windll.kernel32.SetFileAttributesW(str(meta_path), 0x80)

        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=4)
            
        # Re-hide the file on Windows
        if os.name == 'nt':
            import ctypes
            # 0x02 is FILE_ATTRIBUTE_HIDDEN
            ctypes.windll.kernel32.SetFileAttributesW(str(meta_path), 0x02)
    except Exception as e:
        logging.getLogger(__name__).error(f"Error saving metadata to {meta_path}: {e}")

def prompt_overwrite(filepath):
    """Prompt using Questionary."""
    if Path(filepath).exists():
        return questionary.confirm(
            message=f"File {Path(filepath).name} already exists. Overwrite?",
            style=get_questionary_style()
        ).execute()
    return True

def setup_directories():
    """Ensure essential configuration folder exists."""
    Path('./config').mkdir(parents=True, exist_ok=True)

def requests_retry_session(
    retries=5,
    backoff_factor=1.0,
    status_forcelist=(500, 502, 504),
    session=None,
):
    """
    Setup a requests session with retry logic.
    Using standard requests, we can implement our own wrapper for exponential backoff 
    if we want to use simple requests calls, or use urllib3 Retry. We'll use urllib3.
    """
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def requests_fast_session(session=None):
    """
    Setup a requests session with ZERO retries for fast probing.
    """
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = session or requests.Session()
    # Zero retries
    retry = Retry(
        total=0,
        connect=0,
        read=0,
        status=0,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def download_file_with_retry(url, dest_path, headers=None, max_retries=5):
    """Simple wrapper to download a file with basic exponential backoff retry."""
    import requests
    logger = logging.getLogger(__name__)
    
    # Professional User-Agent to avoid blocks
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    if headers:
        default_headers.update(headers)
        
    attempt = 0
    backoff = 1
    
    while attempt < max_retries:
        try:
            logger.info(f"Downloading file from {url} to {dest_path} (Attempt {attempt+1}/{max_retries})")
            # Increased timeout to 60s for slow CDNs
            response = requests.get(url, headers=default_headers, stream=True, timeout=60)
            response.raise_for_status()
            
            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            if dest_path.exists() and dest_path.stat().st_size > 0:
                logger.info(f"Successfully downloaded file to {dest_path}")
                return True
            else:
                logger.error(f"Download completed but file is empty or missing: {dest_path}")
                return False
        except RequestException as e:
            # V5.18.1: Clean Error Handling
            # Log the full technical error to the log file (FileHandler)
            logger.debug(f"Verbose Download Error ({url}): {e}")
            
            # Print a clean, concise error to the console
            err_msg = "Connection timed out" if "timeout" in str(e).lower() else "Network error"
            if "status_code" in str(e).lower() or "403" in str(e): err_msg = "Access Denied (403)"
            if "404" in str(e): err_msg = "File not found (404)"
            
            print(f"\x1b[38;2;153;41;0mError: {err_msg} (Attempt {attempt+1}/{max_retries})\x1b[0m")
            
            attempt += 1
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2 # Exponential backoff
            else:
                return False

def find_torrent_client(client_name):
    """
    Tries to find the executable path for the given torrent client.
    Returns the Path object or None if not found.
    """
    import os
    client_name = client_name.lower()
    user_appdata = Path(os.environ.get('APPDATA', ''))
    program_files = Path(os.environ.get('ProgramFiles', 'C:\\Program Files'))
    program_files_x86 = Path(os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'))

    paths = []
    if "qbittorrent" in client_name:
        paths = [
            program_files / "qBittorrent" / "qbittorrent.exe",
            program_files_x86 / "qBittorrent" / "qbittorrent.exe",
        ]
    elif "utorrent" in client_name:
        paths = [
            user_appdata / "uTorrent" / "uTorrent.exe",
            program_files_x86 / "uTorrent" / "uTorrent.exe",
        ]
    elif "bittorrent" in client_name:
        paths = [
            user_appdata / "BitTorrent" / "BitTorrent.exe",
            program_files / "BitTorrent" / "BitTorrent.exe",
            program_files_x86 / "BitTorrent" / "BitTorrent.exe"
        ]
    else:
        return None

    for p in paths:
        if p.exists():
            return p
    return None

def scan_library_for_missing_subtitles(movies_path):
    """
    Recursively scans the movies_path for folders containing video files but NO subtitles.
    Returns a list of dicts: {'title': str, 'year': str, 'folder': Path}
    """
    missing_list = []

def open_torrent_in_client(client_name, torrent_path, save_dir):
    """
    Opens the chosen torrent client with the .torrent file and sets the save directory.
    """
    import subprocess
    import logging
    client_exe = find_torrent_client(client_name)
    if not client_exe:
        logging.getLogger(__name__).error(f"Could not find executable for {client_name}")
        return False

    try:
        if "qbittorrent" in client_name.lower():
            # qBittorrent CLI: qbittorrent.exe [torrent_file] --save-path=[path]
            subprocess.Popen([str(client_exe), str(torrent_path), f"--save-path={save_dir}"])
        elif "utorrent" in client_name.lower():
            # uTorrent CLI: uTorrent.exe /DIRECTORY [path] [torrent_file]
            subprocess.Popen([str(client_exe), "/DIRECTORY", str(save_dir), str(torrent_path)])
        
        return True
    except Exception as e:
        logging.getLogger(__name__).error(f"Error launching {client_name}: {e}")
        return False

def finalize_movie_folder(movie_dir, movie_title, movie_year, quality):
    """
    Finds the largest video file in the folder (including subfolders),
    moves it to the root, renames it, and cleans up all other files and subfolders.
    """
    import shutil
    logger = logging.getLogger(__name__)
    movie_dir = Path(movie_dir)
    
    if not movie_dir.exists():
        logger.error(f"Movie directory does not exist: {movie_dir}")
        return False
        
    video_extensions = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv')
    largest_file = None
    max_size = 0
    
    # 1. Find the largest video file
    for root, dirs, files in os.walk(movie_dir):
        for f in files:
            p = Path(root) / f
            if p.suffix.lower() in video_extensions:
                size = p.stat().st_size
                if size > max_size:
                    max_size = size
                    largest_file = p
                    
    if not largest_file:
        logger.warning(f"No video files found in {movie_dir}")
        return False
        
    # 2. Determine target movie filename
    clean_title = sanitize_filename(movie_title)
    extension = largest_file.suffix
    new_movie_name = f"{clean_title} - {movie_year} - {quality}{extension}"
    target_movie_path = movie_dir / new_movie_name
    
    # Preserve subtitles
    srt_files = list(movie_dir.rglob("*.srt"))
    subtitle_targets = []
    for srt in srt_files:
        # Move subtitles to root if they aren't there already
        if srt.parent != movie_dir:
            dest = movie_dir / srt.name
            try:
                if srt.exists() and srt != dest:
                    shutil.move(str(srt), str(dest))
                subtitle_targets.append(dest)
            except Exception as e:
                logger.error(f"Failed to move subtitle {srt}: {e}")
        else:
            subtitle_targets.append(srt)

    # 3. Move the movie file to root (if not already there)
    try:
        if largest_file.resolve() != target_movie_path.resolve():
            # If target already exists, remove it first
            if target_movie_path.exists():
                target_movie_path.unlink()
            shutil.move(str(largest_file), str(target_movie_path))
            logger.info(f"Moved and renamed movie to: {target_movie_path}")
    except Exception as e:
        logger.error(f"Failed to move movie file: {e}")
        return False

    # 4. Final Cleanup: Delete all subfolders and non-essential files
    # We keep the new movie file, subtitle targets, and any .torrent files
    torrent_files = list(movie_dir.glob("*.torrent"))
    essential_files = {target_movie_path.resolve()}
    for s in subtitle_targets:
        essential_files.add(s.resolve())
    for t in torrent_files:
        essential_files.add(t.resolve())
        
    for item in movie_dir.iterdir():
        if item.resolve() in essential_files:
            continue
            
        try:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        except Exception as e:
            logger.warning(f"Could not delete {item}: {e}")
            
    return True

def save_config_full(config):
    """Saves the entire configuration dictionary to config.json."""
    try:
        with open("config.json", "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        logging.getLogger(__name__).error(f"Error saving config: {e}")

def get_machine_id():
    """Retrieves a unique Hardware UUID from the Windows BIOS."""
    import subprocess
    try:
        cmd = 'wmic csproduct get uuid'
        uuid = subprocess.check_output(cmd, shell=True).decode().split()[1]
        return uuid
    except Exception:
        import uuid
        return str(uuid.getnode())

def get_computer_name():
    """Returns the Windows Computer Name."""
    return os.environ.get('COMPUTERNAME', 'Unknown-PC')

def perform_new_device_wipe():
    """Wipes the current config.json and deletes the logs folder for a fresh start."""
    new_id = get_machine_id()
    new_name = get_computer_name()
    new_config = {
        "MACHINE_ID": new_id,
        "COMPUTER_NAME": new_name,
        "MOVIES_PATH": None,
        "OPENSUBTITLES_API_KEY": None,
        "TMDB_API_KEY": None,
        "LAST_WORKING_MIRROR": "https://yts.mx",
        "PREFER_QUALITY": "1080p",
        "FIRST_RUN": True
    }
    
    try:
        with open("./config/config.json", "w", encoding='utf-8') as f:
            json.dump(new_config, f, indent=4)
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to reset config: {e}")

    log_dir = Path('./logs')
    if log_dir.exists():
        try:
            shutil.rmtree(log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to delete logs: {e}")
            
    return True





