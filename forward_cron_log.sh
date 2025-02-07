#!/bin/bash

# Variables
LOG_FILE="/home/ubuntu/Reddit-UFOs_Archive/cron_log.txt"
source "/home/ubuntu/Reddit-UFOs_Archive/cron_webhook.txt"  # Replace with the actual path to your config.txt file

# Check if the log file exists
if [ ! -f "$LOG_FILE" ]; then
    echo "Log file does not exist: $LOG_FILE"
    exit 1
fi

# Check if the log file is empty
if [ ! -s "$LOG_FILE" ]; then
    echo "Log file is empty. Exiting."
    exit 0
fi

# Read the log file line by line and send each line as a message to Discord
while IFS= read -r line
do
    # Escape special characters using jq to ensure valid JSON format
    json_payload=$(jq -nc --arg content "$line" '{content: $content}')
    
    # Send each line to the Discord webhook as a message
    response=$(curl -s -X POST "$WEBHOOK_URL" \
    -H "Content-Type: application/json" \
    -d "$json_payload")

    # Check if Discord API returned an error
    if [[ "$response" == *'"code": 50109'* ]]; then
        echo "Error: Invalid JSON format detected."
        exit 1
    fi
done < "$LOG_FILE"

# Check if the messages were sent successfully
if [ $? -eq 0 ]; then
    echo "Log file lines successfully posted to Discord."
    
    # Optionally delete the log file after posting
    rm -f "$LOG_FILE"
    if [ $? -eq 0 ]; then
        echo "Log file deleted successfully."
    else
        echo "Failed to delete log file."
    fi
else
    echo "Failed to send log file lines to Discord."
fi
