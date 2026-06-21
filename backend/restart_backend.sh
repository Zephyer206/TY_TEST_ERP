#!/bin/bash

# Kill all processes on port 8000
echo "Stopping processes on port 8000..."
for pid in 4940 26504 6724; do
    kill -9 $pid 2>/dev/null && echo "Killed PID $pid"
done

# Wait for port to be released
sleep 3

# Start backend
echo "Starting backend..."
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > backend_new.log 2>&1 &

# Wait and check
sleep 4
tail -20 backend_new.log
