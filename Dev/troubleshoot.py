import praw
import requests
import os
import time
import logging
import sys
import re
from datetime import datetime, timedelta, timezone
from prawcore.exceptions import RequestException, ResponseException
from praw.exceptions import RedditAPIException
import config  # Import the config file with credentials

# === Step 1: Configure Reddit API ===
# Either fill in your credentials here or make sure ~/.config/praw.ini has them under [bot1]
# Reddit API credentials
reddit = praw.Reddit(
    client_id=config.source_client_id,
    client_secret=config.source_client_secret,
    password=config.source_password,
    username=config.source_username,
    user_agent=config.source_user_agent
)

# === Step 2: Load submission ===
post_id = "1ksr66d"
submission = reddit.submission(id=post_id)

# === Step 3: Check if it's a Reddit-hosted video ===
if hasattr(submission, "media") and submission.media and "reddit_video" in submission.media:
    fallback_url = submission.media["reddit_video"]["fallback_url"]
    print(f"Video fallback URL:\n{fallback_url}")

    # Extract media ID from fallback URL
    match = re.search(r"v\.redd\.it/([^/]+)/", fallback_url)
    if match:
        media_id = match.group(1)
        audio_url = f"https://v.redd.it/{media_id}/DASH_audio.mp4"
        print(f"Audio URL:\n{audio_url}")
    else:
        print("❌ Could not extract media ID from fallback URL.")
else:
    print("❌ This submission does not contain a Reddit-hosted video.")
