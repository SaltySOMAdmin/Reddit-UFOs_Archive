import praw
import time
import logging
from datetime import datetime, timedelta, timezone
from prawcore.exceptions import RequestException, ResponseException, NotFound
from praw.exceptions import RedditAPIException
import config  # Import the config file with credentials
import re

# Set up logging
logging.basicConfig(filename='/home/ubuntu/Reddit-UFOs_Archive/error_log.txt', level=logging.ERROR, 
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

# Get current time and calculate cutoff for the last 8 hours
current_time = datetime.now(timezone.utc)
cutoff_time = current_time - timedelta(hours=12)

print("Starting script: Checking posts from the last 12 hours.")

# List of removal flairs in /r/ufos
removal_flairs = [
    "Rule 1: Follow the Standards of Civility",
    "Rule 2: Posts must be on-topic",
    "Rule 3: Be substantive",
    "Rule 14: Off-topic political discussion",
    "Rule 4: No duplicate posts",
    "Rule 5: No commercial activity",
    "Rule 6: Bad title",
    "Rule 7: Posting limits",
    "Rule 8: No memes",
    "Rule 9: Link posts must include a submission statement",
    "Rule 11: Common Questions",
    "Posting Guidelines for Sightings",
    "Better suited for the current megathread",
    "Rule 12: Meta-posts must be posted in r/ufosmeta",
    "Rule 13: Low effort comments regarding public figures"
]

removed_flair_id = "2aae3c82-e59b-11ef-82e4-264414cc8e5f"

# Check posts in /r/UFOs_Archive
for archived_submission in destination_subreddit.new(limit=200):  # Adjust limit if needed
    try:
        post_time = datetime.fromtimestamp(archived_submission.created_utc, timezone.utc)
        if post_time < cutoff_time:
            logging.debug(f"Skipping older post: {archived_submission.id}")
            break  # Stop processing older posts

        logging.debug(f"Checking archived post: {archived_submission.id} - {archived_submission.title}")

        # Ensure all comments are loaded
        archived_submission.comments.replace_more(limit=0)

        for comment in archived_submission.comments:
            match = re.search(r'\*\*Original Post ID:\*\* `([a-z0-9]+)`', comment.body)
            if match:
                original_post_id = match.group(1)
                logging.debug(f"Extracted original post ID: {original_post_id}")

                try:
                    original_submission = reddit.submission(id=original_post_id)
                    time.sleep(5)  # Rate limit handling after fetching submission

                    if original_submission.removed_by_category or original_submission.selftext == "[deleted]" or (original_submission.link_flair_text and original_submission.link_flair_text in removal_flairs):
                        archived_submission.mod.flair(flair_template_id=removed_flair_id)
                        print(f"Updated flair for archived post: {archived_submission.title}")
                        break  # Stop checking once updated
                    else:
                        logging.debug(f"Original post still exists: {original_post_id}")
                except NotFound:
                    archived_submission.mod.flair(flair_template_id=removed_flair_id)
                    logging.info(f"Original post not found, marking archived post as removed: {archived_submission.id}")
                    print(f"Original post not found, marking archived post as removed: {archived_submission.title}")
                    break
                except Exception as e:
                    logging.error(f"Error fetching original post {original_post_id}: {str(e)}")

        time.sleep(5)  # Rate limit handling after each post check
    
    except (RequestException, ResponseException, RedditAPIException) as ex:
        logging.error(f"Reddit API error for archived post {archived_submission.id}: {str(ex)}")
        print(f"Reddit API error for archived post {archived_submission.id}: {str(ex)}")
    except Exception as e:
        logging.error(f"General error for archived post {archived_submission.id}: {str(e)}")
        print(f"General error for archived post {archived_submission.id}: {str(e)}")
logging.info("Script execution completed.")
print("Script execution completed.")
