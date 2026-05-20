"""
End-to-end test of the scan pipeline against real Pokémon card images.
For each image:
  1. OCR via Apple Vision (Swift CLI)
  2. POST to /scan/identify
  3. Compare predicted card name against ground truth
  4. Bucket by confidence tier (auto-confirm ≥95% / ask 80-94% / manual <80%)
"""
import os
import sys
import json
import subprocess
import requests

BACKEND = "http://localhost:8000/api/v1"
OCR_SCRIPT = os.path.join(os.path.dirname(__file__), "ocr.swift")
TEST_DIR = "/Users/Projects/JUSTINS_APP/v2/Test-Data"

# Ground truth — what the card actually is
GROUND_TRUTH = {
    "download.jpeg":      "Gyarados EX",
    "download (1).jpeg":  "Charizard",         # Base Set
    "download (2).jpeg":  "Greninja ex",        # SV
    "download (3).jpeg":  "Pinsir",
    "download (4).jpeg":  "Dark Charizard",     # Team Rocket
    "download (5).jpeg":  "Umbreon VMAX",
    "download (6).jpeg":  "Venusaur ex",
    "download (7).jpeg":  "Charizard V",
    "download (8).jpeg":  "Bulbasaur",
    "download (9).jpeg":  "Lugia",              # Neo Genesis
    "download (10).jpeg": "Heracross",
    "download (11).jpeg": "Charmander",
    "download (12).jpeg": "Greninja ex",
    "download (13).jpeg": "Pikachu",            # Japanese Detective Pikachu — hard
    "download (14).jpeg": "Single Strike Urshifu",
    "download (15).jpeg": "Mimikyu VMAX",
    "download (16).jpeg": "Teal Mask Ogerpon ex",
    "download (17).jpeg": "Single Strike Urshifu V",
    "download (18).jpeg": "Seviper",
    "download (19).jpeg": "Falinks V",
}


def login():
    r = requests.post(f"{BACKEND}/auth/login",
        json={"email": "demo@pokescan.com", "password": "pokemon123"})
    r.raise_for_status()
    return r.json()["access_token"]


def ocr(image_path: str) -> str:
    """Run Swift OCR; output format is 'TEXT|confidence|source' per line."""
    result = subprocess.run(
        ["swift", OCR_SCRIPT, image_path],
        capture_output=True, text=True, timeout=30
    )
    # Strip metadata: take just the TEXT portion for the backend
    lines = []
    for raw in result.stdout.splitlines():
        # split on last "|" - text may itself contain "|" in rare OCR cases
        parts = raw.rsplit("|", 2)
        if len(parts) >= 1:
            lines.append(parts[0])
    return "\n".join(lines).strip()


def confidence_tier(c: float) -> str:
    if c >= 0.95: return "auto-confirm"
    if c >= 0.80: return "ask user"
    return "manual"


def name_matches(predicted: str, actual: str) -> bool:
    """Loose match — predicted contains actual or vice versa."""
    p = predicted.lower().replace("'s ", " ").replace("-", " ")
    a = actual.lower().replace("'s ", " ").replace("-", " ")
    # Strip common suffixes for base name compare
    for suffix in [" ex", " v", " vmax", " gx"]:
        p_base = p.replace(suffix, "")
        a_base = a.replace(suffix, "")
        if a_base in p_base or p_base in a_base:
            return True
    return a in p or p in a


def main():
    token = login()
    headers = {"Authorization": f"Bearer {token}"}

    results = []
    for fname, actual in sorted(GROUND_TRUTH.items()):
        path = os.path.join(TEST_DIR, fname)
        if not os.path.exists(path):
            continue
        ocr_text = ocr(path)
        first_line = ocr_text.splitlines()[0] if ocr_text else ""

        try:
            r = requests.post(f"{BACKEND}/scan/identify",
                json={"ocr_text": ocr_text, "ocr_confidence": 0.8},
                headers=headers, timeout=30)
            if r.status_code == 200:
                data = r.json()
                predicted = data["name"]
                conf = data["confidence"]
                pipeline = data["pipeline"]
                price = data.get("market_price")
                hit = name_matches(predicted, actual)
                results.append({
                    "file": fname, "actual": actual, "ocr": first_line,
                    "predicted": predicted, "confidence": conf,
                    "tier": confidence_tier(conf), "pipeline": pipeline,
                    "price": price, "hit": hit,
                })
            else:
                results.append({
                    "file": fname, "actual": actual, "ocr": first_line,
                    "predicted": None, "confidence": 0.0,
                    "tier": "FAILED", "pipeline": "none",
                    "price": None, "hit": False,
                })
        except Exception as e:
            results.append({
                "file": fname, "actual": actual, "ocr": first_line,
                "predicted": f"ERROR: {e}", "confidence": 0.0,
                "tier": "ERROR", "pipeline": "none",
                "price": None, "hit": False,
            })

    # Print table
    print(f"\n{'File':<22} {'Actual':<28} {'OCR':<22} {'Predicted':<28} {'Conf':>6} {'Tier':<13} {'Hit':<4}")
    print("-" * 130)
    for r in results:
        ocr_short = (r["ocr"] or "")[:20]
        pred_short = (r["predicted"] or "—")[:26]
        actual_short = r["actual"][:26]
        hit_str = "✓" if r["hit"] else "✗"
        print(f"{r['file']:<22} {actual_short:<28} {ocr_short:<22} {pred_short:<28} {r['confidence']:>6.2f} {r['tier']:<13} {hit_str:<4}")

    # Summary
    total = len(results)
    hits = sum(1 for r in results if r["hit"])
    auto = sum(1 for r in results if r["tier"] == "auto-confirm")
    ask = sum(1 for r in results if r["tier"] == "ask user")
    manual = sum(1 for r in results if r["tier"] == "manual")
    failed = sum(1 for r in results if r["tier"] in ("FAILED", "ERROR"))

    print(f"\n{'='*60}")
    print(f"SUMMARY: {hits}/{total} correct identifications ({100*hits//total}%)")
    print(f"  Auto-confirm (≥95%): {auto}")
    print(f"  Ask user (80-94%):   {ask}")
    print(f"  Manual assist (<80%): {manual}")
    print(f"  Failed/Error:        {failed}")


if __name__ == "__main__":
    main()
