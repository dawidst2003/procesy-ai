#!/usr/bin/env python3
"""F12 — czy każda liczba z kolumny wartości występuje w cytacie tego samego wiersza tabeli karty.

Wiersz tabeli markdown: kolumna 1 = atrybut, kolumna 2 = wartość, pozostałe = znacznik / dokument / cytat.
Liczby porównywane po normalizacji (przecinek = kropka, bez spacji tysięcy).
Pomijane, żeby nie zasypać kontroli szumem:
  - sekcje 9 (ślad kroków) i 10 (poprawki) — to rejestr pracy, nie fakty,
  - tabela C7 (od v2 2026-09-14) — kolumna 2 to dosłowne zdanie źródła, nie wartość,
  - numery CAS / WE (np. 67-63-0, 200-661-7) — porównywane jako całe ciągi,
  - roczniki (19xx/20xx) i daty (dd.mm, dd.mm.rrrr), numery sekcji (§7.1), dokumentów (#3, D2),
  - liczby całkowite 0–20 bez jednostki (numery list, kategorie).
Wynik = FLAGI do sprawdzenia przez kontrolę, nie werdykt.

Użycie: python _skrypty/karta_wartosc_cytat.py <karta.md> [<karta.md> ...]
"""
import re, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

JEDNOSTKA = r"\s?(?:%|‰|g|mg|kg|ml|l|L|min|s|sek|h|°C|ºC|ppm|mm|cm|µm|m|szt|MPa|mPa)\b"
CAS = re.compile(r"\b\d{2,7}-\d{2,3}-\d\b")
DATA = re.compile(r"\b\d{1,2}\.\d{1,2}\.(?:\d{2}|\d{4})\b|\b\d{1,2}\.\d{2}(?=\s|$|[;,)])|\b(?:19|20)\d{2}\b")
SMIECI = re.compile(r"§\s*\d+(?:\.\d+)*|#\d+|\bD\d+\b|\b[A-Z]{1,3}\d+\b")
LICZBA = re.compile(r"(?<![\w.,-])\d+(?:[.,]\d+)?(?![\w-])")


def norm(s):
    s = s.replace(" ", " ").replace(" ", " ")
    return re.sub(r"(?<=\d) (?=\d{3}\b)", "", s)


def liczby(s):
    s = norm(s)
    cas = set(CAS.findall(s))
    s = CAS.sub(" ", s)
    s = DATA.sub(" ", s)
    s = SMIECI.sub(" ", s)
    wynik = set()
    for m in LICZBA.finditer(s):
        x = m.group(0).replace(",", ".")
        ma_jednostke = re.match(JEDNOSTKA, s[m.end():m.end() + 6]) is not None
        if "." not in x and int(x) <= 20 and not ma_jednostke:
            continue
        wynik.add(x)
    return wynik, cas


def sprawdz(p):
    flagi, pomijaj, poziom = [], False, 0
    for nr, linia in enumerate(open(p, encoding="utf-8"), 1):
        if linia.startswith("#"):
            lvl = len(linia) - len(linia.lstrip("#"))
            if pomijaj and lvl <= poziom:
                pomijaj = False
            if not pomijaj and (re.match(r"##\s*(9|10)\b", linia) or re.search(r"\bC7\b", linia)):
                pomijaj, poziom = True, lvl
            continue
        if pomijaj or not linia.startswith("|") or re.match(r"^\|[\s:|-]+\|?\s*$", linia):
            continue
        kom = [k.strip() for k in linia.strip().strip("|").split("|")]
        if len(kom) < 3 or not re.search(r"[„\"“]", " ".join(kom[2:])):
            continue
        l_w, cas_w = liczby(kom[1])
        l_c, cas_c = liczby(" ".join(kom[2:]))
        reszta = norm(" ".join(kom[2:])).replace(",", ".")
        brak = sorted(x for x in l_w if x not in l_c and x not in reszta)
        brak += sorted(c for c in cas_w if c not in cas_c)
        if brak:
            flagi.append(f"w.{nr} [{kom[0][:40]}] bez pokrycia w cytacie: {', '.join(brak)}")
    return flagi


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    for p in sys.argv[1:]:
        f = sprawdz(p)
        print(f"{p}: {'OK' if not f else str(len(f)) + ' FLAG'}")
        for x in f:
            print("   ", x)
