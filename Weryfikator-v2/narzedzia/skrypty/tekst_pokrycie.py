#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R14a · Pominięcia: czy pozycje krytyczne z karty [POTWIERDZONE] są w treści.

Po co: pominięcie nie zgłasza się samo — tekst bez ostrzeżenia czyta się kompletnie, a sędzia-model
wykrywa brak dużo słabiej niż błąd (test szczelności projektu odniesienia, 2026-09: pierwsza pomoc pominięta
w 3 z 16 opisów, które przeszły pełną kontrolę). Metoda, która działa: lista ze źródła → sprawdzenie
obecności pozycja po pozycji. Ten skrypt robi to mechanicznie.

Co jest pozycją krytyczną — profil (`pozycje_krytyczne` w profile/<profil>-tekst.json):
  - grupa z `elementy`: np. pierwsza pomoc — każda droga (skóra/oczy/połknięcie/wdychanie) obecna
    w wierszu karty musi być w treści, w strefie opisanej `strefa_opisu`;
  - grupa z `wzorzec_kodu`: np. kody H — każdy kod z wiersza [POTWIERDZONE] musi stać w treści;
  - grupa z `tryb: zdania`: każde zdanie wiersza sprawdzane po słowach treściowych (informacyjnie).

Użycie:
    python tekst_pokrycie.py opis.md karta.md [opis2.md karta2.md …]
    python tekst_pokrycie.py --pary pary.csv [--tylko <regex ścieżki opisu>]
    python tekst_pokrycie.py --lista karta.md        # lista kontrolna dla autora PRZED pisaniem
Kody: P1 brak elementu grupy (blokujące wg profilu) · P2 brak kodu · P3 zdanie słabo pokryte (info).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tekst_wspolne as tw  # noqa: E402

# Zdania karty, które są adnotacją roboczą, a nie treścią źródła — nie idą na listę kontrolną.
RX_ADNOTACJA = re.compile(r"patrz |rozjazd|rewizj|szukano|nie zawiera odpowiednika|starsz\w+ (wersj|rewizj)|"
                          r"\bD-?[A-Z]*\d|\bD\d+\b|wiersz\w* |karta |dokument\w* |§ ?\d|brak osobnej", re.I)

SLOWA_POMIJANE = set("oraz przez jest może należy które która który przy przed tylko wyłącznie także "
                     "również bardzo kontakt kontaktu natychmiast wszystkie każdy produkt produktu "
                     "preparat preparatu stosować użyciu użycia".split())


def pozycje(karta: Path, ust: dict) -> list[dict]:
    """Pozycje krytyczne karty: [{grupa, etykieta, wiersz, blokujaca, typ, wzorzec/slowa}]."""
    wiersze = [w for w in tw.wiersze_karty(karta) if w["potwierdzony"]]
    wynik = []
    for g in ust.get("pozycje_krytyczne", []):
        rx_atr = tw.rx(g["atrybut"])
        pasujace = [w for w in wiersze if rx_atr.search(w["atrybut"])]
        if not pasujace:
            continue
        blok = bool(g.get("blokujaca", True))
        if g.get("elementy"):
            tekst = tw.norm(" ".join(w["tekst"] for w in pasujace))
            for el in g["elementy"]:
                if tw.rx(el["w_karcie"]).search(tekst):
                    wynik.append({"grupa": g["nazwa"], "etykieta": el["etykieta"], "wiersz": pasujace[0]["nr"],
                                  "blokujaca": blok, "typ": "element", "w_opisie": el["w_opisie"],
                                  "strefa": g.get("strefa_opisu")})
        elif g.get("wzorzec_kodu"):
            kody = []
            for w in pasujace:
                for k in tw.rx(g["wzorzec_kodu"]).findall(w["wartosc"] or w["tekst"]):
                    k = re.sub(r"\s+", "", k.upper())
                    if k not in kody:
                        kody.append(k)
                        wynik.append({"grupa": g["nazwa"], "etykieta": k, "wiersz": w["nr"],
                                      "blokujaca": blok, "typ": "kod"})
        elif g.get("tryb") == "zdania":
            for w in pasujace:
                for zd in re.split(r"(?<=[.;!?])\s+|\s+—\s+|<br\s*/?>", w["wartosc"]):
                    slowa = [s[:6] for s in re.findall(r"[a-ząćęłńóśźż]{5,}", tw.norm(zd))
                             if s not in SLOWA_POMIJANE]
                    if len(slowa) >= 3 and not re.search(r"\[BRAK\]", zd) and not RX_ADNOTACJA.search(zd):
                        wynik.append({"grupa": g["nazwa"], "etykieta": zd.strip()[:110], "wiersz": w["nr"],
                                      "blokujaca": False, "typ": "zdanie", "slowa": slowa,
                                      "prog": float(g.get("prog_pokrycia", 0.5))})
    return wynik


def sprawdz(opis: Path, karta: Path, ust: dict) -> list[dict]:
    jedn = tw.jednostki_opisu(opis)
    caly = tw.tekst_opisu(opis)
    flagi = []
    brak_kodow: dict[tuple[str, bool], list[str]] = {}
    for p in pozycje(karta, ust):
        if p["typ"] == "kod":
            if not re.search(r"(?<![a-z0-9])" + re.escape(p["etykieta"].lower()) + r"(?![0-9])", caly.replace(" ", "")):
                brak_kodow.setdefault((p["grupa"], p["blokujaca"]), []).append(p["etykieta"])
            continue
        if p["typ"] == "element":
            strefa = tw.rx(p["strefa"]) if p.get("strefa") else None
            # jednostka należy do strefy, gdy strefę wskazuje ona sama albo nagłówek jej sekcji
            teksty = [tw.norm(j["tekst"]) for j in jedn
                      if not strefa or strefa.search(tw.norm(j["tekst"])) or strefa.search(tw.norm(j["sekcja"]))]
            if not any(tw.rx(p["w_opisie"]).search(t) for t in teksty):
                flagi.append({"plik": opis, "linia": "-", "kod": "P1" if p["blokujaca"] else "P1i",
                              "opis": f"{p['grupa']}: brak „{p['etykieta']}” (karta w. {p['wiersz']}: {karta.name})"})
        else:
            trafione = sum(1 for s in p["slowa"] if s in caly)
            if trafione / len(p["slowa"]) < p["prog"]:
                flagi.append({"plik": opis, "linia": "-", "kod": "P3i",
                              "opis": f"{p['grupa']}: zdanie słabo pokryte ({trafione}/{len(p['slowa'])}) "
                                      f"— „{p['etykieta']}” (karta w. {p['wiersz']})"})
    for (grupa, blok), kody in brak_kodow.items():
        flagi.append({"plik": opis, "linia": "-", "kod": "P2" if blok else "P2i",
                      "opis": f"{grupa}: brak w treści {', '.join(kody)} ({karta.name})"})
    return flagi


def lista(karta: Path, ust: dict) -> None:
    print(f"LISTA KONTROLNA — pozycje krytyczne [POTWIERDZONE] z {karta.name}")
    print("Każda musi się znaleźć w treści (albo świadome pominięcie z powodem w raporcie dowodowym).\n")
    for p in pozycje(karta, ust):
        znak = "■" if p["blokujaca"] else "□"
        print(f"{znak} [{p['grupa']}] {p['etykieta']}  (karta w. {p['wiersz']})")


def main(argv: list[str]) -> int:
    ust = tw.ustawienia(wymagane=("pozycje_krytyczne",))
    if "--lista" in argv:
        lista(Path(tw.opcja(argv, "--lista")), ust)
        return 0
    flagi, n = [], 0
    for opis, karta in tw.pary(argv):
        if not opis.is_file() or not karta.is_file():
            flagi.append({"plik": opis, "linia": "-", "kod": "P0", "opis": f"brak pliku: {opis if not opis.is_file() else karta}"})
            continue
        n += 1
        flagi += sprawdz(opis, karta, ust)
    return tw.wypisz_wynik("tekst_pokrycie", flagi, {"P0", "P1", "P2"}, n)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
