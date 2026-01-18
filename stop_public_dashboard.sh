#!/bin/bash
# Stop the public dashboard and ngrok tunnel

set -e

echo "Stopping Weather Dashboard and ngrok tunnel..."

# Kill dashboard
if [ -f /tmp/dashboard_pid ]; then
    DASHBOARD_PID=$(cat /tmp/dashboard_pid)
    kill $DASHBOARD_PID 2>/dev/null || true
    rm /tmp/dashboard_pid
    echo "✓ Dashboard stopped"
fi

# Kill ngrok
if [ -f /tmp/ngrok_pid ]; then
    NGROK_PID=$(cat /tmp/ngrok_pid)
    kill $NGROK_PID 2>/dev/null || true
    rm /tmp/ngrok_pid
    echo "✓ Ngrok tunnel stopped"
fi

# Kill any remaining processes on port 5000
lsof -ti:5000 | xargs kill -9 2>/dev/null || true

echo "✓ All processes stopped"
