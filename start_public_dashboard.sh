#!/bin/bash
# Start Weather Dashboard with ngrok public access

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Weather Platform - Public Dashboard${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Parse arguments
PORT=${1:-5000}
INTERVAL=${2:-60}

# Kill any existing processes on the port
echo -e "${YELLOW}Checking for existing processes on port $PORT...${NC}"
lsof -ti:$PORT | xargs kill -9 2>/dev/null || true

# Start the Flask dashboard in the background
echo -e "${YELLOW}Starting Flask dashboard on port $PORT...${NC}"
source .venv/bin/activate
python run_dashboard.py --host 0.0.0.0 --port $PORT --interval $INTERVAL > /tmp/dashboard.log 2>&1 &
DASHBOARD_PID=$!
echo -e "${GREEN}✓ Dashboard started (PID: $DASHBOARD_PID)${NC}"

# Wait for dashboard to be ready
echo -e "${YELLOW}Waiting for dashboard to be ready...${NC}"
for i in {1..10}; do
    if curl -s http://localhost:$PORT/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Dashboard is ready!${NC}"
        break
    fi
    sleep 1
done

# Start ngrok tunnel
echo -e "${YELLOW}Starting ngrok tunnel...${NC}"
./ngrok http $PORT > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!
echo -e "${GREEN}✓ Ngrok tunnel started (PID: $NGROK_PID)${NC}"

# Wait for ngrok to establish tunnel
echo -e "${YELLOW}Waiting for ngrok tunnel...${NC}"
sleep 3

# Get the public URL
PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | head -1 | cut -d'"' -f4)

# Save PIDs for cleanup
echo "$DASHBOARD_PID" > /tmp/dashboard_pid
echo "$NGROK_PID" > /tmp/ngrok_pid

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✓ Dashboard is now publicly accessible!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}Public URL:${NC}  $PUBLIC_URL"
echo -e "${GREEN}Local URL:${NC}   http://localhost:$PORT"
echo -e "${GREEN}Ngrok Web UI:${NC} http://localhost:4040"
echo ""
echo -e "${YELLOW}Features:${NC}"
echo "  • Live temperature predictions"
echo "  • Auto-updating metrics (every 30 seconds)"
echo "  • Scheduled pipeline runs (every $INTERVAL minutes)"
echo ""
echo -e "${YELLOW}Share this URL with others:${NC}"
echo -e "${BLUE}$PUBLIC_URL${NC}"
echo ""
echo -e "${YELLOW}Logs:${NC}"
echo "  • Dashboard: tail -f /tmp/dashboard.log"
echo "  • Ngrok: tail -f /tmp/ngrok.log"
echo ""
echo -e "${YELLOW}To stop:${NC}"
echo "  • Press Ctrl+C, or run: ./stop_public_dashboard.sh"
echo -e "${BLUE}========================================${NC}"
echo ""

# Keep script running and show live logs
echo -e "${YELLOW}Showing live dashboard logs (Ctrl+C to stop):${NC}"
echo ""
tail -f /tmp/dashboard.log
