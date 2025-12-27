import praw
import requests
import os
import time
import logging
import sys
import re
from datetime import datetime, timezone
from prawcore.exceptions import RequestException, ResponseException
from praw.exceptions import RedditAPIException
import config
import subprocess
import shutil

# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------
logging.basicConfig(
    filename='/home/ubuntu/Reddit-UFOs_Archive/error_log.txt',
    level=logging.ERROR,
    format='%(asctime)s %(levelname)s: %(message)s'
)

# ------------------------------------------------------------
# Reddit API
# ------------------------------------------------------------
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

source_subreddit = source_reddit.subreddit('ufos')
destination_subreddit = archives_reddit.subreddit('UFOs_Archive')

# ------------------------------------------------------------
# Paths / Constants
# ------------------------------------------------------------
MEDIA_DOWNLOAD_DIR = "/home/ubuntu/Reddit-UFOs_Archive/temp_media"
PROCESSED_FILE = "/home/ubuntu/Reddit-UFOs_Archive/processed_posts.txt"
MAX_PROCESSED_IDS = 2000

os.makedirs(MEDIA_DOWNLOAD_DIR, exist_ok=True)

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def get_post_id():
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <post_id>")
        sys.exit(1)
    return sys.argv[1]

def download_media(url, file_name):
    if "preview.redd.it" in url:
        url = url.replace("preview.redd.it", "i.redd.it")

    headers = {'User-Agent': 'Mozilla/5.0'}
    full_path = os.path.join(MEDIA_DOWNLOAD_DIR, file_name)

    resp = requests.get(url, stream=True, headers=headers)
    if resp.status_code == 200:
        with open(full_path, 'wb') as f:
            for chunk in resp.iter_content(1024):
                f.write(chunk)
        return full_path

    logging.error(f"Failed to download media: {url}")
    return None

def split_text(text, max_length=10000):
    chunks = []
    while len(text) > max_length:
        idx = text.rfind("\n", 0, max_length)
        if idx == -1:
            idx = max_length
        chunks.append(text[:idx])
        text = text[idx:].lstrip()
    chunks.append(text)
    return chunks

def get_audio_url_from_fallback(video_url):
    if not video_url:
        return None
    return video_url.rsplit('/', 1)[0] + "/CMAF_AUDIO_64.mp4"

def update_processed_posts(post_id):
    try:
        existing_ids = []
        if os.path.exists(PROCESSED_FILE):
            with open(PROCESSED_FILE, "r") as f:
                existing_ids = f.read().splitlines()

        all_ids = existing_ids + [post_id]

        seen = set()
        unique_ids = [x for x in all_ids if not (x in seen or seen.add(x))]

        if len(unique_ids) > MAX_PROCESSED_IDS:
            unique_ids = unique_ids[-MAX_PROCESSED_IDS:]

        temp_path = PROCESSED_FILE + ".tmp"
        with open(temp_path, "w") as f:
            f.write("\n".join(unique_ids) + "\n")

        os.replace(temp_path, PROCESSED_FILE)
        logging.info(f"Added {post_id} to processed_posts.txt")

    except Exception as e:
        logging.error(f"Failed to update processed_posts.txt: {e}")

# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
post_id = get_post_id()
submission = source_reddit.submission(id=post_id)

video_url = None
audio_url = None
dash_url = None
media_url = None
original_media_url = None
gallery_images = []

video_file = os.path.join(MEDIA_DOWNLOAD_DIR, 'media_video.mp4')
audio_file = os.path.join(MEDIA_DOWNLOAD_DIR, 'media_audio.mp4')
merged_file = os.path.join(MEDIA_DOWNLOAD_DIR, 'merged_video.mp4')

try:
    logging.info(f"Processing single submission {submission.id}")

    title = submission.title
    is_self_post = submission.is_self

    # --------------------------------------------------------
    # Gallery handling
    # --------------------------------------------------------
    if hasattr(submission, 'is_gallery') and submission.is_gallery:
        for item in submission.gallery_data['items']:
            media_id = item['media_id']
            meta = submission.media_metadata.get(media_id, {})

            if meta.get("status") != "valid":
                continue

            img_url = None

            if meta.get('e') == 'Image' and 's' in meta:
                img_url = meta['s']['u'].split('?')[0]

            elif meta.get('e') == 'AnimatedImage' and 's' in meta:
                img_url = meta['s'].get('gif') or meta['s'].get('mp4')

            elif meta.get('e') == 'RedditVideo':
                dash_url = meta.get('dashUrl')
                if dash_url:
                    for res in ("1080", "720", "480"):
                        test = dash_url.replace("DASHPlaylist.mpd", f"DASH_{res}.mp4")
                        if requests.head(test).status_code == 200:
                            img_url = test
                            break

                if not img_url and submission.media and 'reddit_video' in submission.media:
                    img_url = submission.media['reddit_video'].get('fallback_url')

            if img_url:
                ext = os.path.splitext(img_url.split("?")[0])[-1]
                downloaded = download_media(img_url, f"{media_id}{ext}")
                if downloaded:
                    gallery_images.append(downloaded)

    # --------------------------------------------------------
    # media_metadata video
    # --------------------------------------------------------
    elif submission.media_metadata:
        for meta in submission.media_metadata.values():
            if meta.get('e') == 'RedditVideo' and 'dashUrl' in meta:
                dash_url = meta['dashUrl']
                for res in ("1080", "720", "480"):
                    test = dash_url.replace("DASHPlaylist.mpd", f"DASH_{res}.mp4")
                    if requests.head(test).status_code == 200:
                        video_url = test
                        break

                if not video_url and submission.media:
                    video_url = submission.media['reddit_video'].get('fallback_url')

                has_audio = True
                is_gif = meta.get('isGif', False)
                original_media_url = video_url
                break

    # --------------------------------------------------------
    # reddit_video
    # --------------------------------------------------------
    elif submission.media and 'reddit_video' in submission.media:
        rv = submission.media['reddit_video']
        video_url = rv.get('fallback_url')
        has_audio = rv.get('has_audio', False)
        is_gif = rv.get('is_gif', False)
        original_media_url = video_url
        dash_url = rv.get('dash_url') or rv.get('dashUrl')

    # --------------------------------------------------------
    # Direct image
    # --------------------------------------------------------
    elif submission.url.endswith(('jpg', 'jpeg', 'png', 'gif')):
        media_url = download_media(submission.url, os.path.basename(submission.url))
        original_media_url = submission.url

    # --------------------------------------------------------
    # Video processing
    # --------------------------------------------------------
    if video_url:
        if has_audio and not is_gif:
            audio_url = get_audio_url_from_fallback(video_url)
            if audio_url:
                try:
                    subprocess.run(
                        ["ffmpeg", "-y", "-loglevel", "error",
                         "-i", video_url, "-i", audio_url,
                         "-c", "copy", merged_file],
                        check=True
                    )
                    media_url = merged_file
                except subprocess.CalledProcessError:
                    media_url = download_media(video_url, "media_video.mp4")
        else:
            media_url = download_media(video_url, "media_video.mp4")

    # --------------------------------------------------------
    # Submit
    # --------------------------------------------------------
    if is_self_post:
        new_post = destination_subreddit.submit(title, selftext=submission.selftext)
    elif gallery_images:
        if len(gallery_images) >= 2:
            new_post = destination_subreddit.submit_gallery(
                title, images=[{'image_path': p} for p in gallery_images]
            )
        else:
            new_post = destination_subreddit.submit_image(title, image_path=gallery_images[0])
    elif media_url and os.path.exists(media_url):
        if media_url.endswith('mp4'):
            new_post = destination_subreddit.submit_video(title, video_path=media_url)
        else:
            new_post = destination_subreddit.submit_image(title, image_path=media_url)
    else:
        new_post = destination_subreddit.submit(title, url=submission.url)

    # --------------------------------------------------------
    # Flair
    # --------------------------------------------------------
    if submission.link_flair_text:
        for flair in destination_subreddit.flair.link_templates:
            if flair['text'] == submission.link_flair_text:
                new_post.flair.select(flair['id'])
                break

    # --------------------------------------------------------
    # Comment
    # --------------------------------------------------------
    body = (
        f"**Original post by u/{submission.author}:** "
        f"[Here](https://www.reddit.com{submission.permalink})\n\n"
        f"**Original Post ID:** {submission.id}"
    )

    if original_media_url:
        body += f"\n\n**Direct link to media:** [Media Here]({original_media_url})"
    if audio_url:
        body += f"\n\n**Direct link to Audio:** [Audio Here]({audio_url})"
    if submission.selftext:
        body += f"\n\n**Original post text:** {submission.selftext}\n\n---"

    for chunk in split_text(body):
        new_post.reply(chunk)
        time.sleep(5)

    # --------------------------------------------------------
    # Record processed post
    # --------------------------------------------------------
    update_processed_posts(submission.id)

    print(f"Copied single post {submission.id}: {submission.title}")

except (RequestException, ResponseException, RedditAPIException) as ex:
    logging.error(f"API error for post {submission.id}: {ex}")
except Exception as e:
    logging.error(f"General error for post {submission.id}: {e}")

finally:
    for f in gallery_images:
        if os.path.exists(f):
            os.remove(f)
    for f in (media_url, merged_file, audio_file):
        if f and os.path.exists(f):
            os.remove(f)
