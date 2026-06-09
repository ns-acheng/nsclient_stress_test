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
    local browser="$1"
    local url="$2"

    # Check if browser exists
    if [ -d "/Applications/${browser}.app" ]; then
        open -a "$browser" "$url" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "Opened $url in $browser"
            return 0
        else
            echo "Warning: Failed to open $url in $browser" >&2
            return 1
        fi
    else
        echo "Warning: $browser not installed, skipping" >&2
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
    
    # Try Chrome
    open_in_browser "Google Chrome" "$url"

    # Try Firefox (no wait needed, browsers open in parallel)
    open_in_browser "Firefox" "$url"

    # Try Safari
    open_in_browser "Safari" "$url"

    # Brief pause between URLs to avoid overwhelming the system
    sleep 0.5
    
    count=$((count + 1))
done

echo "Completed opening $count URLs"
exit 0
