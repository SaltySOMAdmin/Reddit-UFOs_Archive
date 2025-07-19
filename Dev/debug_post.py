import praw
import config  # assumes you have a config.py with Reddit credentials
import json

# Set up Reddit API client
reddit = praw.Reddit(
    client_id=config.destination_client_id,
    client_secret=config.destination_client_secret,
    password=config.destination_password,
    username=config.destination_username,
    user_agent=config.destination_user_agent
)

# Parse test_post_id from command-line argument
def get_post_ID():
    if len(sys.argv) < 2:
        print("Error: No post ID provided.")
        print(f"Usage: python {sys.argv[0]} <post_id>")
        sys.exit(1)  # Exit the script with an error code
    return sys.argv[1]
# Replace this with the ID of the post you want to inspect

submission_id = get_post_ID()
submission = reddit.submission(id=submission_id)

# Collect relevant info
media_info = {
    "id": submission.id,
    "title": submission.title,
    "url": submission.url,
    "permalink": submission.permalink,
    "is_video": submission.is_video,
    "media": submission.media,
    "secure_media": submission.secure_media,
    "media_metadata": getattr(submission, "media_metadata", None),
    "is_gallery": getattr(submission, "is_gallery", False),
    "gallery_data": getattr(submission, "gallery_data", None),
}

# Pretty-print to terminal
print(json.dumps(media_info, indent=4, default=str))
