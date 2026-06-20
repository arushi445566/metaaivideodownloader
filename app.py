import os
import tempfile
import urllib.request
import urllib.parse
import re
from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

def get_remote_file_size(url):
    try:
        req = urllib.request.Request(url, method='HEAD')
        req.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        with urllib.request.urlopen(req, timeout=3) as response:
            size = response.info().get('Content-Length')
            if size:
                return int(size)
    except:
        pass
    return None

def extract_meta_share_video(share_url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        req = urllib.request.Request(share_url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as response:
            html = response.read().decode('utf-8')
            
        # Pre-decode unicode escaped ampersands and html entities
        html_decoded = html.replace('\\u0026', '&').replace('&amp;', '&')
        
        # Regex to find the video CDN url
        pattern = r'(https?://[^\s"\'\\]+?(?:fbcdn\.net|fbsbx\.com)[^\s"\'\\]+?\.mp4[^\s"\'\\]*)'
        matches = re.findall(pattern, html_decoded)
        if not matches:
            # Fallback to general video hostname
            pattern_fallback = r'(https?://video[^\s"\'\\]+?\.mp4[^\s"\'\\]*)'
            matches = re.findall(pattern_fallback, html_decoded)
            
        if matches:
            return matches[0].rstrip('\\')
    except Exception as e:
        print(f"Meta AI share extraction failed: {e}")
    return None

def check_direct_video(url):
    try:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.lower()
        
        # 1. Check extension in path
        if any(path.endswith(ext) for ext in ['.mp4', '.m4v', '.mov', '.webm']):
            return True
            
        # 2. Check Meta/Facebook/Instagram CDN hostnames
        if any(domain in parsed.netloc for domain in ['fbcdn.net', 'fbsbx.com', 'cdninstagram.com']):
            return True
            
        # 3. Request HEAD to verify content-type
        req = urllib.request.Request(url, method='HEAD')
        req.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        with urllib.request.urlopen(req, timeout=3) as response:
            content_type = response.info().get_content_type()
            if content_type and content_type.startswith('video/'):
                return True
    except Exception as e:
        print(f"HEAD check failed: {e}")
        # Try GET range check
        try:
            req = urllib.request.Request(url, method='GET')
            req.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            req.add_header('Range', 'bytes=0-0')
            with urllib.request.urlopen(req, timeout=3) as response:
                content_type = response.info().get_content_type()
                if content_type and content_type.startswith('video/'):
                    return True
        except Exception as ex:
            print(f"GET Range check failed: {ex}")
            
    return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/download', methods=['POST'])
def download_video():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'URL is required'}), 400

    video_url = data['url']

    # Fast-path 1: Check if the link is already a direct video file
    if check_direct_video(video_url):
        parsed = urllib.parse.urlparse(video_url)
        filename = os.path.basename(parsed.path)
        title = filename if filename else 'meta_ai_video'
        if '.' in title:
            title = title.rsplit('.', 1)[0]
        title = title.split('?')[0]
        if not title:
            title = 'meta_ai_video'
            
        size = get_remote_file_size(video_url)
        size_str = f" ({round(size / 1024 / 1024, 1)} MB)" if size else ""
        return jsonify({
            'success': True,
            'title': title,
            'download_url': video_url,
            'formats': [{
                'format_id': 'original',
                'quality': f"HD Video - Original{size_str}",
                'resolution': 'HD',
                'ext': 'mp4',
                'url': video_url
            }]
        })

    # Fast-path 2: Check if it's a Meta AI share/chat page URL
    if 'meta.ai' in video_url:
        extracted = extract_meta_share_video(video_url)
        if extracted:
            size = get_remote_file_size(extracted)
            size_str = f" ({round(size / 1024 / 1024, 1)} MB)" if size else ""
            return jsonify({
                'success': True,
                'title': 'meta_ai_video',
                'download_url': extracted,
                'formats': [{
                    'format_id': 'original',
                    'quality': f"HD Video - Original{size_str}",
                    'resolution': 'HD',
                    'ext': 'mp4',
                    'url': extracted
                }]
            })
        else:
            return jsonify({'error': 'Failed to extract video from Meta AI share page. Please check that the link is public.'}), 400

    # yt-dlp options
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }

    # Auto-load cookies.txt if it exists in the app directory
    cookies_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.txt')
    if os.path.exists(cookies_path):
        ydl_opts['cookiefile'] = cookies_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # First try to extract the info to see if we can just return a direct URL
            info_dict = ydl.extract_info(video_url, download=False)
            
            # If a direct URL is available, we return it so the frontend can download it
            direct_url = info_dict.get('url')
            if not direct_url and 'entries' in info_dict:
                # Sometimes playlists/entries are returned
                direct_url = info_dict['entries'][0].get('url')

            # Fallback if direct_url is still None but we have formats (common for Instagram/Facebook)
            if not direct_url and info_dict.get('formats'):
                # Try to find a progressive format first
                for fmt in info_dict['formats']:
                    vcodec = fmt.get('vcodec')
                    acodec = fmt.get('acodec')
                    ext = fmt.get('ext')
                    is_progressive = False
                    if ext == 'mp4' and vcodec != 'none' and acodec != 'none':
                        is_progressive = True
                    if is_progressive and fmt.get('url'):
                        direct_url = fmt['url']
                        break
                
                # If no progressive format found, try to find any video format
                if not direct_url:
                    for fmt in info_dict['formats']:
                        if fmt.get('height') and fmt.get('height') > 0 and fmt.get('url'):
                            direct_url = fmt['url']
                            break
                            
                # Last resort fallback
                if not direct_url:
                    for fmt in info_dict['formats']:
                        if fmt.get('url'):
                            direct_url = fmt['url']
                            break

            if direct_url:
                title = info_dict.get('title', 'meta_ai_video')
                
                # Parse formats
                formats_list = []
                formats = info_dict.get('formats', [])
                
                # 1. Find the best progressive height
                best_prog_height = 0
                for fmt in formats:
                    vcodec = fmt.get('vcodec')
                    acodec = fmt.get('acodec')
                    ext = fmt.get('ext')
                    is_progressive = False
                    if ext == 'mp4' and vcodec != 'none' and acodec != 'none':
                        is_progressive = True
                    if is_progressive:
                        height = fmt.get('height') or 0
                        if height > best_prog_height:
                            best_prog_height = height
                
                # 2. Extract progressive formats (contain both video and audio)
                for fmt in formats:
                    vcodec = fmt.get('vcodec')
                    acodec = fmt.get('acodec')
                    ext = fmt.get('ext')
                    is_progressive = False
                    if ext == 'mp4' and vcodec != 'none' and acodec != 'none':
                        is_progressive = True
                    if is_progressive:
                        height = fmt.get('height')
                        resolution = f"{height}p" if height else (fmt.get('format_id').upper() if fmt.get('format_id') in ['sd', 'hd'] else "Standard")
                        filesize = fmt.get('filesize') or fmt.get('filesize_approx')
                        size_str = f" ({round(filesize / 1024 / 1024, 1)} MB)" if filesize else ""
                        
                        formats_list.append({
                            'format_id': fmt.get('format_id'),
                            'quality': f"MP4 - {resolution}{size_str}",
                            'resolution': resolution,
                            'ext': 'mp4',
                            'url': fmt.get('url')
                        })
                
                # 3. Extract higher quality video-only formats (requires server merging via ffmpeg)
                for fmt in formats:
                    vcodec = fmt.get('vcodec')
                    acodec = fmt.get('acodec')
                    ext = fmt.get('ext')
                    
                    if ext == 'mp4' and vcodec != 'none' and vcodec is not None and (acodec == 'none' or acodec is None):
                        height = fmt.get('height') or 0
                        if height > best_prog_height:
                            resolution = f"{height}p"
                            filesize = fmt.get('filesize') or fmt.get('filesize_approx')
                            # Estimated merged size (video size + approx audio size of ~5MB)
                            size_str = f" (~{round((filesize + 5 * 1024 * 1024) / 1024 / 1024, 1)} MB)" if filesize else " (HQ)"
                            
                            encoded_url = urllib.parse.quote(video_url)
                            merge_url = f"/api/download/file?url={encoded_url}&format_id={fmt.get('format_id')}&title={urllib.parse.quote(title)}"
                            
                            formats_list.append({
                                'format_id': fmt.get('format_id'),
                                'quality': f"MP4 - {resolution}{size_str} [HQ Compiling]",
                                'resolution': resolution,
                                'ext': 'mp4',
                                'url': merge_url
                            })
                
                # Fallback to single format if no progressive formats parsed
                if not formats_list:
                    size = get_remote_file_size(direct_url)
                    size_str = f" ({round(size / 1024 / 1024, 1)} MB)" if size else ""
                    formats_list.append({
                        'format_id': 'original',
                        'quality': f"HD Video - Original{size_str}",
                        'resolution': 'HD',
                        'ext': 'mp4',
                        'url': direct_url
                    })
                    
                return jsonify({
                    'success': True,
                    'title': title,
                    'download_url': direct_url,
                    'formats': formats_list
                })
            else:
                return jsonify({'error': 'Could not extract direct video URL.'}), 400

    except Exception as e:
        print(f"Error extracting video: {e}")
        error_msg = str(e)
        # Check if URL belongs to Instagram or Facebook and has a typical block signature
        is_meta_platform = any(p in video_url.lower() for p in ['instagram.com', 'facebook.com', 'fb.watch'])
        if is_meta_platform:
            # Let's provide a helpful, user-friendly error message detailing how to use cookies.txt
            return jsonify({
                'error': 'Instagram/Facebook is blocking access to this video. To bypass this, please export your browser cookies as a file named "cookies.txt" (Netscape format) using an extension like "Get cookies.txt LOCALLY", save it in the project root directory, and try downloading again.'
            }), 400
        return jsonify({'error': error_msg}), 500

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy.html')

@app.route('/terms-of-service')
def terms_of_service():
    return render_template('terms.html')

@app.route('/disclaimer')
def disclaimer():
    return render_template('disclaimer.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/instagram-downloader')
def instagram_downloader():
    return render_template('instagram.html')

@app.route('/facebook-downloader')
def facebook_downloader():
    return render_template('facebook.html')

@app.route('/api/download/file', methods=['GET'])
def download_file_route():
    video_url = request.args.get('url')
    format_id = request.args.get('format_id')
    title = request.args.get('title', 'video')
    
    if not video_url:
        return 'URL is required', 400
        
    temp_dir = tempfile.mkdtemp()
    output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')
    
    # If format_id is specified and is not 'original', we download bestvideo + bestaudio or specific format
    # Using ffmpeg path on macOS
    ydl_opts = {
        'format': f"{format_id}+bestaudio/best" if format_id and format_id != 'original' else 'bestvideo+bestaudio/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4',
    }

    # Use local homebrew path on macOS if present, otherwise let yt-dlp search system PATH
    if os.path.exists('/opt/homebrew/bin/ffmpeg'):
        ydl_opts['ffmpeg_location'] = '/opt/homebrew/bin/ffmpeg'

    # Auto-load cookies.txt if it exists in the app directory
    cookies_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.txt')
    if os.path.exists(cookies_path):
        ydl_opts['cookiefile'] = cookies_path
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Since we merged it to mp4, make sure we find the correct file
            if not os.path.exists(filename):
                # Try finding any mp4 or other video file in temp_dir
                files = os.listdir(temp_dir)
                if files:
                    # Choose the largest file in temp_dir (which is the merged video)
                    files_paths = [os.path.join(temp_dir, f) for f in files]
                    filename = max(files_paths, key=os.path.getsize)
            
            response = send_file(filename, as_attachment=True, download_name=f"{title}.mp4")
            
            @response.call_on_close
            def remove_file():
                try:
                    for f in os.listdir(temp_dir):
                        os.remove(os.path.join(temp_dir, f))
                    os.rmdir(temp_dir)
                except Exception as e:
                    print(f"Cleanup call_on_close error: {e}")
                    
            return response
            
    except Exception as e:
        print(f"Download/Merge error: {e}")
        # Clean up temp_dir immediately if error occurs
        try:
            for f in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, f))
            os.rmdir(temp_dir)
        except:
            pass
        return f"Error processing video: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    app.run(debug=True, host='0.0.0.0', port=port)
