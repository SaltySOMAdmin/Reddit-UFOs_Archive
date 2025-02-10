import praw
import time
import logging
from datetime import datetime, timedelta, timezone
from prawcore.exceptions import RequestException, ResponseException, NotFound
from praw.exceptions import RedditAPIException
import config  # Import the config file with credentials
import re

# Set up logging
logging.basicConfig(filename='/home/ubuntu/Reddit-UFOs_Archive/removed_posts_log.txt', level=logging.DEBUG, 
                    format='%(asctime)s %(levelname)s: %(message)s')

# Reddit API credentials
reddit = praw.Reddit(
    client_id=config.destination_client_id,
    client_secret=config.destination_client_secret,
    password=config.destination_password,
    username=config.destination_username,
    user_agent=config.destination_user_agent
)

# Destination subreddit
destination_subreddit = reddit.subreddit('UFOs_Archive')

# Get current time and calculate cutoff for the last 24 hours
current_time = datetime.now(timezone.utc)
cutoff_time = current_time - timedelta(days=1)

logging.info("Starting script: Checking posts from the last 24 hours.")

# Check posts in /r/UFOs_Archive
for archived_submission in destination_subreddit.new(limit=1000):  # Adjust limit if needed
    try:
        post_time = datetime.fromtimestamp(archived_submission.created_utc, timezone.utc)
        if post_time < cutoff_time:
            logging.debug(f"Skipping older post: {archived_submission.id}")
            break  # Stop processing older posts

        logging.info(f"Checking archived post: {archived_submission.id} - {archived_submission.title}")

        # Ensure all comments are loaded
        archived_submission.comments.replace_more(limit=0)

        for comment in archived_submission.comments:
            match = re.search(r'\[Here\]\((https://www\.reddit\.com/r/ufos/comments/[^)]+)\)', comment.body)
            if match:
                original_post_url = match.group(1)
                original_post_id = original_post_url.split("/")[-2]

                logging.debug(f"Found original post link: {original_post_url}")

                try:
                    original_submission = reddit.submission(id=original_post_id)
                    time.sleep(2)  # Slight rate limit handling after fetching submission
                    
                    # **Check multiple conditions for removal**
                    if (
                        original_submission.removed_by_category is not None or  # Mod removed
                        original_submission.selftext == "[deleted]" or  # User deleted (self-posts)
                        original_submission.author is None  # User deleted (all post types)
                    ):
                        logging.info(f"Marking archived post {archived_submission.id} as removed.")
                        archived_submission.mod.flair(text="Removed")
                        logging.info(f"Updated flair for archived post: {archived_submission.id}")
                        break  # Stop checking once updated
                    else:
                        logging.debug(f"Original post still exists: {original_post_id}")
                except NotFound:
                    logging.info(f"Original post {original_post_id} not found, marking archived post as removed.")
                    archived_submission.mod.flair(text="Removed")
                    break
                except Exception as e:
                    logging.error(f"Error fetching original post {original_post_id}: {str(e)}")

        time.sleep(5)  # Rate limit handling after each post check
    
    except (RequestException, ResponseException, RedditAPIException) as ex:
        logging.error(f"Reddit API error for archived post {archived_submission.id}: {str(ex)}")
    except Exception as e:
        logging.error(f"General error for archived post {archived_submission.id}: {str(e)}")

logging.info("Script execution completed.")
