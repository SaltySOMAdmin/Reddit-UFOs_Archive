import praw
import config  # your credentials file

# Reddit API credentials
source_reddit = praw.Reddit(
    client_id=config.source_client_id,
    client_secret=config.source_client_secret,
    password=config.source_password,
    username=config.source_username,
    user_agent=config.source_user_agent
)

# Subreddit to fetch rules from
source_subreddit = source_reddit.subreddit('ufos')

print(f"Rules for r/{source_subreddit.display_name}:\n")

for rule in source_subreddit.rules:
    print(f"Priority: {rule.priority}")
    print(f"Rule Number: {rule.priority + 1}")
    print(f"Short Name: {rule.short_name}")
    print(f"Description: {rule.description}\n{'-'*60}\n")
