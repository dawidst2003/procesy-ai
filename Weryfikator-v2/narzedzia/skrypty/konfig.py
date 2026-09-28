#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Konfiguracja projektu — jedyne miejsce, w którym skrypty wiedzą coś o konkretnym kliencie.

Skrypty kontrolne są uniwersalne. Różnice projektu (jak nazywa się NASZ serwis/sklep, jaki jest
język rynku, gdzie leżą karty i dokumenty) czyta się stąd, nie z kodu.

Kolejność szukania pliku `weryfikacja.json`:
    1. argument `--konfig <plik>` (obsługiwany przez skrypty, które go przyjmują),
    2. zmienna środowiskowa `WERYFIKACJA_KONFIG`,
    3. najbliższy `weryfikacja.json` w górę drzewa od pierwszej ścieżki podanej w argumentach
       (czyli od karty albo folderu dokumentów) — do 8 poziomów,
    4. wartości domyślne (patrz DOMYSLNE) — neutralne, bez nazwy klienta.

Domyślne wartości są tak dobrane, żeby brak pliku konfiguracyjnego NIE wyłączał kontroli:
token własnego serwisu domyślnie to słowa rodzajowe („sklep", „nasza strona"), a nie pusta lista.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

DOMYSLNE = {
    # Tokeny, po których poznajemy NASZ serwis / sklep w tabeli dokumentów karty.
    # To źródło handlowe: nie daje [POTWIERDZONE] i nie jest źródłem faktu producenta.
    "tokeny_wlasne": ["sklep", "nasz sklep", "nasza strona"],
    # Język rynku docelowego (reguła P7 rejestru). "pl" = cytaty po polsku, gdy istnieje wersja PL.
    "jezyk_rynku": "pl",
    # Nazwa klienta — tylko do nagłówków raportów.
    "klient": "",
    # Struktura folderów partii, względem korzenia projektu (używa status_partii.py).
    "sciezki": {
        "zrodla": "04-opisy-produktow/zrodla",
        "produkty": "produkty",
        "dokumenty": "dokumenty",
        "kontrola": "04-opisy-produktow/kontrola",
    },
    # Plik .env z kluczami (szukanie źródeł). Pusty = szukaj obok weryfikacja.json.
    "env": "",
}

_cache: dict | None = None
_sciezka_pliku: Path | None = None


def _znajdz_plik(argv: list[str]) -> Path | None:
    jawny = None
    for i, a in enumerate(argv):
        if a == "--konfig" and i + 1 < len(argv):
            jawny = argv[i + 1]
        elif a.startswith("--konfig="):
            jawny = a.split("=", 1)[1]
    if jawny:
        p = Path(jawny).expanduser()
        return p if p.is_file() else None
    z_env = os.environ.get("WERYFIKACJA_KONFIG")
    if z_env and Path(z_env).is_file():
        return Path(z_env)
    for a in argv[1:]:
        if a.startswith("-"):
            continue
        p = Path(a).expanduser()
        if not p.exists():
            continue
        start = p if p.is_dir() else p.parent
        for kat in [start, *list(start.parents)[:8]]:
            kand = kat / "weryfikacja.json"
            if kand.is_file():
                return kand
    return None


def wczytaj(argv: list[str] | None = None) -> dict:
    """Zwraca słownik konfiguracji (scalony z domyślnymi). Wynik jest cache'owany."""
    global _cache, _sciezka_pliku
    if _cache is not None:
        return _cache
    argv = list(sys.argv if argv is None else argv)
    plik = _znajdz_plik(argv)
    dane = dict(DOMYSLNE)
    if plik:
        try:
            wczytane = json.loads(plik.read_text(encoding="utf-8"))
            for k, v in wczytane.items():
                if k == "sciezki" and isinstance(v, dict):
                    dane["sciezki"] = {**DOMYSLNE["sciezki"], **v}
                else:
                    dane[k] = v
            _sciezka_pliku = plik
        except Exception as e:  # konfiguracja nie może wywalić kontroli
            print(f"[konfig] nie udało się wczytać {plik}: {e} — biorę wartości domyślne",
                  file=sys.stderr)
    if not dane.get("tokeny_wlasne"):
        dane["tokeny_wlasne"] = list(DOMYSLNE["tokeny_wlasne"])
    _cache = dane
    return dane


def sciezka_konfigu() -> Path | None:
    wczytaj()
    return _sciezka_pliku


def korzen() -> Path:
    """Katalog, w którym leży weryfikacja.json (albo cwd, gdy pliku nie ma)."""
    p = sciezka_konfigu()
    return p.parent if p else Path.cwd()


def tokeny_wlasne() -> list[str]:
    return [t.lower() for t in wczytaj()["tokeny_wlasne"]]


def rx_wlasne() -> re.Pattern:
    """Regex dopasowujący tokeny naszego serwisu (własny sklep / strona klienta)."""
    alt = "|".join(re.escape(t) for t in tokeny_wlasne()) or "sklep"
    return re.compile(r"(?<![a-ząćęłńóśźż0-9])(?:%s)(?![a-ząćęłńóśźż0-9])" % alt, re.I)


def jest_wlasny(tekst: str) -> bool:
    return bool(rx_wlasne().search(tekst or ""))


def jezyk_rynku() -> str:
    return (wczytaj().get("jezyk_rynku") or "pl").upper()


def sciezki() -> dict:
    return wczytaj()["sciezki"]


if __name__ == "__main__":
    k = wczytaj()
    print(f"plik: {sciezka_konfigu() or '(brak — wartości domyślne)'}")
    print(json.dumps(k, ensure_ascii=False, indent=2))
