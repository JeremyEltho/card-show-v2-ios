import Foundation
import Observation

@Observable
final class AuthViewModel {
    var isAuthenticated = false
    var currentUser: AuthUser?
    var isLoading = false
    var errorMessage: String?

    private let network = NetworkService.shared
    private let auth = AuthService.shared

    // Testing convenience — auto-login as demo user on launch when not authenticated.
    // Flip to false to require manual login (e.g. before App Store submission).
    static let autoLoginForTesting = true
    private static let demoEmail    = "demo@pokescan.com"
    private static let demoPassword = "pokemon123"
    private static let demoName     = "Demo Vendor"

    init() {
        Task {
            isAuthenticated = await auth.isAuthenticated()
            currentUser = await auth.currentUser
            if !isAuthenticated && Self.autoLoginForTesting {
                await ensureDemoAccount()
            }
        }
    }

    /// Auto-creates + logs in the demo user. Idempotent: silently re-uses an
    /// existing demo account if one is already on the backend.
    func ensureDemoAccount() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            let user = try await auth.login(
                email: Self.demoEmail,
                password: Self.demoPassword,
                network: network
            )
            currentUser = user
            isAuthenticated = true
            return
        } catch {
            // Login failed — try to register
        }
        do {
            let user = try await auth.register(
                email: Self.demoEmail,
                password: Self.demoPassword,
                displayName: Self.demoName,
                network: network
            )
            currentUser = user
            isAuthenticated = true
        } catch {
            errorMessage = "Couldn't connect to backend. Open Settings → Connection to fix the URL."
        }
    }

    func login(email: String, password: String) async {
        isLoading = true
        errorMessage = nil
        do {
            let user = try await auth.login(email: email, password: password, network: network)
            currentUser = user
            isAuthenticated = true
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func register(email: String, password: String, displayName: String) async {
        isLoading = true
        errorMessage = nil
        do {
            let user = try await auth.register(email: email, password: password, displayName: displayName, network: network)
            currentUser = user
            isAuthenticated = true
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func logout() async {
        await auth.logout(network: network)
        currentUser = nil
        isAuthenticated = false
    }
}
