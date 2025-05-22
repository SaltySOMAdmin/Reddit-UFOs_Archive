import praw
import requests
import logging
import config  # Import the config file with credentials
import xml.etree.ElementTree as ET  # For parsing DASH manifest
from prawcore.exceptions import NotFound, Forbidden

# Set up logging to both file and console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('/home/ubuntu/Reddit-UFOs_Archive/Dev/post_diagnostic_log.txt'),
        logging.StreamHandler()
    ]
)

# Reddit API credentials
reddit = praw.Reddit(
    client_id=config.source_client_id,
    client_secret=config.source_client_secret,
    password=config.source_password,
    username=config.source_username,
    user_agent=config.source_user_agent
)

# Create a requests session to persist cookies
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.reddit.com/',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Origin': 'https://www.reddit.com'
})

# Function to get audio URL with fallbacks and manifest parsing
def get_audio_url(submission_data, post_url):
    try:
        # Check if submission_data is a PRAW Submission object or a dictionary
        is_submission = isinstance(submission_data, praw.models.Submission)
        if is_submission:
            media = submission_data.media if hasattr(submission_data, 'media') and submission_data.media else {}
            reddit_video = media.get('reddit_video', {})
        else:
            media = submission_data.get('media', {})
            reddit_video = media.get('reddit_video', {})

        dash_url = reddit_video.get('dash_url')
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.reddit.com/'
        }
        if dash_url:
            # Try DASH_audio.mp4
            base_url = dash_url.rsplit('/', 1)[0]
            audio_url = f"{base_url}/DASH_audio.mp4"
            response = session.head(audio_url, headers=headers, timeout=5)
            if response.status_code == 200:
                logging.info(f"Audio URL {audio_url} is accessible")
                return audio_url
            logging.info(f"Audio URL {audio_url} not accessible, status code: {response.status_code}, headers: {response.headers}")

            # Try audio.mp4 as fallback
            audio_url = f"{base_url}/audio.mp4"
            response = session.head(audio_url, headers=headers, timeout=5)
            if response.status_code == 200:
                logging.info(f"Audio URL {audio_url} is accessible")
                return audio_url
            logging.info(f"Audio URL {audio_url} not accessible, status code: {response.status_code}, headers: {response.headers}")

            # Try parsing DASH manifest (DASHPlaylist.mpd)
            try:
                response = session.get(dash_url, headers=headers, timeout=5)
                if response.status_code == 200:
                    manifest = ET.fromstring(response.text)
                    for adapt_set in manifest.findall(".//{urn:mpeg:dash:schema:mpd:2011}AdaptationSet[@contentType='audio']"):
                        for rep in adapt_set.findall("{urn:mpeg:dash:schema:mpd:2011}Representation"):
                            base_url_node = rep.find("{urn:mpeg:dash:schema:mpd:2011}BaseURL")
                            if base_url_node is not None:
                                audio_url = base_url.rsplit('/', 1)[0] + '/' + base_url_node.text
                                response = session.head(audio_url, headers=headers, timeout=5)
                                if response.status_code == 200:
                                    logging.info(f"Audio URL {audio_url} from DASH manifest is accessible")
                                    return audio_url
                                logging.info(f"Audio URL {audio_url} from DASH manifest not accessible, status code: {response.status_code}, headers: {response.headers}")
            except Exception as e:
                logging.error(f"Error parsing DASH manifest for {dash_url}: {e}")

        elif "v.redd.it" in post_url:
            base_url = post_url.rsplit('/', 1)[0]
            audio_url = f"{base_url}/DASH_audio.mp4"
            response = session.head(audio_url, headers=headers, timeout=5)
            if response.status_code == 200:
                logging.info(f"Audio URL {audio_url} is accessible")
                return audio_url
            logging.info(f"Audio URL {audio_url} not accessible, status code: {response.status_code}, headers: {response.headers}")

            # Try audio.mp4 as fallback
            audio_url = f"{base_url}/audio.mp4"
            response = session.head(audio_url, headers=headers, timeout=5)
            if response.status_code == 200:
                logging.info(f"Audio URL {audio_url} is accessible")
                return audio_url
            logging.info(f"Audio URL {audio_url} not accessible, status code: {response.status_code}, headers: {response.headers}")
        return None
    except Exception as e:
        logging.error(f"Error checking audio URL: {e}")
        return None

# Function to fetch post details via API, JSON, and HTML
def fetch_post_details(post_id):
    try:
        # Try fetching via PRAW
        logging.info(f"Attempting to fetch post {post_id} via PRAW")
        submission = reddit.submission(id=post_id)

        # Basic post details
        logging.info(f"Title: {submission.title}")
        logging.info(f"Author: {submission.author}")
        logging.info(f"Flair: {submission.link_flair_text}")
        logging.info(f"URL: {submission.url}")
        logging.info(f"Permalink: https://www.reddit.com{submission.permalink}")
        logging.info(f"Created UTC: {submission.created_utc}")
        logging.info(f"Is Self Post: {submission.is_self}")
        logging.info(f"Is Video: {submission.is_video}")
        logging.info(f"Removed by Category: {submission.removed_by_category}")
        logging.info(f"Media: {submission.media}")
        logging.info(f"Cross Post Parent: {submission.crosspost_parent if hasattr(submission, 'crosspost_parent') else 'None'}")

        # Check for gallery data
        if hasattr(submission, 'is_gallery') and submission.is_gallery:
            logging.info(f"Gallery Data: {submission.gallery_data}")
            logging.info(f"Media Metadata: {submission.media_metadata}")
            for item in submission.gallery_data.get('items', []):
                media_id = item.get('media_id')
                meta = submission.media_metadata.get(media_id, {})
                logging.info(f"Gallery Item Media ID: {media_id}, Metadata: {meta}")

        # Check for video and audio details
        if submission.is_video and submission.media:
            reddit_video = submission.media.get('reddit_video', {})
            logging.info(f"Reddit Video Details: {reddit_video}")
            logging.info(f"Has Audio: {reddit_video.get('has_audio', False)}")
            logging.info(f"Is GIF: {reddit_video.get('is_gif', False)}")
            logging.info(f"Fallback URL: {reddit_video.get('fallback_url')}")
            logging.info(f"DASH URL: {reddit_video.get('dash_url')}")

            # Attempt to get audio URL
            audio_url = get_audio_url(submission, submission.url)
            logging.info(f"Derived Audio URL: {audio_url}")

            # Try downloading audio with PRAW
            if audio_url:
                try:
                    response = reddit.request('GET', audio_url, stream=True)
                    logging.info(f"PRAW Audio Request Status: {response.status_code}, Headers: {response.headers}")
                except Exception as e:
                    logging.error(f"PRAW Audio Request Error: {e}")

                # Try downloading audio with session
                try:
                    response = session.get(audio_url, stream=True, timeout=5)
                    logging.info(f"Session Audio Request Status: {response.status_code}, Headers: {response.headers}")
                except Exception as e:
                    logging.error(f"Session Audio Request Error: {e}")

        # Check cross-post parent if applicable
        if hasattr(submission, 'crosspost_parent') and submission.crosspost_parent:
            parent_id = submission.crosspost_parent.split('_')[1]
            logging.info(f"Fetching cross-post parent {parent_id}")
            try:
                parent_submission = reddit.submission(id=parent_id)
                logging.info(f"Parent Title: {parent_submission.title}")
                logging.info(f"Parent URL: {parent_submission.url}")
                logging.info(f"Parent Media: {parent_submission.media}")
                logging.info(f"Parent Removed: {parent_submission.removed_by_category}")
                parent_audio_url = get_audio_url(parent_submission, parent_submission.url)
                logging.info(f"Parent Derived Audio URL: {parent_audio_url}")
            except Exception as e:
                logging.error(f"Error fetching cross-post parent {parent_id}: {e}")

    except NotFound:
        logging.error(f"PRAW returned 404 for post {post_id}. Post may be deleted or inaccessible.")
    except Forbidden:
        logging.error(f"PRAW returned 403 for post {post_id}. Check subreddit permissions or credentials.")
    except Exception as e:
        logging.error(f"PRAW Error fetching details for post {post_id}: {e}")

    # Fallback: Try fetching post JSON using PRAW's authenticated request
    try:
        logging.info(f"Attempting to fetch post {post_id} via authenticated JSON request")
        json_url = f"https://www.reddit.com/comments/{post_id}.json"
        response = reddit.request('GET', json_url)
        if response.status_code == 200:
            post_data = response.json()[0]['data']['children'][0]['data']
            logging.info(f"Authenticated JSON Post Data: {post_data}")
            logging.info(f"Title: {post_data.get('title')}")
            logging.info(f"Author: {post_data.get('author')}")
            logging.info(f"Flair: {post_data.get('link_flair_text')}")
            logging.info(f"URL: {post_data.get('url')}")
            logging.info(f"Permalink: https://www.reddit.com{post_data.get('permalink')}")
            logging.info(f"Created UTC: {post_data.get('created_utc')}")
            logging.info(f"Is Self Post: {post_data.get('is_self')}")
            logging.info(f"Is Video: {post_data.get('is_video')}")
            logging.info(f"Removed by Category: {post_data.get('removed_by_category')}")
            logging.info(f"Media: {post_data.get('media')}")
            logging.info(f"Cross Post Parent: {post_data.get('crosspost_parent', 'None')}")

            # Check audio URL using JSON data
            audio_url = get_audio_url(post_data, post_data.get('url'))
            logging.info(f"Derived Audio URL from JSON: {audio_url}")

            # Try downloading audio with PRAW
            if audio_url:
                try:
                    response = reddit.request('GET', audio_url, stream=True)
                    logging.info(f"PRAW Audio Request Status (JSON): {response.status_code}, Headers: {response.headers}")
                except Exception as e:
                    logging.error(f"PRAW Audio Request Error (JSON): {e}")
        else:
            logging.error(f"Authenticated JSON request failed for {json_url}. Status code: {response.status_code}, Headers: {response.headers}")
    except Exception as e:
        logging.error(f"Authenticated JSON request error for post {post_id}: {e}")

    # Fallback: Check HTML page for removal status with session cookies
    try:
        logging.info(f"Attempting to fetch post {post_id} HTML page")
        html_url = f"https://www.reddit.com/comments/{post_id}"
        # Simulate a browser login by fetching the Reddit homepage first
        session.get('https://www.reddit.com', timeout=5)
        response = session.get(html_url, timeout=10)
        if response.status_code == 200:
            html_content = response.text.lower()
            if "this post was deleted" in html_content or "this post has been removed" in html_content:
                logging.info(f"HTML indicates post {post_id} is deleted or removed")
            else:
                logging.info(f"HTML page for {post_id} loaded successfully, post appears accessible")
            logging.info(f"HTML Snippet: {html_content[:500]}")
        else:
            logging.error(f"HTML request failed for {html_url}. Status code: {response.status_code}, Headers: {response.headers}")
    except Exception as e:
        logging.error(f"HTML request error for post {post_id}: {e}")

    # Check subreddit status
    try:
        subreddit = reddit.subreddit('ufos')
        logging.info(f"Subreddit ufos: Type={subreddit.subreddit_type}, Quarantined={subreddit.quarantine}")
    except Exception as e:
        logging.error(f"Error fetching subreddit status: {e}")

# Main execution
if __name__ == "__main__":
    post_ids = ["1ksxnxv", "1ksr66d"]  # Test both posts
    for post_id in post_ids:
        logging.info(f"Processing post {post_id}")
        fetch_post_details(post_id)