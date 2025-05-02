import praw
import time
import logging
from datetime import datetime, timedelta, timezone
from prawcore.exceptions import RequestException, ResponseException, NotFound
from praw.exceptions import RedditAPIException
import config  # Import the config file with credentials
import re
import tenacity

# Set up logging
logging.basicConfig(filename='/home/ubuntu/Reddit-UFOs_Archive/error_log.txt', level=logging.DEBUG, 
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

# Get current time and calculate cutoff for the last 16 hours
current_time = datetime.now(timezone.utc)
cutoff_time = current_time - timedelta(hours=4)

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

REQUEST_DELAY = 1.0  # Reduced slightly for efficiency, adjust if rate limits are hit
last_request_time = 0

def wait_if_needed():
    global last_request_time
    elapsed = time.time() - last_request_time
    if elapsed < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - elapsed)
    last_request_time = time.time()

# Retry decorator for API calls
@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
    retry=tenacity.retry_if_exception_type((RequestException, ResponseException, RedditAPIException)),
    before_sleep=lambda retry_state: logging.warning(f"Retrying API call: attempt {retry_state.attempt_number}")
)
def fetch_submission(submission_id):
    return reddit.submission(id=submission_id)

print("Starting script: Checking posts from the last 16 hours.")

# Check posts in /r/UFOs_Archive
for archived_submission in destination_subreddit.new(limit=200):
    try:
        post_time = datetime.fromtimestamp(archived_submission.created_utc, timezone.utc)
        if post_time < cutoff_time:
            logging.debug(f"Skipping older post: {archived_submission.id}")
            break

        logging.debug(f"Checking archived post: {archived_submission.id} - {archived_submission.title}")

        # Ensure all comments are loaded
        archived_submission.comments.replace_more(limit=0)
        original_post_id = None

        # Search for original post ID in comments
        for comment in archived_submission.comments:
            if comment.author and comment.author.name == config.destination_username:  # Ensure comment is from bot
                match = re.search(r'\*\*Original Post ID:\*\* `([a-z0-9]+)`', comment.body)
                if match:
                    original_post_id = match.group(1)
                    logging.debug(f"Extracted original post ID: {original_post_id}")
                    break

        if not original_post_id:
            logging.warning(f"No original post ID found for archived post: {archived_submission.id}")
            continue

        try:
            original_submission = fetch_submission(original_post_id)
            wait_if_needed()

            # Check if post is removed, deleted, or has a removal flair
            is_removed = (
                original_submission.removed_by_category is not None or
                original_submission.selftext == "[deleted]" or
                original_submission.selftext == "[removed]" or
                (original_submission.link_flair_text and original_submission.link_flair_text in removal_flairs) or
                not original_submission.author  # Author deleted or banned
            )

            if is_removed:
                archived_submission.mod.flair(flair_template_id=removed_flair_id)
                logging.info(f"Updated flair to 'Removed' for archived post: {archived_submission.id}")
                print(f"Updated flair to 'Removed' for archived post: {archived_submission.title}")
            else:
                logging.debug(f"Original post still exists: {original_post_id}")

        except NotFound:
            archived_submission.mod.flair(flair_template_id=removed_flair_id)
            logging.info(f"Original post not found, marked as removed: {archived_submission.id}")
            print(f"Original post not found, marked as removed: {archived_submission.title}")
        except Exception as e:
            logging.error(f"Error fetching original post {original_post_id}: {str(e)}")
            continue

        wait_if_needed()

    except (RequestException, ResponseException, RedditAPIException) as ex:
        logging.error(f"Reddit API error for archived post {archived_submission.id}: {str(ex)}")
        print(f"Reddit API error for archived post {archived_submission.id}: {str(ex)}")
    except Exception as e:
        logging.error(f"General error for archived post {archived_submission.id}: {str(e)}")
        print(f"General error for archived post {archived_submission.id}: {str(e)}")

logging.info("Script execution completed.")
print("Script execution completed.")