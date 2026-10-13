# libs/config_manager.py
import json
from pathlib import Path
from datetime import datetime
import os

try:
    from android.storage import primary_external_storage_path
    APP_DIR = Path(primary_external_storage_path()) / 'YouTubeObserve'
except ImportError:
    APP_DIR = Path.home() / 'YouTubeObserve'

CONFIG_DIR = APP_DIR / 'config'
PREFS_FILE = CONFIG_DIR / 'preferences.json'
CHANNELS_FILE = CONFIG_DIR / 'channels.json'
ARCHIVE_DIR = APP_DIR / 'archives'
DOWNLOADS_DIR = APP_DIR / 'downloads'

APP_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CHANNEL_CONFIG = {
    'name': '',
    'url': '',
    'enabled': True,
    'type': 'audio',
    'format': 'm4a',
    'audio_quality': 'best',
    'video_quality': 'best',
    'download_folder': str(DOWNLOADS_DIR),
    'output_template': '%(title)s - (%(id)s).%(ext)s',
    'date_filter': '',
    'duration_min': 0,
    'duration_max': 0,
    'skip_shorts': True,
    'keywords': [],
    'playlist_range': '',
    'rate_limit': '',
    'embed_metadata': True,
    'embed_thumbnail': True,
    'fallback_artist': '',
    'genre': '',
    'subtitles': False,
    'subtitle_language': 'en',
    'extra_args': '',
    'archive_file': '',
    'last_run': None,
    'last_checked': None,
    'new_count': 0,
    'thumbnail_url': ''
}

def initialize():
    """Initialize app structure"""
    CHANNELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not CHANNELS_FILE.exists():
        CHANNELS_FILE.write_text(json.dumps([], indent=2))
    if not PREFS_FILE.exists():
        PREFS_FILE.write_text(json.dumps({
            'auto_refresh': False,
            'refresh_interval': 30,
            'wifi_only': True
        }, indent=2))

def load_all_channels():
    """Load all channels from config file"""
    if not CHANNELS_FILE.exists():
        return []
    
    try:
        content = CHANNELS_FILE.read_text(encoding='utf-8')
        if not content:
            return []
        return json.loads(content)
    except Exception as e:
        print(f"Error loading channels: {e}")
        return []

def save_channel(channel):
    """Save or update a channel"""
    channels = load_all_channels()
    
    found = False
    for i, ch in enumerate(channels):
        if ch['name'] == channel['name']:
            channels[i] = channel
            found = True
            break
    
    if not found:
        channels.append(channel)
    
    if not channel.get('archive_file'):
        safe_name = channel['name'].lower().replace(' ', '_')
        archive_path = ARCHIVE_DIR / f'{safe_name}.txt'
        archive_path.touch(exist_ok=True)
        channel['archive_file'] = str(archive_path)
    
    CHANNELS_FILE.write_text(json.dumps(channels, indent=2, ensure_ascii=False))
    return channel

def delete_channel(channel_name):
    """Delete a channel"""
    channels = load_all_channels()
    channels = [ch for ch in channels if ch['name'] != channel_name]
    CHANNELS_FILE.write_text(json.dumps(channels, indent=2))

def load_channel(channel_name):
    """Load specific channel"""
    channels = load_all_channels()
    for ch in channels:
        if ch['name'] == channel_name:
            return ch
    return None

def update_channel(channel):
    """Update channel data"""
    save_channel(channel)

def set_new_count(channel, count):
    """Set new video count"""
    channel['new_count'] = count
    channel['last_checked'] = datetime.now().isoformat()
    save_channel(channel)

def clear_new_count(channel):
    """Clear new video count"""
    channel['new_count'] = 0
    save_channel(channel)

def update_last_run(channel):
    """Update last run timestamp"""
    channel['last_run'] = datetime.now().isoformat()
    save_channel(channel)

def save_preference(key, value):
    """Save app preference"""
    prefs = {}
    if PREFS_FILE.exists():
        try:
            prefs = json.loads(PREFS_FILE.read_text())
        except:
            pass
    
    prefs[key] = value
    PREFS_FILE.write_text(json.dumps(prefs, indent=2))

def load_preference(key, default=None):
    """Load app preference"""
    if not PREFS_FILE.exists():
        return default
    
    try:
        prefs = json.loads(PREFS_FILE.read_text())
        return prefs.get(key, default)
    except:
        return default