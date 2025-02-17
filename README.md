# Subreddit-to-Subreddit Archive
 
### This is a reddit bot designed to backup posts from one subreddit to another on a set schedule. 
- Post-ids are logged to verify posts aren't duplicated.
- Post flairs are copied to match the original post.
- Comments are left in the body of the duplicated post tagging the original post, the original author, and direct links to media if applicable. 
- A separate script is included to modify the flair of posts that are removed from the original subreddit. 

# Setup

### Setup a Linux Host
I'm using Ubuntu LTS on an Oracle Cloud VM. There are free-tiers available as of today. Google Compute and Amazon AWS are similar products. You can also roll your own host with an old PC. 

### Install necessary software prereqs: 
	sudo apt install python3
	sudo apt install python3-praw
	sudo apt install python3-prawcore

### Create a dedicated Reddit account for your bot.
A bot account needs to be created and Reddit API credentials need to be entered into config.py. You can use different accounts for the source and destination subreddits or you can use one account for both. Specify in the main script under the section with - client_id=config.destination_client_id,

A Discord webhook needs to be created and entered into forward_cron_log.sh and into forward_error_log.sh - you can setup two channels or use the same webhook for both. 

### Configure the script.
There are several sections you can customize in the script. You'll need to enter your source and destination subs.

	source_subreddit = source_reddit.subreddit('ufos')

	destination_subreddit = archives_reddit.subreddit('UFOs_Archive')

You'll also need to set your timedelta. I run my script every 14 minutes but the script checks posts that are created within the past 28 minutes. This gives two opportunities for posts to be duplicated. 

	cutoff_time = current_time - timedelta(minutes=28)

### Crontab Settings
This is where you will set your schedule to run. My script runs every 14 minutes (Example: 10:00, 10:14, 10:28, 10:42, 10:56) and it logs actions to cron_log.txt Errors are logged within the script to error_log.txt as they happen. To open your cron settings type this into your terminal: crontab -e

- Main Script

	*/14 * * * /usr/bin/python3 /home/ubuntu/Reddit-UFOs_Archive/CopyPosts-UFOs_Archives.py >> /home/ubuntu/Reddit-UFOs_Archive/cron_log.txt 2>&1

- Update flair script

	2 */8 * * * /usr/bin/python3 /home/ubuntu/Reddit-UFOs_Archive/DailyRemovedFlair.py >> /home/ubuntu/Reddit-UFOs_Archive/removed_posts_log.txt 2>&1


- Upload logs to Discord Webhook then wipe the log

	*/15 * * * * /home/ubuntu/Reddit-UFOs_Archive/forward_error_log.sh
	*/15 * * * * /home/ubuntu/Reddit-UFOs_Archive/forward_cron_log.sh
	10 */8 * * * /home/ubuntu/Reddit-UFOs_Archive/forward_removed_posts_log.sh

