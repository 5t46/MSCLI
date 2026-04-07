import logging
import urllib3
import sys
import time
import threading
from pathlib import Path
from .utils import requests_retry_session, sanitize_filename, download_file_with_retry, prompt_overwrite, load_config, save_config, requests_fast_session

# Suppress SSL warnings for insecure mirrors
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class Spinner:
    def __init__(self, message="Searching..."):
        self.message = message
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._animate)
        self.chars = ["*", " ", " ", " "] # Star Pulse effect

    def _animate(self):
        idx = 0
        while not self.stop_event.is_set():
            sys.stdout.write(f"\r\033[93m[{self.chars[idx % len(self.chars)]}]\033[0m {self.message}")
            sys.stdout.flush()
            time.sleep(0.15)
            idx += 1
            
    def __enter__(self):
        # Hide cursor
        sys.stdout.write("\033[?25l")
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_event.set()
        self.thread.join()
        # Clear line and Show cursor
        sys.stdout.write("\r\033[K\033[?25h")
        sys.stdout.flush()

YTS_DOMAINS = [
    "https://yts.bz",
    "https://yts.mx",
    "https://yts.pm",
    "https://yts.rs",
    "https://yts.lt",
    "https://yts.do",
    "https://yts.ag",
    "https://yts.tuna.me",
    "https://movies-api.accel.li" # Backup Proxy
]

def search_movies(query, target_year=None, min_rating=0.0, genre=None):
    """
    Search for movies using multiple YTS API mirrors with Fail-Fast logic.
    Prioritizes the LAST_WORKING_MIRROR from config.
    """
    # Mirror fail-fast logic
    config = load_config()
    last_working = config.get("LAST_WORKING_MIRROR")
    
    # Reorder domains to try last_working first
    search_order = YTS_DOMAINS.copy()
    if last_working in search_order:
        search_order.remove(last_working)
        search_order.insert(0, last_working)
        
    session = requests_retry_session()
    fast_session = requests_fast_session()
    
    params = {
        "query_term": query,
        "limit": 50,
        "sort_by": "rating"
    }
    if genre:
        params["genre"] = genre
        
    with Spinner(f"Searching YTS for '{query}'...") as sp:
        for domain in search_order:
            url = f"{domain}/api/v2/list_movies.json"
            logger.debug(f"Attempting search on {domain} for query: '{query}'...")
            
            try:
                # Use fast_session for mirror probing (3s timeout, 0 retries)
                response = fast_session.get(url, params=params, timeout=3, verify=False)
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") == "ok" and "movies" in data.get("data", {}):
                    movies = data["data"]["movies"]
                    
                    # Local filtering
                    filtered_movies = []
                    for m in movies:
                        rating = m.get('rating', 0.0)
                        year = m.get('year')
                        if rating < min_rating: continue
                        if target_year and str(year) != str(target_year): continue
                        filtered_movies.append(m)
                    
                    if filtered_movies:
                        if domain != last_working:
                            save_config("LAST_WORKING_MIRROR", domain)
                        
                        return filtered_movies
                    else:
                        logger.debug(f"Mirror {domain} returned 0 results for this specific filter.")
                else:
                    logger.debug(f"Mirror {domain} returned no movies for '{query}'. Trying next...")
                    
            except Exception as e:
                logger.debug(f"Mirror {domain} failed or timed out: {e}")
                continue
            
    print("\x1b[38;2;153;41;0mError: All YTS mirrors failed for this query.\x1b[0m")
    return []

def download_torrent(movie_title, movie_year, quality, torrent_url, target_dir: Path, filename=None):
    """
    Downloads the selected torrent file to the target movie directory.
    Checks if file exists and prompts.
    """
    clean_title = sanitize_filename(movie_title)
    if not filename:
        filename = f"{clean_title} - {movie_year} - {quality}.torrent"
    dest_path = target_dir / filename
    
    # If it's a temp file, don't prompt for overwrite, just do it.
    is_temp = "temp_" in filename
    if not is_temp and not prompt_overwrite(dest_path):
        logger.info(f"Skipping torrent download, '{filename}' already exists.")
        return dest_path
    
    logger.info(f"Initiating torrent download for: {filename}")
    success = download_file_with_retry(torrent_url, dest_path)
    
    return dest_path if success else None


