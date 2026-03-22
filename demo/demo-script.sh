#!/bin/bash
# apple-a-day demo script — recorded with asciinema

echo "$ pip install apple-a-day"
sleep 0.8
echo "Successfully installed apple-a-day-0.2.0"
sleep 0.5
echo ""

echo "$ aad checkup --min-severity warning"
sleep 0.5
aad checkup --min-severity warning
sleep 2

echo ""
echo "$ aad checkup --json --min-severity critical --fields severity,summary,fix"
sleep 0.5
aad checkup --json --min-severity critical --fields severity,summary,fix 2>&1 | head -25
sleep 2

echo ""
echo "$ aad schema | head -15"
sleep 0.5
aad schema | head -15
sleep 2
