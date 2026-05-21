import SwiftUI
import SwiftData

@main
struct CardShowProApp: App {
    @State private var authVM = AuthViewModel()
    @State private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            Group {
                if authVM.isAuthenticated {
                    RootView()
                } else if authVM.isLoading || AuthViewModel.autoLoginForTesting {
                    // Auto-login in progress, or showing the splash before login appears
                    SplashView(errorMessage: authVM.errorMessage) {
                        Task { await authVM.ensureDemoAccount() }
                    }
                } else {
                    LoginView()
                }
            }
            .environment(authVM)
            .environment(appState)
            .preferredColorScheme(.dark)
        }
        .modelContainer(for: [LocalInventoryItem.self, OfflineOperation.self])
    }
}

/// Brief logo + progress screen shown while the demo account is being set up.
private struct SplashView: View {
    let errorMessage: String?
    let retry: () -> Void

    var body: some View {
        ZStack {
            Theme.Colors.bg.ignoresSafeArea()
            VStack(spacing: Theme.Spacing.md) {
                Image(systemName: "rectangle.dashed.badge.record")
                    .font(.system(size: 64, weight: .light))
                    .foregroundStyle(Theme.Colors.amber)
                Text("CARDSHOW PRO")
                    .font(.system(size: 24, weight: .heavy, design: .rounded))
                    .tracking(4)
                    .foregroundStyle(Theme.Colors.textPrimary)

                if let errorMessage {
                    VStack(spacing: Theme.Spacing.sm) {
                        Text(errorMessage)
                            .font(Theme.Typography.caption)
                            .foregroundStyle(Theme.Colors.red)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, Theme.Spacing.lg)
                        Button(action: retry) {
                            Text("RETRY")
                                .font(Theme.Typography.label)
                                .tracking(2)
                                .padding(.horizontal, Theme.Spacing.lg)
                                .padding(.vertical, Theme.Spacing.sm)
                                .background(Capsule().fill(Theme.Colors.amber))
                                .foregroundStyle(.black)
                        }
                    }
                    .padding(.top, Theme.Spacing.md)
                } else {
                    ProgressView()
                        .tint(Theme.Colors.amber)
                        .padding(.top, Theme.Spacing.md)
                    Text("Connecting…")
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Colors.textTertiary)
                }
            }
        }
    }
}
