"""
One-time generator. Fetches all unique card names from pokemontcg.io and writes them
to backend/app/data/pokemon_names.json. The dictionary is loaded at startup by
NameValidator and used as the canonical source for fuzzy OCR correction.

Run from repo root:  python scripts/build_name_dictionary.py
"""
import asyncio
import json
import os
import re
import sys

import httpx

OUT = os.path.join(os.path.dirname(__file__), "..", "backend", "app", "data", "pokemon_names.json")

# Token splitters used when extracting base Pokémon names from card titles
SUFFIX_TOKENS = {"ex", "EX", "GX", "V", "VMAX", "VSTAR", "BREAK", "LEGEND"}
PREFIX_TOKENS = {
    "Dark", "Light", "Shining", "Crystal", "Radiant", "Ancient", "Future",
    "Detective", "Team", "Galarian", "Alolan", "Hisuian", "Paldean",
}
SINGLE_STRIKE_TOKENS = {"Single Strike", "Rapid Strike", "Fusion Strike"}


async def fetch_all_names() -> dict:
    """
    Fetch every card from pokemontcg.io and extract:
      - full card names ("Charizard ex", "Single Strike Urshifu V")
      - base Pokémon names ("Charizard", "Urshifu")
      - common trainer names (cards with supertype="Trainer")
    """
    api_key = os.getenv("POKEMONTCG_API_KEY", "")
    headers = {"X-Api-Key": api_key} if api_key else {}

    full_names: set[str] = set()
    base_names: set[str] = set()
    trainer_names: set[str] = set()
    energy_names: set[str] = set()

    page = 1
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            r = await client.get(
                "https://api.pokemontcg.io/v2/cards",
                params={"pageSize": 250, "page": page, "select": "id,name,supertype,subtypes"},
                headers=headers,
            )
            if r.status_code != 200:
                print(f"API error: {r.status_code} {r.text[:200]}", file=sys.stderr)
                break
            cards = r.json().get("data", [])
            if not cards:
                break

            for c in cards:
                name = c["name"].strip()
                supertype = c.get("supertype", "")

                if supertype == "Trainer":
                    trainer_names.add(name)
                elif supertype == "Energy":
                    energy_names.add(name)
                else:  # Pokémon
                    full_names.add(name)

                    # Extract base Pokémon name by stripping known suffixes/prefixes
                    base = _strip_modifiers(name)
                    if base and base != name:
                        base_names.add(base)
                    if base:
                        base_names.add(base)

            print(f"  Page {page}: total {len(full_names)} Pokémon, "
                  f"{len(trainer_names)} trainers, {len(energy_names)} energy")
            if len(cards) < 250:
                break
            page += 1

    return {
        "pokemon_full": sorted(full_names),
        "pokemon_base": sorted(base_names),
        "trainers": sorted(trainer_names),
        "energy": sorted(energy_names),
    }


def _strip_modifiers(name: str) -> str:
    """Extract the base Pokémon name. 'Charizard ex' -> 'Charizard'."""
    s = name
    # Strip Single Strike / Rapid Strike / Fusion Strike prefixes
    for prefix in SINGLE_STRIKE_TOKENS:
        if s.startswith(prefix + " "):
            s = s[len(prefix) + 1:]
            break
    # Strip team/regional prefixes
    for prefix in PREFIX_TOKENS:
        if s.startswith(prefix + " "):
            s = s[len(prefix) + 1:]
            break
    # Strip suffix tokens
    parts = s.split()
    while parts and parts[-1] in SUFFIX_TOKENS:
        parts = parts[:-1]
    # Drop possessive forms like "Ash's Pikachu" -> "Pikachu"
    if parts and parts[0].endswith("'s"):
        parts = parts[1:]
    return ' '.join(parts).strip()


async def main():
    print("Fetching all cards from pokemontcg.io...")
    data = await fetch_all_names()

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nWrote {OUT}")
    print(f"  pokemon_full: {len(data['pokemon_full'])}")
    print(f"  pokemon_base: {len(data['pokemon_base'])}")
    print(f"  trainers:     {len(data['trainers'])}")
    print(f"  energy:       {len(data['energy'])}")


if __name__ == "__main__":
    asyncio.run(main())
