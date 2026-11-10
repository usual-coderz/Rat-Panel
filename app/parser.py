"""Extract `Country - price` pairs out of a /cap reply."""
from __future__ import annotations

import re

from app.countries import Country, resolve

_LINE = re.compile(
    r"^(?P<name>[^$\d]{2,48}?)\s*(?:[-–—:=]|\s{2,})\s*\$?\s*(?P<price>\d{1,4}(?:[.,]\d{1,3})?)\s*(?:USD|\$)?\s*$",
    re.I,
)
_EMOJI = re.compile(r"[^\w\s.'\-&()]", re.UNICODE)
_NOISE = {"country", "rate", "price", "cap", "capacity", "available", "stock"}


def _price(raw: str) -> float | None:
    value = raw.replace(",", ".")
    try:
        number = float(value)
    except ValueError:
        return None
    return number if number > 0 else None


def parse(text: str) -> list[tuple[Country, float]]:
    out: list[tuple[Country, float]] = []
    seen: set[str] = set()

    for raw_line in (text or "").splitlines():
        line = _EMOJI.sub(" ", raw_line).strip()
        if not line:
            continue
        match = _LINE.match(line)
        if not match:
            continue

        name = re.sub(r"\s{2,}", " ", match.group("name")).strip(" -–—:=.")
        if not name or name.lower() in _NOISE:
            continue
        price = _price(match.group("price"))
        if price is None:
            continue

        country = resolve(name)
        if country is None or country.iso2 in seen:
            continue
        seen.add(country.iso2)
        out.append((country, price))
    return out