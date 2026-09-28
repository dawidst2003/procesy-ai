#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R14d · Tabela składu w treści sumuje się ponad 100%.

Po co: składniki z różnych sekcji dokumentu mają różną bazę (np. substancje czynne na 100 g
vs woda z innej sekcji karty charakterystyki). Złożone w jednej tabeli dają sumę > 100%
(projekt odniesienia, 2026-09: 43 + 8 + 52,4 = 103,4%). Liczy tylko dokładne wartości „N %”;
zakresy („≥1–<5%”) pomija i podaje ich liczbę.

Użycie:
    python tekst_sklad.py opis.md [opis2.md …]        # karta niepotrzebna
    python tekst_sklad.py --pary pary.csv [--tylko <regex>]
Kod: S1 suma > 100% + tolerancja (blokujące).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tekst_wspolne as tw  # noqa: E402

RX_DOKLADNA = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s?%\s*$")
RX_ZAKRES = re.compile(r"\d\s?%?\s*[-–]\s*[<≤]?\s*\d|[<>≤≥]\s*\d")


def tabele(opis: Path) -> list[tuple[int, str, list[list[str]]]]:
    """(linia startu, nagłówek sekcji + nagłówek tabeli, wiersze danych)."""
    wynik, biezaca, sekcja, start, glowka = [], None, "", 0, ""
    for nr, linia in enumerate(opis.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        s = linia.strip()
        if s.startswith("#"):
            sekcja = s.lstrip("#").strip()
        if s.startswith("|"):
            kom = [c.strip() for c in s.strip("|").split("|")]
            if biezaca is None:
                biezaca, start, glowka = [], nr, " ".join(kom)
                continue
            if all(re.fullmatch(r":?-{2,}:?", c or "--") for c in kom):
                continue
            biezaca.append(kom)
        elif biezaca is not None:
            wynik.append((start, sekcja + " | " + glowka, biezaca))
            biezaca = None
    if biezaca is not None:
        wynik.append((start, sekcja + " | " + glowka, biezaca))
    return wynik


def sprawdz(opis: Path, ust: dict) -> list[dict]:
    cfg = ust.get("sklad", {})
    rx_nagl = tw.rx(cfg.get("naglowek", "skład|składnik"))
    tol = float(cfg.get("tolerancja", 0.5))
    flagi = []
    for start, glowka, wiersze in tabele(opis):
        if not rx_nagl.search(glowka):
            continue
        wartosci, zakresy = [], 0
        for kom in wiersze:
            for c in kom[1:]:
                c2 = tw.norm(c)
                m = RX_DOKLADNA.match(c2)
                if m:
                    wartosci.append(float(m.group(1)))
                    break
                if "%" in c2 and RX_ZAKRES.search(c2):
                    zakresy += 1
                    break
        if len(wartosci) >= 2 and sum(wartosci) > 100 + tol:
            flagi.append({"plik": opis, "linia": start, "kod": "S1",
                          "opis": f"tabela „{glowka[:50]}”: suma {sum(wartosci):.1f}% "
                                  f"({' + '.join(f'{v:g}' for v in wartosci)}; zakresów pominiętych: {zakresy})"})
    return flagi


def main(argv: list[str]) -> int:
    ust = tw.ustawienia()
    if "--pary" in argv:
        opisy = [o for o, _ in tw.pary(argv)]
    else:
        opisy = [Path(a) for a in tw.argumenty_pozycyjne(argv, tw.OPCJE_Z_WARTOSCIA)]
    flagi = []
    for o in opisy:
        if o.is_file():
            flagi += sprawdz(o, ust)
    return tw.wypisz_wynik("tekst_sklad", flagi, {"S1"}, len(opisy))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
