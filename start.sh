#!/bin/bash

pkill -f "/app/log.py" 2>/dev/null
nohup uv run /app/log.py > /var/log/app.log 2>&1 &

echo "Services restarted"