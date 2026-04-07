import os

def bencode_decode(data, start=0):
    """
    Decodes bencoded data starting from the given position.
    Returns the decoded object and the next position.
    """
    if data[start:start+1] == b'i':
        end = data.find(b'e', start)
        return int(data[start+1:end]), end + 1
    elif data[start:start+1] == b'l':
        pos = start + 1
        res = []
        while data[pos:pos+1] != b'e':
            val, pos = bencode_decode(data, pos)
            res.append(val)
        return res, pos + 1
    elif data[start:start+1] == b'd':
        pos = start + 1
        res = {}
        while data[pos:pos+1] != b'e':
            key, pos = bencode_decode(data, pos)
            val, pos = bencode_decode(data, pos)
            res[key.decode('utf-8', errors='ignore')] = val
        return res, pos + 1
    elif b'0' <= data[start:start+1] <= b'9':
        sep = data.find(b':', start)
        length = int(data[start:sep])
        return data[sep+1:sep+1+length], sep+1+length
    else:
        raise ValueError(f"Invalid bencode prefix at {start}: {data[start:start+1]}")

def bencode_encode(data):
    """
    Encodes a Python object into bencoded bytes.
    """
    if isinstance(data, int):
        return f"i{data}e".encode()
    elif isinstance(data, list):
        return b'l' + b''.join(bencode_encode(x) for x in data) + b'e'
    elif isinstance(data, dict):
        # Keys must be sorted in bencode
        encoded_keys = []
        for k in sorted(data.keys()):
            encoded_keys.append(bencode_encode(k.encode()) + bencode_encode(data[k]))
        return b'd' + b''.join(encoded_keys) + b'e'
    elif isinstance(data, bytes):
        return f"{len(data)}:".encode() + data
    elif isinstance(data, str):
        encoded = data.encode('utf-8')
        return f"{len(encoded)}:".encode() + encoded
    else:
        raise TypeError(f"Cannot bencode {type(data)}")

def clean_movie_torrent(torrent_path, new_filename):
    """
    Modifies a .torrent file to:
    1. Only include the largest file (the movie).
    2. Rename the file to new_filename.
    3. Update the torrent name and file paths.
    """
    if not os.path.exists(torrent_path):
        return False

    with open(torrent_path, 'rb') as f:
        content = f.read()

    try:
        data, _ = bencode_decode(content)
        info = data.get('info')
        if not info:
            return False

        # Check if single or multi-file
        if 'files' in info:
            # Multi-file torrent
            files = info['files']
            # Find largest file
            largest_file = max(files, key=lambda x: x.get('length', 0))
            
            # Keep only the largest file (the movie)
            info['files'] = [largest_file]
            
            # Rename the movie file path
            # 'path' is a list of folder/file parts
            file_ext = os.path.splitext(largest_file['path'][-1].decode('utf-8'))[1]
            if not file_ext:
                file_ext = '.mp4' # fallback
            
            clean_name = os.path.splitext(new_filename)[0] + file_ext
            largest_file['path'] = [clean_name.encode()]
            
            # Set the torrent name (folder name) to the same clean name
            info['name'] = clean_name.encode()
        else:
            # Single-file torrent
            file_ext = os.path.splitext(info['name'].decode('utf-8'))[1]
            if not file_ext:
                file_ext = '.mp4'
            
            clean_name = os.path.splitext(new_filename)[0] + file_ext
            info['name'] = clean_name.encode()

        # Re-encode and save
        new_content = bencode_encode(data)
        with open(torrent_path, 'wb') as f:
            f.write(new_content)
        
        return True

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to clean torrent: {e}")
        return False
