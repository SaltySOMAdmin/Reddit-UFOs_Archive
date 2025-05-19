import praw
import config
import re

# Set up Reddit instance
reddit = praw.Reddit(
    client_id=config.source_client_id,
    client_secret=config.source_client_secret,
    password=config.source_password,
    username=config.source_username,
    user_agent=config.source_user_agent
)

post_id = "1kqgzrd"
submission = reddit.submission(id=post_id)

print(f"\nTitle: {submission.title}")
print(f"Author: {submission.author}")
print(f"Created: {submission.created_utc}")
print(f"Flair: {submission.link_flair_text} | Flair Template ID: {submission.link_flair_template_id}")
print(f"Is self post: {submission.is_self}")
print(f"URL: {submission.url}")
print(f"Is gallery: {getattr(submission, 'is_gallery', False)}")
print(f"Is video: {'v.redd.it' in submission.url}")
print(f"Post Hint: {getattr(submission, 'post_hint', 'N/A')}")
print(f"Is Reddit hosted preview image? {'preview.redd.it' in submission.url}")

# Check for preview image transformation
if "preview.redd.it" in submission.url:
    clean_url = submission.url.split('?')[0].replace("preview.redd.it", "i.redd.it")
    print(f"Transformed image URL: {clean_url}")

# If gallery, print media info
if hasattr(submission, 'is_gallery') and submission.is_gallery:
    print("\nGallery Items:")
    for item in submission.gallery_data['items']:
        media_id = item['media_id']
        meta = submission.media_metadata.get(media_id, {})
        url = meta.get('s', {}).get('u')
        print(f" - Media ID: {media_id}, URL: {url}")

# If Reddit video, extract fallback and audio URL
if 'v.redd.it' in submission.url and submission.media:
    reddit_video = submission.media.get('reddit_video', {})
    fallback = reddit_video.get('fallback_url')
    audio_url = fallback.rsplit('/', 1)[0] + '/DASH_audio.mp4'
    print(f"\nVideo fallback URL: {fallback}")
    print(f"Audio URL: {audio_url}")

print("\nSubmission selftext:")
print(submission.selftext or "[No selftext]")
