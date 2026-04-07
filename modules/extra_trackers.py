import requests
from bs4 import BeautifulSoup
import logging
import re
from urllib.parse import quote

logger = logging.getLogger(__name__)

# Constants
ONE_THREE_THREE_SEVEN_X_BASE = "https://1337x.to"
EZTV_BASE = "https://eztv.re"

def search_eztv(imdb_id):
    """
    Uses EZTV API to find torrents for a specific IMDB ID.
    Returns a list of torrent objects.
    """
    if not imdb_id: return []
    
    # Remove 'tt' prefix if present for the API
    clean_id = imdb_id.replace('tt', '')
    api_url = f"{EZTV_BASE}/api/get-torrents?limit=50&imdb_id={clean_id}"
    
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        torrents = data.get('torrents', [])
        results = []
        
        for t in torrents:
            results.append({
                "name": t.get('filename'),
                "url": t.get('magnet_url'),
                "seeds": str(t.get('seeds')),
                "leeches": str(t.get('peers')),
                "size": str(t.get('size_bytes')), # We'll need formatting
                "source": "EZTV"
            })
        return results
    except Exception as e:
        logger.error(f"EZTV search error: {e}")
        return []

def search_all_extra(title, year=None, imdb_id=None):
    """Combines results from extra trackers."""
    query = f"{title} {year}" if year else title
    
    # Run searches
    extra_results = []
    
    # 1. Search EZTV (Great for Series/Shows)
    if imdb_id:
        logger.info(f"Searching EZTV for IMDB: {imdb_id}...")
        extra_results.extend(search_eztv(imdb_id))
        
    return extra_results
