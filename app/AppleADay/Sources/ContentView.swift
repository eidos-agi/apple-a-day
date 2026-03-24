import SwiftUI

struct ContentView: View {
    @EnvironmentObject var healthService: HealthService

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Image(systemName: "stethoscope")
                    .font(.title3)
                    .foregroundColor(.accentColor)
                Text("Apple a Day")
                    .font(.headline)
                Spacer()
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)

            Divider()

            // Content based on app state
            switch healthService.appState {
            case .loading:
                LoadingView()
            case .cliNotFound:
                CliNotFoundView()
            case .noData:
                NoDataView(onRunCheckup: { healthService.runCheckup() })
            case .ready:
                HealthPanelView()
                    .environmentObject(healthService)
            case .error(let message):
                ErrorView(message: message, onRetry: { healthService.loadData() })
            }
        }
        .frame(width: 320)
        .onAppear {
            healthService.bootstrap()
        }
    }
}

// MARK: - State Views

private struct LoadingView: View {
    var body: some View {
        VStack(spacing: 8) {
            ProgressView()
            Text("Loading health data...")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding(20)
    }
}

private struct CliNotFoundView: View {
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle")
                .font(.largeTitle)
                .foregroundColor(.orange)
            Text("apple-a-day CLI not found")
                .font(.subheadline.bold())
            Text("Install with:")
                .font(.caption)
                .foregroundColor(.secondary)
            Text("pip install -e ~/repos-eidos-agi/apple-a-day")
                .font(.system(.caption, design: .monospaced))
                .padding(6)
                .background(Color.gray.opacity(0.1))
                .cornerRadius(4)
        }
        .padding(20)
    }
}

private struct NoDataView: View {
    let onRunCheckup: () -> Void

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "heart.text.square")
                .font(.largeTitle)
                .foregroundColor(.secondary)
            Text("No health data yet")
                .font(.subheadline.bold())
            Text("Run your first checkup to see how your Mac is doing.")
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
            Button(action: onRunCheckup) {
                Label("Run First Checkup", systemImage: "play.fill")
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.small)
        }
        .padding(20)
    }
}

private struct ErrorView: View {
    let message: String
    let onRetry: () -> Void

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "xmark.circle")
                .font(.largeTitle)
                .foregroundColor(.red)
            Text(message)
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
            Button("Retry", action: onRetry)
                .buttonStyle(.bordered)
                .controlSize(.small)
        }
        .padding(20)
    }
}

// MARK: - Health Panel

struct HealthPanelView: View {
    @EnvironmentObject var healthService: HealthService

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                // Overall Grade Card
                if let score = healthService.score {
                    GradeCardView(score: score)
                }

                // Daemon Status
                DaemonStatusRow(
                    checkup: healthService.checkupDaemon,
                    vitals: healthService.vitalsDaemon
                )

                // Last Checkup Info
                if let checkup = healthService.lastCheckup {
                    LastCheckupRow(entry: checkup)
                }

                // Dimension Scores
                if let score = healthService.score {
                    DimensionScoresView(matrix: score.matrix)
                }

                // Active Findings
                if let checkup = healthService.lastCheckup {
                    FindingsView(criticals: checkup.criticals, warnings: checkup.warnings)
                }

                // Vitals Sparklines
                if !healthService.recentVitals.isEmpty {
                    VitalsView(samples: healthService.recentVitals)
                }

                Divider()

                // Quick Actions
                QuickActionsView()
                    .environmentObject(healthService)
            }
            .padding(12)
        }
    }
}

// MARK: - Grade Card

private struct GradeCardView: View {
    let score: ScoreOutput

    var body: some View {
        HStack(spacing: 12) {
            Text(score.worstGrade.letter)
                .font(.system(size: 36, weight: .bold, design: .rounded))
                .foregroundColor(score.worstGrade.color)
            VStack(alignment: .leading, spacing: 2) {
                Text("Overall Health")
                    .font(.subheadline.bold())
                Text("Score: \(Int(score.score))/100")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            Spacer()
        }
        .padding(10)
        .background(score.worstGrade.color.opacity(0.1))
        .cornerRadius(8)
    }
}

// MARK: - Daemon Status Row

private struct DaemonStatusRow: View {
    let checkup: DaemonStatus
    let vitals: DaemonStatus

    var body: some View {
        HStack {
            Label {
                Text("Daily Checkup")
                    .font(.caption)
            } icon: {
                Circle()
                    .fill(checkup.color)
                    .frame(width: 6, height: 6)
            }
            Spacer()
            Label {
                Text("Vitals Monitor")
                    .font(.caption)
            } icon: {
                Circle()
                    .fill(vitals.color)
                    .frame(width: 6, height: 6)
            }
        }
    }
}

// MARK: - Last Checkup

private struct LastCheckupRow: View {
    let entry: CheckupLogEntry

    var body: some View {
        HStack {
            Text("Last checkup")
                .font(.caption)
                .foregroundColor(.secondary)
            Spacer()
            Text(formatTimestamp(entry.ts))
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }

    private func formatTimestamp(_ ts: String) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withFullDate, .withTime, .withColonSeparatorInTime]
        if let date = formatter.date(from: ts) {
            let relative = RelativeDateTimeFormatter()
            relative.unitsStyle = .abbreviated
            return relative.localizedString(for: date, relativeTo: Date())
        }
        return ts
    }
}

// MARK: - Dimension Scores

private struct DimensionScoresView: View {
    let matrix: [String: Double]

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Health Dimensions")
                .font(.caption.bold())
                .foregroundColor(.secondary)
            ForEach(ScoreOutput.dimensions, id: \.self) { dim in
                if let value = matrix[dim] {
                    let grade = HealthGrade(score: value)
                    HStack {
                        Circle()
                            .fill(grade.color)
                            .frame(width: 8, height: 8)
                        Text(dim.capitalized)
                            .font(.caption)
                        Spacer()
                        Text(grade.letter)
                            .font(.caption.bold())
                            .foregroundColor(grade.color)
                        Text("\(Int(value))")
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .frame(width: 24, alignment: .trailing)
                    }
                }
            }
        }
    }
}

// MARK: - Findings

private struct FindingsView: View {
    let criticals: [String]
    let warnings: [String]

    var body: some View {
        if !criticals.isEmpty || !warnings.isEmpty {
            VStack(alignment: .leading, spacing: 4) {
                Text("Active Findings")
                    .font(.caption.bold())
                    .foregroundColor(.secondary)
                ForEach(criticals, id: \.self) { finding in
                    HStack(alignment: .top, spacing: 4) {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundColor(.red)
                            .font(.caption)
                        Text(finding)
                            .font(.caption)
                    }
                }
                ForEach(warnings, id: \.self) { finding in
                    HStack(alignment: .top, spacing: 4) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundColor(.orange)
                            .font(.caption)
                        Text(finding)
                            .font(.caption)
                    }
                }
            }
        }
    }
}

// MARK: - Vitals Sparklines

private struct VitalsView: View {
    let samples: [VitalsSample]

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Vitals (last hour)")
                .font(.caption.bold())
                .foregroundColor(.secondary)

            // CPU Load
            let loads = samples.map { $0.load1m }
            let cores = Double(samples.last?.cores ?? 8)
            SparklineRow(
                label: "CPU Load",
                data: loads,
                current: String(format: "%.1f", loads.last ?? 0),
                threshold: cores,
                color: sparkColor(loads.last ?? 0, threshold: cores)
            )

            // Thermal
            let thermals = samples.compactMap { $0.thermal }.map { Double($0) }
            if !thermals.isEmpty {
                SparklineRow(
                    label: "Thermal",
                    data: thermals,
                    current: samples.last.flatMap { $0.thermal != nil ? $0.thermalLevel : nil } ?? "—",
                    threshold: 2,
                    color: sparkColor(thermals.last ?? 0, threshold: 2)
                )
            }

            // Swap
            let swaps = samples.compactMap { $0.swapMb }.map { Double($0) }
            if !swaps.isEmpty {
                SparklineRow(
                    label: "Swap",
                    data: swaps,
                    current: "\(swaps.last.map { Int($0) } ?? 0) MB",
                    threshold: 1024,
                    color: sparkColor(swaps.last ?? 0, threshold: 1024)
                )
            }
        }
    }

    private func sparkColor(_ value: Double, threshold: Double) -> Color {
        let ratio = value / max(threshold, 1)
        if ratio < 0.5 { return .green }
        if ratio < 0.8 { return .yellow }
        if ratio < 1.0 { return .orange }
        return .red
    }
}

private struct SparklineRow: View {
    let label: String
    let data: [Double]
    let current: String
    let threshold: Double
    let color: Color

    var body: some View {
        HStack(spacing: 6) {
            Text(label)
                .font(.system(.caption2))
                .foregroundColor(.secondary)
                .frame(width: 52, alignment: .leading)
            SparklineView(data: data, color: color)
                .frame(height: 16)
            Text(current)
                .font(.system(.caption2, design: .monospaced))
                .foregroundColor(color)
                .frame(width: 44, alignment: .trailing)
        }
    }
}

// MARK: - SparklineView (native SwiftUI Path)

struct SparklineView: View {
    let data: [Double]
    let color: Color

    var body: some View {
        GeometryReader { geo in
            if data.count >= 2 {
                let minVal = data.min() ?? 0
                let maxVal = max(data.max() ?? 1, minVal + 0.001)
                let range = maxVal - minVal

                Path { path in
                    for (i, value) in data.enumerated() {
                        let x = geo.size.width * CGFloat(i) / CGFloat(data.count - 1)
                        let y = geo.size.height * (1 - CGFloat((value - minVal) / range))
                        if i == 0 {
                            path.move(to: CGPoint(x: x, y: y))
                        } else {
                            path.addLine(to: CGPoint(x: x, y: y))
                        }
                    }
                }
                .stroke(color, lineWidth: 1.5)
            }
        }
    }
}

// MARK: - Quick Actions

private struct QuickActionsView: View {
    @EnvironmentObject var healthService: HealthService

    var body: some View {
        HStack(spacing: 8) {
            Button(action: { healthService.runCheckup() }) {
                if healthService.isRunningCheckup {
                    ProgressView()
                        .controlSize(.small)
                } else {
                    Label("Checkup", systemImage: "heart.text.square")
                }
            }
            .disabled(healthService.isRunningCheckup)

            Button(action: { healthService.openReport() }) {
                Label("Report", systemImage: "doc.text")
            }

            Button(action: { NSApplication.shared.terminate(nil) }) {
                Label("Quit", systemImage: "power")
            }
        }
        .buttonStyle(.bordered)
        .controlSize(.small)
        .font(.caption)
    }
}
