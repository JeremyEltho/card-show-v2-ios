import SwiftUI

/// Editable card detail. Tap any row in TransactionsView to land here.
/// Vendors can:
///   - Edit notes, condition, prices, source, payment method, counterparty
///   - Change the status (e.g. promote bought → sold)
///   - Delete the entry
struct CardDetailView: View {
    let item: LocalInventoryItem
    let vm: InventoryViewModel
    @Environment(\.dismiss) private var dismiss

    // Editable fields — populated from the item on .task
    @State private var status: String = "bought"
    @State private var condition: String = "near_mint"
    @State private var purchasePriceText: String = ""
    @State private var salePriceText: String = ""
    @State private var sourceLocation: String = ""
    @State private var paymentMethod: String = ""
    @State private var counterparty: String = ""
    @State private var notes: String = ""
    @State private var showDeleteConfirm = false

    private let conditions = ["mint", "near_mint", "lightly_played", "moderately_played", "heavily_played", "damaged"]
    private let paymentMethods = ["", "Cash", "Venmo", "Zelle", "PayPal", "Card", "Trade"]
    private let statuses = ["bought", "sold", "traded"]

    var body: some View {
        ZStack {
            Theme.Colors.bg.ignoresSafeArea()

            ScrollView {
                VStack(spacing: Theme.Spacing.md) {
                    heroImage
                    titleBlock
                    statusPicker
                    priceSection
                    detailsSection
                    notesSection
                    deleteButton
                }
                .padding(Theme.Spacing.md)
                .padding(.bottom, Theme.Spacing.xl)
            }
        }
        .navigationTitle(item.cardName ?? "Card")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Theme.Colors.bg, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button("Save") { save() }
                    .foregroundStyle(Theme.Colors.amber)
                    .fontWeight(.semibold)
            }
        }
        .confirmationDialog("Delete this card?", isPresented: $showDeleteConfirm, titleVisibility: .visible) {
            Button("Delete", role: .destructive) {
                Task {
                    await vm.delete(item: item)
                    dismiss()
                }
            }
            Button("Cancel", role: .cancel) {}
        }
        .onAppear { loadFromItem() }
    }

    // MARK: - Sections

    private var heroImage: some View {
        Group {
            if let url = item.cardImageUrl.flatMap(URL.init) {
                AsyncImage(url: url) { phase in
                    switch phase {
                    case .success(let img): img.resizable().aspectRatio(contentMode: .fit)
                    default: Theme.Colors.surface
                    }
                }
                .frame(maxWidth: 200, maxHeight: 280)
                .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.md))
                .shadow(color: .black.opacity(0.5), radius: 24, y: 12)
            }
        }
    }

    private var titleBlock: some View {
        VStack(spacing: Theme.Spacing.xs) {
            Text(item.cardName ?? item.cardId)
                .font(Theme.Typography.headline)
                .foregroundStyle(Theme.Colors.textPrimary)
                .multilineTextAlignment(.center)
            if let set = extractSetName(from: item) {
                Text(set)
                    .font(Theme.Typography.body)
                    .foregroundStyle(Theme.Colors.textSecondary)
            }
            if let market = extractMarketPrice(from: item) {
                Text("MARKET · " + String(format: "$%.2f", market))
                    .font(Theme.Typography.label)
                    .tracking(1.5)
                    .foregroundStyle(Theme.Colors.amber)
                    .padding(.top, 4)
            }
        }
    }

    private var statusPicker: some View {
        sectionCard("STATUS") {
            HStack(spacing: 0) {
                ForEach(statuses, id: \.self) { s in
                    Button { status = s } label: {
                        Text(s.uppercased())
                            .font(Theme.Typography.label)
                            .tracking(1.5)
                            .frame(maxWidth: .infinity)
                            .frame(height: 40)
                            .background(status == s ? tint(for: s).opacity(0.2) : Color.clear)
                            .foregroundStyle(status == s ? tint(for: s) : Theme.Colors.textTertiary)
                            .overlay(
                                RoundedRectangle(cornerRadius: 8)
                                    .stroke(status == s ? tint(for: s) : Color.clear, lineWidth: 1)
                            )
                    }
                    .buttonStyle(.plain)
                    .padding(2)
                }
            }
        }
    }

    private var priceSection: some View {
        sectionCard("PRICES") {
            VStack(spacing: 8) {
                priceField(label: "PAID", value: $purchasePriceText, tint: Theme.Colors.blue)
                Divider().background(Theme.Colors.divider)
                priceField(label: "SOLD FOR", value: $salePriceText, tint: Theme.Colors.green)
            }
        }
    }

    private var detailsSection: some View {
        sectionCard("DETAILS") {
            VStack(spacing: 8) {
                Picker("Condition", selection: $condition) {
                    ForEach(conditions, id: \.self) { c in
                        Text(c.replacingOccurrences(of: "_", with: " ").capitalized).tag(c)
                    }
                }
                .pickerStyle(.menu)
                .tint(Theme.Colors.amber)

                Divider().background(Theme.Colors.divider)

                textField(label: "Source", text: $sourceLocation, placeholder: "e.g. GameStop Nationals")
                Divider().background(Theme.Colors.divider)
                textField(label: "Counterparty", text: $counterparty, placeholder: "who you bought from / sold to")
                Divider().background(Theme.Colors.divider)

                HStack {
                    Text("Payment")
                        .font(Theme.Typography.body)
                        .foregroundStyle(Theme.Colors.textSecondary)
                    Spacer()
                    Picker("Payment", selection: $paymentMethod) {
                        ForEach(paymentMethods, id: \.self) { p in
                            Text(p.isEmpty ? "—" : p).tag(p)
                        }
                    }
                    .pickerStyle(.menu)
                    .tint(Theme.Colors.amber)
                }
            }
        }
    }

    private var notesSection: some View {
        sectionCard("NOTES") {
            ZStack(alignment: .topLeading) {
                if notes.isEmpty {
                    Text("Free-form notes — anything you want to remember")
                        .font(Theme.Typography.body)
                        .foregroundStyle(Theme.Colors.textTertiary)
                        .padding(.top, 8)
                        .padding(.leading, 4)
                }
                TextEditor(text: $notes)
                    .font(Theme.Typography.body)
                    .foregroundStyle(Theme.Colors.textPrimary)
                    .scrollContentBackground(.hidden)
                    .frame(minHeight: 80)
            }
        }
    }

    private var deleteButton: some View {
        Button(role: .destructive) {
            showDeleteConfirm = true
        } label: {
            Label("DELETE CARD", systemImage: "trash.fill")
                .font(Theme.Typography.label)
                .tracking(2)
                .frame(maxWidth: .infinity)
                .frame(height: 48)
                .background(Theme.Colors.redSoft)
                .foregroundStyle(Theme.Colors.red)
                .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.md))
        }
        .padding(.top, Theme.Spacing.md)
    }

    // MARK: - Helpers

    private func tint(for status: String) -> Color {
        switch status {
        case "bought": return Theme.Colors.blue
        case "sold":   return Theme.Colors.green
        case "traded": return Theme.Colors.amber
        default:       return Theme.Colors.textSecondary
        }
    }

    @ViewBuilder
    private func sectionCard<C: View>(_ title: String, @ViewBuilder content: () -> C) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
            Text(title)
                .font(Theme.Typography.label).tracking(1)
                .foregroundStyle(Theme.Colors.textTertiary)
                .padding(.horizontal, Theme.Spacing.sm)
            VStack { content() }
                .padding(Theme.Spacing.md)
                .background(
                    RoundedRectangle(cornerRadius: Theme.Radius.md)
                        .fill(Theme.Colors.surface)
                        .overlay(
                            RoundedRectangle(cornerRadius: Theme.Radius.md)
                                .stroke(Theme.Colors.border, lineWidth: 1)
                        )
                )
        }
    }

    private func priceField(label: String, value: Binding<String>, tint: Color) -> some View {
        HStack {
            Text(label).font(Theme.Typography.label).tracking(1)
                .foregroundStyle(Theme.Colors.textTertiary)
                .frame(width: 90, alignment: .leading)
            Spacer()
            Text("$").foregroundStyle(Theme.Colors.textSecondary)
            TextField("0.00", text: value)
                .keyboardType(.decimalPad)
                .multilineTextAlignment(.trailing)
                .frame(width: 110)
                .font(Theme.Typography.priceMd)
                .foregroundStyle(tint)
        }
    }

    private func textField(label: String, text: Binding<String>, placeholder: String) -> some View {
        HStack {
            Text(label)
                .font(Theme.Typography.body)
                .foregroundStyle(Theme.Colors.textSecondary)
            Spacer()
            TextField(placeholder, text: text)
                .multilineTextAlignment(.trailing)
                .foregroundStyle(Theme.Colors.textPrimary)
                .font(Theme.Typography.body)
        }
    }

    // MARK: - Load / save

    private func loadFromItem() {
        status = item.status
        condition = item.condition
        purchasePriceText = item.purchasePrice.map { String(format: "%.2f", $0) } ?? ""
        salePriceText = item.salePrice.map { String(format: "%.2f", $0) } ?? ""
        sourceLocation = item.sourceLocation ?? ""
        paymentMethod = item.paymentMethod ?? ""
        counterparty = item.counterparty ?? ""
        notes = item.notes ?? ""
    }

    private func save() {
        InventoryService.shared.update(
            item: item,
            status: status,
            condition: condition,
            purchasePrice: Double(purchasePriceText),
            salePrice: Double(salePriceText),
            notes: notes,
            sourceLocation: sourceLocation,
            paymentMethod: paymentMethod,
            counterparty: counterparty
        )
        Task { await vm.load() }
        dismiss()
    }
}
