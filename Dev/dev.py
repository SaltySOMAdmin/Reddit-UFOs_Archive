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
try:
    from RedDownloader import RedDownloader
except ImportError:
    logging.error("Failed to import RedDownloader. Falling back to video-only download.")
    RedDownloader = None

# Set up logging
logging.basicConfig(
    filename='/home/ubuntu/Reddit-UFOs_Archive/Dev/error_log.txt',
    level=logging.INFO,  # Changed to INFO to log RedDownloader results
    format='%(asctime)s %(levelname)s: %(message)s'
)

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
destination_subreddit = archives_reddit.subreddit('SaltyDevSub')

# File to store processed post IDs
PROCESSED_FILE = "/home/ubuntu/Reddit-UFOs_Archive/Dev/processed_posts.txt"
MEDIA_DIR = "/home/ubuntu/Reddit-UFOs_Archive/Dev/media"

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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, stream=True, headers=headers, timeout=10)
        if response.status_code == 200:
            with open(file_name, 'wb') as out_file:
                for chunk in response.iter_content(chunk_size=1024):
                    out_file.write(chunk)
            logging.info(f"Downloaded media from {url} to {file_name}")
            return file_name
        else:
            logging.error(f"Failed to download media from {url}. Status code: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"Error downloading media from {url}: {str(e)}")
        return None

def download_video_with_reddownloader(submission, file_name):
    if not RedDownloader:
        logging.info(f"RedDownloader not available for {submission.id}")
        return None
    try:
        os.makedirs(MEDIA_DIR, exist_ok=True)
        downloader = RedDownloader(
            url=f"https://www.reddit.com{submission.permalink}",
            output=MEDIA_DIR,
            filename=submission.id,
            quality="best"
        )
        result = downloader.download()
        output_path = os.path.join(MEDIA_DIR, f"{submission.id}.mp4")
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logging.info(f"RedDownloader downloaded video with audio for {submission.id} to {output_path}")
            return output_path
        else:
            logging.error(f"RedDownloader failed to produce valid file for {submission.id}")
            return None
    except Exception as e:
        logging.error(f"RedDownloader error for {submission.id}: {str(e)}")
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

# Parse time delta from command-line argument
def parse_time_delta(arg):
    if not arg:
        return timedelta(minutes=28)
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
                    file_name = os.path.join(MEDIA_DIR, f"{media_id}{ext}")
                    downloaded = download_media(img_url, file_name)
                    if downloaded:
                        gallery_images.append(downloaded)
        elif not is_self_post:
            if submission.url.endswith(('jpg', 'jpeg', 'png', 'gif')):
                file_name = os.path.join(MEDIA_DIR, submission.url.split('/')[-1])
                media_url = download_media(submission.url, file_name)
                original_media_url = submission.url
            elif 'v.redd.it' in submission.url and submission.media:
                reddit_video = submission.media.get('reddit_video', {})
                video_url = reddit_video.get('fallback_url')
                has_audio = reddit_video.get('has_audio', False)
                is_gif = reddit_video.get('is_gif', False)

                # Try RedDownloader for video with audio
                file_name = os.path.join(MEDIA_DIR, f"{submission.id}.mp4")
                if has_audio and not is_gif and RedDownloader:
                    media_url = download_video_with_reddownloader(submission, file_name)
                    original_media_url = submission.url
                # Fallback to video-only if RedDownloader fails or is unavailable
                if not media_url and video_url:
                    file_name = os.path.join(MEDIA_DIR, "media_video.mp4")
                    media_url = download_media(video_url, file_name)
                    original_media_url = video_url

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
            if submission.selftext:
                comment_body += f"\n\n**Original post text:** {submission.selftext}"
                comment_body += "\n\n---\n\n"
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

    # Cleanup
    for img in gallery_images:
        if os.path.exists(img):
            os.remove(img)
    if media_url and os.path.exists(media_url):
        os.remove(media_url)