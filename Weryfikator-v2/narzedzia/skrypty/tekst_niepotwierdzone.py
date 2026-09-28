#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R14b · Wartość bez [POTWIERDZONE] w treści.

Po co: treść ma powstawać wyłącznie z wierszy [POTWIERDZONE]. Wartość z wiersza [DO POTWIERDZENIA]
albo [BRAK] potrafi przejść do tekstu po cichu — np. adres wytwórcy wzięty tylko z listingu sklepu
(projekt odniesienia, 2026-09: adres wytwórcy w 68 opublikowanych opisach, karta: [DO POTWIERDZENIA]).

Jak: z wartości wierszy BEZ [POTWIERDZONE] wyciąga fragmenty charakterystyczne (adres, kod pocztowy,
liczba z jednostką, fraza w cudzysłowie — wzorce z profilu, `niepotwierdzone.wzorce`). Flaga, gdy
fragment stoi w treści, a nie stoi w żadnym wierszu [POTWIERDZONE] tej samej karty.

Użycie:
    python tekst_niepotwierdzone.py opis.md karta.md [...]
    python tekst_niepotwierdzone.py --pary pary.csv [--tylko <regex>]
Kod: N1 fragment z wiersza niepotwierdzonego w treści (blokujące).
Wynik to lista do sprawdzenia: bywa, że ten sam fakt ma w karcie osobny wiersz [POTWIERDZONE]
zapisany inaczej — wtedy flaga jest fałszywa i wystarczy ją odhaczyć.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tekst_wspolne as tw  # noqa: E402


def fragmenty(wartosc: str, wzorce: list[re.Pattern], pomijaj: re.Pattern | None) -> set[str]:
    w = tw.norm(re.sub(r"\[(POTWIERDZONE|DO POTWIERDZENIA|BRAK)\]", " ", wartosc))
    w = re.sub(r"szukano w:.*", "", w)
    wynik = set()
    for rx in wzorce:
        for m in rx.finditer(w):
            f = (m.group(1) if m.groups() else m.group(0)).strip(" .,;:")
            if len(f) >= 4 and not (pomijaj and pomijaj.search(f)):
                wynik.add(f)
    return wynik


def sprawdz(opis: Path, karta: Path, ust: dict) -> list[dict]:
    cfg = ust.get("niepotwierdzone", {})
    wzorce = [re.compile(x, re.I) for x in cfg.get("wzorce", [])]
    pomijaj = re.compile(cfg["pomijaj_fragmenty"], re.I) if cfg.get("pomijaj_fragmenty") else None
    # Wiersze, które projekt świadomie bierze z niepotwierdzonego źródła (rejestr rozstrzygnięć),
    # np. ilość w opakowaniu wg sklepu — nie dają flagi.
    pom_atr = re.compile(cfg["pomijaj_atrybuty"], re.I) if cfg.get("pomijaj_atrybuty") else None
    wiersze = tw.wiersze_karty(karta)
    potw = tw.norm(" ".join(w["tekst"] for w in wiersze if w["potwierdzony"]))
    jedn = tw.jednostki_opisu(opis)
    tytul = tw.norm(jedn[0]["tekst"]) if jedn else ""  # nazwa produktu z H1 nie jest „faktem z wiersza”
    trafienia: dict[tuple[int, int], list[str]] = {}
    wiersz_po_nr = {w["nr"]: w for w in wiersze}
    zgloszone = set()
    for w in wiersze:
        if w["potwierdzony"] or (pom_atr and pom_atr.search(w["atrybut"])):
            continue
        for f in sorted(fragmenty(w["wartosc"], wzorce, pomijaj), key=len, reverse=True):
            if f in potw or f in tytul or any(f in z for z in zgloszone):
                continue
            for j in jedn:
                if f in tw.norm(j["tekst"]):
                    zgloszone.add(f)
                    trafienia.setdefault((w["nr"], j["nr"]), []).append(f)
                    break
    flagi = []
    for (nr_w, nr_j), frag in sorted(trafienia.items()):
        w = wiersz_po_nr[nr_w]
        znacznik = "/".join(sorted(w["znaczniki"]))
        flagi.append({"plik": opis, "linia": nr_j, "kod": "N1",
                      "opis": f"{', '.join('„' + f + '”' for f in frag)} — w karcie tylko jako [{znacznik}] "
                              f"(w. {nr_w} „{w['atrybut'][:40]}”, {karta.name})"})
    return flagi


def main(argv: list[str]) -> int:
    ust = tw.ustawienia(wymagane=("niepotwierdzone",))
    flagi, n = [], 0
    for opis, karta in tw.pary(argv):
        if not opis.is_file() or not karta.is_file():
            flagi.append({"plik": opis, "linia": "-", "kod": "N0", "opis": "brak pliku opisu albo karty"})
            continue
        n += 1
        flagi += sprawdz(opis, karta, ust)
    return tw.wypisz_wynik("tekst_niepotwierdzone", flagi, {"N0", "N1"}, n)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
