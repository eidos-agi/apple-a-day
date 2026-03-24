import Foundation
import SwiftUI

@MainActor
class HealthService: ObservableObject {
    @Published var appState: AppState = .loading
    @Published var overallGrade: HealthGrade?
    @Published var score: ScoreOutput?
    @Published var lastCheckup: CheckupLogEntry?
    @Published var recentVitals: [VitalsSample] = []
    @Published var checkupDaemon: DaemonStatus = .unknown
    @Published var vitalsDaemon: DaemonStatus = .unknown
    @Published var isRunningCheckup = false
    @Published var cliPath: String?

    private let logDir: String = {
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        return "\(home)/.config/eidos/aad-logs"
    }()

    // MARK: - Logging

    static func log(_ message: String) {
        NSLog("[AppleADay] %@", message)
    }

    // MARK: - Initialization

    func bootstrap() {
        Self.log("Bootstrapping...")
        if let path = findCli() {
            cliPath = path
            Self.log("Found CLI at \(path)")
            loadData()
        } else {
            Self.log("CLI not found")
            appState = .cliNotFound
        }
    }

    // MARK: - CLI Discovery

    private func findCli() -> String? {
        let candidates = [
            "\(FileManager.default.homeDirectoryForCurrentUser.path)/.pyenv/shims/aad",
            "/usr/local/bin/aad",
            "/opt/homebrew/bin/aad",
        ]
        for path in candidates {
            if FileManager.default.isExecutableFile(atPath: path) {
                return path
            }
        }
        // Fall back to PATH lookup
        let result = shell("which", "aad")
        if result.status == 0, !result.output.isEmpty {
            return result.output.trimmingCharacters(in: .whitespacesAndNewlines)
        }
        return nil
    }

    // MARK: - Data Loading

    func loadData() {
        guard cliPath != nil else { return }
        loadLastCheckup()
        loadRecentVitals()
        loadScore()
        checkDaemons()

        if lastCheckup == nil && recentVitals.isEmpty {
            appState = .noData
        } else {
            appState = .ready
        }
    }

    private func loadLastCheckup() {
        let path = "\(logDir)/checkup.ndjson"
        guard let data = FileManager.default.contents(atPath: path),
              let content = String(data: data, encoding: .utf8) else {
            Self.log("No checkup log found at \(path)")
            return
        }
        let lines = content.components(separatedBy: "\n").filter { !$0.isEmpty }
        guard let lastLine = lines.last,
              let lineData = lastLine.data(using: .utf8) else { return }
        do {
            lastCheckup = try JSONDecoder().decode(CheckupLogEntry.self, from: lineData)
            Self.log("Loaded last checkup: grade=\(lastCheckup?.grade.letter ?? "?")")
        } catch {
            Self.log("Failed to parse checkup log: \(error)")
        }
    }

    private func loadRecentVitals() {
        let path = "\(logDir)/vitals.ndjson"
        guard let data = FileManager.default.contents(atPath: path),
              let content = String(data: data, encoding: .utf8) else {
            Self.log("No vitals log found at \(path)")
            return
        }
        let lines = content.components(separatedBy: "\n").filter { !$0.isEmpty }
        let recent = lines.suffix(60)
        var samples: [VitalsSample] = []
        for line in recent {
            guard let lineData = line.data(using: .utf8) else { continue }
            if let sample = try? JSONDecoder().decode(VitalsSample.self, from: lineData) {
                samples.append(sample)
            }
        }
        recentVitals = samples
        Self.log("Loaded \(samples.count) vitals samples")
    }

    private func loadScore() {
        guard let path = cliPath else { return }
        Task {
            let result = shell(path, "score", "--json")
            if result.status == 0, let data = result.output.data(using: .utf8) {
                do {
                    let parsed = try JSONDecoder().decode(ScoreOutput.self, from: data)
                    score = parsed
                    overallGrade = parsed.worstGrade
                    Self.log("Score loaded: \(parsed.grade.letter), worst=\(parsed.worstGrade.letter)")
                } catch {
                    Self.log("Failed to parse score: \(error)")
                }
            }
        }
    }

    // MARK: - Daemon Status

    private func checkDaemons() {
        let result = shell("launchctl", "list")
        if result.status == 0 {
            let output = result.output
            checkupDaemon = output.contains("com.eidos.apple-a-day") ? .running : .stopped
            vitalsDaemon = output.contains("com.eidos.aad-vitals") ? .running : .stopped
            Self.log("Daemons: checkup=\(checkupDaemon.label), vitals=\(vitalsDaemon.label)")
        }
    }

    // MARK: - Actions

    func runCheckup() {
        guard let path = cliPath else { return }
        isRunningCheckup = true
        Self.log("Running checkup...")
        Task {
            let result = shell(path, "checkup", "--json")
            isRunningCheckup = false
            if result.status == 0 {
                Self.log("Checkup completed")
                loadData()
            } else {
                Self.log("Checkup failed: \(result.output)")
                appState = .error("Checkup failed: \(result.output.prefix(200))")
            }
        }
    }

    func openReport() {
        guard let path = cliPath else { return }
        Self.log("Opening HTML report...")
        Task {
            let result = shell(path, "report", "--html")
            if result.status != 0 {
                Self.log("Report failed: \(result.output)")
            }
        }
    }

    // MARK: - Shell Helper

    private func shell(_ args: String...) -> (status: Int32, output: String) {
        let process = Process()
        let pipe = Pipe()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        process.arguments = args
        process.standardOutput = pipe
        process.standardError = pipe
        process.environment = ProcessInfo.processInfo.environment
        do {
            try process.run()
            process.waitUntilExit()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            let output = String(data: data, encoding: .utf8) ?? ""
            return (process.terminationStatus, output)
        } catch {
            Self.log("Shell error: \(error)")
            return (-1, error.localizedDescription)
        }
    }
}
