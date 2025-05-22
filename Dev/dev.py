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

# Set up logging
logging.basicConfig(filename='/home/ubuntu/Reddit-UFOs_Archive/Dev/error_log.txt', level=logging.ERROR,
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

# File to store processed post IDs
PROCESSED_FILE = "/home/ubuntu/Reddit-UFOs_Archive/Dev/processed_posts.txt"

# Start Definitions
def merge_video_audio(video_path, audio_url, output_path='merged_video.mp4'):
    audio_path = 'media_audio.mp4'
    # Download audio
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(audio_url, stream=True, headers=headers)
    if response.status_code == 200:
        with open(audio_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                f.write(chunk)
    else:
        logging.error(f"Failed to download audio from {audio_url}. Status code: {response.status_code}")
        return video_path  # fallback to video only

    # Merge with ffmpeg (stream copy)
    try:
        result = subprocess.run([
            'ffmpeg', '-y',
            '-i', video_path,
            '-i', audio_path,
            '-c', 'copy',
            '-movflags', '+faststart',
            output_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode != 0:
            logging.error(f"ffmpeg error: {result.stderr.decode()}")
            return video_path
        return output_path
    except Exception as e:
        logging.error(f"ffmpeg merge exception: {e}")
        return video_path
        
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

    response = requests.get(url, stream=True, headers=headers)
    if response.status_code == 200:
        with open(file_name, 'wb') as out_file:
            for chunk in response.iter_content(chunk_size=1024):
                out_file.write(chunk)
        return file_name
    else:
        logging.error(f"Failed to download media from {url}. Status code: {response.status_code}")
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

# Improved get_audio_url to reliably get audio from dash_url or fallback
def get_audio_url(submission):
    reddit_video = submission.media.get('reddit_video', {})
    dash_url = reddit_video.get('dash_url')
    if dash_url:
        base_url = dash_url.rsplit('/', 1)[0]
        return f"{base_url}/DASH_audio.mp4"
    if "v.redd.it" in submission.url:
        base_url = submission.url.rsplit('/', 1)[0]
        return f"{base_url}/DASH_audio.mp4"
    return None

# Subreddits
source_subreddit = source_reddit.subreddit('ufos')
destination_subreddit = archives_reddit.subreddit('SaltyDevSub')

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

# Fetch new posts
for submission in source_subreddit.new():
    try:
        logging.info(f"Processing submission: {submission.title}, Flair: {submission.link_flair_text}, Created: {submission.created_utc}")
        audio_url = None
        merged_audio = False  # Flag to track if audio was merged

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
        elif not is_self_post:
            if submission.url.endswith(('jpg', 'jpeg', 'png', 'gif')):
                file_name = submission.url.split('/')[-1]
                media_url = download_media(submission.url, file_name)
                original_media_url = submission.url
            elif 'v.redd.it' in submission.url and submission.media:
                reddit_video = submission.media.get('reddit_video', {})
                video_url = reddit_video.get('fallback_url')
                has_audio = reddit_video.get('has_audio', False)
                is_gif = reddit_video.get('is_gif', False)

                if video_url:
                    file_name = 'media_video.mp4'
                    media_url = download_media(video_url, file_name)
                    original_media_url = video_url

                    if has_audio and not is_gif:
                        audio_url = get_audio_url(submission)
                        if media_url and audio_url:
                            merged_path = merge_video_audio(media_url, audio_url)
                            if os.path.exists(merged_path):
                                logging.info(f"Successfully merged video and audio into {merged_path}")
                                media_url = merged_path  # Replace original media_url with merged file
                                merged_audio = True
                            else:
                                logging.error("Merged video not found after ffmpeg run")

        new_post = None
        source_flair_text = submission.link_flair_text

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

        if new_post:
            comment_body = f"**Original post by u/:** [Here](https://www.reddit.com{submission.permalink})\n"
            comment_body += f"\n**Original Post ID:** {submission.id}"
            if original_media_url:
                comment_body += f"\n\n**Direct link to media:** [Media Here]({original_media_url})"
            # Only add audio link if audio was NOT merged into video
            if audio_url and not merged_audio:
                comment_body += f"\n\n**Direct link to Audio:** [Audio Here]({audio_url})"
            if submission.selftext:
                comment_body += f"\n\n**Original post text:** {submission.selftext}"
                comment_body += "\n\n---\n\n"                
                # Add flair ID if available
            if hasattr(submission, 'link_flair_template_id'):
                comment_body += f"\n\n**Original Flair ID:** {submission.link_flair_template_id}\n"
            if submission.link_flair_text:
                comment_body += f"\n**Original Flair Text:** {submission.link_flair_text}"

            if len(comment_body) > 10000:
                for chunk in split_text(comment_body):
                    new_post.reply(chunk)
                    time.sleep(5)
            else:
                new_post.reply(comment_body)

        save_processed_post(submission.id)
        print(f"Copied post {submission.id}: {submission.title}")
        time.sleep(10)

    except (RequestException, ResponseException, RedditAPIException) as ex:
        logging.error(f"Error for post {submission.id}: {str(ex)}")
    except Exception as e:
        logging.error(f"General error for post {submission.id}: {str(e)}")

    for img in gallery_images:
        if os.path.exists(img):
            os.remove(img)
    if media_url and os.path.exists(media_url):
        os.remove(media_url)
    if os.path.exists('media_audio.mp4'):
        os.remove('media_audio.mp4')
    if os.path.exists('merged_video.mp4') and media_url != 'merged_video.mp4':
        os.remove('merged_video.mp4')
