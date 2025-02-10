import praw
import time
import logging
from datetime import datetime, timedelta, timezone
from prawcore.exceptions import RequestException, ResponseException, NotFound
from praw.exceptions import RedditAPIException
import config  # Import the config file with credentials
import re

# Set up logging
logging.basicConfig(filename='removed_posts_log.txt', level=logging.DEBUG, 
                    format='%(asctime)s %(levelname)s: %(message)s')

# Reddit API credentials
reddit = praw.Reddit(
    client_id=config.destination_client_id,
    client_secret=config.destination_client_secret,
    password=config.destination_password,
    username=config.destination_username,
    user_agent=config.destination_user_agent
)

# Source and destination subreddits
source_subreddit = reddit.subreddit('UFOs')
destination_subreddit = reddit.subreddit('UFOs_Archive')

# Get current time and calculate cutoff for the last 24 hours
current_time = datetime.now(timezone.utc)
cutoff_time = current_time - timedelta(days=1)

logging.info("Starting script: Checking posts from the last 24 hours.")

try:
    for archived_post in destination_subreddit.new(limit=100):  # Adjust limit as needed
        if archived_post.created_utc < cutoff_time.timestamp():
            continue
        
        source_post = None
        for post in source_subreddit.search(archived_post.title, sort='new', time_filter='week'):
            if post.title == archived_post.title:
                source_post = post
                break

        if source_post and source_post.link_flair_text:
            try:
                archived_post.mod.flair(text=source_post.link_flair_text)
                logging.info(f"Updated flair for archived post: {archived_post.title}")
            except RedditAPIException as e:
                logging.error(f"Failed to set flair for post {archived_post.id}: {e}")
        else:
            logging.info(f"No matching source post found or no flair present for: {archived_post.title}")

except (RequestException, ResponseException, NotFound) as e:
    logging.error(f"Error fetching posts: {e}")