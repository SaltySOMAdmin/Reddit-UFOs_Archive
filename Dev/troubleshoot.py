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
import re

submission = reddit.submission(id="1ksr66d")
video_url = submission.media['reddit_video']['fallback_url']  # e.g., https://v.redd.it/abc123/DASH_720.mp4

# Extract media ID from the fallback URL
media_id_match = re.search(r"v\.redd\.it/([^/]+)/", video_url)
if media_id_match:
    media_id = media_id_match.group(1)
    audio_url = f"https://v.redd.it/{media_id}/DASH_audio.mp4"
    print("Audio URL:", audio_url)
