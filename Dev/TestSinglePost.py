import praw
import requests
import os
import re
import logging
from praw.exceptions import RedditAPIException
from prawcore.exceptions import RequestException, ResponseException
import config

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

# Reddit API
reddit = praw.Reddit(
    client_id=config.source_client_id,
    client_secret=config.source_client_secret,
    username=config.source_username,
    password=config.source_password,
    user_agent=config.source_user_agent
)

dest_reddit = praw.Reddit(
    client_id=config.destination_client_id,
    client_secret=config.destination_client_secret,
    username=config.destination_username,
    password=config.destination_password,
    user_agent=config.destination_user_agent
)

submission_id = "1knunoq"
submission = reddit.submission(id=submission_id)
submission_title = submission.title
submission_url = submission.url
is_self_post = submission.is_self
destination_subreddit = dest_reddit.subreddit("SaltyDevSub")

def download_media(url, filename):
    try:
        if "preview.redd.it" in url:
            url = re.sub(r'^https://preview\.redd\.it/([^?]+)\?.*$', r'https://i.redd.it/\1', url)
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, stream=True, headers=headers)
        if r.status_code == 200:
            with open(filename, 'wb') as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)
            return filename
        else:
            logging.error(f"Failed to download {url}, status code: {r.status_code}")
    except Exception as e:
        logging.error(f"Exception downloading media: {str(e)}")
    return None

try:
    logging.info(f"Fetching post: {submission_title}")

    new_post = None
    media_path = None
    corrected_url = submission_url

    if "preview.redd.it" in submission_url:
        corrected_url = re.sub(r'^https://preview\.redd\.it/([^?]+)\?.*$', r'https://i.redd.it/\1', submission_url)

    if is_self_post:
        new_post = destination_subreddit.submit(submission_title, selftext=submission.selftext)
    elif corrected_url.endswith(('jpg', 'jpeg', 'png', 'gif')):
        file_name = corrected_url.split('/')[-1]
        media_path = download_media(corrected_url, file_name)
        if media_path:
            new_post = destination_subreddit.submit_image(submission_title, image_path=media_path)
    else:
        new_post = destination_subreddit.submit(submission_title, url=submission_url)

    if new_post:
        comment = f"Original post: [Link](https://reddit.com/{submission_id})"
        if submission.selftext:
            comment += f"\n\n---\n\n{submission.selftext}"
        new_post.reply(comment)
        logging.info(f"Posted: {new_post.id}")
    if media_path and os.path.exists(media_path):
        os.remove(media_path)

except (RedditAPIException, RequestException, ResponseException) as e:
    logging.error(f"Reddit API error: {str(e)}")
except Exception as e:
    logging.error(f"General error: {str(e)}")
