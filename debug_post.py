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

# Replace this with the ID of the post you want to inspect
submission_id = "1k1w8qk"
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
