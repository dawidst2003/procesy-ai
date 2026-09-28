#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R15 · Zamek publikacji — ostatnia bramka przed wgraniem / wysłaniem paczki. Bez modelu.

Po co: w projekcie odniesienia sędzia całości (najdroższy model) przez 4 przebiegi znajdował głównie rzeczy
mechaniczne — paczka starsza niż pliki, pliki zmienione po werdykcie, sierotki, status niezgodny
ze stanem, ślady kuchni w paczce. To sprawdza skrypt: za darmo i za każdym razem.

Użycie:
    python zamek_publikacji.py --paczka paczka.csv [--kod-kol product_code] [--sep ";"]
        [--regeneruj "polecenie z {wyjscie}"]     # Z1: paczka = świeża regeneracja z artefaktów
        [--artefakty "<glob>" …]                   # Z2: żaden artefakt nowszy niż paczka
        [--lista kody.txt|lista.csv]               # Z3: sierotki (w liście, nie w paczce) i nadmiarowe
        [--raporty "<glob>" …]                     # Z5: artefakt zmieniony po ostatnim raporcie kontroli
Z3 zawsze: kody unikalne, zero pustych treści. Z4 zawsze: zakazane wzorce w treści (znaczniki pewności,
ślady procesu + `zamek.zakazane` z profilu/projektu) i zbalansowane tagi HTML.
Polecenie --regeneruj uruchamia się w korzeniu projektu (folder z weryfikacja.json).
Wynik: ZAMEK OTWARTY (wolno wgrać) albo ZAMEK ZAMKNIĘTY + lista powodów. Kod wyjścia 1 = zamknięty.
"""
from __future__ import annotations

import csv
import glob
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import konfig  # noqa: E402
import tekst_wspolne as tw  # noqa: E402

csv.field_size_limit(10**9)

ZAKAZANE_DOMYSLNE = [
    r"\[(POTWIERDZONE|DO POTWIERDZENIA|BRAK|DO UZUPE\w*)",
    r"szukano w", r"\bTODO\b", r"karta fakt", r"kanar", r"podłożon", r"nie dotyczy \|",
]
TAGI = ("table", "ul", "ol", "details", "summary", "p", "h2", "h3", "strong")


def wczytaj(p: Path, kod: str, sep: str) -> tuple[list[str], dict[str, dict], list[dict]]:
    with p.open(encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f, delimiter=sep)
        wiersze = list(r)
        return list(r.fieldnames or []), {w[kod]: w for w in wiersze}, wiersze


def opcje_wiele(argv: list[str], nazwa: str) -> list[str]:
    return [argv[i + 1] for i, a in enumerate(argv) if a == nazwa and i + 1 < len(argv)]


def main(argv: list[str]) -> int:
    paczka = Path(tw.opcja(argv, "--paczka"))
    kod = tw.opcja(argv, "--kod-kol", "product_code")
    sep = tw.opcja(argv, "--sep", ";")
    baza = konfig.korzen()
    powody, uwagi = [], []

    kolumny, po_kodzie, wiersze = wczytaj(paczka, kod, sep)
    tresci = [c for c in kolumny if c != kod]

    # Z3 — kody i puste treści
    kody = [w[kod] for w in wiersze]
    duble = sorted({k for k in kody if kody.count(k) > 1})
    if duble:
        powody.append(f"Z3 zdublowane kody ({len(duble)}): {', '.join(duble[:10])}")
    puste = [w[kod] for w in wiersze if not any((w.get(c) or "").strip() for c in tresci)]
    if puste:
        powody.append(f"Z3 wiersze bez treści ({len(puste)}): {', '.join(puste[:10])}")

    # Z4 — zakazane wzorce i tagi
    cfg_z = tw.ustawienia().get("zamek", {})
    if not cfg_z.get("zakazane"):
        uwagi.append("UWAGA: brak profilu tekstu (zamek.zakazane) — sprawdzam tylko wzorce domyślne, bez P4")
    rx_zak = [re.compile(z, re.I) for z in ZAKAZANE_DOMYSLNE + cfg_z.get("zakazane", [])]
    rx_ostrz = [re.compile(z, re.I) for z in cfg_z.get("ostrzegawcze", [])]
    ostrzezenia = []
    for w in wiersze:
        for c in tresci:
            t = w.get(c) or ""
            czysty = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))
            for r in rx_zak:
                m = r.search(czysty)
                if m:
                    powody.append(f"Z4 {w[kod]} [{c}]: zakazany wzorzec „{m.group(0)}”")
            for r in rx_ostrz:
                m = r.search(czysty)
                if m:
                    ostrzezenia.append(f"Z4? {w[kod]} [{c}]: „…{czysty[max(0, m.start() - 40):m.end() + 30]}…”")
            for tag in TAGI:
                o, z = len(re.findall(rf"<{tag}[\s>]", t, re.I)), len(re.findall(rf"</{tag}>", t, re.I))
                if o != z:
                    powody.append(f"Z4 {w[kod]} [{c}]: <{tag}> otwarte {o} / zamknięte {z}")

    # Z1 — paczka = regeneracja
    polecenie = tw.opcja(argv, "--regeneruj")
    if polecenie:
        with tempfile.TemporaryDirectory() as tmp:
            wyj = Path(tmp) / "regeneracja.csv"
            r = subprocess.run(polecenie.replace("{wyjscie}", str(wyj)), shell=True, cwd=baza,
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            if r.returncode != 0 or not wyj.is_file():
                powody.append(f"Z1 regeneracja nie powiodła się (kod {r.returncode}): {(r.stderr or r.stdout)[-300:]}")
            else:
                _, reg, _ = wczytaj(wyj, kod, sep)
                tylko_p, tylko_r = sorted(set(po_kodzie) - set(reg)), sorted(set(reg) - set(po_kodzie))
                if tylko_p:
                    powody.append(f"Z1 w paczce, a nie w regeneracji ({len(tylko_p)}): {', '.join(tylko_p[:10])}")
                if tylko_r:
                    powody.append(f"Z1 w regeneracji, a nie w paczce ({len(tylko_r)}): {', '.join(tylko_r[:10])}")
                rozne = [k for k in po_kodzie if k in reg and any((po_kodzie[k].get(c) or "") != (reg[k].get(c) or "") for c in tresci)]
                if rozne:
                    powody.append(f"Z1 treść paczki ≠ bieżące artefakty ({len(rozne)}): {', '.join(rozne[:10])}")
                else:
                    uwagi.append(f"Z1 paczka = regeneracja ({len(set(po_kodzie) & set(reg))} kodów identycznych)")

    # Z2 — artefakty nowsze niż paczka
    t_paczki = paczka.stat().st_mtime
    artefakty = [Path(p) for g in opcje_wiele(argv, "--artefakty") for p in glob.glob(str(baza / g) if not os.path.isabs(g) else g)]
    nowsze = [p for p in artefakty if p.stat().st_mtime > t_paczki]
    if nowsze:
        powody.append(f"Z2 artefakty nowsze niż paczka ({len(nowsze)}): {', '.join(p.name for p in nowsze[:10])}")
    elif artefakty:
        uwagi.append(f"Z2 {len(artefakty)} artefaktów, żaden nowszy niż paczka")

    # Z5 — zmiany po ostatnim raporcie kontroli
    raporty = [Path(p) for g in opcje_wiele(argv, "--raporty") for p in glob.glob(str(baza / g) if not os.path.isabs(g) else g)]
    if raporty and artefakty:
        t_rap = max(p.stat().st_mtime for p in raporty)
        po = [p for p in artefakty if p.stat().st_mtime > t_rap]
        if po:
            powody.append(f"Z5 artefakty zmienione po ostatnim raporcie kontroli ({len(po)}): {', '.join(p.name for p in po[:10])}")

    # Z3 — lista oczekiwanych kodów
    lista = tw.opcja(argv, "--lista")
    if lista:
        lp = Path(lista) if os.path.isabs(lista) else baza / lista
        if lp.suffix.lower() == ".csv":
            with lp.open(encoding="utf-8-sig", newline="") as f:
                oczek = {r[kod] for r in csv.DictReader(f, delimiter=sep)}
        else:
            oczek = {l.strip() for l in lp.read_text(encoding="utf-8").splitlines() if l.strip()}
        sier, nadm = sorted(oczek - set(po_kodzie)), sorted(set(po_kodzie) - oczek)
        if sier:
            powody.append(f"Z3 sierotki — w liście, brak w paczce ({len(sier)}): {', '.join(sier[:10])}")
        if nadm:
            powody.append(f"Z3 nadmiarowe — w paczce, brak w liście ({len(nadm)}): {', '.join(nadm[:10])}")

    print(f"Paczka: {paczka} · wierszy {len(wiersze)} · kolumny treści: {', '.join(tresci)}")
    for u in uwagi:
        print(f"  ok  {u}")
    for o in ostrzezenia:
        print(f"  ?   {o}  (nie blokuje — spójrz)")
    for p in powody:
        print(f"  ✗   {p}")
    print("\nZAMEK ZAMKNIĘTY — nie wgrywać" if powody else "\nZAMEK OTWARTY — wolno wgrać")
    return 1 if powody else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
