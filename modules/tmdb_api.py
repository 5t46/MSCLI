import logging
import requests
from .utils import requests_retry_session

logger = logging.getLogger(__name__)

TMDB_BASE_URL = "https://api.themoviedb.org/3"

def search_person(api_key, name):
    """
    Search for a person on TMDb to get their ID.
    """
    if not api_key or api_key == "STARI_TMDB_PLACEHOLDER":
        return None
        
    session = requests_retry_session()
    params = {
        "api_key": api_key,
        "query": name
    }
    
    try:
        url = f"{TMDB_BASE_URL}/search/person"
        response = session.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("results", [])
        if results:
            # Pick the most popular result
            return results[0]
    except Exception as e:
        logger.error(f"TMDb Person Search Error: {e}")
        
    return None

def get_person_movies(api_key, person_id, job=None):
    """
    Get movie credits for a person. 
    If 'job' is None, returns 'cast' (Actor).
    If 'job' is 'Director', returns 'crew' filtered by job.
    """
    if not api_key or not person_id:
        return []
        
    session = requests_retry_session()
    params = {
        "api_key": api_key
    }
    
    try:
        url = f"{TMDB_BASE_URL}/person/{person_id}/movie_credits"
        response = session.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = []
        source_list = data.get("crew", []) if job else data.get("cast", [])
        
        for m in source_list:
            if not m.get("title"): continue
            if job and m.get("job") != job: continue
            
            # Extract Year from YYYY-MM-DD
            release_date = m.get("release_date", "")
            year = release_date.split("-")[0] if release_date else "N/A"
            
            results.append({
                "title": m.get("title"),
                "year": year,
                "rating": m.get("vote_average", 0.0),
                "popularity": m.get("popularity", 0.0),
                "id": m.get("id"),
                "imdb_code": m.get("imdb_id"), # Might not be in this short list
                "torrents": [] # Placeholder for consistency
            })
            
        # Sort by rating descending (highest rated movies first)
        results.sort(key=lambda x: x.get('rating', 0.0), reverse=True)
        
        return results
    except Exception as e:
        logger.error(f"TMDb Credits Error: {e}")
        
    return []

def get_tmdb_movie_details(api_key, movie_id):
    """
    Fetches full metadata for a specific movie ID.
    Returns (summary, genres_list, runtime, imdb_id).
    """
    if not api_key or not movie_id:
        return None
        
    session = requests_retry_session()
    params = {
        "api_key": api_key
    }
    
    try:
        url = f"{TMDB_BASE_URL}/movie/{movie_id}"
        response = session.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Format the genres
        genres = [g.get("name") for g in data.get("genres", [])]
        
        return {
            "summary": data.get("overview", "No summary available."),
            "genres": genres,
            "runtime": data.get("runtime", 0),
            "imdb_id": data.get("imdb_id"),
            "rating": data.get("vote_average", 0.0)
        }
    except Exception as e:
        logger.error(f"TMDb Detail Fetch Error: {e}")
        
    return None
