import praw
import requests
import os
import time
import logging
import sys
import re
from datetime import datetime, timedelta, timezone
from prawcore.exceptions import RequestException, ResponseException
from praw.exceptions import RedditAPIException
import config  # Import the config file with credentials
import subprocess
import shutil

# Set up logging
logging.basicConfig(filename='/home/ubuntu/Reddit-UFOs_Archive/error_log.txt', level=logging.ERROR, 
                    format='%(asctime)s %(levelname)s: %(message)s')

# Reddit API credentials
source_reddit = praw.Reddit(
    client_id=config.source_client_id,
    client_secret=config.source_client_secret,
    password=config.source_password,
    username=config.source_username,
    user_agent=config.source_user_agent
)

archives_reddit = praw.Reddit(
    client_id=config.destination_client_id,
    client_secret=config.destination_client_secret,
    password=config.destination_password,
    username=config.destination_username,
    user_agent=config.destination_user_agent
)

# Subreddits
source_subreddit = source_reddit.subreddit('ufos')
destination_subreddit = archives_reddit.subreddit('UFOs_Archive')

# File to store processed post IDs
PROCESSED_FILE = "/home/ubuntu/Reddit-UFOs_Archive/processed_posts.txt"

# Max IDs to store in previous file
MAX_PROCESSED_IDS = 2000

# Specify temp media location
MEDIA_DOWNLOAD_DIR = "/home/ubuntu/Reddit-UFOs_Archive/temp_media"
os.makedirs(MEDIA_DOWNLOAD_DIR, exist_ok=True)

# Start definitions
def load_processed_posts():
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, "r") as file:
            return set(file.read().splitlines())
    return set()

def save_processed_post(post_id):
    with open(PROCESSED_FILE, "a") as file:
        file.write(post_id + "\n")

def download_media(url, file_name):
    if "preview.redd.it" in url:
        url = url.replace("preview.redd.it", "i.redd.it")

    headers = {
        'User-Agent': 'Mozilla/5.0'
    }
    full_path = os.path.join(MEDIA_DOWNLOAD_DIR, file_name)
    response = requests.get(url, stream=True, headers=headers)
    if response.status_code == 200:
        with open(full_path, 'wb') as out_file:
            for chunk in response.iter_content(chunk_size=1024):
                out_file.write(chunk)
        return full_path
    else:
        logging.error(f"Failed to download media from {url}. Status code: {response.status_code}. Submission ID: {submission.id}")
        return None

def split_text(text, max_length=10000):
    chunks = []
    while len(text) > max_length:
        split_point = text.rfind("\n", 0, max_length)
        if split_point == -1:
            split_point = max_length
        chunks.append(text[:split_point])
        text = text[split_point:].lstrip()
    chunks.append(text)
    return chunks

def get_audio_url(dash_url):
    """
    Extract the video ID from the video_url and construct the proper audio URL with bitrate.
    Example input: https://v.redd.it/916xfnxxvd2f1/DASH_1080.mp4
    Output: https://v.redd.it/916xfnxxvd2f1/DASH_AUDIO_128.mp4
    """
    match = re.search(r"/asset/([^/]+)/DASHPlaylist\.mpd", dash_url)
    if match:
        asset_id = match.group(1)
        return f"https://v.redd.it/{asset_id}/DASH_AUDIO_128.mp4"
    return None

# Parse time delta from command-line argument
def parse_time_delta(arg):
    if not arg:
        return timedelta(minutes=28)  # Default to 28 minutes if no argument
    match = re.match(r'^(\d+)([mh])$', arg)
    if not match:
        logging.error(f"Invalid time delta format: {arg}. Using default 28 minutes.")
        return timedelta(minutes=28)
    value, unit = int(match.group(1)), match.group(2)
    if unit == 'm':
        return timedelta(minutes=value)
    elif unit == 'h':
        return timedelta(hours=value)

# Get time delta from command-line argument
time_delta = parse_time_delta(sys.argv[1] if len(sys.argv) > 1 else None)

# Time filtering
current_time = datetime.now(timezone.utc)
cutoff_time = current_time - time_delta

processed_posts = load_processed_posts()

# Start of script - Fetch new posts
print(f"Starting script. Scan interval: {time_delta}.")
newly_copied_post_ids = [] # count number of posts to remove old IDs from processed_posts log
for submission in source_subreddit.new():
    video_url = None
    audio_url = None
    dash_url = None
    video_file = os.path.join(MEDIA_DOWNLOAD_DIR, 'media_video.mp4')
    audio_file = os.path.join(MEDIA_DOWNLOAD_DIR, 'media_audio.mp4')
    merged_file = os.path.join(MEDIA_DOWNLOAD_DIR, 'merged_video.mp4')
    try:
        logging.info(f"Processing submission: {submission.title}, Flair: {submission.link_flair_text}, Created: {submission.created_utc}")
        audio_url = None

        if submission.id in processed_posts:
            continue

        post_time = datetime.fromtimestamp(submission.created_utc, timezone.utc)
        if post_time < cutoff_time:
            continue

        title = submission.title
        is_self_post = submission.is_self
        media_url = None
        original_media_url = None
        gallery_images = []

        # If image gallery
        if hasattr(submission, 'is_gallery') and submission.is_gallery:
            for item in submission.gallery_data['items']:
                media_id = item['media_id']
                meta = submission.media_metadata.get(media_id, {})
                if 's' in meta and 'u' in meta['s']:
                    img_url = meta['s']['u'].split('?')[0].replace("&", "&")
                    ext = os.path.splitext(img_url)[-1]
                    file_name = f"{media_id}{ext}"
                    downloaded = download_media(img_url, file_name)
                    if downloaded:
                        gallery_images.append(downloaded)

        # Handle Reddit video from media_metadata (gallery-like or crossposted video posts)
        elif hasattr(submission, "media_metadata") and submission.media_metadata:
            for key, meta in submission.media_metadata.items():
                if meta.get('e') == 'RedditVideo' and 'dashUrl' in meta:
                    dash_url = meta['dashUrl']
                    test_urls = [
                        dash_url.replace("DASHPlaylist.mpd", "DASH_1080.mp4"),
                        dash_url.replace("DASHPlaylist.mpd", "DASH_720.mp4"),
                        dash_url.replace("DASHPlaylist.mpd", "DASH_480.mp4")
                    ]
                    video_url = None
                    for url in test_urls:
                        head_resp = requests.head(url, headers={'User-Agent': 'Mozilla/5.0'})
                        if head_resp.status_code == 200:
                            video_url = url
                            break

                    # Fallback to submission.media.reddit_video.fallback_url if dashUrl fails
                    if not video_url and submission.media and 'reddit_video' in submission.media:
                        fallback_url = submission.media['reddit_video'].get('fallback_url')
                        if fallback_url:
                            logging.warning(f"dashUrl failed for {submission.id}, using fallback_url.")
                            video_url = fallback_url

                    has_audio = True
                    is_gif = meta.get('isGif', False)
                    original_media_url = video_url
                    break


        # Handle direct Reddit video (fallback_url)
        elif submission.media and 'reddit_video' in submission.media:
            reddit_video = submission.media['reddit_video']
            video_url = reddit_video.get('fallback_url')
            has_audio = reddit_video.get('has_audio', False)
            is_gif = reddit_video.get('is_gif', False)
            original_media_url = video_url

        # Handle direct image
        elif not is_self_post and submission.url.endswith(('jpg', 'jpeg', 'png', 'gif')):
            file_name = submission.url.split('/')[-1]
            media_url = download_media(submission.url, file_name)
            original_media_url = submission.url

        # Process video if found
        if video_url:
            video_downloaded = download_media(video_url, 'media_video.mp4')
            if has_audio and not is_gif and dash_url:
                audio_url = get_audio_url(dash_url)
                if audio_url:
                    audio_downloaded = download_media(audio_url, 'media_audio.mp4')

                    # Combine using ffmpeg if both downloaded
                    if video_downloaded and audio_downloaded:
                        cmd = [
                            "ffmpeg", "-loglevel", "error", "-y",
                            "-i", video_file,
                            "-i", audio_file,
                            "-c", "copy",
                            merged_file
                        ]
                        try:
                            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            media_url = merged_file
                        except subprocess.CalledProcessError as e:
                            logging.error(f"FFmpeg failed to merge video/audio with return code {e.returncode}")
                            media_url = video_file
                    else:
                        media_url = video_file
                else:
                    media_url = video_file
            else:
                media_url = video_file

        new_post = None
        source_flair_text = submission.link_flair_text

        # If self post
        if is_self_post:
            new_post = destination_subreddit.submit(title, selftext=submission.selftext)
        elif gallery_images:
            images = [{'image_path': path} for path in gallery_images]
            new_post = destination_subreddit.submit_gallery(title, images=images)
        elif media_url and os.path.exists(media_url) and os.path.getsize(media_url) > 0:
            if media_url.endswith(('jpg', 'jpeg', 'png', 'gif')):
                new_post = destination_subreddit.submit_image(title, image_path=media_url)
            elif media_url.endswith('mp4'):
                new_post = destination_subreddit.submit_video(title, video_path=media_url)
        else:
            new_post = destination_subreddit.submit(title, url=submission.url)

        # Set post flair from source
        if new_post and source_flair_text:
            matching_flair = None
            for flair in destination_subreddit.flair.link_templates:
                if flair['text'] == source_flair_text:
                    matching_flair = flair['id']
                    break
            if matching_flair:
                new_post.flair.select(matching_flair)
                logging.info(f"Applied flair: {source_flair_text} to post {new_post.id}")
            else:
                logging.info(f"No matching flair found for: {source_flair_text}")

        # Build comment with post information
        if new_post:
            comment_body = f"**Original post by u/{submission.author}:** [Here](https://www.reddit.com{submission.permalink})\n"
            comment_body += f"\n**Original Post ID:** {submission.id}"
            if original_media_url:
                comment_body += f"\n\n**Direct link to media:** [Media Here]({original_media_url})"
            if audio_url:
                comment_body += f"\n\n**Direct link to Audio:** [Audio Here]({audio_url})"
            if submission.selftext:
                comment_body += f"\n\n**Original post text:** {submission.selftext}"
                comment_body += "\n\n---\n\n"                
            if hasattr(submission, 'link_flair_template_id'):
                comment_body += f"\n\n**Original Flair ID:** {submission.link_flair_template_id}\n"
            if submission.link_flair_text:
                comment_body += f"\n**Original Flair Text:** {submission.link_flair_text}"
            # Split comment if greater than 10,000 characters - Reddit limit
            if len(comment_body) > 10000:
                for chunk in split_text(comment_body):
                    new_post.reply(chunk)
                    time.sleep(5)
            else:
                new_post.reply(comment_body)

        newly_copied_post_ids.append(submission.id)
        print(f"Copied post {submission.id}: {submission.title}")
        # Respect Reddit API Limit
        time.sleep(10)
    # Log exceptions
    except (RequestException, ResponseException, RedditAPIException) as ex:
        logging.error(f"Error for post {submission.id}: {str(ex)}")
    except Exception as e:
        logging.error(f"General error for post {submission.id}: {str(e)}")
    # Cleanup downloaded media
    for img in gallery_images:
        if os.path.exists(img):
            os.remove(img)
    if media_url and os.path.exists(media_url):
        os.remove(media_url)
    if os.path.exists(audio_file):
        os.remove(audio_file)
    if os.path.exists(merged_file):
        os.remove(merged_file)
        
# Append new post IDs and trim oldest lines
if newly_copied_post_ids:
    try:
        # Load existing IDs
        if os.path.exists(PROCESSED_FILE):
            with open(PROCESSED_FILE, "r") as file:
                existing_ids = file.read().splitlines()
        else:
            existing_ids = []

        # Append new IDs
        combined_ids = existing_ids + newly_copied_post_ids

        # Trim to last MAX_PROCESSED_IDS entries
        if len(combined_ids) > MAX_PROCESSED_IDS:
            combined_ids = combined_ids[-MAX_PROCESSED_IDS:]

        # Save updated list
        with open(PROCESSED_FILE, "w") as file:
            file.write('\n'.join(combined_ids) + '\n')
    except Exception as e:
        logging.error(f"Failed to update processed_posts.txt: {str(e)}")
