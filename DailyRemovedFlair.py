import praw
import time
import logging
from datetime import datetime, timedelta, timezone
from prawcore.exceptions import RequestException, ResponseException
from praw.exceptions import RedditAPIException
import config  # Import the config file with credentials

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

# Source and destination subreddits
source_subreddit = reddit.subreddit('ufos')
destination_subreddit = reddit.subreddit('UFOs_Archive')

# Get current time and calculate cutoff for the last 24 hours
current_time = datetime.now(timezone.utc)
cutoff_time = current_time - timedelta(days=1)

# Scan posts from the last day
for submission in source_subreddit.new(limit=1000):  # Adjust limit if needed
    try:
        post_time = datetime.fromtimestamp(submission.created_utc, timezone.utc)
        if post_time < cutoff_time:
            break  # Stop processing older posts
        
        # Check if the post was removed by a mod
        if submission.banned_by:  # None if not removed by a mod
            logging.info(f"Removed post found: {submission.title} ({submission.id})")
            
            # Search for the corresponding post in the archive
            for archived_submission in destination_subreddit.new(limit=1000):
                if archived_submission.title == submission.title:
                    archived_submission.mod.flair(text="Removed")
                    logging.info(f"Updated flair for archived post: {archived_submission.id}")
                    break  # Stop searching once found
        
        time.sleep(5)  # Rate limit handling
    
    except (RequestException, ResponseException, RedditAPIException) as ex:
        logging.error(f"Reddit API error for post {submission.id}: {str(ex)}")
    except Exception as e:
        logging.error(f"General error for post {submission.id}: {str(e)}")
