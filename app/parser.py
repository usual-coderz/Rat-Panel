"""Extract country/price pairs out of a source reply, whatever the layout."""
from __future__ import annotations

import re

from app.countries import Country, resolve

_EMOJI = re.compile(r"[^\w\s.'\-&()+%/]", re.UNICODE)
_BULLET = re.compile(r"^[\s\-–—•·*|=:,>/]+")
_TAIL = re.compile(r"[\s\-–—•·*|=:,>/]+$")
_MONEY = re.compile(
    r"(?<![\w.,])(?:[$€£₽]\s?)?(?P<price>\d{1,6}(?:[.,]\d{1,3}){0,2})"
    r"\s?(?:usd|eur|rub|inr|gbp|руб|[$€£₽])?",
    re.IGNORECASE,
)
_NOISE = {
    "country", "rate", "price", "prices", "cap", "capacity", "available", "stock",
    "region", "code", "in", "out", "total", "updated", "list",
}


def _price(raw: str) -> float | None:
    value = raw.strip().replace(" ", "").replace("$", "")
    if not value:
        return None
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        head, _, tail = value.partition(",")
        value = head + tail if len(tail) == 3 and head else head + "." + tail
    try:
        number = float(value)
    except ValueError:
        return None
    return number if 0 < number < 100_000 else None


def _clean(text: str) -> str:
    text = _EMOJI.sub(" ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    text = _BULLET.sub("", text)
    text = _TAIL.sub("", text)
    return text.strip()[:48]


def _candidates(line: str):
    for match in _MONEY.finditer(line):
        price = _price(match.group("price"))
        if price is None:
            continue
        head = _clean(line[: match.start()])
        tail = _clean(line[match.end():])
        if head:
            yield head, price
        if tail:
            yield tail, price


def parse(text: str) -> list[tuple[Country, float]]:
    out: list[tuple[Country, float]] = []
    seen: set[str] = set()

    for raw_line in (text or "").splitlines():
        line = re.sub(r"\s{2,}", "  ", raw_line).strip()
        if len(_clean(line)) < 2:
            continue

        for name, price in _candidates(line):
            if not name or name.lower() in _NOISE:
                continue
            country = resolve(name)
            if country is None or country.iso2 in seen:
                continue
            seen.add(country.iso2)
            out.append((country, price))
            break

    return out