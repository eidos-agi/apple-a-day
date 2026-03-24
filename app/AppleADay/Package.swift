// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "AppleADay",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "AppleADay",
            path: "Sources",
            exclude: ["Info.plist", "AppIcon.icns"]
        ),
    ]
)
