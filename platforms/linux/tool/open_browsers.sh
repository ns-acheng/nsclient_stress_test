#!/bin/bash

# Check if URLs are provided
if [ $# -eq 0 ]; then
    echo "No URLs provided."
    echo "Usage: $0 url1 url2 ... url10"
    exit 1
fi

count=0
max_tabs=10

# Function to safely open URL in a browser
open_in_browser() {
    local browser_cmd="$1"
    local browser_name="$2"
    local url="$3"

    # Check if browser command exists
    if command -v "$browser_cmd" >/dev/null 2>&1; then
        "$browser_cmd" "$url" </dev/null >/dev/null 2>&1 &
        if [ $? -eq 0 ]; then
            echo "Opened $url in $browser_name"
            return 0
        else
            echo "Warning: Failed to open $url in $browser_name" >&2
            return 1
        fi
    else
        echo "Warning: $browser_name not installed, skipping" >&2
        return 1
    fi
}

# Loop through all arguments
for url in "$@"; do
    # Stop if we've opened 10 tabs
    if [ $count -ge $max_tabs ]; then
        break
    fi

    echo "Opening URL: $url"

    # Try browsers in order, stop at first success
    if open_in_browser "firefox" "Firefox" "$url"; then
        :
    elif open_in_browser "google-chrome" "Google Chrome" "$url"; then
        :
    elif open_in_browser "chromium-browser" "Chromium" "$url"; then
        :
    elif open_in_browser "chromium" "Chromium" "$url"; then
        :
    else
        echo "Warning: No supported browser could open $url" >&2
    fi

    # Brief pause between URLs to avoid overwhelming the system
    sleep 0.5

    count=$((count + 1))
done

echo "Completed opening $count URLs"
exit 0
