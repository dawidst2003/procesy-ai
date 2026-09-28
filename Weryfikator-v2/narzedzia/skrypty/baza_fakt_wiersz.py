#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B2 — czy cytat z karty stoi doslownie w wierszu wewnetrznej bazy wiedzy (CSV/TSV).

Odpowiednik karta_cytaty_zrodlo.py dla profilu `profile/baza-wiedzy-csv.md`: zrodlem nie jest plik PDF,
tylko komorka w zamrozonej kopii bazy faktow klienta.

Uzycie:
    python skrypty/baza_fakt_wiersz.py <karta.md albo tekst.md> <baza.csv> [opcje]

Opcje:
    --kolumna <nazwa>   kolumna z trescia faktu (domyslnie: pierwsza z: fakt, tresc, opis, zdanie, value)
    --sep <znak>        separator CSV (domyslnie: wykrywany z naglowka: ; , \\t |)
    --prog <0-1>        prog podobienstwa dla statusu ROZJAZD (domyslnie 0.88)
    --min-znakow <n>    krotsze cytaty pomijane (domyslnie 25)
    --cicho             tylko podsumowanie

Statusy per cytat:
    ZGODNY        cytat wystepuje doslownie (po normalizacji) w ktoryms wierszu kolumny
    ROZJAZD       najlepsze dopasowanie >= prog, ale nie doslowne  -> parafraza podana jako cytat
    BRAK_W_BAZIE  nic podobnego w bazie                            -> fakt spoza bazy albo zla baza
    ZLY_WIERSZ    cytat jest w bazie, ale w innym wierszu niz podany w karcie („wiersz N")
    POMINIETO     za krotki / same liczby / nazwa wlasna

Exit 1 przy ROZJAZD, BRAK_W_BAZIE albo ZLY_WIERSZ. Skrypt niczego nie zapisuje.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import re
import sys
import unicodedata
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

KOLUMNY_DOMYSLNE = ("fakt", "tresc", "treść", "opis", "zdanie", "value", "text")
CYTAT_RE = re.compile(r"[„\"]([^„\"”]{10,600})[”\"]")
WIERSZ_RE = re.compile(r"wiersz\s*(\d+)", re.I)


def normalizuj(t: str) -> str:
    t = unicodedata.normalize("NFKC", t or "")
    t = t.replace(" ", " ").replace("‑", "-")
    t = re.sub(r"[„”\"'’‘]", " ", t)
    t = re.sub(r"[–—]", "-", t)
    t = re.sub(r"\[\s*\.\.\.\s*\]|\[…\]|…", " ", t)   # oznaczony skrot w cytacie
    t = re.sub(r"\s+", " ", t)
    return t.strip().lower()


def wykryj_sep(naglowek: str) -> str:
    for s in (";", "\t", ",", "|"):
        if naglowek.count(s) >= 1:
            return s
    return ";"


def wczytaj_baze(sciezka: Path, kolumna: str | None, sep: str | None):
    surowe = sciezka.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    if not surowe:
        sys.exit(f"pusta baza: {sciezka}")
    sep = sep or wykryj_sep(surowe[0])
    czytnik = csv.DictReader(surowe, delimiter=sep)
    pola = [p.strip() for p in (czytnik.fieldnames or [])]
    if not pola:
        sys.exit(f"brak naglowka w {sciezka}")
    if kolumna:
        wybrana = next((p for p in pola if p.lower() == kolumna.lower()), None)
        if not wybrana:
            sys.exit(f"brak kolumny '{kolumna}' w {sciezka} (sa: {', '.join(pola)})")
    else:
        wybrana = next((p for p in pola if p.strip().lower() in KOLUMNY_DOMYSLNE), None)
        if not wybrana:
            wybrana = max(pola, key=len)  # ostatecznosc: najdluzsza nazwa kolumny
    wiersze = []
    for i, w in enumerate(czytnik, start=2):   # 1 = naglowek, jak w arkuszu
        tresc = (w.get(wybrana) or "").strip()
        if tresc:
            wiersze.append((i, tresc, normalizuj(tresc)))
    return wybrana, sep, wiersze


def znajdz(cytat_n: str, wiersze):
    """(status_wiersz, nr, tresc, podobienstwo) — doslowne dopasowanie albo najblizsze."""
    for nr, tresc, norm in wiersze:
        if cytat_n in norm:
            return "ZGODNY", nr, tresc, 1.0
    najlepszy, nr_n, tresc_n = 0.0, None, ""
    for nr, tresc, norm in wiersze:
        r = difflib.SequenceMatcher(None, cytat_n, norm).ratio()
        if r > najlepszy:
            najlepszy, nr_n, tresc_n = r, nr, tresc
    return "ROZJAZD", nr_n, tresc_n, najlepszy


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("karta")
    ap.add_argument("baza")
    ap.add_argument("--kolumna")
    ap.add_argument("--sep")
    ap.add_argument("--prog", type=float, default=0.88)
    ap.add_argument("--min-znakow", type=int, default=25)
    ap.add_argument("--cicho", action="store_true")
    a = ap.parse_args()

    karta = Path(a.karta)
    baza = Path(a.baza)
    for p in (karta, baza):
        if not p.is_file():
            sys.exit(f"nie ma pliku: {p}")

    kolumna, sep, wiersze = wczytaj_baze(baza, a.kolumna, a.sep)
    tekst = karta.read_text(encoding="utf-8", errors="replace").splitlines()

    licz = {"ZGODNY": 0, "ROZJAZD": 0, "BRAK_W_BAZIE": 0, "ZLY_WIERSZ": 0, "POMINIETO": 0}
    problemy = []

    for nr_linii, linia in enumerate(tekst, start=1):
        deklarowany = WIERSZ_RE.search(linia)
        deklarowany = int(deklarowany.group(1)) if deklarowany else None
        for cytat in CYTAT_RE.findall(linia):
            cn = normalizuj(cytat)
            if len(cn) < a.min_znakow or not re.search(r"[a-ząćęłńóśźż]{4,}", cn):
                licz["POMINIETO"] += 1
                continue
            status, nr, tresc, ratio = znajdz(cn, wiersze)
            if status == "ZGODNY":
                if deklarowany and deklarowany != nr:
                    licz["ZLY_WIERSZ"] += 1
                    problemy.append((nr_linii, "ZLY_WIERSZ", cytat, nr, tresc, 1.0, deklarowany))
                else:
                    licz["ZGODNY"] += 1
                continue
            if ratio >= a.prog:
                licz["ROZJAZD"] += 1
                problemy.append((nr_linii, "ROZJAZD", cytat, nr, tresc, ratio, deklarowany))
            else:
                licz["BRAK_W_BAZIE"] += 1
                problemy.append((nr_linii, "BRAK_W_BAZIE", cytat, nr, tresc, ratio, deklarowany))

    print(f"== {karta.name}  ×  {baza.name} (kolumna '{kolumna}', separator '{sep}', "
          f"wierszy w bazie: {len(wiersze)})")
    if not a.cicho:
        for nr_linii, status, cytat, nr, tresc, ratio, dekl in problemy:
            print(f"  l.{nr_linii:<4} [{status}] podobienstwo {ratio:.2f}")
            print(f"    karta : „{cytat[:160]}”")
            if status == "BRAK_W_BAZIE":
                print(f"    baza  : najblizszy wiersz {nr}: „{tresc[:160]}”")
            elif status == "ZLY_WIERSZ":
                print(f"    baza  : cytat stoi w wierszu {nr}, karta podaje wiersz {dekl}")
            else:
                print(f"    baza  : wiersz {nr}: „{tresc[:160]}”")
    print("-" * 78)
    print("PODSUMOWANIE: " + " | ".join(f"{k}: {v}" for k, v in licz.items()))
    return 1 if (licz["ROZJAZD"] or licz["BRAK_W_BAZIE"] or licz["ZLY_WIERSZ"]) else 0


if __name__ == "__main__":
    sys.exit(main())
