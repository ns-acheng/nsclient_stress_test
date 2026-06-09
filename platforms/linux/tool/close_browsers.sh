#!/bin/bash

# List of browser process names to close (Linux common browsers)
browsers=("firefox" "google-chrome" "chrome" "chromium-browser" "chromium")

closed_browsers=()
not_running=()

# Close each browser gracefully
for browser in "${browsers[@]}"; do
    # Check if the browser is running using pgrep
    if pgrep -x "$browser" > /dev/null 2>&1; then
        echo "Closing $browser..."
        pkill -TERM -x "$browser" 2>/dev/null

        # Wait briefly to allow graceful close
        sleep 2

        # Force kill if still running after 2 seconds
        if pgrep -x "$browser" > /dev/null 2>&1; then
            echo "Force closing $browser..."
            pkill -KILL -x "$browser" 2>/dev/null
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
