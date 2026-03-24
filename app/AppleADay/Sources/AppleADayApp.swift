import SwiftUI

@main
struct AppleADayApp: App {
    @StateObject private var healthService = HealthService()

    init() {
        HealthService.log("AppleADayApp init — process \(ProcessInfo.processInfo.processIdentifier)")
    }

    var body: some Scene {
        MenuBarExtra {
            ContentView()
                .environmentObject(healthService)
        } label: {
            MenuBarStatusLabel(grade: healthService.overallGrade)
        }
        .menuBarExtraStyle(.window)
    }
}

private struct MenuBarStatusLabel: View {
    let grade: HealthGrade?

    var body: some View {
        HStack(spacing: 2) {
            Image(systemName: "stethoscope")
                .renderingMode(.template)
                .foregroundColor(grade?.color ?? .gray)
            if let letter = grade?.letter {
                Text(letter)
                    .font(.caption2.bold())
                    .foregroundColor(grade?.color ?? .gray)
            }
        }
    }
}
