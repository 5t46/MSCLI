import os
import sys
import logging
import shutil
import webbrowser
import json
import time
from pathlib import Path
from tkinter import Tk, filedialog

try:
    from prompt_toolkit import prompt
    from prompt_toolkit.formatted_text import HTML
    from InquirerPy import inquirer
    from InquirerPy.base.control import Choice
    from InquirerPy.separator import Separator
    from rapidfuzz import fuzz
except ImportError:
    print("\n\x1b[38;2;153;41;0m[!] CRITICAL ERROR: Required libraries are missing.\x1b[0m")
    print("\x1b[38;2;103;130;138m[i] Please run 'install.bat' first to set up the application environment.\x1b[0m\n")
    import sys
    sys.exit(1)

from modules.utils import (
    setup_logging, setup_directories, load_config, save_config, 
    save_config_full, get_machine_id, get_computer_name, 
    perform_new_device_wipe, 
    sanitize_filename, open_torrent_in_client, 
    finalize_movie_folder, find_torrent_client,
    load_movie_metadata, save_movie_metadata,
    get_gradient_text, draw_detail_card,
    extract_filename_from_torrent
)
from modules.yts_api import search_movies, download_torrent
from modules.opensubtitles_api import search_subtitles, download_subtitle
from modules.tmdb_api import search_person, get_person_movies, get_tmdb_movie_details
from modules.yts_subs_api import search_yts_subtitles, download_yts_subtitle
from modules.extra_trackers import search_all_extra
from rapidfuzz import fuzz

# COLOR CONSTANTS (V5 Dark Premium - 60% Brightness)
C_MAIN = "\x1b[38;2;0;153;153m"   # Deep Teal
C_GOLD = "\x1b[38;2;153;129;0m"   # Bronze
C_VINC = "\x1b[38;2;103;130;138m" # Muted Blue
C_SUCC = "\x1b[38;2;30;123;30m"   # Moss Green
C_WARN = "\x1b[38;2;153;41;0m"    # Crimson

logger = logging.getLogger(__name__)

def prompt_for_api_key():
    """Classic V4 Secret Prompt."""
    try:
        config = load_config()
    except Exception as e:
        print("\x1b[38;2;255;69;0mError: Corrupt ./config/config.json file.\x1b[0m")
        logger.debug(f"Verbose config error: {e}")
        return {}
    api_key = config.get("OPENSUBTITLES_API_KEY")
    if api_key:
        return api_key
        
    width = shutil.get_terminal_size().columns
    print(f"\n{C_VINC}{'═' * width}\x1b[0m")
    print(get_gradient_text(" OpenSubtitles API Key Required ".center(width), (0, 153, 153), (0, 60, 153)))
    print(f"{C_VINC}{'═' * width}\x1b[0m")
    print(f"\n{C_VINC}You can get one for free at: https://www.opensubtitles.com/en/consumers\x1b[0m")
    
    api_key = inquirer.secret(
        message="Enter your OpenSubtitles API Key:",
        validate=lambda result: len(result) > 0,
        invalid_message="API Key cannot be empty.",
    ).execute()
    
    if api_key:
        save_config("OPENSUBTITLES_API_KEY", api_key)
    return api_key

def prompt_for_movies_path():
    """Classic V4 Tkinter Folder Picker."""
    config = load_config()
    movies_path = config.get("MOVIES_PATH")
    
    if movies_path and Path(movies_path).exists():
        return movies_path
        
    print("\nPlease select a folder to save downloaded movies in the dialog that appears...")
    
    while True:
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(title="Select Movies Folder")
        root.destroy()
        
        if not path:
            print("Folder selection is required. Please select a valid directory.")
            continue
            
        movies_path = str(Path(path).resolve())
        save_config("MOVIES_PATH", movies_path)
        return movies_path

def prompt_for_tmdb_key():
    """Classic V4 style prompt for TMDb Key."""
    config = load_config()
    tmdb_key = config.get("TMDB_API_KEY")
    if tmdb_key and tmdb_key != "STARI_TMDB_PLACEHOLDER":
        return tmdb_key
        
    width = shutil.get_terminal_size().columns
    print(f"\n{C_VINC}{'═' * width}\x1b[0m")
    print(get_gradient_text(" TMDb API Key Required ".center(width), (0, 153, 153), (0, 60, 153)))
    print(f"{C_VINC}{'═' * width}\x1b[0m")
    print(f"\n{C_VINC}Get your free key at: https://www.themoviedb.org\x1b[0m")
    
    tmdb_key = inquirer.secret(
        message="Enter your TMDb API Key:",
        validate=lambda result: len(result) > 0,
        invalid_message="TMDb API Key cannot be empty.",
    ).execute()
    
    if tmdb_key:
        save_config("TMDB_API_KEY", tmdb_key)
    return tmdb_key

def parse_input(query_str):
    """
    Parses 'Movie Name, 1997, 8.4'
    Returns (title, year, rating)
    """
    parts = [p.strip() for p in query_str.split(',')]
    title = ""
    year = None
    rating = 0.0
    
    for part in parts:
        if part.isdigit() and len(part) == 4:
            year = part
        elif part.replace('.', '', 1).isdigit() and '.' in part:
            rating = float(part)
        elif part.isdigit() and 0 <= int(part) <= 10:
            rating = float(part)
        else:
            title = part if not title else f"{title}, {part}"
            
    return title.strip(), year, rating

def display_paginated_movies(movies, chunk_size=5):
    """Classic V4 Chunked Pagination."""
    offset = 0
    while True:
        chunk = movies[offset:offset+chunk_size]
        if not chunk:
            print("\nNo more results to show.")
            offset = 0
            continue
            
        choices = []
        for i, m in enumerate(chunk):
            title = m.get('title', 'Unknown')
            year = m.get('year', 'Unknown')
            rating = m.get('rating', 0.0)
            rating_formatted = f"{rating:.1f}"
            choices.append(Choice(value=m, name=f"{offset+i+1}. {title} ({year}) - ⭐ {rating_formatted}"))
            
        if offset + chunk_size < len(movies):
            choices.append(Choice(value="LOAD_MORE", name=f"{len(chunk)+1}. -- Load more results... --"))
            
        choices.append(Choice(value=None, name=f"{len(choices)+1}. -- Cancel --"))
        
        selected = inquirer.select(
            message="Select a movie:",
            choices=choices,
            default=choices[0].value
        ).execute()
        
        if selected == "LOAD_MORE":
            offset += chunk_size
            continue
            
        return selected

def handle_settings():
    """Restored V4 Settings Menu Logic with V5 Colors."""
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        width = shutil.get_terminal_size().columns
        config = load_config()
        movies_path = config.get("MOVIES_PATH", "Not Set")

        print(f"{C_GOLD}{'═' * width}\x1b[0m")
        print(get_gradient_text(" SETTINGS MENU ".center(width), (255, 215, 0), (255, 165, 0)))
        print("Manage your paths and API credentials".center(width))
        print(f"{C_GOLD}{'═' * width}\x1b[0m")

        settings_choice = inquirer.select(
            message="What would you like to update?",
            choices=[
                Choice("folder", name=f"1. Change Movies Folder ( Current: {movies_path} )"),
                Choice("api", name="2. Update OpenSubtitles API Key"),
                Choice("tmdb", name="3. Update TMDB API Key ( For Actor Search )"),
                Choice("mirror", name=f"4. Change YTS Mirror ( Current: {config.get('LAST_WORKING_MIRROR', 'https://yts.mx')} )"),
                Choice("back", name="5. Back to Search")
            ]
        ).execute()

        if settings_choice == "back":
            break
        elif settings_choice == "folder":
            config["MOVIES_PATH"] = None
            save_config_full(config)
            prompt_for_movies_path()
        elif settings_choice == "api":
            config["OPENSUBTITLES_API_KEY"] = None
            save_config_full(config)
            prompt_for_api_key()
        elif settings_choice == "tmdb":
            config["TMDB_API_KEY"] = None
            save_config_full(config)
            prompt_for_tmdb_key()
        elif settings_choice == "mirror":
            new_mirror = prompt(HTML('<ansiyellow>?</ansiyellow> Enter new YTS Mirror URL: ')).strip()
            if new_mirror:
                config["LAST_WORKING_MIRROR"] = new_mirror
                save_config_full(config)
                print(f"{C_SUCC}Mirror updated successfully!\x1b[0m")
                time.sleep(1)

def main():
    setup_logging()
    setup_directories()
    
    # 1. Device Detection
    try:
        current_id = get_machine_id()
        config = load_config()
        last_id = config.get("MACHINE_ID")
        
        if last_id and last_id != current_id:
            os.system('cls' if os.name == 'nt' else 'clear')
            width = shutil.get_terminal_size().columns
            border = "!" * width
            print(f"{C_WARN}{border}\x1b[0m")
            print(f"{C_WARN} NEW DEVICE DETECTED \x1b[0m".center(width))
            print(f"{C_WARN}{border}\x1b[0m")
            print(f"\n[SYSTEM] It looks like you moved this app to a new PC: {get_computer_name()}")
            print("[SYSTEM] Wiping old settings to ensure a fresh start...")
            perform_new_device_wipe()
            config = load_config()
            time.sleep(2)
        elif not last_id:
            save_config("MACHINE_ID", current_id)
            save_config("COMPUTER_NAME", get_computer_name())
    except Exception as e:
        print("\x1b[38;2;255;69;0mError: System permission failure (Reset).\x1b[0m")
        logger.debug(f"Verbose reset error: {e}")

    # 2. Wizard check (Subtitles, Movies, and TMDb)
    if not config.get("MOVIES_PATH") or not config.get("OPENSUBTITLES_API_KEY") or not config.get("TMDB_API_KEY"):
        os.system('cls' if os.name == 'nt' else 'clear')
        width = shutil.get_terminal_size().columns
        title = " Welcome to Movies Downloader & Subtitles "
        subtitle = " Setup Wizard - Let's get you ready! "
        print(f"{C_VINC}{'═' * width}\x1b[0m")
        # 60% brightness gradient: (0,153,153) to (0,60,153)
        print(get_gradient_text(title.center(width), (0, 153, 153), (0, 60, 153)))
        print(subtitle.center(width))
        print(f"{C_VINC}{'═' * width}\x1b[0m")
        print("\n[INFO] This wizard will help you configure the app for the first time.\n")
    
    api_key = prompt_for_api_key()
    movies_path = prompt_for_movies_path()
    tmdb_key = prompt_for_tmdb_key()
    
    while True:
        try:
            os.system('cls' if os.name == 'nt' else 'clear')
            width = shutil.get_terminal_size().columns
            title = " Movies Downloader & Subtitles "
            desc = "Search for movies and download matching subtitles automatically"
            
            # Feature 3: Gradient Header (Dimmed to 60%)
            print(f"{C_MAIN}{'═' * width}\x1b[0m")
            print(get_gradient_text(title.center(width), (0, 153, 153), (0, 72, 153)))
            print(f"\033[90m{desc.center(width)}\033[0m")
            author_str = "Author: Star".center(width)
            # Use muted red for author
            print(author_str.replace("Star", "\x1b[38;2;153;30;30mStar\x1b[0m"))
            print(f"{C_MAIN}{'═' * width}\x1b[0m")
            
            print(f"{C_SUCC}Movies folder:\x1b[0m {movies_path}\n")
            
            main_menu = inquirer.select(
                message="What would you like to do?",
                choices=[
                    Choice("all_search", "1. Search All Trackers ( YTS + EZTV )"),
                    Choice("search", "2. Search for a Movie ( YTS )"),
                    Choice("genre", "3. Browse by Genre"),
                    Choice("actor", "4. Search by Actor"),
                    Choice("director", "5. Search by Director"),
                    Choice("settings", "6. Settings ( Folders / API Keys )"),
                    Choice("exit", "7. Exit")
                ]
            ).execute()
            
            if main_menu == "exit":
                print(f"\n{C_VINC}Thank you for using Movie Downloader & Subtitles! Goodbye\x1b[0m")
                break
                
            if main_menu == "settings":
                handle_settings()
                config = load_config()
                movies_path = config.get("MOVIES_PATH", movies_path)
                api_key = config.get("OPENSUBTITLES_API_KEY", api_key)
                continue

            # SEARCH FLOW
            movies = []
            if main_menu == "genre":
                genre_list = ["Action", "Adventure", "Animation", "Biography", "Comedy", "Crime", "Documentary", "Drama", "Family", "Fantasy", "History", "Horror", "Music", "Musical", "Mystery", "Romance", "Sci-Fi", "Sport", "Thriller", "War", "Western"]
                g_choices = [Choice(g, f"{i+1}. {g}") for i, g in enumerate(genre_list)]
                g_choices.append(Choice(None, "-- Back --"))
                genre = inquirer.select(message="Select Genre:", choices=g_choices).execute()
                if not genre: continue
                movies = search_movies("", genre=genre)
            elif main_menu in ["actor", "director"]:
                tk = prompt_for_tmdb_key()
                name = prompt(HTML('<ansiyellow>?</ansiyellow> Enter Name: ')).strip()
                if not name: continue
                print(f"\n{C_VINC}Searching TMDb for '{name}'...\x1b[0m")
                person = search_person(tk, name)
                if not person:
                    print(f"{C_WARN}Error: No {main_menu} found with that name.\x1b[0m")
                    time.sleep(1.5)
                    continue
                movies = get_person_movies(tk, person['id'], job="Director" if main_menu == "director" else None)
                movies = search_movies(title, target_year=year, min_rating=rating)
            elif main_menu == "all_search":
                query_str = prompt(HTML('<ansiyellow>?</ansiyellow> Enter a <ansired>Movie/Show</ansired> name to search across all trackers: '))
                if not query_str.strip(): continue
                title, year, rating = parse_input(query_str)
                print(f"\n{C_VINC}Searching All Trackers for '{title}'...\x1b[0m")
                # 1. YTS
                yts_m = search_movies(title, target_year=year)
                for m in yts_m: m['source_label'] = "YTS"
                movies.extend(yts_m)
                
                # 2. EZTV
                extra_m = search_all_extra(title, year)
                # Group EZTV results as "Single Result" movies to match YTS structure
                for ex in extra_m:
                    movies.append({
                        'title': ex['name'],
                        'year': year if year else 'Unknown',
                        'rating': 0.0,
                        'source_label': ex['source'],
                        'is_extra': True,
                        'extra_data': ex,
                        'torrents': [{'quality': ex['size'], 'url': ex['url'], 'seeds': ex['seeds'], 'size': ex['size']}]
                    })
            else: # Classic Search
                query_str = prompt(HTML('<ansiyellow>?</ansiyellow> Enter a <ansired>Movie</ansired> name to search for! <ansired>Example</ansired> <ansired>(</ansired> Inception or Inception, 2019, 8.8 <ansired>)</ansired> : '))
                if not query_str.strip(): continue
                title, year, rating = parse_input(query_str)
                movies = search_movies(title, target_year=year, min_rating=rating)

            if not movies:

                print(f"{C_WARN}Error: No movies found matching criteria! Try another search.\x1b[0m\n")
                time.sleep(1.5)
                continue
                
            selected_movie = display_paginated_movies(movies)
            if not selected_movie: continue
            
            # Deep Fetch for TMDb results (Actor/Director/etc) if details are missing
            if not selected_movie.get('genres') or not selected_movie.get('summary') or selected_movie.get('summary') == 'No summary available.':
                tmdb_id = selected_movie.get('id')
                if tmdb_id and "tmdb" in str(tmdb_id).lower() or isinstance(tmdb_id, int):
                    tk = prompt_for_tmdb_key()
                    print(f"{C_VINC}Fetching deep metadata from TMDb...\x1b[0m")
                    deep_details = get_tmdb_movie_details(tk, tmdb_id)
                    if deep_details:
                        selected_movie['summary'] = deep_details.get('summary')
                        selected_movie['genres'] = deep_details.get('genres')
                        selected_movie['runtime'] = deep_details.get('runtime')
                        if deep_details.get('imdb_id'):
                            selected_movie['imdb_code'] = deep_details.get('imdb_id')

            details = {
                "Year": selected_movie.get('year'),
                "Rating": f"⭐ {selected_movie.get('rating', 0.0)}/10",
                "Runtime": f"{selected_movie.get('runtime', 'Unknown')} min",
                "Genres": ", ".join(selected_movie.get('genres', [])),
                "Summary": selected_movie.get('summary', 'No summary available.')
            }
            # The box width is now dynamic inside draw_detail_card
            draw_detail_card(selected_movie['title'], details)
            
            while True: 
                action = inquirer.select(
                    message=f"Action for: {selected_movie['title']} ({selected_movie['year']})",
                    choices=[
                        Choice("download", "1. Download this Movie"), 
                        Choice("trailer", "2. Watch Trailer"), 
                        Choice("back", "3. -- Back --")
                    ]
                ).execute()
                if action == "back": break
                if action == "trailer":
                    webbrowser.open(f"https://www.youtube.com/results?search_query={selected_movie['title']}+{selected_movie['year']}+trailer")
                    continue
                
                # Torrent selection
                torrents = selected_movie.get('torrents', [])
                if not torrents:
                    print(f"\n{C_VINC}Finding YTS torrents...\x1b[0m")
                    yts_res = search_movies(selected_movie['title'], target_year=selected_movie['year'])
                    if yts_res: torrents = yts_res[0].get('torrents', [])
                
                if not torrents:
                    print(f"{C_WARN}Error: No torrents available!\x1b[0m")
                    break
                    
                q_choices = [Choice(t, f"{i+1}. {t['quality']} ({t['size']})") for i, t in enumerate(torrents)]
                q_choices.append(Choice(None, f"{len(torrents)+1}. -- Cancel --"))
                sel_t = inquirer.select(message="Select quality to download:", choices=q_choices).execute()
                if not sel_t: break
                
                movie_title = selected_movie['title']
                movie_year = selected_movie['year']
                quality = sel_t['quality']
                torrent_url = sel_t['url']
                
                movie_dir = Path(movies_path) / f"{sanitize_filename(movie_title)} - {movie_year}"
                movie_dir.mkdir(parents=True, exist_ok=True)
                
                print(f"\n{C_VINC}Downloading torrent...\x1b[0m")
                t_path = download_torrent(movie_title, movie_year, quality, torrent_url, movie_dir)
                
                if t_path:
                    print(f"{C_SUCC}Torrent saved to:\x1b[0m {t_path}")
                
                if not t_path:
                    print(f"{C_WARN}Error: Failed to download torrent.\x1b[0m")
                    break



                # 1. Handle Download Prompt (Moved up)
                clients = []
                if find_torrent_client("qbittorrent"): clients.append(Choice("qbittorrent", "1. Open in qBittorrent"))
                if find_torrent_client("utorrent"): clients.append(Choice("utorrent", "2. Open in uTorrent"))
                clients.append(Choice("manual", f"{len(clients)+1}. Do nothing (save file)"))
                
                imp = inquirer.select(message="How would you like to handle the download?", choices=clients).execute()
                if imp != "manual" and open_torrent_in_client(imp, t_path, movie_dir):
                    print(f"{C_SUCC}Successfully imported to {imp}!\x1b[0m")

                # 2. Extract internal filename for high-accuracy match
                internal_fn = extract_filename_from_torrent(t_path)
                if internal_fn:
                    print(f"{C_SUCC}PROBE SUCCESS: Detected internal movie file:\x1b[0m {internal_fn}")
                else:
                    internal_fn = f"{movie_title} {movie_year}" # Fallback
                
                # 3. Subtitle Search Flow (YTS-Subs -> OpenSubs)
                lang_map = {"ar": "Arabic", "en": "English", "ru": "Russian"}
                target_language = "ar"
                sub_path = None
                
                while True:
                    print(f"\n{C_VINC}Searching YTS-Subs for {lang_map[target_language]} matching '{internal_fn}'...\x1b[0m")
                    yts_subs = search_yts_subtitles(selected_movie.get('imdb_code'), language=lang_map[target_language])
                    
                    best_sub = None
                    if yts_subs:
                        # Find best filename match
                        for s in yts_subs:
                            # Higher weight for exact release names found on YTS-Subs
                            # token_set_ratio is robust against dots vs spaces
                            score = fuzz.token_set_ratio(internal_fn.lower(), s['name'].lower())
                            s['match_score'] = score
                        
                        yts_subs.sort(key=lambda x: x['match_score'], reverse=True)
                        top_yts = yts_subs[0]
                        
                        if top_yts['match_score'] >= 90:
                            best_sub = top_yts
                            print(f"{C_SUCC}Sync Match found on YifySubtitles ({best_sub['match_score']}% match)!\x1b[0m")
                        elif top_yts['match_score'] >= 70:
                            # Keep it as a candidate but check OpenSubtitles too
                            print(f"{C_VINC}Possible match on YifySubtitles ({top_yts['match_score']}%), checking fallback...\x1b[0m")
                            best_sub = top_yts
                    
                    # If no perfect YTS match, or we want to double check OpenSubtitles
                    if not best_sub or best_sub['match_score'] < 95:
                        print(f"{C_VINC}Searching OpenSubtitles for {lang_map[target_language]} fallback matching '{internal_fn}'...\x1b[0m")
                        os_sub = search_subtitles(api_key, movie_title, movie_year, quality, target_language, full_release_title=internal_fn)
                        if os_sub:
                            # if it's already a good match from our API logic, we trust it there.
                            if not best_sub or os_sub.get('score', 0) > best_sub.get('match_score', 0):
                                best_sub = os_sub
                                print(f"{C_SUCC}Best match found on OpenSubtitles ({best_sub.get('score', 0):.0f} points)!\x1b[0m")

                    if best_sub:
                        if 'file_id' in best_sub: # OpenSubtitles entry
                            sub_path = download_subtitle(api_key, best_sub['file_id'], movie_title, movie_year, movie_dir, lang_map.get(target_language, "Subtitle"))
                        else: # YTS-Subs entry
                            sub_path = download_yts_subtitle(best_sub, movie_dir, movie_title)
                        
                        if sub_path:
                            print(f"{C_SUCC}Subtitle saved to:\x1b[0m {sub_path}")
                            break
                    
                    print(f"{C_WARN}Error: No accurate {target_language} subtitles found.\x1b[0m")
                    fallback_choice = inquirer.select(message="Alternative:", choices=[Choice("en", "1. English"), Choice("ru", "2. Russian"), Choice(None, "3. Skip")]).execute()
                    if not fallback_choice: break
                    target_language = fallback_choice

                # 4. Final CleanUP (If opened in client)
                if imp != "manual":
                    print("\n" + f"{C_SUCC}═\x1b[0m" * width)
                    prompt(HTML(f'<ansigreen>Download has been started!</ansigreen> Press <ansiyellow>ENTER</ansiyellow> to run the "Final CleanUP" &amp; Finish once the download reaches 100% in your client...'))
                    print(f"\n{C_VINC}Cleaning up folder and removing junk files...\x1b[0m")
                    if finalize_movie_folder(movie_dir, movie_title, movie_year, quality):
                        print(f"{C_SUCC}Success! Your folder is now clean and organized.\x1b[0m")
                    else:
                        print(f"{C_WARN}Warning: Cleanup encounterted issues. Some files may still be in subfolders.\x1b[0m")
                    print(f"{C_SUCC}═\x1b[0m" * width + "\n")
                break
                
        except (KeyboardInterrupt, EOFError):
            print(f"\n{C_VINC}Thank you for using Movie Downloader & Subtitles! Goodbye\x1b[0m")
            break

if __name__ == "__main__":
    main()
