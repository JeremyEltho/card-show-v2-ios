# CardShow Pro v2

Production-grade Pokémon card scanning and inventory platform.

## Quick Start (Local Dev)

### Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in API keys
alembic upgrade head           # creates cardshowpro.db
python seed.py                 # demo user + 5 sample cards
uvicorn main:app --reload --port 8000
```
Verify: http://localhost:8000/health  
API docs: http://localhost:8000/docs

### iOS App
```
open ios/CardShowPro.xcodeproj
# Select iPhone 17 Pro simulator
# Cmd+R to build and run
```

## Demo Credentials
- Email: `demo@cardshowpro.com`
- Password: `pokemon123`

## API Keys Required
| Key | Where to get |
|-----|-------------|
| `POKEMONTCG_API_KEY` | https://dev.pokemontcg.io |
| `JUSTTCG_API_KEY` | https://justtcg.com |

Both have free tiers. `POKEMONTCG_API_KEY` is optional but raises rate limits from 1k to 20k req/day. `JUSTTCG_API_KEY` is optional — the app falls back to pricing embedded in the pokemontcg.io card data.

## Architecture

```
iOS App (SwiftUI, iOS 17+)
  ↓ HTTPS JWT
FastAPI Backend (Python 3.12)
  ↓
SQLite (local dev) → PostgreSQL (production)

Card data:  pokemontcg.io API → card_cache table
Pricing:    JustTCG API (fallback: embedded TCGPlayer data)
Auth:       Custom JWT (bcrypt + python-jose)
```

## Scan Confidence UX

| Confidence | UX |
|-----------|-----|
| ≥ 95% | Auto-logged immediately, 3-second Undo banner |
| 80–94% | Ask user: confirm card image + price |
| < 80% | Manual assist: editable OCR text + card search |

## Project Structure

```
v2/
├── backend/          FastAPI + SQLite
│   ├── app/
│   │   ├── api/routes/    auth, cards, inventory, scan, analytics, sync
│   │   ├── core/          config, security, database
│   │   ├── models/        SQLAlchemy ORM
│   │   ├── schemas/       Pydantic I/O
│   │   └── services/      business logic
│   ├── alembic/           DB migrations
│   ├── tests/             pytest suite (12 tests)
│   └── seed.py            demo data
├── ios/
│   ├── CardShowPro.xcodeproj
│   └── CardShowPro/
│       ├── App/           entry point + AppState
│       ├── Views/         Scanner, Inventory, Analytics, Auth, Settings
│       ├── ViewModels/    @Observable MVVM
│       ├── Services/      Network, CardScanner, Auth, Inventory, Sync
│       ├── Models/        Codable API models
│       ├── Persistence/   SwiftData offline queue
│       └── Utilities/     FuzzyMatcher, Keychain, ImagePreprocessor
└── docs/
```

## Running Tests
```bash
cd backend && .venv/bin/pytest tests/ -v
```

## Deploy Backend to Railway
```bash
brew install railway && railway login
cd backend && railway init
railway env set SECRET_KEY=<random> DATABASE_URL=<railway-postgres-url>
railway env set POKEMONTCG_API_KEY=<key>
railway up
```

## iOS to TestFlight
1. Xcode → Product → Archive
2. Distribute App → App Store Connect
3. Add TestFlight testers in App Store Connect
