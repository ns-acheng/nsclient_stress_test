#!/bin/bash

# List of browser app names to close (macOS common browsers)
browsers=("Safari" "Google Chrome" "Firefox")

closed_browsers=()
not_running=()

# Close each browser gracefully
for browser in "${browsers[@]}"; do
    # Check if the browser is running using pgrep with process name pattern
    # Safari process is "Safari", Chrome is "Google Chrome", Firefox is "firefox"
    if pgrep -i "$browser" > /dev/null 2>&1; then
        echo "Closing $browser..."
        osascript -e "quit app \"$browser\"" 2>/dev/null

        # Wait briefly to allow graceful close
        sleep 1

        # Force quit if still running after 2 seconds
        if pgrep -i "$browser" > /dev/null 2>&1; then
            echo "Force closing $browser..."
            pkill -ix "$browser" 2>/dev/null
        fi
        closed_browsers+=("$browser")
    else
        not_running+=("$browser")
    fi
done

# Summary
if [ ${#closed_browsers[@]} -gt 0 ]; then
    echo "Closed browsers: ${closed_browsers[*]}"
else
    echo "No browsers were running"
fi

if [ ${#not_running[@]} -gt 0 ]; then
    echo "Not running: ${not_running[*]}"
fi

echo "Browser closing complete."
