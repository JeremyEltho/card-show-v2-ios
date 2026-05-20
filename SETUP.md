# CardShow Pro — Setup

Run the backend locally and the iOS app on your iPhone. From clone to working app: **under 10 minutes**.

## Prerequisites

- **macOS** with Xcode 16+ (free from Mac App Store)
- **Python 3.12+** (`brew install python@3.12`)
- A **free Apple ID** (works for personal device install; 7-day re-sign required)
- An **iPhone** running iOS 17 or later

---

## 1. Clone the repo

```bash
git clone https://github.com/JeremyEltho/card-show-v2.git
cd card-show-v2
```

## 2. Run the backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Optional but recommended — get a free key at https://dev.pokemontcg.io
# Open .env and paste it into POKEMONTCG_API_KEY=

alembic upgrade head      # creates pokescan.db
python seed.py            # adds demo user + 5 sample cards
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Verify the server is up:

```bash
curl http://localhost:8000/health
# → {"status":"ok","db":"connected","version":"2.0.0"}
```

Leave this terminal running. The API docs are auto-generated at http://localhost:8000/docs.

## 3. Point the iOS app at your machine

On your iPhone, the app needs to reach the backend on your Mac. **Find your Mac's local IP**:

```bash
ipconfig getifaddr en0
# Example output: 192.168.1.42
```

Open `ios/CardShowPro/Services/NetworkService.swift` and update line 27:

```swift
static var baseURL = "http://192.168.1.42:8000/api/v1"   // your Mac's IP
```

> **Note:** the simulator can use `http://localhost:8000/api/v1` because it shares your Mac's network. A physical phone cannot.

## 4. Open the project in Xcode

```bash
open ios/CardShowPro.xcodeproj
```

## 5. Configure code signing (one-time)

1. In Xcode, click the **CardShowPro** project in the file tree (top-left).
2. Select the **CardShowPro** target.
3. Click the **Signing & Capabilities** tab.
4. Check **Automatically manage signing**.
5. Under **Team**, click the dropdown and choose **Add an Account…**.
6. Sign in with your **Apple ID**.
7. Back in the Team dropdown, select your name (it will say "Personal Team").

If you see an error like "no provisioning profile", change the **Bundle Identifier** to something unique like `com.yourname.cardshowpro` — Apple won't allow two people to use the same one.

## 6. Run on your iPhone

1. Connect your iPhone via USB (or AirPlay over Wi-Fi).
2. In Xcode's toolbar, click the device selector (where it says "iPhone 17 Pro Simulator") and choose **your iPhone**.
3. On your iPhone: **Settings → General → VPN & Device Management** — tap your developer cert and click **Trust** (only needed first time).
4. Press **⌘R** to build, install, and launch.

The app opens to the login screen. Tap **Create account** and sign up.

> **Heads up:** with a free Apple ID, the app expires after **7 days**. Rebuild from Xcode to refresh it. A paid Apple Developer account ($99/year) removes this limit.

---

## Running tests

```bash
cd backend && source .venv/bin/activate
pytest tests/ -v       # 35 tests, all green
```

```bash
# Scan accuracy test (uses Test-Data/ folder of real card images)
python ../scripts/test_scan.py
```

---

## Architecture cheat sheet

```
iOS App (SwiftUI, iOS 17+)
  │
  ▼ HTTPS / JWT bearer
FastAPI Backend (Python 3.12, port 8000)
  │
  ├─ SQLite (./pokescan.db)
  ├─ pokemontcg.io   (card metadata, lazy-cached)
  └─ JustTCG / TCGPlayer (pricing, lazy-cached)
```

### Scan confidence tiers (vendor workflow)

| Confidence | UX                                  |
|-----------:|-------------------------------------|
|     ≥ 95% | Auto-log + 3s "Undo" banner          |
|   80–94%  | Confirmation sheet — vendor confirms |
|    < 80%  | Manual search field                  |

### Three tabs

| Tab    | What it does                                              |
|--------|-----------------------------------------------------------|
| Scan   | Camera + name capture + buy/sell logging                  |
| Stock  | Cards you currently have to sell (one-tap "SELL" button)  |
| Today  | Buys/Sells/Net for the current show                       |

---

## Troubleshooting

**Camera doesn't work on the simulator.** Use a physical device — iOS Simulator doesn't have a real camera.

**"Could not connect to server".** Make sure backend is running and that `NetworkService.baseURL` points to your Mac's IP, not `localhost`. Phones can't see Mac's `localhost`.

**Test on a card.** Open the app → Scan tab → point at any Pokémon card from your collection or from `Test-Data/` printed on paper. Should auto-log if confidence ≥ 95%.

**Build fails with "no such module" errors.** Re-run `cd ios && xcodegen generate` to regenerate the Xcode project (requires `brew install xcodegen`).

---

## What's next

- Tap **Settings** (gear icon, top-right of Today tab) → enter your active show name.
- Open the Today tab → see your buys/sells/net update live as you scan.
- Swipe left on a row in Stock → quick mark-sold.
