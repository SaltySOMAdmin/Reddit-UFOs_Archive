import praw
import requests
import os
import time
import logging
from datetime import datetime, timedelta, timezone
from prawcore.exceptions import RequestException, ResponseException
from praw.exceptions import RedditAPIException
import config  # Import the config file with credentials

# Set up logging
logging.basicConfig(filename='error_log.txt', level=logging.ERROR, 
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
PROCESSED_FILE = "/home/ubuntu/sightings_backup/Reddit-UFOs_Archive/processed_posts.txt"

def load_processed_posts():
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, "r") as file:
            return set(file.read().splitlines())
    return set()

def save_processed_post(post_id):
    with open(PROCESSED_FILE, "a") as file:
        file.write(post_id + "\n")

def download_media(url, file_name):
    response = requests.get(url, stream=True)
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

# Source subreddit
source_subreddit = source_reddit.subreddit('ufos')
# Destination subreddit
destination_subreddit = archives_reddit.subreddit('UFOs_Archive')

# Get current time and calculate cutoff
current_time = datetime.now(timezone.utc)
cutoff_time = current_time - timedelta(minutes=19)

processed_posts = load_processed_posts()

# Fetch new posts
for submission in source_subreddit.new():
    try:
        logging.info(f"Processing submission: {submission.title}, Flair: {submission.link_flair_text}, Created: {submission.created_utc}")
        
        if submission.id in processed_posts:
            continue  # Skip already processed posts

        post_time = datetime.fromtimestamp(submission.created_utc, timezone.utc)
        if post_time < cutoff_time:
            continue

        title = submission.title
        is_self_post = submission.is_self
        media_url = None
        original_media_url = None

        # Handle media posts (images or videos)
        if not is_self_post:
            if submission.url.endswith(('jpg', 'jpeg', 'png', 'gif')):
                file_name = submission.url.split('/')[-1]
                media_url = download_media(submission.url, file_name)
                original_media_url = submission.url
            elif 'v.redd.it' in submission.url and submission.media:
                video_url = submission.media['reddit_video']['fallback_url']
                file_name = 'video.mp4'
                media_url = download_media(video_url, file_name)
                original_media_url = video_url

        new_post = None
        # Repost to the destination subreddit
        if is_self_post:
            new_post = destination_subreddit.submit(title, selftext=submission.selftext)
        elif media_url and os.path.exists(media_url) and os.path.getsize(media_url) > 0:
            if media_url.endswith(('jpg', 'jpeg', 'png', 'gif')):
                new_post = destination_subreddit.submit_image(title, image_path=media_url, flair_id=None)
            elif media_url.endswith('mp4'):
                new_post = destination_subreddit.submit_video(title, video_path=media_url, flair_id=None)
        else:
            new_post = destination_subreddit.submit(title, url=submission.url)

        # Comment on the new post
        if new_post:
            comment_body = f"Original post by u/{submission.author}: [Here]({submission.permalink})"
            if original_media_url:
                comment_body += f"\n\nDirect link to media: [Media Here]({original_media_url})"
            if submission.selftext:
                comment_body += f"\n\nOriginal post text: {submission.selftext}"
            
            # Check if the comment body is too long
            if len(comment_body) > 10000:
                chunks = split_text(comment_body)
                for chunk in chunks:
                    new_post.reply(chunk)
                    time.sleep(5)
            else:
                new_post.reply(comment_body)

        # Save the processed post ID
        save_processed_post(submission.id)

        print(f"Copied post: {submission.title}")
        time.sleep(10)
    
    except (RequestException, ResponseException, RedditAPIException) as ex:
        logging.error(f"Error for post {submission.id}: {str(ex)}")
    except Exception as e:
        logging.error(f"General error for post {submission.id}: {str(e)}")

    # Clean up downloaded media files
    if media_url and os.path.exists(media_url):
        os.remove(media_url)
