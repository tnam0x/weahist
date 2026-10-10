"""Resolve scripts/cities_source.json into web/cities.json via Open-Meteo geocoding.

Run after editing the source list:

    uv run python scripts/update_cities.py

Each entry is geocoded with its `query` restricted to its country (VN by default);
the most populous match wins. The output is committed so builds and the app never
depend on the geocoding API at build time.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "cities_source.json"
OUTPUT = ROOT / "web" / "cities.json"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"


def resolve(client: httpx.Client, query: str, country: str) -> dict[str, Any]:
    resp = client.get(
        GEOCODING_URL,
        params={"name": query, "count": 10, "language": "en", "countryCode": country},
    )
    resp.raise_for_status()
    results = resp.json().get("results") or []
    if not results:
        raise LookupError(f"no geocoding match for {query!r} in {country}")
    # Prefer populated places (PPL*) over islands, regions, airports...
    places = [r for r in results if str(r.get("feature_code", "")).startswith("PPL")]
    return max(places or results, key=lambda r: r.get("population") or 0)


def main() -> int:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    countries_vi: dict[str, str] = source["countries_vi"]
    out: list[dict[str, Any]] = []
    with httpx.Client(timeout=30) as client:
        for group in ("vietnam", "world"):
            for entry in source[group]:
                country = entry.get("country", "VN")
                hit = resolve(client, entry["query"], country)
                out.append(
                    {
                        "slug": entry["slug"],
                        "group": group,
                        "vi": entry["vi"],
                        "en": entry["en"],
                        "province": entry.get("province"),
                        "country_code": country,
                        "country_vi": countries_vi[country],
                        "country_en": hit.get("country") or country,
                        "latitude": round(hit["latitude"], 4),
                        "longitude": round(hit["longitude"], 4),
                        "timezone": hit.get("timezone") or "UTC",
                    }
                )
                print(
                    f"{entry['slug']:<18} {hit['name']:<22} {hit['latitude']:.3f},"
                    f"{hit['longitude']:.3f} pop={hit.get('population')}"
                )
    slugs = [c["slug"] for c in out]
    if len(slugs) != len(set(slugs)):
        raise SystemExit("duplicate slugs in cities_source.json")
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(out)} places to {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
