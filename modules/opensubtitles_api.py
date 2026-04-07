import os
import zipfile
import logging
from pathlib import Path
from rapidfuzz import fuzz
from .utils import requests_retry_session, sanitize_filename, download_file_with_retry, prompt_overwrite

logger = logging.getLogger(__name__)

OPENSUBTITLES_API_URL = "https://api.opensubtitles.com/api/v1/"
C_WARN = "\x1b[38;2;255;100;100m" # Orange-Red for warnings

def search_subtitles(api_key, movie_title, movie_year, quality=None, language="ar", file_size=None, interactive=False, full_release_title=None):
    """
    Search for subtitles using the OpenSubtitles API.
    Returns the best matching subtitle data, or a list of top matches if interactive=True.
    """
    session = requests_retry_session()
    headers = {
        "Api-Key": api_key,
        "User-Agent": "MoviesDownloader_Star_V3_Official",
        "Content-Type": "application/json"
    }
    
    # If full_release_title is provided (from our deep torrent inspection), we use it as the primary query.
    params = {
        "query": full_release_title if full_release_title else movie_title,
        "year": movie_year,
        "languages": language
    }
    
    search_url = f"{OPENSUBTITLES_API_URL}subtitles"
    logger.info(f"Searching OpenSubtitles for: {movie_title} ({movie_year})")
    
    try:
        response = session.get(search_url, headers=headers, params=params, timeout=10)
        if response.status_code in (401, 403):
            logger.error("OpenSubtitles API key is invalid or unauthorized.")
            return None
            
        response.raise_for_status()
        data = response.json()
        results = data.get("data", [])
        
        # Fallback: If no results with full release name, try a broader YTS search
        if not results and full_release_title:
            logger.info("No specific matches found. Trying broad YTS/YIFY fallback search...")
            fallback_params = {
                "query": f"{movie_title} {movie_year} YTS YIFY",
                "languages": language
            }
            fb_resp = session.get(search_url, headers=headers, params=fallback_params, timeout=10)
            if fb_resp.status_code == 200:
                results = fb_resp.json().get("data", [])

        if not results:
            return None
            
        # Score all results
        scored_results = _score_all_subtitles(results, movie_title, movie_year, quality)
        
        if not scored_results:
            return None

        # Sort by score descending
        scored_results.sort(key=lambda x: x['score'], reverse=True)

        if interactive:
            return scored_results[:10]  # Return top 10 potential candidates
            
        return scored_results[0]  # Return best match
        
    except Exception as e:
        # V5.18.2: Concise Error reporting
        logger.debug(f"OS Search Detail: {e}")
        print("\x1b[38;2;153;41;0mError: OpenSubtitles search failed (Check API Key/Connection).\x1b[0m")
        return None

def _score_all_subtitles(results, target_title, target_year, target_quality):
    """
    Score all found subtitles.
    Returns a list of dicts: {'file_id': str, 'file_name': str, 'release_name': str, 'score': float}
    """
    all_scored = []
    
    target_title_lower = target_title.lower()
    target_quality_lower = target_quality.lower() if target_quality else ""
        
    for item in results:
        attrs = item.get("attributes", {})
        sub_id = item.get("id")
        files = attrs.get("files", [{}])
        file_id = files[0].get("file_id") if files else None
        
        if not sub_id or not file_id:
            continue
            
        # Parse data
        release_title = attrs.get("release", "")
        # Use filename as fallback for release title
        display_name = release_title if release_title else files[0].get("file_name", "Unknown Release")
        
        movie_name = attrs.get("feature_details", {}).get("movie_name", "").lower()
        year = attrs.get("feature_details", {}).get("year")
        download_count = attrs.get("download_count", 0)
        file_name = files[0].get("file_name", "").lower()
        
        score = 0
        
        # 1. Year Match (Required or highly preferred)
        if str(year) == str(target_year):
            score += 100
        else:
            score -= 50
            
        # 2. Title Match
        if target_title_lower == movie_name:
            score += 50
        elif target_title_lower in movie_name or target_title_lower in display_name.lower():
            score += 25
            
        # 3. Quality / Release Match
        if target_quality_lower:
            if target_quality_lower in display_name.lower():
                score += 30
            if target_quality_lower in file_name:
                score += 20
        
        # Boost YTS/YIFY if it's in the release name (Commonly used by the user)
        if "yts" in display_name.lower() or "yify" in display_name.lower():
            score += 40
            
        # 4. Filename Similarity
        target_string = f"{target_title_lower} {target_year}"
        if target_quality_lower:
            target_string += f" {target_quality_lower}"
            
        sim_score = fuzz.partial_ratio(target_string, display_name.lower())
        score += (sim_score * 0.2)
        
        # 5. Download count bonus
        import math
        dl_bonus = min(30, math.log10(max(1, download_count)) * 10)
        score += dl_bonus
        
        all_scored.append({
            "file_id": file_id,
            "file_name": file_name,
            "release_name": display_name,
            "score": score
        })
            
    return all_scored

def download_subtitle(api_key, file_id, movie_title, movie_year, movie_dir: Path, language_name="Arabic"):
    """
    Requests the download link and downloads the subtitle file to the movie directory.
    Extracts if it's a zip file.
    """
    session = requests_retry_session()
    headers = {
        "Api-Key": api_key,
        "User-Agent": "MoviesDownloader_Star_V3_Official",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    payload = {
        "file_id": int(file_id)
    }
    
    download_url = f"{OPENSUBTITLES_API_URL}download"
    logger.info(f"Requesting {language_name} subtitle download link...")
    
    try:
        response = session.post(download_url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        link = data.get("link")
        if not link:
            logger.error("No download link returned by OpenSubtitles API")
            return None
            
        logger.info(f"Got download link: {link}")
        
        clean_title = sanitize_filename(movie_title)
        
        # Subtitle should not have year: {Movie Title} - {Language}.srt
        final_filename = f"{clean_title} - {language_name}.srt"
        final_dest = movie_dir / final_filename
        
        if not prompt_overwrite(final_dest):
            logger.info(f"Skipping subtitle download, '{final_filename}' already exists.")
            return final_dest

        temp_dest = movie_dir / "temp_subtitle.raw"
        success = download_file_with_retry(link, temp_dest)
        
        if not success:
            return None
            
        # Check if it's a ZIP file
        if zipfile.is_zipfile(temp_dest):
            logger.info("Downloaded subtitle is a ZIP archive. Extracting...")
            with zipfile.ZipFile(temp_dest, 'r') as zip_ref:
                # Find the first .srt file in the archive
                srt_files = [f for f in zip_ref.namelist() if f.endswith('.srt')]
                if srt_files:
                    # Extract specifically the srt file, rename and move it
                    with zip_ref.open(srt_files[0]) as source, open(final_dest, "wb") as target:
                        target.write(source.read())
                    logger.info(f"Successfully extracted and saved: {final_dest}")
                else:
                    print("\x1b[38;2;153;41;0mError: ZIP archive missing .srt files.\x1b[0m")
        else:
            # Assume it's an SRT file directly
            if final_dest.exists():
                final_dest.unlink()
            temp_dest.rename(final_dest)
            logger.info(f"Successfully saved subtitle: {final_dest}")
            
        # Cleanup
        if temp_dest.exists():
            temp_dest.unlink()
            
        return final_dest

    except Exception as e:
        print(f"{C_WARN}Error: {str(e)}\x1b[0m")
        logger.error(f"Error downloading or processing subtitle: {e}")
        return None
