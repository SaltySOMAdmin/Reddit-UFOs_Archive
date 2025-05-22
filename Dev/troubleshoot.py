import praw
import requests
import logging
import config  # Import the config file with credentials
import xml.etree.ElementTree as ET  # For parsing DASH manifest

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
def get_audio_url(submission):
    try:
        reddit_video = submission.media.get('reddit_video', {}) if submission.media else {}
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

        elif "v.redd.it" in submission.url:
            base_url = submission.url.rsplit('/', 1)[0]
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
        logging.error(f"Error checking audio URL for submission {submission.id}: {e}")
        return None

# Function to fetch and log post details
def fetch_post_details(post_id):
    try:
        submission = reddit.submission(id=post_id)
        logging.info(f"Fetching details for post {post_id}")

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
            audio_url = get_audio_url(submission)
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

    except Exception as e:
        logging.error(f"Error fetching details for post {post_id}: {e}")

# Main execution
if __name__ == "__main__":
    post_id = "oonmcr62jd2f1"
    fetch_post_details(post_id)