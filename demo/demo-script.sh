#!/bin/bash
# apple-a-day demo — hero feature in first 10 seconds

echo "→ Installing apple-a-day (zero dependencies)"
sleep 0.5
echo "$ pip install apple-a-day"
sleep 0.3
echo "Successfully installed apple-a-day-0.2.0"
sleep 0.8

echo ""
echo "→ Full Mac health checkup"
echo "$ aad checkup --min-severity warning"
sleep 0.5
aad checkup --min-severity warning
sleep 3

echo ""
echo "→ Agent-friendly JSON (filter to critical only, 3 fields)"
echo '$ aad checkup --json --min-severity critical --fields severity,summary,fix | head -20'
sleep 0.5
aad checkup --json --min-severity critical --fields severity,summary,fix 2>&1 | head -20
sleep 2

echo ""
echo "→ Runtime schema for agent discovery"
echo "$ aad schema | head -12"
sleep 0.5
aad schema | head -12
sleep 1.5
