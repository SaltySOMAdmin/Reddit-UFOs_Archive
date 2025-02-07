# sightings-archive-ufos_archive
 
Designed to backup posts from one Sub to another every 14 minutes. 

Prereqs: 
sudo apt install python3-praw
sudo apt install python3-prawcore

A bot account needs to be created and Reddit API credentials need to be entered into CopyPosts.py
A Discord webhook needs to be created and entered into forward_log.sh

#Crontab Settings
Run Copy script every 14 minutes and log to log.txt
*/14 * * * * /usr/bin/python3 CopyPosts.py >> /home/user/log.txt 2>&1

Upload log.txt to Discord Webhook then wipe the log
*/14 * * * * forward_log.sh
