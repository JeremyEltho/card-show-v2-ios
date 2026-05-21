@preconcurrency import AVFoundation
import Vision
import CoreImage
import UIKit

// Delegate protocol for the scanner
protocol CardScannerDelegate: AnyObject {
    func scannerDidMatch(_ match: CardMatch)
    func scannerDidUpdateOverlay(rect: CGRect?, in viewBounds: CGRect)
}

actor CardScannerService: NSObject {
    weak var delegate: (any CardScannerDelegate)?

    private var captureSession: AVCaptureSession?
    private var previewLayer: AVCaptureVideoPreviewLayer?
    private var lastProcessedTime: Date = .distantPast
    /// One frame per second. Pokémon card scanning doesn't need 30 FPS — the OCR + fuzzy
    /// match is heavy and lower frequency keeps the device cool + responsive.
    private let processingInterval: TimeInterval = 1.0
    private var isProcessing = false

    /// Synchronous gate used by the capture delegate (which runs on a non-actor thread).
    /// Prevents spawning a Task for every camera frame when one's already in flight.
    nonisolated(unsafe) private var frameGate = AtomicFlag()

    // Start camera session
    func startSession() async throws -> AVCaptureVideoPreviewLayer {
        let session = AVCaptureSession()
        session.sessionPreset = .hd1920x1080

        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
              let input = try? AVCaptureDeviceInput(device: device) else {
            throw NSError(domain: "PokeScan", code: 1, userInfo: [NSLocalizedDescriptionKey: "Camera not available"])
        }

        session.addInput(input)

        let output = AVCaptureVideoDataOutput()
        output.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_420YpCbCr8BiPlanarFullRange]
        output.setSampleBufferDelegate(self, queue: DispatchQueue(label: "com.pokescan.camera"))
        session.addOutput(output)

        let layer = AVCaptureVideoPreviewLayer(session: session)
        layer.videoGravity = .resizeAspectFill
        self.captureSession = session
        self.previewLayer = layer

        DispatchQueue.global(qos: .userInitiated).async { session.startRunning() }
        return layer
    }

    func stopSession() {
        captureSession?.stopRunning()
        captureSession = nil
    }

    // Main frame processing
    func processFrame(_ sampleBuffer: CMSampleBuffer) async {
        guard !isProcessing,
              Date().timeIntervalSince(lastProcessedTime) > processingInterval,
              let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }

        isProcessing = true
        lastProcessedTime = Date()
        defer { isProcessing = false }

        let ciImage = CIImage(cvPixelBuffer: pixelBuffer)

        // Stage 1: Try rectangle detection (works well on clean backgrounds).
        // If it fails (cluttered desk, keyboard backdrop, low contrast), DON'T bail —
        // fall through and OCR the area corresponding to the on-screen guide frame.
        let cardRect = await detectCardRectangle(in: ciImage)
        let d = delegate
        await MainActor.run { d?.scannerDidUpdateOverlay(rect: cardRect?.boundingBox, in: .zero) }

        // Stage 2: Build the OCR region.
        //   - With a detection: perspective-correct → crop title band
        //   - Without one: just crop the top 35% of the camera frame (the user is
        //     instructed to fit the card inside the on-screen guide, so the card name
        //     should land in roughly that region)
        let ocrImage: CIImage
        if let rect = cardRect {
            let corrected = ImagePreprocessor.perspectiveCorrect(ciImage, rect: rect)
            ocrImage = ImagePreprocessor.cropTitleBand(corrected)
        } else {
            // Crop the central card-shaped band of the frame where the user is told
            // to place the card. Top portion gets us the card name.
            let ext = ciImage.extent
            let band = CGRect(
                x: ext.midX - ext.width * 0.35,
                y: ext.midY + ext.height * 0.05,
                width: ext.width * 0.70,
                height: ext.height * 0.20
            )
            ocrImage = ciImage.cropped(to: band)
        }
        let enhanced = ImagePreprocessor.enhanceContrast(ocrImage)

        // Stage 3: OCR
        guard let ocrText = await recognizeText(in: enhanced), !ocrText.isEmpty else { return }

        // Stage 4: On-device fuzzy match against bundled canonical dictionary (5,437 names)
        guard let localMatch = FuzzyMatcher.shared.match(ocrText) else { return }

        // Stage 6: Look up full metadata + market price from pokemontcg.io directly.
        // If the API is unreachable we still return the local match (no price, no image).
        if let api = await PokemonTCGService.shared.lookup(name: localMatch.name) {
            var enriched = api
            enriched.confidence = localMatch.confidence    // preserve scanner confidence tier
            await finalize(enriched)
        } else {
            await finalize(localMatch)
        }
    }

    private func finalize(_ match: CardMatch) async {
        let d = delegate
        await MainActor.run { d?.scannerDidMatch(match) }
    }

    private func detectCardRectangle(in image: CIImage) async -> VNRectangleObservation? {
        await withCheckedContinuation { continuation in
            let request = VNDetectRectanglesRequest { req, _ in
                let observations = req.results as? [VNRectangleObservation] ?? []
                // Filter for card-shaped rectangles (portrait, 1:1.4 ratio)
                let card = observations.filter { ob in
                    let h = ob.boundingBox.height, w = ob.boundingBox.width
                    let ratio = h / w
                    return (1.1...1.7).contains(ratio)
                        && ob.confidence > 0.5
                        && w > 0.15 && h > 0.20
                }.max(by: { $0.confidence < $1.confidence })
                continuation.resume(returning: card)
            }
            request.minimumAspectRatio = 0.55
            request.maximumAspectRatio = 0.85
            request.minimumSize = 0.15
            // Critical: default is 1. Without this, Vision only returns the single
            // best rectangle, which might be the laptop / table edge / keyboard,
            // not the card. Allow up to 10 candidates and we'll filter for the card.
            request.maximumObservations = 10
            try? VNImageRequestHandler(ciImage: image, options: [:]).perform([request])
        }
    }

    private func recognizeText(in image: CIImage) async -> String? {
        await withCheckedContinuation { continuation in
            let request = VNRecognizeTextRequest { req, _ in
                guard let observations = req.results as? [VNRecognizedTextObservation] else {
                    continuation.resume(returning: nil); return
                }
                // Sort top-to-bottom (largest Y → smallest) and collect ALL recognised lines.
                // The card name might not be the highest-confidence line; the candidate
                // ranker in FuzzyMatcher picks the best one.
                let lines = observations
                    .sorted { $0.boundingBox.midY > $1.boundingBox.midY }
                    .compactMap { $0.topCandidates(1).first?.string }
                continuation.resume(returning: lines.joined(separator: "\n"))
            }
            request.recognitionLevel = .accurate
            request.usesLanguageCorrection = true
            request.recognitionLanguages = ["en-US"]
            try? VNImageRequestHandler(ciImage: image, options: [:]).perform([request])
        }
    }

}

// MARK: - AVCaptureVideoDataOutputSampleBufferDelegate

extension CardScannerService: AVCaptureVideoDataOutputSampleBufferDelegate {
    nonisolated func captureOutput(_ output: AVCaptureOutput,
                                   didOutput sampleBuffer: CMSampleBuffer,
                                   from connection: AVCaptureConnection) {
        // Synchronous gate — drop the frame immediately if a previous one is still
        // being processed. Without this we'd queue up dozens of Tasks per second
        // and overwhelm the device. The atomic flag is cleared inside processFrame
        // once OCR + fuzzy match complete.
        guard frameGate.tryAcquire() else { return }

        let buffer = sampleBuffer
        Task.detached(priority: .userInitiated) { [weak self] in
            guard let self else { return }
            await self.processFrame(buffer)
            self.frameGate.release()
        }
    }
}

// MARK: - Simple atomic flag (used by the non-actor capture delegate)

final class AtomicFlag: @unchecked Sendable {
    private let lock = NSLock()
    private var inFlight = false

    /// Returns true if the caller acquired the flag, false if it was already set.
    func tryAcquire() -> Bool {
        lock.lock(); defer { lock.unlock() }
        if inFlight { return false }
        inFlight = true
        return true
    }

    func release() {
        lock.lock(); defer { lock.unlock() }
        inFlight = false
    }
}
