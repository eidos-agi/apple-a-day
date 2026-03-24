.PHONY: roll install-cli test

# Rebuild and deploy the macOS menu bar app
roll:
	pkill -x AppleADay || true
	cd app/AppleADay && swift build
	@mkdir -p /Applications/AppleADay.app/Contents/MacOS
	@mkdir -p /Applications/AppleADay.app/Contents/Resources
	cp app/AppleADay/.build/arm64-apple-macosx/debug/AppleADay /Applications/AppleADay.app/Contents/MacOS/AppleADay
	cp app/AppleADay/Sources/Info.plist /Applications/AppleADay.app/Contents/Info.plist
	codesign --force --sign - /Applications/AppleADay.app
	/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f /Applications/AppleADay.app
	sleep 1
	open /Applications/AppleADay.app

# Install CLI in dev mode (editable)
install-cli:
	pip install -e .

# Run test suite
test:
	python -m pytest tests/ -v
