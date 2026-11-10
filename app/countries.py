"""Country name -> ISO2 / calling code."""
from __future__ import annotations

import re
from dataclasses import dataclass

import phonenumbers
import pycountry

ALIASES = {
    "uk": "GB", "britain": "GB", "usa": "US", "america": "US", "uae": "AE",
    "dubai": "AE", "south korea": "KR", "russia": "RU", "holland": "NL",
    "vietnam": "VN", "turkiye": "TR", "czech republic": "CZ",
}
_CLEAN = re.compile(r"[^a-z0-9 ]+")


@dataclass(frozen=True)
class Country:
    iso2: str
    name: str
    calling_code: str


def _norm(text: str) -> str:
    return _CLEAN.sub(" ", text.lower()).strip()


class _Index:
    def __init__(self) -> None:
        self.by_name: dict[str, str] = {}
        for region in phonenumbers.SUPPORTED_REGIONS:
            country = pycountry.countries.get(alpha_2=region)
            if not country:
                continue
            for label in filter(None, [country.name, getattr(country, "official_name", None)]):
                self.by_name[_norm(label)] = region
            self.by_name[region.lower()] = region
            self.by_name[country.alpha_3.lower()] = region
        for alias, iso2 in ALIASES.items():
            if pycountry.countries.get(alpha_2=iso2):
                self.by_name[_norm(alias)] = iso2

    def name(self, iso2: str) -> str:
        country = pycountry.countries.get(alpha_2=iso2)
        return country.name if country else iso2.upper()


_index: _Index | None = None


def index() -> _Index:
    global _index
    if _index is None:
        _index = _Index()
    return _index


def resolve(raw: str) -> Country | None:
    """Accepts a country name, ISO2/ISO3 code, calling code or phone number."""
    idx = index()
    text = (raw or "").strip()
    if not text:
        return None

    digits = re.sub(r"\D", "", text)
    if digits and re.fullmatch(r"[+\d\s\-()]+", text):
        try:
            code = str(phonenumbers.parse("+" + digits, None).country_code)
        except phonenumbers.NumberParseException:
            code = digits.lstrip("0") if len(digits) <= 3 else ""
        regions = [r for r in phonenumbers.SUPPORTED_REGIONS
                   if str(phonenumbers.country_code_for_region(r)) == code]
        if regions:
            try:
                region = phonenumbers.region_code_for_number(phonenumbers.parse("+" + digits, None))
            except phonenumbers.NumberParseException:
                region = regions[0]
            region = region if region in regions else regions[0]
            return Country(region, idx.name(region), code)

    iso2 = idx.by_name.get(_norm(text))
    if iso2:
        return Country(iso2, idx.name(iso2), str(phonenumbers.country_code_for_region(iso2)))
    return None