import logging
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import os
import zipfile
import io
from .utils import requests_retry_session, sanitize_filename

logger = logging.getLogger(__name__)

# Primary and fallback mirrors
YTS_SUBS_MIRRORS = [
    "https://yts-subs.com",
    "https://yifysubtitles.ch",
    "https://yifysubtitles.org"
]

def search_yts_subtitles(imdb_id, language='Arabic'):
    """
    Scrapes YTS/YIFY subtitle sites for accurate subtitles using IMDb ID.
    Returns a list of matching subtitle entries with metadata.
    """
    if not imdb_id:
        return []
        
    session = requests_retry_session()
    
    for mirror in YTS_SUBS_MIRRORS:
        url = f"{mirror}/movie-imdb/{imdb_id}"
        logger.info(f"Searching YTS subtitles on {mirror} for {imdb_id}...")
        
        try:
            response = session.get(url, timeout=10)
            if response.status_code != 200:
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            sub_table = soup.find('table', {'class': 'other-subs'})
            if not sub_table:
                # Some mirrors might have a different class
                sub_table = soup.find('tbody')
                
            if not sub_table:
                continue
                
            results = []
            rows = sub_table.find_all('tr')
            for row in rows:
                lang_td = row.find('td', {'class': 'flag-col'})
                if not lang_td:
                    # Fallback check for language in any td
                    all_tds = row.find_all('td')
                    if not any(language.lower() in td.text.lower() for td in all_tds):
                        continue
                elif language.lower() not in lang_td.text.lower():
                    continue
                
                # Found a language match
                link_tag = row.find('a', href=True)
                if not link_tag:
                    continue
                
                rating = 0
                rating_td = row.find('td', {'class': 'rating-cell'})
                if rating_td:
                    try:
                        rating = int(rating_td.text.strip())
                    except:
                        pass
                
                results.append({
                    'name': link_tag.text.strip().replace('subtitle ', ''),
                    'page_url': mirror + link_tag['href'],
                    'rating': rating,
                    'source': mirror
                })
                
            if results:
                # Sort by rating descending
                results.sort(key=lambda x: x['rating'], reverse=True)
                logger.info(f"Found {len(results)} {language} subtitles on {mirror}")
                return results
                
        except Exception as e:
            logger.debug(f"Mirror {mirror} failed: {e}")
            continue
            
    return []

def download_yts_subtitle(sub_entry, movie_dir: Path, movie_title):
    """
    Downloads and extracts a subtitle from a YTS subtitle page.
    The page usually has a big "Download Subtitle" button that leads to a ZIP.
    """
    if not sub_entry or 'page_url' not in sub_entry:
        return None
        
    session = requests_retry_session()
    try:
        # Step 1: Go to the subtitle details page to find the real ZIP link
        logger.info(f"Fetching download page: {sub_entry['page_url']}")
        response = session.get(sub_entry['page_url'], timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        # The button usually looks like <a class="btn-icon download-subtitle" href="/subtitle/...zip">
        dl_link = soup.find('a', {'class': 'download-subtitle'}, href=True)
        if not dl_link:
            # Fallback: look for any link containing /subtitle/ and .zip
            dl_link = soup.find('a', href=lambda h: h and '/subtitle/' in h and h.endswith('.zip'))
            
        if not dl_link:
            print("\x1b[38;2;153;41;0mError: Could not find download link on YTS subtitle page.\x1b[0m")
            return None
            
        final_url = dl_link['href']
        if not final_url.startswith('http'):
            # Use the mirror domain as base
            from urllib.parse import urljoin
            final_url = urljoin(sub_entry['source'], final_url)
            
        # Step 2: Download the ZIP
        logger.info(f"Downloading ZIP: {final_url}")
        zip_resp = session.get(final_url, timeout=15)
        zip_resp.raise_for_status()
        
        # Step 3: Extract the SRT
        with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as z:
            # Find the first .srt file in the zip
            srt_files = [f for f in z.namelist() if f.lower().endswith('.srt')]
            if not srt_files:
                print("\x1b[38;2;153;41;0mError: No SRT found inside the downloaded ZIP.\x1b[0m")
                return None
            
            # Use the largest SRT file (best guess for full movie)
            best_srt = max(srt_files, key=lambda f: z.getinfo(f).file_size)
            
            # Targeted filename: Movie Title - Arabic.srt
            dest_filename = f"{sanitize_filename(movie_title)} - Arabic.srt"
            dest_path = movie_dir / dest_filename
            
            with open(dest_path, 'wb') as f:
                f.write(z.read(best_srt))
                
            logger.info(f"Success! Subtitle saved to: {dest_path}")
            return dest_path
            
    except Exception as e:
        logger.error(f"Failed to download from YTS-Subs: {e}")
        return None
