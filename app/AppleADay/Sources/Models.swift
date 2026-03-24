import SwiftUI

// MARK: - Health Grade

enum HealthGrade: String, Codable {
    case a = "A"
    case b = "B"
    case c = "C"
    case d = "D"
    case f = "F"

    var letter: String { rawValue }

    var color: Color {
        switch self {
        case .a, .b: return .green
        case .c: return .yellow
        case .d: return .orange
        case .f: return .red
        }
    }

    init(score: Double) {
        switch score {
        case 90...100: self = .a
        case 75..<90: self = .b
        case 50..<75: self = .c
        case 25..<50: self = .d
        default: self = .f
        }
    }
}

// MARK: - Score Output (aad score --json)

struct ScoreOutput: Codable {
    let ts: String
    let score: Double
    let grade: HealthGrade
    let matrix: [String: Double]

    static let dimensions = [
        "stability", "memory", "storage", "services",
        "security", "infra", "network", "cpu", "thermal"
    ]

    var worstGrade: HealthGrade {
        guard let worst = matrix.values.min() else { return .a }
        return HealthGrade(score: worst)
    }
}

// MARK: - Checkup Log Entry (checkup.ndjson)

struct CheckupLogEntry: Codable {
    let ts: String
    let trigger: String
    let durationMs: Double
    let score: Double
    let grade: HealthGrade
    let matrix: [String: Double]
    let counts: SeverityCounts
    let criticals: [String]
    let warnings: [String]

    enum CodingKeys: String, CodingKey {
        case ts, trigger, score, grade, matrix, counts, criticals, warnings
        case durationMs = "duration_ms"
    }
}

struct SeverityCounts: Codable {
    let critical: Int
    let warning: Int
    let info: Int
    let ok: Int
}

// MARK: - Vitals Sample (vitals.ndjson)

struct VitalsSample: Codable {
    let ts: String
    let load: [Double]
    let cores: Int
    let top: [[AnyCodable]]?
    let thermal: Int?
    let swapMb: Int?

    enum CodingKeys: String, CodingKey {
        case ts, load, cores, top, thermal
        case swapMb = "swap_mb"
    }

    var load1m: Double { load.first ?? 0 }
    var thermalLevel: String {
        switch thermal {
        case 0: return "Nominal"
        case 1: return "Moderate"
        case 2: return "Heavy"
        case 3: return "Trapping"
        case 4: return "Sleeping"
        default: return "Unknown"
        }
    }
}

// MARK: - AnyCodable helper for mixed-type arrays

struct AnyCodable: Codable {
    let value: Any

    init(_ value: Any) { self.value = value }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let d = try? container.decode(Double.self) {
            value = d
        } else if let s = try? container.decode(String.self) {
            value = s
        } else if let i = try? container.decode(Int.self) {
            value = i
        } else {
            value = "?"
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        if let d = value as? Double {
            try container.encode(d)
        } else if let s = value as? String {
            try container.encode(s)
        } else if let i = value as? Int {
            try container.encode(i)
        }
    }
}

// MARK: - Daemon Status

enum DaemonStatus {
    case running
    case stopped
    case unknown

    var label: String {
        switch self {
        case .running: return "Running"
        case .stopped: return "Stopped"
        case .unknown: return "Unknown"
        }
    }

    var color: Color {
        switch self {
        case .running: return .green
        case .stopped: return .red
        case .unknown: return .gray
        }
    }
}

// MARK: - Report Entry

struct ReportEntry: Identifiable {
    let id: String
    let filename: String
    let path: String
    let timestamp: String

    init(filename: String, path: String, timestamp: String) {
        self.id = filename
        self.filename = filename
        self.path = path
        self.timestamp = timestamp
    }
}

// MARK: - App State

enum AppState {
    case loading
    case cliNotFound
    case noData
    case ready
    case error(String)
}
