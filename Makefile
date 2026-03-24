.PHONY: roll install-cli install-login uninstall-login test

# Rebuild and deploy the macOS menu bar app
roll:
	pkill -x AppleADay || true
	cd app/AppleADay && swift build
	@mkdir -p /Applications/AppleADay.app/Contents/MacOS
	@mkdir -p /Applications/AppleADay.app/Contents/Resources
	cp app/AppleADay/.build/arm64-apple-macosx/debug/AppleADay /Applications/AppleADay.app/Contents/MacOS/AppleADay
	cp app/AppleADay/Sources/Info.plist /Applications/AppleADay.app/Contents/Info.plist
	cp app/AppleADay/Sources/AppIcon.icns /Applications/AppleADay.app/Contents/Resources/AppIcon.icns
	codesign --force --sign - /Applications/AppleADay.app
	/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f /Applications/AppleADay.app
	sleep 1
	open /Applications/AppleADay.app

# Launch at login
install-login:
	cp com.eidos.apple-a-day-app.plist ~/Library/LaunchAgents/
	launchctl load ~/Library/LaunchAgents/com.eidos.apple-a-day-app.plist
	@echo "AppleADay will launch at login"

uninstall-login:
	launchctl unload ~/Library/LaunchAgents/com.eidos.apple-a-day-app.plist 2>/dev/null || true
	rm -f ~/Library/LaunchAgents/com.eidos.apple-a-day-app.plist
	@echo "AppleADay removed from login items"

# Install CLI in dev mode (editable)
install-cli:
	pip install -e .

# Run test suite
test:
	python -m pytest tests/ -v
