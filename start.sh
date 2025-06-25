#!/bin/bash

pkill -f "log.py" 2>/dev/null
nohup uv run log.py > /var/log/app.log 2>&1 &

echo "Services restarted"