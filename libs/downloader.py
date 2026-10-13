# libs/downloader.py
import subprocess
import json
import re
import os
from pathlib import Path

def check_new_videos(channel):
    """Check for new videos in a channel/playlist"""
    try:
        cmd = [
            'yt-dlp',
            '--flat-playlist',
            '--dump-json',
            '-j',
            '--no-warnings'
        ]
        
        if channel.get('date_filter'):
            cmd.extend(['--dateafter', channel['date_filter']])
        
        if channel.get('playlist_range'):
            cmd.extend(['--playlist-items', channel['playlist_range']])
        
        if channel.get('rate_limit'):
            cmd.extend(['--ratelimit', channel['rate_limit']])
        
        cmd.append(channel['url'])
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            raise Exception(f"yt-dlp error: {result.stderr}")
        
        videos = []
        for line in result.stdout.strip().split('\n'):
            if line:
                try:
                    video_data = json.loads(line)
                    
                    duration = video_data.get('duration', 0) or 0
                    if channel.get('duration_min') and duration < channel['duration_min'] * 60:
                        continue
                    if channel.get('duration_max') and duration > channel['duration_max'] * 60:
                        continue
                    
                    if channel.get('skip_shorts') and duration < 60:
                        continue
                    
                    if channel.get('keywords'):
                        title = (video_data.get('title') or '').lower()
                        if not any(kw.lower() in title for kw in channel['keywords']):
                            continue
                    
                    videos.append({
                        'id': video_data.get('id'),
                        'title': video_data.get('title'),
                        'duration': str(int(duration / 60)) if duration else '0',
                        'upload_date': video_data.get('upload_date', 'N/A'),
                        'thumbnail_url': video_data.get('thumbnail'),
                        'url': f"https://www.youtube.com/watch?v={video_data.get('id')}"
                    })
                except json.JSONDecodeError:
                    continue
        
        return videos
    
    except Exception as e:
        print(f"Error checking videos: {e}")
        return []

def download_videos(channel, video_urls, progress_callback=None):
    """Download specific videos"""
    try:
        output_folder = Path(channel.get('download_folder', '.'))
        output_folder.mkdir(parents=True, exist_ok=True)
        
        cmd = ['yt-dlp']
        
        cmd.extend(video_urls)
        
        if channel.get('type') == 'audio':
            cmd.extend(['-x', '--audio-format', channel.get('format', 'm4a')])
            cmd.extend(['--audio-quality', channel.get('audio_quality', 'best')])
        else:
            cmd.extend(['-f', channel.get('video_quality', 'best')])
        
        output_template = channel.get('output_template', '%(title)s.%(ext)s')
        cmd.extend(['-o', str(output_folder / output_template)])
        
        archive_file = Path(channel.get('archive_file', str(output_folder / 'archive.txt')))
        archive_file.parent.mkdir(parents=True, exist_ok=True)
        cmd.extend(['--download-archive', str(archive_file)])
        
        if channel.get('embed_metadata'):
            cmd.append('--embed-metadata')
        if channel.get('embed_thumbnail'):
            cmd.append('--embed-thumbnail')
        
        if channel.get('extra_args'):
            cmd.extend(channel['extra_args'].split())
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=None
        )
        
        if result.returncode != 0:
            raise Exception(f"Download failed: {result.stderr}")
        
        return True
    
    except Exception as e:
        print(f"Download error: {e}")
        raise