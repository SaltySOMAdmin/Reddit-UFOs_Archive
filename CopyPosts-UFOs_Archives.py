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

# Set up logging (changed to INFO to capture more details)
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

# File to store processed post IDs
PROCESSED_FILE = "/home/ubuntu/Reddit-UFOs_Archive/processed_posts.txt"

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

    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, stream=True, headers=headers, timeout=10)
        if response.status_code == 200:
            with open(file_name, 'wb') as out_file:
                for chunk in response.iter_content(chunk_size=1024):
                    out_file.write(chunk)
            return file_name
        else:
            logging.warning(f"Failed to download media from {url}. Status code: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        logging.warning(f"Failed to download media from {url}: {str(e)}")
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

def get_audio_url(video_url):
    if "v.redd.it" in video_url:
        base_url = video_url.rsplit('/', 1)[0]
        return f"{base_url}/DASH_audio.mp4"
    return None

# Subreddits
source_subreddit = source_reddit.subreddit('ufos')
destination_subreddit = archives_reddit.subreddit('UFOs_Archive')

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
        logging.info(f"Processing submission: {submission.title}, ID: {submission.id}, Flair: {submission.link_flair_text}, Created: {submission.created_utc}")
        audio_url = None

        if submission.id in processed_posts:
            logging.info(f"Skipping already processed post: {submission.id}")
            continue

        post_time = datetime.fromtimestamp(submission.created_utc, timezone.utc)
        if post_time < cutoff_time:
            logging.info(f"Skipping post {submission.id} older than cutoff time")
            continue

        title = submission.title
        is_self_post = submission.is_self
        media_url = None
        original_media_url = None
        gallery_images = []

        # Log gallery metadata for debugging
        if hasattr(submission, 'is_gallery') and submission.is_gallery:
            logging.info(f"Gallery post metadata - ID: {submission.id}, gallery_data: {getattr(submission, 'gallery_data', None)}, media_metadata: {getattr(submission, 'media_metadata', None)}")

        # Handle gallery posts
        if hasattr(submission, 'is_gallery') and submission.is_gallery:
            if hasattr(submission, 'gallery_data') and submission.gallery_data and 'items' in submission.gallery_data and submission.gallery_data['items']:
                for item in submission.gallery_data['items']:
                    media_id = item.get('media_id')
                    if not media_id or media_id not in submission.media_metadata:
                        logging.warning(f"Invalid or missing media_id {media_id} in gallery item for post {submission.id}")
                        continue
                    meta = submission.media_metadata.get(media_id, {})
                    if 's' in meta and 'u' in meta['s'] and meta.get('status') == 'valid':
                        img_url = meta['s']['u'].split('?')[0].replace("&", "&")
                        ext = os.path.splitext(img_url)[-1] or '.jpg'  # Default to .jpg if no extension
                        file_name = f"{media_id}{ext}"
                        downloaded = download_media(img_url, file_name)
                        if downloaded:
                            gallery_images.append(downloaded)
                        else:
                            logging.warning(f"Failed to download image {img_url} for post {submission.id}")
                    else:
                        logging.warning(f"Invalid media metadata for media_id {media_id} in post {submission.id}")
            else:
                logging.warning(f"Gallery post {submission.id} has no valid items in gallery_data. Falling back to URL submission.")

        # Handle non-gallery media posts
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
                        audio_url = get_audio_url(submission.url)
            else:
                logging.info(f"Non-media post {submission.id} with URL: {submission.url}")

        # Submit the post with fallback for gallery posts
        new_post = None
        source_flair_text = submission.link_flair_text

        try:
            if is_self_post and submission.selftext:
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
                # Fallback for gallery or media posts: Submit as URL post
                new_post = destination_subreddit.submit(title, url=submission.url)
                logging.info(f"Fallback to URL submission for post {submission.id}")
        except RedditAPIException as e:
            logging.error(f"Failed to submit post {submission.id}: {str(e)}")
            # Fallback: Submit as self-post with metadata
            metadata_body = f"Original URL: {submission.url}\n\nOriginal post text: {submission.selftext or 'N/A'}\n\nError: {str(e)}"
            new_post = destination_subreddit.submit(title, selftext=metadata_body)
            logging.info(f"Fallback to self-post for post {submission.id}")

        # Apply flair if available
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

        # Add comment with all metadata
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
            if hasattr(submission, 'is_gallery') and submission.is_gallery:
                comment_body += f"\n\n**Gallery Data:** {submission.gallery_data or 'N/A'}"
                comment_body += f"\n\n**Media Metadata:** {submission.media_metadata or 'N/A'}"

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
        logging.error(f"API error for post {submission.id}: {str(ex)}")
        # Fallback: Submit as self-post with minimal data
        try:
            new_post = destination_subreddit.submit(
                submission.title,
                selftext=f"Failed to archive post due to API error. Original URL: {submission.url}\nError: {str(ex)}"
            )
            save_processed_post(submission.id)
            print(f"Fallback archived post {submission.id} as self-post due to API error")
        except Exception as e:
            logging.error(f"Failed to archive post {submission.id} even as fallback: {str(e)}")
    except Exception as e:
        logging.error(f"General error for post {submission.id}: {str(e)}")
        # Fallback: Submit as self-post with minimal data
        try:
            new_post = destination_subreddit.submit(
                submission.title,
                selftext=f"Failed to archive post due to error. Original URL: {submission.url}\nError: {str(e)}"
            )
            save_processed_post(submission.id)
            print(f"Fallback archived post {submission.id} as self-post due to general error")
        except Exception as e:
            logging.error(f"Failed to archive post {submission.id} even as fallback: {str(e)}")

    # Clean up downloaded files
    for img in gallery_images:
        if os.path.exists(img):
            os.remove(img)
    if media_url and os.path.exists(media_url):
        os.remove(media_url)