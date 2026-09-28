#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R10 · Kanarek podkładany skryptem — przez orkiestratora, nigdy przez sędziego.

Po co: kanarek ma sprawdzić UWAGĘ kontrolera. Gdy sędzia sam go sobie podkłada (projekt odniesienia,
2026-09), wie, gdzie jest, i test mierzy tylko jego narzędzie. Gdy kanarek jest zawsze tego
samego typu (podmiana liczby), nie mierzy pominięć — a to one przeciekają najczęściej.

Tryb PODŁÓŻ — kopiuje pliki do folderu kontrolera, w jednym (losowo) wprowadza jeden błąd,
wyrównuje daty modyfikacji wszystkich kopii, a klucz zapisuje POZA folderem kontrolera:
    python kanarek.py --do <folder kontrolera> --klucz <plik klucza> [--typ losowy|podmiana|usuniecie|dopisanie]
                      [--seed N] plik1.md plik2.md …
Typy (losowy = równo rozłożone):
    podmiana  — liczba z jednostką w wierszu tabeli / punkcie listy zmieniona na inną,
    usuniecie — jedno zdanie albo punkt z sekcji ostrzeżeń / pierwszej pomocy / przeciwwskazań (pominięcie),
    dopisanie — punkt z twierdzeniem bez źródła dopisany do zalet / zastosowań.

Tryb SPRAWDŹ — czy raport kontrolera wskazał kanarka:
    python kanarek.py --sprawdz <plik klucza> raport1.md [raport2.md …]
Heurystyka (nazwa pliku + fragment kanarka w raporcie) — wynik WYKRYTY / NIE WYKRYTY / DO OCENY.
Niewykryty kanarek = przebieg kontroli nieważny (R10).

Sekcje i szablony dopisań: profil (`kanarek` w profile/<profil>-tekst.json), inaczej domyślne niżej.
"""
from __future__ import annotations

import json
import os
import random
import re
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tekst_wspolne as tw  # noqa: E402

DOMYSLNE = {
    "sekcje_usuniecia": "ostrzeż|przeciwwskaz|pierwsz\\w* pomoc|bezpiecze|środki ostrożności",
    "sekcje_dopisania": "zalet|zastosowan|cechy|parametr",
    # {n:a|b|c} — liczba losowana z listy; wartości wiarygodne, żeby kanarek nie zdradzał się absurdem.
    "szablony_dopisania": [
        "- Zachowuje pełną skuteczność przez **{n:12|18|36} miesięcy** od otwarcia opakowania",
        "- Przebadany dermatologicznie na grupie **{n:30|50|100} osób**",
        "- Wytrzymuje **do {n:3|5|10} cykli** sterylizacji parowej bez utraty właściwości",
        "- Zachowuje właściwości w temperaturze od **{n:4|5|10} °C**",
    ],
}
RX_LICZBA = re.compile(r"(?<![\d.,/])(\d+(?:[.,]\d+)?)(\s?(?:%|mm|cm|ml|l|g|kg|mg|°C|min|h|s|szt\.?|µm|mies\w*|lat[a]?))(?![\wąćęłńóśźż])")


def ust() -> dict:
    u = dict(DOMYSLNE)
    u.update(tw.ustawienia().get("kanarek", {}))
    return u


def _inna_liczba(s: str, jednostka: str, rnd: random.Random) -> str:
    """Wiarygodna inna wartość: ±20–50% (albo ±1–3 dla małych liczb), procent nie przekracza 100."""
    dziesietna = "," if "," in s else ("." if "." in s else "")
    v = float(s.replace(",", "."))
    if v <= 5:
        kandydaci = [v + d for d in (-2, -1, 1, 2, 3) if v + d > 0]
    else:
        kandydaci = [v * f for f in (0.5, 0.67, 0.8, 1.25, 1.5)]
    if "%" in jednostka:
        kandydaci = [k for k in kandydaci if k <= 100] or [v / 2]
    nowa = rnd.choice([k for k in kandydaci if abs(k - v) > 1e-9])
    if dziesietna:
        return f"{nowa:.1f}".replace(".", dziesietna)
    return str(max(1, int(round(nowa)))) if int(round(nowa)) != int(v) else str(int(v) + 1)


def _wypelnij(szablon: str, rnd: random.Random) -> str:
    return re.sub(r"\{n:([^}]+)\}", lambda m: rnd.choice(m.group(1).split("|")), szablon)


def podloz(linie: list[str], typ: str, u: dict, rnd: random.Random) -> dict | None:
    sekcja = ""
    kand = []
    for i, l in enumerate(linie):
        s = l.strip()
        if s.startswith("#"):
            sekcja = s
            continue
        tresc = s.startswith("|") or re.match(r"^([-*]|\d+\.)\s", s)
        if typ == "podmiana" and tresc and not re.fullmatch(r"[|:\-\s]+", s):
            for m in RX_LICZBA.finditer(l):
                kand.append((i, m))
        elif typ == "usuniecie" and re.search(u["sekcje_usuniecia"], sekcja, re.I) and s and not s.startswith("|"):
            kand.append((i, None))
        elif typ == "dopisanie" and re.search(u["sekcje_dopisania"], sekcja, re.I) and re.match(r"^[-*]\s", s):
            kand.append((i, None))
    if not kand:
        return None
    i, m = rnd.choice(kand)
    przed = linie[i]
    if typ == "podmiana":
        nowa = _inna_liczba(m.group(1), m.group(2), rnd)
        linie[i] = przed[:m.start(1)] + nowa + przed[m.end(1):]
        return {"typ": typ, "linia": i + 1, "przed": m.group(0).strip(), "po": (nowa + m.group(2)).strip()}
    if typ == "usuniecie":
        konc = "\r\n" if przed.endswith("\r\n") else "\n"
        m_pref = re.match(r"^(\s*(?:[-*]|\d+\.)\s+)?(.*)$", przed.rstrip("\r\n"))
        prefiks, tresc = m_pref.group(1) or "", m_pref.group(2)
        zdania = re.split(r"(?<=[.;])\s+", tresc)
        if len(zdania) > 1:
            k = rnd.randrange(1, len(zdania))  # nie pierwsze: pierwsze zwykle niesie etykietę punktu
            usun = zdania.pop(k)
            linie[i] = prefiks + " ".join(zdania) + konc
        else:
            usun = tresc
            del linie[i]
        return {"typ": typ, "linia": i + 1, "przed": usun.strip(), "po": ""}
    nowy = _wypelnij(rnd.choice(u["szablony_dopisania"]), rnd)
    konc = "\r\n" if przed.endswith("\r\n") else "\n"
    linie.insert(i + 1, nowy + konc)
    return {"typ": typ, "linia": i + 2, "przed": "", "po": nowy.lstrip("-* ").replace("**", "")}


def tryb_podloz(argv: list[str]) -> int:
    folder = Path(tw.opcja(argv, "--do"))
    klucz = Path(tw.opcja(argv, "--klucz"))
    typ = tw.opcja(argv, "--typ", "losowy")
    seed = tw.opcja(argv, "--seed")
    pliki = [Path(p) for p in tw.argumenty_pozycyjne(argv, ("--do", "--klucz", "--typ", "--seed", "--konfig"))]
    if not pliki:
        print("brak plików"); return 2
    if folder.resolve() in klucz.resolve().parents:
        print("BŁĄD: klucz nie może leżeć w folderze kontrolera"); return 2
    rnd = random.Random(int(seed) if seed else None)
    folder.mkdir(parents=True, exist_ok=True)
    u = ust()
    typy = ["podmiana", "usuniecie", "dopisanie"] if typ == "losowy" else [typ]
    kolejnosc = pliki[:]
    rnd.shuffle(kolejnosc)
    wynik = None
    for t in rnd.sample(typy, len(typy)):
        for p in kolejnosc:
            linie = p.read_text(encoding="utf-8").splitlines(keepends=True)
            w = podloz(linie, t, u, rnd)
            if w:
                wynik = (p, linie, w)
                break
        if wynik:
            break
    if not wynik:
        print("nie znalazłem miejsca na kanarka w żadnym pliku"); return 2
    for p in pliki:
        shutil.copy2(p, folder / p.name)
    cel, linie, w = wynik
    (folder / cel.name).write_text("".join(linie), encoding="utf-8", newline="")
    teraz = time.time()
    for p in pliki:
        os.utime(folder / p.name, (teraz, teraz))
    w.update({"plik": cel.name, "zrodlo": str(cel), "folder": str(folder), "data": time.strftime("%Y-%m-%d %H:%M")})
    klucz.parent.mkdir(parents=True, exist_ok=True)
    klucz.write_text(json.dumps(w, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"kanarek podłożony w 1 z {len(pliki)} kopii w {folder} · klucz: {klucz} (nie pokazuj go kontrolerowi)")
    return 0


def tryb_sprawdz(argv: list[str]) -> int:
    k = json.loads(Path(tw.opcja(argv, "--sprawdz")).read_text(encoding="utf-8"))
    raporty = [Path(p) for p in tw.argumenty_pozycyjne(argv, ("--sprawdz", "--konfig"))]
    tekst = tw.norm(" ".join(p.read_text(encoding="utf-8", errors="replace") for p in raporty if p.is_file()))
    nazwa = tw.norm(Path(k["plik"]).stem)
    ma_plik = nazwa in tekst
    frag = tw.norm(k["po"] or k["przed"])
    if k["typ"] == "usuniecie":
        slowa = [s[:6] for s in re.findall(r"[a-ząćęłńóśźż]{5,}", frag)]
        trafione = sum(1 for s in slowa if s in tekst)
        ma_frag = bool(slowa) and trafione / len(slowa) >= 0.5
    else:
        ma_frag = frag in tekst or tw.norm(k["po"]).split(" ")[0] in tekst
    werdykt = "WYKRYTY" if ma_plik and ma_frag else ("DO OCENY" if ma_plik or ma_frag else "NIE WYKRYTY")
    print(f"kanarek ({k['typ']}) w {k['plik']} l. {k['linia']}: {werdykt}")
    print(f"  przed: {k['przed'][:120]}\n  po:    {k['po'][:120]}")
    if werdykt == "NIE WYKRYTY":
        print("  → przebieg kontroli nieważny (R10): nowy kontroler, inny agent.")
    return 0 if werdykt == "WYKRYTY" else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    sys.exit(tryb_sprawdz(a) if "--sprawdz" in a else tryb_podloz(a))
