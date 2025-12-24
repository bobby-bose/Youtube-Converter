from flask import Flask, render_template, request, send_file, jsonify
import yt_dlp
import os
import threading
import time
from datetime import datetime
import re

app = Flask(__name__)

# Create downloads directory if it doesn't exist
DOWNLOAD_FOLDER = 'downloads'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Store conversion status
conversion_status = {}

# Quality settings
QUALITY_SETTINGS = {
    'audio': {
        'high': {'preferredquality': '320', 'format': 'bestaudio/best'},
        'medium': {'preferredquality': '192', 'format': 'bestaudio/best'},
        'low': {'preferredquality': '128', 'format': 'worstaudio/worst'}
    },
    'video': {
        'high': {'format': 'bestvideo[ext=mp4]+bestaudio/best', 'ext': 'mp4'},
        'medium': {'format': 'best[height<=720][ext=mp4]', 'ext': 'mp4'},
        'low': {'format': 'worst[height<=480][ext=mp4]', 'ext': 'mp4'}
    },
    'video_audio': {
        'high': {'format': 'best[height<=1080][ext=mp4]', 'ext': 'mp4'},
        'medium': {'format': 'best[height<=720][ext=mp4]', 'ext': 'mp4'},
        'low': {'format': 'worst[height<=480][ext=mp4]', 'ext': 'mp4'}
    }
}

# Video format alternatives
VIDEO_FORMATS = {
    'mp4': {'ext': 'mp4', 'name': 'MP4'},
    'flv': {'ext': 'flv', 'name': 'FLV'},
    'mkv': {'ext': 'mkv', 'name': 'MKV'},
    'webm': {'ext': 'webm', 'name': 'WebM'}
}

def get_video_info(video_url):
    """Extract video information and available formats without downloading"""
    try:
        # Try multiple configurations for PythonAnywhere compatibility
        configs = [
            {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'no_check_certificate': True,
                'socket_timeout': 60,
                'retries': 1,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'extractor_args': {
                    'youtube': {
                        'player_client': 'android',
                    }
                },
            },
            {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'no_check_certificate': True,
                'socket_timeout': 30,
                'retries': 1,
                'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
                'extractor_args': {
                    'youtube': {
                        'player_client': 'ios',
                    }
                },
            },
            {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'no_check_certificate': True,
                'socket_timeout': 15,
                'retries': 1,
                'user_agent': 'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
                'extractor_args': {
                    'youtube': {
                        'player_client': 'android_embedded',
                    }
                },
            }
        ]
        
        for i, ydl_opts in enumerate(configs):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(video_url, download=False)
                    
                    # Format duration
                    duration = info.get('duration', 0)
                    if duration:
                        hours = duration // 3600
                        minutes = (duration % 3600) // 60
                        seconds = duration % 60
                        if hours > 0:
                            duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                        else:
                            duration_str = f"{minutes:02d}:{seconds:02d}"
                    else:
                        duration_str = "Unknown"
                    
                    # Get available formats
                    formats = info.get('formats', [])
                    available_formats = []
                    
                    # Group formats by quality
                    audio_formats = []
                    video_formats = []
                    
                    for fmt in formats:
                        if fmt.get('acodec') != 'none' and fmt.get('vcodec') == 'none':
                            # Audio only
                            audio_formats.append({
                                'format_id': fmt.get('format_id'),
                                'ext': fmt.get('ext'),
                                'abr': fmt.get('abr'),
                                'asr': fmt.get('asr'),
                                'filesize': fmt.get('filesize')
                            })
                        elif fmt.get('vcodec') != 'none':
                            # Video (with or without audio)
                            video_formats.append({
                                'format_id': fmt.get('format_id'),
                                'ext': fmt.get('ext'),
                                'height': fmt.get('height'),
                                'width': fmt.get('width'),
                                'fps': fmt.get('fps'),
                                'filesize': fmt.get('filesize')
                            })
                    
                    # Get file size estimate
                    estimated_size = "Unknown"
                    for fmt in formats:
                        if fmt.get('filesize'):
                            estimated_size = format_file_size(fmt['filesize'])
                            break
                    
                    return {
                        'title': info.get('title', 'Unknown Title'),
                        'description': info.get('description', 'No description available')[:200] + '...' if info.get('description') else 'No description available',
                        'thumbnail': info.get('thumbnail', ''),
                        'duration': duration_str,
                        'duration_seconds': duration,
                        'estimated_size': estimated_size,
                        'uploader': info.get('uploader', 'Unknown'),
                        'view_count': info.get('view_count', 0),
                        'upload_date': info.get('upload_date', ''),
                        'available_formats': {
                            'audio': audio_formats[:5],  # Limit to top 5
                            'video': video_formats[:10]  # Limit to top 10
                        },
                        'webpage_url': info.get('webpage_url', video_url)
                    }
            except Exception as e:
                if i == len(configs) - 1:  # Last attempt
                    raise e
                continue
                
    except Exception as e:
        return {'error': f'Network/Proxy Error: {str(e)}'}

def download_media(video_url, output_path, task_id, media_type, quality, format_ext='mp3'):
    """Downloads YouTube video and converts to specified format"""
    try:
        conversion_status[task_id] = {'status': 'downloading', 'progress': 0, 'message': 'Starting download...'}
        
        # Get quality settings
        if media_type in QUALITY_SETTINGS and quality in QUALITY_SETTINGS[media_type]:
            quality_settings = QUALITY_SETTINGS[media_type][quality]
        else:
            quality_settings = {'format': 'bestaudio/best', 'preferredquality': '192'}
        
        # Try multiple configurations for PythonAnywhere compatibility
        configs = [
            {
                'format': quality_settings['format'],
                'outtmpl': os.path.join(output_path, f'{task_id}_%(title)s.%(ext)s'),
                'progress_hooks': [lambda d: update_progress(d, task_id)],
                'no_check_certificate': True,
                'socket_timeout': 60,
                'retries': 1,
                'fragment_retries': 1,
                'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
                'extractor_args': {
                    'youtube': {
                        'player_client': 'ios',
                    }
                },
            },
            {
                'format': quality_settings['format'],
                'outtmpl': os.path.join(output_path, f'{task_id}_%(title)s.%(ext)s'),
                'progress_hooks': [lambda d: update_progress(d, task_id)],
                'no_check_certificate': True,
                'socket_timeout': 30,
                'retries': 1,
                'fragment_retries': 1,
                'user_agent': 'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
                'extractor_args': {
                    'youtube': {
                        'player_client': 'android_embedded',
                    }
                },
            },
            {
                'format': quality_settings['format'],
                'outtmpl': os.path.join(output_path, f'{task_id}_%(title)s.%(ext)s'),
                'progress_hooks': [lambda d: update_progress(d, task_id)],
                'no_check_certificate': True,
                'socket_timeout': 15,
                'retries': 1,
                'fragment_retries': 1,
                'user_agent': 'Mozilla/5.0 (Android 10; Mobile; rv:91.0) Gecko/91.0 Firefox/91.0',
                'extractor_args': {
                    'youtube': {
                        'player_client': 'android',
                    }
                },
            }
        ]
        
        for i, base_opts in enumerate(configs):
            try:
                ydl_opts = base_opts.copy()
                
                # Add post-processors for audio conversion
                if media_type == 'audio':
                    ydl_opts['postprocessors'] = [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': format_ext,
                        'preferredquality': quality_settings.get('preferredquality', '192'),
                    }]
                elif media_type in ['video', 'video_audio'] and format_ext != 'mp4':
                    # For non-MP4 video formats, we need to convert
                    ydl_opts['postprocessors'] = [{
                        'key': 'FFmpegVideoConvertor',
                        'preferedformat': format_ext,
                    }]
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Extract info first
                    info = ydl.extract_info(video_url, download=False)
                    title = info.get('title', 'Unknown Title')
                    
                    conversion_status[task_id].update({
                        'status': 'downloading',
                        'message': f'Downloading: {title}',
                        'title': title
                    })
                    
                    # Download and convert
                    ydl.download([video_url])
                    
                    # Find the converted file
                    for file in os.listdir(output_path):
                        if file.startswith(task_id):
                            file_path = os.path.join(output_path, file)
                            file_size = os.path.getsize(file_path)
                            
                            # Clean filename for download
                            clean_filename = file.replace(f'{task_id}_', '')
                            
                            conversion_status[task_id] = {
                                'status': 'completed',
                                'progress': 100,
                                'message': 'Conversion complete!',
                                'file_path': file_path,
                                'file_name': clean_filename,
                                'file_size': format_file_size(file_size),
                                'title': title,
                                'media_type': media_type,
                                'quality': quality
                            }
                            return
                            
            except Exception as e:
                if i == len(configs) - 1:  # Last attempt
                    conversion_status[task_id] = {
                        'status': 'error',
                        'progress': 0,
                        'message': f'Network/Proxy Error: Unable to connect to YouTube. This may be due to hosting provider restrictions. Error: {str(e)}'
                    }
                else:
                    continue
                    
    except Exception as e:
        conversion_status[task_id] = {
            'status': 'error',
            'progress': 0,
            'message': f'Error: {str(e)}'
        }

def update_progress(d, task_id):
    """Update progress during download"""
    if d['status'] == 'downloading':
        percent_str = d.get('_percent_str', '0.0%')
        try:
            percent = float(percent_str.strip('%'))
            conversion_status[task_id]['progress'] = percent
        except:
            pass

def format_file_size(size_bytes):
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0B"
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.1f}{size_names[i]}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_info', methods=['POST'])
def get_info():
    data = request.get_json()
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    info = get_video_info(url)
    if 'error' in info:
        return jsonify({'error': info['error']}), 400
    
    return jsonify(info)

@app.route('/get_download_command', methods=['POST'])
def get_download_command():
    """Generate yt-dlp command for client-side download"""
    data = request.get_json()
    url = data.get('url')
    media_type = data.get('media_type', 'audio')
    quality = data.get('quality', 'medium')
    format_ext = data.get('format', 'mp3')
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    # Generate command based on selection
    if media_type == 'audio':
        if quality == 'high':
            quality_flag = '320'
        elif quality == 'low':
            quality_flag = '128'
        else:
            quality_flag = '192'
        
        command = f"yt-dlp -x --audio-format {format_ext} --audio-quality {quality_flag} \"{url}\""
    elif media_type == 'video':
        if quality == 'high':
            format_flag = 'best[height<=1080]'
        elif quality == 'low':
            format_flag = 'worst[height<=480]'
        else:
            format_flag = 'best[height<=720]'
        
        command = f"yt-dlp -f \"{format_flag}[ext={format_ext}]\" \"{url}\""
    else:  # video_audio
        if quality == 'high':
            format_flag = 'best[height<=1080]'
        elif quality == 'low':
            format_flag = 'worst[height<=480]'
        else:
            format_flag = 'best[height<=720]'
        
        command = f"yt-dlp -f \"{format_flag}[ext=mp4]\" \"{url}\""
    
    return jsonify({
        'command': command,
        'instructions': {
            'step1': 'Install yt-dlp: pip install yt-dlp',
            'step2': 'Install FFmpeg for audio/video conversion',
            'step3': 'Run the command in your terminal',
            'note': 'Download happens on your computer, not on the server'
        }
    })

# Remove server-side download routes - now browser-only

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
