#!/bin/bash

# Variables
LOG_FILE="/home/ubuntu/Reddit-UFOs_Archive/cron_log.txt" # log location specified in cron
source "/home/ubuntu/Reddit-UFOs_Archive/cron_webhook.txt"  # Load webhook URL or file containing it

# Check if the log file is empty
if [ ! -s "$LOG_FILE" ]; then
    echo "Log file is empty. Exiting."
    exit 0
fi

# Check if the file contains only the one line
if [ "$(wc -l < "$LOG_FILE")" -eq 1 ] && grep -Fxq "Starting script. Scan interval: 0:42:00." "$LOG_FILE"; then
    echo "Log file only contains the unimportant start line. Deleting it."
    rm -f "$LOG_FILE"
    exit 0
fi

# Read the log file line by line and send each line as a message to Discord
while IFS= read -r line
do
    # Strip newlines and carriage returns
    cleaned_line=$(echo "$line" | tr -d '\n' | tr -d '\r')

    # Escape special characters using jq to ensure valid JSON format
    json_payload=$(jq -nc --arg content "$cleaned_line" '{content: $content}' 2>/dev/null)

    # Verify that jq processed the line correctly
    if [ $? -ne 0 ] || [ -z "$json_payload" ]; then
        echo "Error: Failed to process log line into valid JSON. Skipping line: $line" >> error_log.txt
        continue
    fi

    # Send the message to the Discord webhook
    response=$(curl -s -X POST "$WEBHOOK_URL" \
    -H "Content-Type: application/json" \
    -d "$json_payload")

    # Check for Discord API errors
    if [[ "$response" == *'"code": 50109'* ]]; then
        echo "Error: Invalid JSON format detected in Discord API response. Logging payload..." >> error_log.txt
        echo "Payload: $json_payload" >> error_log.txt
        continue
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
