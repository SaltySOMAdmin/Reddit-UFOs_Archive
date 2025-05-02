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
logging.basicConfig(
    filename='/home/ubuntu/Reddit-UFOs_Archive/error_log.txt',
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s'
)

# Reddit API credentials for /r/ufos (source, moderator account)
source_reddit = praw.Reddit(
    client_id=config.source_client_id,
    client_secret=config.source_client_secret,
    password=config.source_password,
    username=config.source_username,
    user_agent=config.source_user_agent
)

# Reddit API credentials for /r/UFOs_Archive (destination, bot account)
destination_reddit = praw.Reddit(
    client_id=config.destination_client_id,
    client_secret=config.destination_client_secret,
    password=config.destination_password,
    username=config.destination_username,
    user_agent=config.destination_user_agent
)

# Subreddits
source_subreddit = source_reddit.subreddit('ufos')
destination_subreddit = destination_reddit.subreddit('UFOs_Archive')

# Get current time and calculate cutoff for the last 16 hours
current_time = datetime.now(timezone.utc)
cutoff_time = current_time - timedelta(hours=16)

# List of removal flair texts in /r/ufos (for redundancy)
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

# List of removal flair IDs in /r/ufos
removal_flair_ids = [
    "7b14f2ce-cfbf-11eb-89f4-0e476f3d9d3d",  # Rule 1: Follow the Standards of Civility
    "80d51022-cfbf-11eb-abbc-0ef931b77cdb",  # Rule 2: Posts must be on-topic
    "85ced3d8-cfbf-11eb-9eab-0e63e592d261",  # Rule 3: Be substantive
    "8b9f15e8-cfbf-11eb-abeb-0ef152a43b0f",  # Rule 4: No duplicate posts
    "909be63e-cfbf-11eb-bbac-0ede7dbb605d",  # Rule 5: No commercial activity
    "95d860aa-cfbf-11eb-a918-0e7f2c8d7c01",  # Rule 6: Bad title
    "cf3b5fa8-df66-11eb-bce8-0e4db6ae439b",  # Rule 7: Posting limits
    "fd60122a-df66-11eb-93ed-0e956b4f6669",  # Rule 8: No memes
    "643158c8-b0c3-11ec-8fad-0a0cedfa08f2",  # Rule 9: Link posts must include a submission statement
    "597ab2f2-200e-11ed-81e1-ca42d471553b",  # Rule 11: Common Questions
    "9af1649c-cfbf-11eb-b874-0ea1a57cb45d",  # Posting Guidelines for Sightings
    "434058ea-df67-11eb-af98-0eaea14e6779",  # Better suited for the current megathread
    "13d3b30c-94ad-11ed-b87c-bad73d311b50",  # Rule 12: Meta-posts must be posted in r/ufosmeta
    "ce8f9fd6-ff69-11ed-862a-4adf08bd01f6",  # Rule 13: Low effort comments regarding public figures
    "dd02bab2-ff69-11ed-9d19-2648400e7657"   # Rule 14: Off-topic political discussion
]

# Flair ID for "Removed" in /r/UFOs_Archive
removed_flair_id = "2aae3c82-e59b-11ef-82e4-264414cc8e5f"

REQUEST_DELAY = 1.0  # Adjust if rate limits are hit
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
def fetch_submission(reddit, submission_id):
    return reddit.submission(id=submission_id)

print("Starting script: Checking posts from the last 16 hours.")

# Check posts in /r/UFOs_Archive
for archived_submission in destination_subreddit.new(limit=200):
    try:
        post_time = datetime.fromtimestamp(archived_submission.created_utc, timezone.utc)
        if post_time < cutoff_time:
            logging.debug(f"Skipping older post: {archived_submission.id}")
            break  # Stop processing older posts

        logging.debug(f"Checking archived post: {archived_submission.id} - {archived_submission.title}")

        # Ensure all comments are loaded
        archived_submission.comments.replace_more(limit=0)
        original_post_id = None

        # Search for original post ID in comments
        for comment in archived_submission.comments:
            if comment.author and comment.author.name == config.destination_username:  # Ensure comment is from bot
                match = re.search(r'\*\*Original Post ID:\*\* ([a-z0-9]+)', comment.body)
                if match:
                    original_post_id = match.group(1)
                    logging.debug(f"Extracted original post ID: {original_post_id}")
                    break

        if not original_post_id:
            logging.warning(f"No original post ID found for archived post: {archived_submission.id}")
            continue

        try:
            # Fetch the original post in /r/ufos using moderator credentials
            original_submission = fetch_submission(source_reddit, original_post_id)
            wait_if_needed()

            # Check if post is removed, deleted, or has a removal flair
            is_removed = (
                original_submission.removed_by_category is not None or
                original_submission.selftext == "[deleted]" or
                original_submission.selftext == "[removed]" or
                (original_submission.link_flair_text and original_submission.link_flair_text in removal_flairs) or
                (original_submission.link_flair_template_id and original_submission.link_flair_template_id in removal_flair_ids) or
                not original_submission.author  # Author deleted or banned
            )

            if is_removed:
                archived_submission.mod.flair(flair_template_id=removed_flair_id)
                logging.info(f"Updated flair to 'Removed' for archived post: {archived_submission.id}")
                print(f"Updated flair to 'Removed' for archived post: {archived_submission.title}")
            else:
                logging.debug(f"Original post still exists: {original_post_id}")

        except NotcıFound:
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