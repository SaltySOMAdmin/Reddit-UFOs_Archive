import praw
import time
import logging
from datetime import datetime, timedelta, timezone
from prawcore.exceptions import RequestException, ResponseException, NotFound
from praw.exceptions import RedditAPIException
import config  # Your config file
import re

# Set up logging
logging.basicConfig(filename='/home/ubuntu/Reddit-UFOs_Archive/error_log.txt', level=logging.ERROR,
                    format='%(asctime)s %(levelname)s: %(message)s')

# Reddit API credentials — ***use your MOD credentials to see all flair info***
reddit = praw.Reddit(
    client_id=config.source_client_id,
    client_secret=config.source_client_secret,
    password=config.source_password,
    username=config.source_username,
    user_agent=config.source_user_agent
)

# Destination subreddit
destination_subreddit = reddit.subreddit('UFOs_Archive')

# Get current time and calculate cutoff for the last 16 hours
current_time = datetime.now(timezone.utc)
cutoff_time = current_time - timedelta(hours=16)

print("Starting script: Checking posts from the last 16 hours.")

# List of removal flair IDs from /r/UFOs
removal_flair_ids = [
    "7b14f2ce-cfbf-11eb-89f4-0e476f3d9d3d",  # "Rule 1: Follow the Standards of Civility"
    "80d51022-cfbf-11eb-abbc-0ef931b77cdb",  # "Rule 2: Posts must be on-topic"
    "85ced3d8-cfbf-11eb-9eab-0e63e592d261",  # "Rule 3: Be substantive"
    "8b9f15e8-cfbf-11eb-abeb-0ef152a43b0f",  # "Rule 4: No duplicate posts"
    "909be63e-cfbf-11eb-bbac-0ede7dbb605d",  # "Rule 5: No commercial activity"
    "95d860aa-cfbf-11eb-a918-0e7f2c8d7c01",  # "Rule 6: Bad title"
    "cf3b5fa8-df66-11eb-bce8-0e4db6ae439b",  # "Rule 7: Posting limits"
    "fd60122a-df66-11eb-93ed-0e956b4f6669",  # "Rule 8: No memes"
    "643158c8-b0c3-11ec-8fad-0a0cedfa08f2",  # "Rule 9: Link posts must include a submission statement"
    "597ab2f2-200e-11ed-81e1-ca42d471553b",  # "Rule 11: Common Questions"
    "9af1649c-cfbf-11eb-b874-0ea1a57cb45d",  # "Posting Guidelines for Sightings"
    "434058ea-df67-11eb-af98-0eaea14e6779",  # "Better suited for the current megathread"
    "13d3b30c-94ad-11ed-b87c-bad73d311b50",  # "Rule 12: Meta-posts must be posted in r/ufosmeta"
    "ce8f9fd6-ff69-11ed-862a-4adf08bd01f6",  # "Rule 13: Low effort comments regarding public figures"
    "dd02bab2-ff69-11ed-9d19-2648400e7657"  # "Rule 14: Off-topic political discussion"
]

removed_flair_id = "2aae3c82-e59b-11ef-82e4-264414cc8e5f"  # Archive flair ID for removed posts

# Check posts in /r/UFOs_Archive
for archived_submission in destination_subreddit.new(limit=200):
    try:
        post_time = datetime.fromtimestamp(archived_submission.created_utc, timezone.utc)
        if post_time < cutoff_time:
            logging.debug(f"Skipping older post: {archived_submission.id}")
            break  # Stop processing older posts

        logging.debug(f"Checking archived post: {archived_submission.id} - {archived_submission.title}")

        archived_submission.comments.replace_more(limit=0)

        for comment in archived_submission.comments:
            match = re.search(r'\*\*Original Post ID:\*\* `([a-z0-9]+)`', comment.body)
            if match:
                original_post_id = match.group(1)
                logging.debug(f"Extracted original post ID: {original_post_id}")

                try:
                    original_submission = reddit.submission(id=original_post_id)
                    original_submission._fetch()  # <--- ADD THIS LINE

                    if original_submission.removed_by_category or original_submission.selftext == "[deleted]" or (original_submission.link_flair_template_id and original_submission.link_flair_template_id in removal_flair_ids):
                        archived_submission.mod.flair(flair_template_id=removed_flair_id)
                        print(f"Updated flair for archived post: {archived_submission.title}")
                        break
                    else:
                        logging.debug(f"Original post still exists: {original_post_id}")
                except NotFound:
                    archived_submission.mod.flair(flair_template_id=removed_flair_id)
                    logging.info(f"Original post not found, marking archived post as removed: {archived_submission.id}")
                    print(f"Original post not found, marking archived post as removed: {archived_submission.title}")

                except Exception as e:
                    logging.error(f"Error fetching original post {original_post_id}: {str(e)}")
                    print(f"Error fetching original post {original_post_id}: {str(e)}")

    except (RequestException, ResponseException, RedditAPIException) as ex:
        logging.error(f"Reddit API error for archived post {archived_submission.id}: {str(ex)}")
        print(f"Reddit API error for archived post {archived_submission.id}: {str(ex)}")
    except Exception as e:
        logging.error(f"General error for archived post {archived_submission.id}: {str(e)}")
        print(f"General error for archived post {archived_submission.id}: {str(e)}")

print("Script execution completed.")
logging.info("Script execution completed.")
