#!/usr/bin/env python3
"""K4a bez modelu: ten sam atrybut nie może mieć innego znacznika w §4 (fakty) i §6 (K4 — podwójny odczyt).

Dla każdego wiersza §4 i §6 bierze atrybut (kolumna 1) i znacznik z wiersza ([POTWIERDZONE] / [DO POTWIERDZENIA] / [BRAK];
w §6 także „TAK” / „NIE” w kolumnie wyniku). Atrybuty dopasowuje po słowach kluczowych (≥ 4 litery, nazwy substancji, CAS).
Flaga = §4 [POTWIERDZONE] przy §6 [DO POTWIERDZENIA]/NIE albo odwrotnie. Wynik = flagi do sprawdzenia, nie werdykt.
Powód: test szczelności fal 2 i 3 (2026-09-14/15) — ta klasa przeszła kontrolę Sonnet i Opus.

Użycie: python _skrypty/karta_znaczniki_spojnosc.py <karta.md> [<karta.md> ...]
"""
import os, re, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

STOP = set("wartość wartości dokument źródło cytat odczyt znacznik wynik sekcja wiersz karta tabela oraz albo przez "
           "według zgodne zgodny niezależne niezależny drugie pierwsze produktu produkt".split())


def klucze(tekst):
    t = tekst.lower()
    cas = set(re.findall(r"\b\d{2,7}-\d{2,3}-\d\b", t))
    slowa = {w for w in re.findall(r"[a-ząćęłńóśźżäöü0-9][a-ząćęłńóśźżäöü0-9\-]{3,}", t) if w not in STOP}
    return slowa | cas


def znacznik(wiersz, sekcja6):
    w = wiersz.upper()
    if "[DO POTWIERDZENIA]" in w:
        return "DP"
    if "[POTWIERDZONE]" in w:
        return "P"
    if sekcja6:
        kom = [k.strip().upper() for k in wiersz.strip().strip("|").split("|")]
        if kom and re.match(r"^(NIE|NIE ROZSTRZYG|ROZJAZD)", kom[-1]):
            return "DP"
        if kom and re.match(r"^TAK\b", kom[-1]):
            return "P"
    return None


def wiersze(linie, numer):
    wynik, w_sekcji = [], False
    for nr, l in enumerate(linie, 1):
        if l.startswith("## "):
            w_sekcji = bool(re.match(r"##\s*" + numer + r"\b", l))
            continue
        if not w_sekcji or not l.lstrip().startswith("|") or re.match(r"^\s*\|[\s:|-]+\|?\s*$", l):
            continue
        kom = [k.strip() for k in l.strip().strip("|").split("|")]
        z = znacznik(l, numer == "6")
        if len(kom) >= 2 and z:
            wynik.append((nr, kom[0], klucze(kom[0]), z))
    return wynik


def sprawdz(karta):
    linie = open(karta, encoding="utf-8").read().splitlines()
    # v2 (standard PL, 2026-09-15): §6 „Podwójny odczyt” usunięty — porównujemy §4 z pozostałymi sekcjami faktów (§2, §5–§8)
    s4, s6 = wiersze(linie, "4"), wiersze(linie, "(?:2|5|6|7|8)")
    flagi = []
    for n4, a4, k4, z4 in s4:
        for n6, a6, k6, z6 in s6:
            if not k4 or not k6:
                continue
            wspolne = k4 & k6
            if not wspolne or len(wspolne) / min(len(k4), len(k6)) < 0.5:
                continue
            if z4 != z6:
                flagi.append(f"§4 w.{n4} „{a4[:40]}” = {z4} vs §6 w.{n6} „{a6[:40]}” = {z6}")
    return sorted(set(flagi))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    zle = 0
    for k in sys.argv[1:]:
        fl = sprawdz(k)
        zle += bool(fl)
        print(f"{os.path.basename(k)}: {'OK' if not fl else str(len(fl)) + ' FLAG K4a'}")
        for x in fl:
            print("   ", x)
    sys.exit(1 if zle else 0)
