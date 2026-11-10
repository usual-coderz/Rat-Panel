"""Extract country + price rows out of a source reply, whatever the layout."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.countries import Country, resolve

_EMOJI = re.compile(r"[^\w\s.'\-&()+%/]", re.UNICODE)
_BULLET = re.compile(r"^[\s\-–—•·*|=:,>/]+")
_TAIL = re.compile(r"[\s\-–—•·*|=:,>/]+$")
_LABEL = re.compile(
    r"(?P<kind>free|new|spam|perm(?:anent)?)\s*[:=]\s*[$€£₽]?\s*(?P<price>\d{1,5}(?:[.,]\d{1,3})?)",
    re.IGNORECASE,
)
_MONEY = re.compile(
    r"(?<![\w.,])(?:[$€£₽]\s?)?(?P<price>\d{1,6}(?:[.,]\d{1,3}){0,2})"
    r"\s?(?:usd|eur|rub|inr|gbp|руб|[$€£₽])?",
    re.IGNORECASE,
)
_CODE = re.compile(r"^\+\s*\d{1,4}$")
_SPLIT = re.compile(r"[|\s]+")
_NOISE = {
    "country", "countries", "rate", "price", "prices", "cap", "capacity",
    "available", "stock", "region", "code", "in", "out", "total", "updated", "list",
}


@dataclass
class PriceRow:
    country: Country
    free: float | None = None
    new: float | None = None
    spam: float | None = None
    perm: float | None = None
    stock: int | None = None
    cooldown: str | None = None

    @property
    def price(self) -> float:
        """Headline price used for ranking."""
        for value in (self.free, self.new, self.spam, self.perm):
            if value is not None and value > 0:
                return value
        return 0.0

    @property
    def valid(self) -> bool:
        return self.price > 0


def _amount(raw: str, allow_zero: bool = False) -> float | None:
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
    if number < 0 or number >= 100_000:
        return None
    if number == 0 and not allow_zero:
        return None
    return number


def _clean(text: str, limit: int = 48) -> str:
    text = _EMOJI.sub(" ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    text = _BULLET.sub("", text)
    text = _TAIL.sub("", text)
    return text.strip()[:limit]


def _split_code(line: str) -> tuple[str | None, str]:
    text = _clean(line, limit=200)
    parts = text.split()
    if parts and _CODE.match(parts[0]):
        return parts[0], " ".join(parts[1:])
    return None, text


def _labelled(line: str) -> tuple[dict[str, float], int | None, str | None]:
    found: dict[str, float] = {}
    for match in _LABEL.finditer(line):
        kind = match.group("kind").lower()[:4]
        value = _amount(match.group("price"), allow_zero=True)
        if value is not None:
            found.setdefault(kind, value)

    stock: int | None = None
    cooldown: str | None = None
    for token in _SPLIT.split(_LABEL.sub(" ", line)):
        if not token:
            continue
        if token.endswith("s") and token[:-1].isdigit():
            cooldown = token
        elif token.isdigit():
            stock = int(token)
    return found, stock, cooldown


def _header(line: str) -> Country | None:
    code, rest = _split_code(line)
    cut = _LABEL.search(rest)
    if cut:
        rest = rest[: cut.start()]
    rest = _clean(rest)
    country = resolve(rest) if rest else None
    if country is None and code:
        country = resolve(code)
    return country


def parse(text: str) -> list[PriceRow]:
    rows: list[PriceRow] = []
    seen: set[str] = set()
    pending: Country | None = None

    def emit(country: Country, found: dict[str, float], stock, cooldown) -> None:
        if country is None or country.iso2 in seen:
            return
        row = PriceRow(
            country=country,
            free=found.get("free"),
            new=found.get("new"),
            spam=found.get("spam"),
            perm=found.get("perm"),
            stock=stock,
            cooldown=cooldown,
        )
        if not row.valid:
            return
        seen.add(country.iso2)
        rows.append(row)

    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if len(_clean(line)) < 2:
            continue

        if _LABEL.search(line):
            found, stock, cooldown = _labelled(line)
            country = pending or _header(line)
            if found and country:
                emit(country, found, stock, cooldown)
                pending = None
            continue

        code, rest = _split_code(line)
        money = _MONEY.search(rest) if rest else None

        if money and not _LABEL.search(rest):
            head = _clean(rest[: money.start()])
            price = _amount(money.group("price"))
            country = resolve(head) if head and head.lower() not in _NOISE else None
            if country is None and code:
                country = resolve(code)
            if country and price:
                emit(country, {"free": price}, None, None)
                pending = None
                continue

        pending = _header(line)

    return rows