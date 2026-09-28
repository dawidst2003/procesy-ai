#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R14c · Uogólnienie ponad źródło: treść pisze szerzej, niż mówi karta.

Po co: źródło zawęża deklarację („wirusobójczy wobec wirusów otoczkowych”), a treść w zaletach
albo FAQ powtarza samo „wirusobójczy” (projekt odniesienia, 2026-09: zawężenie było w tabeli,
zniknęło w zalecie, kroku użycia i FAQ). Każde zdanie osobno musi nieść zawężenie.

Pary zawężeń — profil (`zawezenia`): {szeroki, zawezenie}. Flaga, gdy:
  1) karta [POTWIERDZONE] zawiera zawężenie i żaden jej wiersz [POTWIERDZONE] nie podaje szerokiej
     deklaracji bez zawężenia (czyli źródło nie daje pełnej wersji), oraz
  2) jednostka treści (zdanie / punkt listy / wiersz tabeli) ma słowo szerokie bez zawężenia.

Użycie:
    python tekst_zawezenia.py opis.md karta.md [...]
    python tekst_zawezenia.py --pary pary.csv [--tylko <regex>]
Kod: Z1 szeroka deklaracja bez zawężenia ze źródła (blokujące).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tekst_wspolne as tw  # noqa: E402


def sprawdz(opis: Path, karta: Path, ust: dict) -> list[dict]:
    potw = [tw.norm(w["tekst"]) for w in tw.wiersze_karty(karta) if w["potwierdzony"]]
    jedn = tw.jednostki_opisu(opis)
    flagi = []
    for para in ust.get("zawezenia", []):
        szer, zaw = tw.rx(para["szeroki"]), tw.rx(para["zawezenie"])
        z_zawezeniem = [t for t in potw if szer.search(t) and zaw.search(t)]
        bez_zawezenia = [t for t in potw if szer.search(t) and not zaw.search(t)]
        if not z_zawezeniem or bez_zawezenia:
            continue
        for j in jedn:
            t = tw.norm(j["tekst"])
            if szer.search(t) and not zaw.search(t):
                flagi.append({"plik": opis, "linia": j["nr"], "kod": "Z1",
                              "opis": f"„{para['szeroki']}” bez zawężenia „{para['zawezenie']}” — "
                                      f"źródło zawęża (karta {karta.name}): {j['tekst'][:90]}"})
    return flagi


def main(argv: list[str]) -> int:
    ust = tw.ustawienia(wymagane=("zawezenia",))
    flagi, n = [], 0
    for opis, karta in tw.pary(argv):
        if not opis.is_file() or not karta.is_file():
            flagi.append({"plik": opis, "linia": "-", "kod": "Z0", "opis": "brak pliku opisu albo karty"})
            continue
        n += 1
        flagi += sprawdz(opis, karta, ust)
    return tw.wypisz_wynik("tekst_zawezenia", flagi, {"Z0", "Z1"}, n)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
