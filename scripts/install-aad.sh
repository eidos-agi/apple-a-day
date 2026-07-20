#!/bin/sh
# Install the aad binary WITHOUT corrupting the running daemon.
# cp-ing over ~/.local/bin/aad while `com.eidos.aad-serve` runs from it corrupts
# the on-disk image (ETXTBSY) → SIGKILL on next exec. Always stop first.
set -e
uid=$(id -u)
go build -o /tmp/aad-go .
launchctl bootout "gui/$uid/com.eidos.aad-serve" 2>/dev/null || true
sleep 1
cp /tmp/aad-go "$HOME/.local/bin/aad"
launchctl bootstrap "gui/$uid" "$HOME/Library/LaunchAgents/com.eidos.aad-serve.plist" 2>/dev/null || true
echo "installed $(~/.local/bin/aad version | grep commit)"
