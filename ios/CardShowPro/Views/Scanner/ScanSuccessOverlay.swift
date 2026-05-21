import SwiftUI

/// Fullscreen success overlay shown after a successful scan + log.
/// Vendor picks one of three actions:
///   - DONE         → pops back to home
///   - SCAN ANOTHER → resumes scanning (multi-scan / bulk-buy mode)
///   - UNDO         → deletes the just-logged item and resumes scanning
struct ScanSuccessOverlay: View {
    let item: LocalInventoryItem?
    let logMode: LogMode
    let onDone: () -> Void
    let onScanAnother: () -> Void
    let onUndo: () -> Void

    var body: some View {
        ZStack {
            // Dim the camera fully — this is a modal moment
            Color.black.opacity(0.78).ignoresSafeArea()

            VStack(spacing: Theme.Spacing.lg) {
                Spacer()

                // Big checkmark + mode tag
                ZStack {
                    Circle()
                        .fill(logMode.tint.opacity(0.18))
                        .frame(width: 96, height: 96)
                    Image(systemName: "checkmark")
                        .font(.system(size: 44, weight: .heavy))
                        .foregroundStyle(logMode.tint)
                }

                VStack(spacing: 4) {
                    Text("\(logMode.title) LOGGED")
                        .font(.system(size: 14, weight: .heavy, design: .rounded))
                        .tracking(3)
                        .foregroundStyle(logMode.tint)

                    Text(item?.cardName ?? "Card")
                        .font(.system(size: 28, weight: .heavy, design: .rounded))
                        .foregroundStyle(Theme.Colors.textPrimary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, Theme.Spacing.lg)

                    if let price = item?.purchasePrice ?? item?.salePrice {
                        Text(String(format: "$%.2f", price))
                            .font(Theme.Typography.priceLg)
                            .foregroundStyle(logMode.tint)
                            .padding(.top, 4)
                    }
                }

                Spacer()

                // Three actions stacked vertically — DONE is biggest (primary)
                VStack(spacing: Theme.Spacing.sm) {
                    Button(action: onScanAnother) {
                        Label("SCAN ANOTHER", systemImage: "viewfinder")
                            .font(Theme.Typography.title)
                            .tracking(2)
                            .frame(maxWidth: .infinity)
                            .frame(height: 56)
                            .background(logMode.tint)
                            .foregroundStyle(.black)
                            .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.lg))
                    }

                    Button(action: onDone) {
                        Text("DONE")
                            .font(Theme.Typography.title)
                            .tracking(2)
                            .frame(maxWidth: .infinity)
                            .frame(height: 48)
                            .background(
                                RoundedRectangle(cornerRadius: Theme.Radius.lg)
                                    .stroke(Theme.Colors.border, lineWidth: 1)
                            )
                            .foregroundStyle(Theme.Colors.textPrimary)
                    }

                    Button(action: onUndo) {
                        Label("UNDO", systemImage: "arrow.uturn.backward")
                            .font(Theme.Typography.label)
                            .tracking(2)
                            .frame(maxWidth: .infinity)
                            .frame(height: 40)
                            .foregroundStyle(Theme.Colors.red)
                    }
                }
                .padding(.horizontal, Theme.Spacing.lg)
                .padding(.bottom, Theme.Spacing.xl)
            }
        }
    }
}
