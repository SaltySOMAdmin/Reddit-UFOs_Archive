import praw
import time
import logging
from datetime import datetime, timedelta, timezone
from prawcore.exceptions import RequestException, ResponseException
from praw.exceptions import RedditAPIException
import config  # Import the config file with credentials
import re

# Set up logging
logging.basicConfig(filename='removed_posts_log.txt', level=logging.INFO, 
                    format='%(asctime)s %(levelname)s: %(message)s')

# Reddit API credentials
reddit = praw.Reddit(
    client_id=config.source_client_id,
    client_secret=config.source_client_secret,
    password=config.source_password,
    username=config.source_username,
    user_agent=config.source_user_agent
)

# Destination subreddit
destination_subreddit = reddit.subreddit('UFOs_Archive')

# Check posts in /r/UFOs_Archive
for archived_submission in destination_subreddit.new(limit=1000):  # Adjust limit if needed
    try:
        for comment in archived_submission.comments:
            match = re.search(r'\[Here\]\((https://www\.reddit\.com/r/ufos/comments/[^)]+)\)', comment.body)
            if match:
                original_post_url = match.group(1)
                original_post_id = original_post_url.split("/")[-2]
                
                original_submission = reddit.submission(id=original_post_id)
                if original_submission.banned_by or original_submission.selftext == "[deleted]":
                    archived_submission.mod.flair(text="Removed")
                    logging.info(f"Updated flair for archived post: {archived_submission.id}")
                    break  # Stop checking once updated
        
        time.sleep(5)  # Rate limit handling
    
    except (RequestException, ResponseException, RedditAPIException) as ex:
        logging.error(f"Reddit API error for archived post {archived_submission.id}: {str(ex)}")
    except Exception as e:
        logging.error(f"General error for archived post {archived_submission.id}: {str(e)}")
