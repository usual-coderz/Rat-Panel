"""Country name / ISO code / calling code / flag -> Country."""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

import phonenumbers
import pycountry

ALIASES = {
    "uk": "GB", "gb": "GB", "great britain": "GB", "britain": "GB", "england": "GB",
    "usa": "US", "us": "US", "america": "US", "united states": "US", "states": "US",
    "u s": "US", "u k": "GB", "u a e": "AE",
    "uae": "AE", "emirates": "AE", "dubai": "AE", "abu dhabi": "AE",
    "saudi": "SA", "saudi arabia": "SA", "ksa": "SA",
    "south korea": "KR", "korea": "KR", "north korea": "KP",
    "russia": "RU", "holland": "NL", "netherlands": "NL",
    "vietnam": "VN", "viet nam": "VN", "turkey": "TR", "turkiye": "TR",
    "czech republic": "CZ", "czechia": "CZ",
    "ivory coast": "CI", "cote divoire": "CI", "cote d ivoire": "CI",
    "drc": "CD", "dr congo": "CD", "congo": "CG", "burma": "MM", "myanmar": "MM",
    "macedonia": "MK", "swaziland": "SZ", "eswatini": "SZ",
    "cape verde": "CV", "cabo verde": "CV", "east timor": "TL",
    "palestine": "PS", "west bank": "PS", "vatican": "VA",
    "st kitts": "KN", "st lucia": "LC", "st vincent": "VC",
    "trinidad": "TT", "bosnia": "BA", "herzegovina": "BA",
}

_CLEAN = re.compile(r"[^a-z0-9 ]+")
_FLAG = re.compile("[\U0001F1E6-\U0001F1FF]{2}")
_CALLING = re.compile(r"[+\d\s\-().]+")

_PREFERRED = {
    "1": "US", "7": "RU", "44": "GB", "61": "AU", "212": "MA", "262": "RE",
    "290": "SH", "358": "FI", "590": "GP", "599": "CW", "47": "NO", "39": "IT",
    "33": "FR", "49": "DE", "81": "JP", "86": "CN", "91": "IN", "55": "BR",
}


@dataclass(frozen=True)
class Country:
    iso2: str
    name: str
    calling_code: str


def _norm(text: str) -> str:
    return re.sub(r"\s{2,}", " ", _CLEAN.sub(" ", text.lower())).strip()


class _Index:
    def __init__(self) -> None:
        self.by_key: dict[str, str] = {}
        self.by_code: dict[str, list[str]] = {}
        self.names: set[str] = set()

        for region in phonenumbers.SUPPORTED_REGIONS:
            country = pycountry.countries.get(alpha_2=region)
            if country is None:
                continue
            for label in filter(None, [
                country.name,
                getattr(country, "official_name", None),
                getattr(country, "common_name", None),
            ]):
                key = _norm(label)
                if key:
                    self.by_key.setdefault(key, region)
                    self.names.add(key)
            self.by_key.setdefault(region.lower(), region)
            alpha3 = getattr(country, "alpha_3", None)
            if alpha3:
                self.by_key.setdefault(alpha3.lower(), region)
            code = str(phonenumbers.country_code_for_region(region))
            self.by_code.setdefault(code, []).append(region)

        for alias, iso2 in ALIASES.items():
            if pycountry.countries.get(alpha_2=iso2):
                key = _norm(alias)
                self.by_key.setdefault(key, iso2)
                self.names.add(key)

        for code, regions in self.by_code.items():
            preferred = _PREFERRED.get(code)
            if preferred in regions:
                regions.remove(preferred)
                regions.insert(0, preferred)
            else:
                regions.sort()

    def name(self, iso2: str) -> str:
        country = pycountry.countries.get(alpha_2=iso2)
        return country.name if country else iso2.upper()


_index: _Index | None = None


def index() -> _Index:
    global _index
    if _index is None:
        _index = _Index()
    return _index


def _make(idx: _Index, iso2: str | None) -> Country | None:
    if not iso2 or iso2 not in phonenumbers.SUPPORTED_REGIONS:
        return None
    return Country(iso2, idx.name(iso2), str(phonenumbers.country_code_for_region(iso2)))


def _from_flag(text: str) -> str | None:
    match = _FLAG.search(text)
    if not match:
        return None
    iso2 = "".join(chr(ord(ch) - 0x1F1E6 + ord("A")) for ch in match.group())
    return iso2 if pycountry.countries.get(alpha_2=iso2) else None


def _from_digits(idx: _Index, digits: str) -> str | None:
    code = ""
    if len(digits) > 3:
        number = None
        try:
            number = phonenumbers.parse("+" + digits, None)
        except phonenumbers.NumberParseException:
            number = None
        if number is not None:
            region = phonenumbers.region_code_for_number(number)
            if region in phonenumbers.SUPPORTED_REGIONS:
                return region
            code = str(number.country_code)
    else:
        code = digits.lstrip("0")

    if not code:
        return None
    regions = idx.by_code.get(code)
    return regions[0] if regions else None


def resolve(raw: str) -> Country | None:
    """Accepts a country name, ISO2/ISO3 code, calling code, flag or phone number."""
    idx = index()
    text = (raw or "").strip()
    if not text:
        return None

    hit = _from_flag(text)
    if hit:
        return _make(idx, hit)

    digits = re.sub(r"\D", "", text)
    if digits and _CALLING.fullmatch(text):
        hit = _from_digits(idx, digits)
        if hit:
            return _make(idx, hit)

    key = _norm(text)
    if not key:
        return None

    iso2 = idx.by_key.get(key)
    if iso2:
        return _make(idx, iso2)

    if len(key) >= 4:
        starts = [k for k in idx.names if k.startswith(key)]
        if len(starts) == 1:
            return _make(idx, idx.by_key[starts[0]])
        close = difflib.get_close_matches(key, idx.names, n=1, cutoff=0.82)
        if close:
            return _make(idx, idx.by_key[close[0]])

    return None