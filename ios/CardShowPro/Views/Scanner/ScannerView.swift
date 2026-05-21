import SwiftUI
import AVFoundation

struct ScannerView: View {
    let logMode: LogMode
    @State private var vm = ScannerViewModel()
    @Environment(AppState.self) private var appState
    @Environment(\.dismiss) private var dismiss

    init(logMode: LogMode = .buy) {
        self.logMode = logMode
    }

    var body: some View {
        ZStack {
            // Camera preview fills the entire screen
            CameraPreviewView(layer: vm.previewLayer)
                .ignoresSafeArea()

            // Card guide frame with dimmed surround + detection overlay
            CardOverlayView(cardRect: vm.cardOverlayRect, scanState: vm.scanState)
                .ignoresSafeArea()
                .allowsHitTesting(false)

            // Top brand bar
            VStack {
                topBar
                Spacer()
                bottomHint
            }

            // Success overlay — appears after every successful log.
            // Vendor decides whether to scan more or go home.
            if vm.didJustLog {
                ScanSuccessOverlay(
                    item: vm.lastLoggedCard,
                    logMode: logMode,
                    onDone: {
                        vm.didJustLog = false
                        vm.lastLoggedCard = nil
                        dismiss()
                    },
                    onScanAnother: { vm.continueScanning() },
                    onUndo: { Task { await vm.undoLastLog() } }
                )
                .transition(.opacity.combined(with: .scale(scale: 0.96)))
                .animation(.spring(response: 0.35, dampingFraction: 0.85), value: vm.didJustLog)
            }
        }
        .sheet(isPresented: Binding(
            get: { if case .awaitingConfirmation = vm.scanState { return true }; return false },
            set: { if !$0 { vm.dismissAndReset() } }
        )) {
            if case .awaitingConfirmation(let match) = vm.scanState {
                ScanResultSheet(
                    match: match,
                    logMode: logMode,
                    isAwaitingConfirmation: true,
                    onConfirm: { price, condition, status in
                        Task { await vm.confirmCard(match, price: price, condition: condition, status: status, sourceLocation: appState.activeShowName) }
                    },
                    onReject: { vm.dismissAndReset() }
                )
                .presentationDetents([.medium, .large])
                .presentationBackground(Theme.Colors.bg)
            }
        }
        .sheet(isPresented: Binding(
            get: { if case .manualAssist = vm.scanState { return true }; return false },
            set: { if !$0 { vm.dismissAndReset() } }
        )) {
            if case .manualAssist(let ocrHint) = vm.scanState {
                ManualAssistView(ocrHint: ocrHint) { match in
                    Task { await vm.confirmCard(match, price: match.marketPrice, condition: "near_mint", status: logMode.inventoryStatus, sourceLocation: appState.activeShowName) }
                }
                .presentationDetents([.medium, .large])
                .presentationBackground(Theme.Colors.bg)
            }
        }
        .task {
            vm.logMode = logMode
            await vm.startCamera()
        }
        .onDisappear { Task { await vm.stopCamera() } }
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(.hidden, for: .navigationBar)
    }

    // MARK: - Top bar

    private var topBar: some View {
        HStack(spacing: Theme.Spacing.sm) {
            // Mode pill — biggest signal on the screen so the vendor knows what
            // action will be taken when the scan auto-confirms.
            HStack(spacing: 6) {
                Image(systemName: logMode.icon)
                    .font(.system(size: 14, weight: .bold))
                Text("\(logMode.title) MODE")
                    .font(Theme.Typography.label)
                    .tracking(2)
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .background(Capsule().fill(logMode.tint))
            .foregroundStyle(.black)

            Spacer()

            if !appState.activeShowName.isEmpty {
                HStack(spacing: 6) {
                    Circle().fill(Theme.Colors.green).frame(width: 6, height: 6)
                    Text(appState.activeShowName.uppercased())
                        .font(Theme.Typography.label)
                        .tracking(1)
                        .foregroundStyle(Theme.Colors.green)
                }
            }
        }
        .padding(.horizontal, Theme.Spacing.md)
        .padding(.vertical, Theme.Spacing.sm)
        .background(.ultraThinMaterial)
    }

    // MARK: - Bottom hint

    private var bottomHint: some View {
        Group {
            switch vm.scanState {
            case .idle, .scanning:
                Text(vm.cardOverlayRect == nil ? "POINT AT A CARD" : "HOLD STEADY…")
                    .font(Theme.Typography.label)
                    .tracking(2)
                    .foregroundStyle(Theme.Colors.textSecondary)
                    .padding(.horizontal, Theme.Spacing.md)
                    .padding(.vertical, Theme.Spacing.sm)
                    .background(Capsule().fill(Color.black.opacity(0.5)))
                    .padding(.bottom, 24)
            default:
                EmptyView()
            }
        }
    }

}

// MARK: - Camera preview UIViewRepresentable

struct CameraPreviewView: UIViewRepresentable {
    let layer: AVCaptureVideoPreviewLayer?

    func makeUIView(context: Context) -> UIView {
        let view = UIView()
        view.backgroundColor = .black
        return view
    }

    func updateUIView(_ uiView: UIView, context: Context) {
        guard let layer else { return }
        layer.frame = uiView.bounds
        if layer.superlayer == nil {
            uiView.layer.addSublayer(layer)
        }
    }
}

// MARK: - Manual assist sheet (dark-themed)

struct ManualAssistView: View {
    let ocrHint: String
    let onSelect: (CardMatch) -> Void

    @State private var searchText: String
    @State private var results: [CardSearchResult] = []
    @State private var isSearching = false
    @Environment(\.dismiss) private var dismiss

    init(ocrHint: String, onSelect: @escaping (CardMatch) -> Void) {
        self.ocrHint = ocrHint
        self.onSelect = onSelect
        _searchText = State(initialValue: ocrHint)
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.Colors.bg.ignoresSafeArea()

                VStack(spacing: 0) {
                    VStack(spacing: Theme.Spacing.sm) {
                        HStack(spacing: 6) {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .foregroundStyle(Theme.Colors.amber)
                            Text("COULDN'T IDENTIFY")
                                .font(Theme.Typography.label)
                                .tracking(1)
                                .foregroundStyle(Theme.Colors.amber)
                        }
                        if !ocrHint.isEmpty {
                            Text("OCR read: \"\(ocrHint)\"")
                                .font(Theme.Typography.captionMono)
                                .foregroundStyle(Theme.Colors.textTertiary)
                        }
                    }
                    .padding(.top, Theme.Spacing.md)
                    .padding(.bottom, Theme.Spacing.md)

                    TextField("Search card name", text: $searchText)
                        .font(Theme.Typography.body)
                        .foregroundStyle(Theme.Colors.textPrimary)
                        .padding(Theme.Spacing.md)
                        .background(
                            RoundedRectangle(cornerRadius: Theme.Radius.md)
                                .fill(Theme.Colors.surface)
                        )
                        .padding(.horizontal, Theme.Spacing.md)
                        .onChange(of: searchText) { _, q in
                            Task { await search(q) }
                        }

                    if isSearching {
                        ProgressView()
                            .tint(Theme.Colors.amber)
                            .padding()
                    }

                    ScrollView {
                        LazyVStack(spacing: Theme.Spacing.sm) {
                            ForEach(results) { card in
                                Button {
                                    onSelect(CardMatch(
                                        cardId: card.id, name: card.name,
                                        setName: card.setName, number: card.number,
                                        imageUrlSm: card.imageUrlSm,
                                        confidence: 1.0, marketPrice: nil, pipeline: "manual"
                                    ))
                                    dismiss()
                                } label: {
                                    HStack(spacing: Theme.Spacing.md) {
                                        if let url = card.imageUrlSm.flatMap(URL.init) {
                                            AsyncImage(url: url) { img in
                                                img.resizable().aspectRatio(contentMode: .fill)
                                            } placeholder: {
                                                Theme.Colors.surfaceHi
                                            }
                                            .frame(width: 40, height: 56)
                                            .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.sm))
                                        }
                                        VStack(alignment: .leading) {
                                            Text(card.name)
                                                .font(Theme.Typography.body)
                                                .foregroundStyle(Theme.Colors.textPrimary)
                                            if let set = card.setName {
                                                Text(set)
                                                    .font(Theme.Typography.caption)
                                                    .foregroundStyle(Theme.Colors.textTertiary)
                                            }
                                        }
                                        Spacer()
                                    }
                                    .padding(Theme.Spacing.md)
                                    .background(
                                        RoundedRectangle(cornerRadius: Theme.Radius.md)
                                            .fill(Theme.Colors.surface)
                                    )
                                }
                                .buttonStyle(.plain)
                            }
                        }
                        .padding(Theme.Spacing.md)
                    }
                }
            }
            .navigationTitle("Manual Search")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                        .foregroundStyle(Theme.Colors.textSecondary)
                }
            }
        }
        .task { await search(ocrHint) }
    }

    private func search(_ query: String) async {
        guard query.count >= 2 else { results = []; return }
        isSearching = true
        results = await PokemonTCGService.shared.search(query: query, limit: 10)
        isSearching = false
    }
}
