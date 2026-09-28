#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""status_partii.py — generuje plik statusu kategorii z danych, zamiast pisania go recznie.

Uzycie:
    python _skrypty/status_partii.py <kategoria> [--out <plik>]

<kategoria> = nazwa folderu w 04-opisy-produktow/zrodla/ (dezynfekcja, higiena-pacjenta, sterylizacja).
Bez --out raport idzie na stdout (zeby przypadkiem nie nadpisac plikow STATUS-* w kontrola/).

Co zbiera (i czego NIE liczy — kazde takie miejsce jest w raporcie opisane wprost
"nie sprawdzono przez skrypt", zeby nie wygladalo na werdykt):
  1. linie.csv + mapa-produktow.csv -> sekcja "Bilans" (SKU, linie, rozklad statusow, niezgodnosci)
  2. produkty/*.md                  -> sekcja "Karty"
  3. kontrola/SEDZIA-*, RAPORT-SEDZIEGO-*, WERYFIKACJA-*, BRAMKA-*, TEST-SKRYPTU-* -> "Raporty kontrolne"
  4. kontrola/BRAKI-do-domkniecia.md -> "BRAKI"
  5. karta_forma.py + karta_cytaty_jezyk.py na kartach kategorii -> "Bramki"
  6. karty z mtime > mtime ostatniego raportu WERYFIKACJA-* -> "Zmiany kart po ostatnim raporcie weryfikacji"

Sekcja "## Wpisy reczne" na koncu: przy ponownym uruchomieniu z tym samym --out wszystko od tego
nagliwka w dol jest przepisywane BEZ ZMIAN (tam orkestrator trzyma decyzje i wartosci podlozone).

Skrypt niczego nie modyfikuje poza plikiem wskazanym w --out. Kart nie dotyka.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import re
import subprocess
import sys
from collections import Counter, OrderedDict
from pathlib import Path
import konfig  # profil projektu: sciezki i tokeny (weryfikacja.json)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# --------------------------------------------------------------------------------------------------
# Stale
# --------------------------------------------------------------------------------------------------

# Sciezki biore z weryfikacja.json projektu (konfig.py); skrypty — z folderu modulu.
ROOT = konfig.korzen()                                  # katalog projektu klienta
_S = konfig.sciezki()
ZRODLA = ROOT / _S["zrodla"]
KONTROLA = ROOT / _S["kontrola"]
SKRYPTY = Path(__file__).resolve().parent               # …/weryfikacja-faktow/skrypty
BRAKI_PLIK = KONTROLA / "BRAKI-do-domkniecia.md"

MARKER_RECZNE = "## Wpisy ręczne"
NIE_SPRAWDZONO = "nie sprawdzono przez skrypt"
TIMEOUT_S = 120

# kategoria -> (nazwa wyswietlana w tabelach BRAKI, aliasy w nazwach plikow raportow)
_KATEGORIE_Z_DYSKU = OrderedDict(
    (d.name, {"etykieta": d.name.replace("-", " ").capitalize(),
              "aliasy": [d.name, d.name.split("-")[0]]})
    for d in sorted(ZRODLA.iterdir()) if d.is_dir() and not d.name.startswith("_")
) if ZRODLA.is_dir() else OrderedDict()

KATEGORIE = _KATEGORIE_Z_DYSKU or OrderedDict([
    ("dezynfekcja",      {"etykieta": "Dezynfekcja",      "aliasy": ["dezynfekcja"]}),
    ("higiena-pacjenta", {"etykieta": "Higiena pacjenta", "aliasy": ["higiena-pacjenta", "higiena"]}),
    ("sterylizacja",     {"etykieta": "Sterylizacja",     "aliasy": ["sterylizacja"]}),
])

PREFIKSY_RAPORTOW = ("SEDZIA-", "RAPORT-SEDZIEGO-", "WERYFIKACJA-", "BRAMKA-", "TEST-SKRYPTU-")

ZNACZNIKI = ["[POTWIERDZONE]", "[DO POTWIERDZENIA]", "[BRAK]"]

RE_STATUS_POLE = re.compile(r"^\|\s*Status(?:\s+karty)?\s*\|\s*(.+?)\s*\|\s*$")
RE_NAGLOWEK = re.compile(r"^(#{1,6})\s+(.*)$")
RE_WERDYKT = re.compile(r"^#{1,6}\s*WERDYKT\b", re.IGNORECASE)
RE_PASS = re.compile(r"\bPASS\b")
RE_FAIL = re.compile(r"\bFAIL\b")
# wiersz tabeli SDS: "| §7 …" albo "| SEKCJA 7. …"
RE_SDS_WIERSZ = re.compile(r"^\|\s*(?:§\s*(\d{1,2})|SEKCJA\s+(\d{1,2}))\b", re.IGNORECASE)
RE_SDS_NIE_DOTYCZY = re.compile(r"SDS\s*[:—–-]\s*nie dotyczy", re.IGNORECASE)
RE_WARUNKI = re.compile(r"Warunki\s+u[żz]ycia", re.IGNORECASE)


# --------------------------------------------------------------------------------------------------
# Pomocnicze
# --------------------------------------------------------------------------------------------------

def czytaj(sciezka: Path) -> str:
    return sciezka.read_text(encoding="utf-8", errors="replace")


def mtime(sciezka: Path) -> dt.datetime:
    return dt.datetime.fromtimestamp(sciezka.stat().st_mtime)


def mtime_txt(sciezka: Path) -> str:
    return mtime(sciezka).strftime("%Y-%m-%d %H:%M")


def rel(sciezka: Path) -> str:
    try:
        return sciezka.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return sciezka.as_posix()


def esc(tekst: str) -> str:
    """Tresc do komorki tabeli markdown."""
    return tekst.replace("|", "\\|").replace("\n", " ").strip()


def skroc(tekst: str, n: int = 240) -> str:
    tekst = " ".join(tekst.split())
    return tekst if len(tekst) <= n else tekst[: n - 1] + "…"


def wczytaj_csv(sciezka: Path) -> tuple[list[dict], list[str]]:
    """CSV z separatorem ';' (tak sa zapisane linie.csv i mapa-produktow.csv)."""
    with sciezka.open(encoding="utf-8-sig", newline="") as fh:
        czytnik = csv.DictReader(fh, delimiter=";")
        wiersze = [w for w in czytnik if any((v or "").strip() for v in w.values())]
        naglowki = czytnik.fieldnames or []
    return wiersze, naglowki


# --------------------------------------------------------------------------------------------------
# 1. Bilans
# --------------------------------------------------------------------------------------------------

def sekcja_bilans(folder: Path) -> tuple[list[str], dict]:
    out: list[str] = ["## Bilans", ""]
    dane = {"linie_ids": set(), "statusy": Counter()}

    plik_linie = folder / "linie.csv"
    plik_mapa = folder / "mapa-produktow.csv"

    if not plik_linie.exists() or not plik_mapa.exists():
        brak = [p.name for p in (plik_linie, plik_mapa) if not p.exists()]
        out += [f"Brak pliku/plików: {', '.join(brak)} — bilansu nie policzono ({NIE_SPRAWDZONO}).", ""]
        return out, dane

    linie, _ = wczytaj_csv(plik_linie)
    mapa, _ = wczytaj_csv(plik_mapa)

    def pole(w: dict, nazwa: str) -> str:
        return (w.get(nazwa) or "").strip()

    kody_linie = [pole(w, "product_code") for w in linie]
    kody_mapa = [pole(w, "product_code") for w in mapa]
    ids_linie = [pole(w, "linia_id") for w in linie if pole(w, "linia_id")]
    ids_mapa = [pole(w, "linia_id") for w in mapa if pole(w, "linia_id")]
    unikalne_linie_id = sorted(set(ids_linie) | set(ids_mapa))
    dane["linie_ids"] = set(unikalne_linie_id)

    statusy_linie = Counter(pole(w, "status") for w in linie)
    dane["statusy"] = statusy_linie

    out += [
        f"- `linie.csv`: {len(linie)} wierszy (SKU), {len(set(kody_linie))} unikalnych `product_code`, "
        f"{len(set(ids_linie))} unikalnych `linia_id` · mtime {mtime_txt(plik_linie)}",
        f"- `mapa-produktow.csv`: {len(mapa)} wierszy (SKU), {len(set(kody_mapa))} unikalnych `product_code`, "
        f"{len(set(ids_mapa))} unikalnych `linia_id` · mtime {mtime_txt(plik_mapa)}",
        f"- **Razem: {len(set(kody_linie) | set(kody_mapa))} SKU, {len(unikalne_linie_id)} linii** "
        f"(suma zbiorów z obu plików).",
        "",
        "### Rozkład statusów (`linie.csv`)",
        "",
        "| status | SKU |",
        "|---|---|",
    ]
    for status, ile in sorted(statusy_linie.items(), key=lambda x: (-x[1], x[0])):
        out.append(f"| {esc(status) or '(pusty)'} | {ile} |")
    out.append("")

    # rozklad statusow w mapie, jesli sie rozni
    statusy_mapa = Counter(pole(w, "status") for w in mapa)
    if statusy_mapa != statusy_linie:
        out += ["### Rozkład statusów (`mapa-produktow.csv`) — różni się od `linie.csv`", "",
                "| status | SKU |", "|---|---|"]
        for status, ile in sorted(statusy_mapa.items(), key=lambda x: (-x[1], x[0])):
            out.append(f"| {esc(status) or '(pusty)'} | {ile} |")
        out.append("")

    # --- niezgodnosci ---
    niezgodnosci: list[str] = []

    dubel_l = [k for k, n in Counter(kody_linie).items() if n > 1]
    dubel_m = [k for k, n in Counter(kody_mapa).items() if n > 1]
    for nazwa, dublety in (("linie.csv", dubel_l), ("mapa-produktow.csv", dubel_m)):
        for kod in sorted(dublety):
            niezgodnosci.append(f"`{kod}` — powtórzony wiersz w `{nazwa}`")

    tylko_l = sorted(set(kody_linie) - set(kody_mapa))
    tylko_m = sorted(set(kody_mapa) - set(kody_linie))
    for kod in tylko_l:
        niezgodnosci.append(f"`{kod}` — jest w `linie.csv`, nie ma w `mapa-produktow.csv`")
    for kod in tylko_m:
        niezgodnosci.append(f"`{kod}` — jest w `mapa-produktow.csv`, nie ma w `linie.csv`")

    st_l = {pole(w, "product_code"): pole(w, "status") for w in linie}
    st_m = {pole(w, "product_code"): pole(w, "status") for w in mapa}
    for kod in sorted(set(st_l) & set(st_m)):
        if st_l[kod] != st_m[kod]:
            niezgodnosci.append(
                f"`{kod}` — różny status: `linie.csv` = „{esc(st_l[kod])}”, "
                f"`mapa-produktow.csv` = „{esc(st_m[kod])}”"
            )

    id_l = {pole(w, "product_code"): pole(w, "linia_id") for w in linie}
    id_m = {pole(w, "product_code"): pole(w, "linia_id") for w in mapa}
    for kod in sorted(set(id_l) & set(id_m)):
        if id_l[kod] != id_m[kod]:
            niezgodnosci.append(
                f"`{kod}` — różny `linia_id`: `linie.csv` = `{id_l[kod]}`, `mapa-produktow.csv` = `{id_m[kod]}`"
            )

    out.append("### Niezgodności między plikami")
    out.append("")
    if niezgodnosci:
        out += [f"- {n}" for n in niezgodnosci]
    else:
        out.append(f"- brak — sprawdzono: duplikaty `product_code` w obu plikach ({len(kody_linie)} + "
                   f"{len(kody_mapa)} wierszy), obecność SKU w obu plikach, zgodność kolumny `status` "
                   f"i `linia_id` dla {len(set(st_l) & set(st_m))} wspólnych SKU.")
    out.append("")
    out.append("Zgodność statusu z faktycznym stanem karty (czy status oddaje to, co w karcie) — "
               f"{NIE_SPRAWDZONO}.")
    out.append("")
    return out, dane


# --------------------------------------------------------------------------------------------------
# 2. Karty
# --------------------------------------------------------------------------------------------------

def opis_sds(tekst: str) -> str:
    """Czy karta ma tabele SDS z sekcjami §1–§16."""
    sekcje = set()
    for linia in tekst.splitlines():
        m = RE_SDS_WIERSZ.match(linia)
        if m:
            num = int(m.group(1) or m.group(2))
            if 1 <= num <= 16:
                sekcje.add(num)
    if len(sekcje) >= 16:
        return "tak (§1–§16)"
    if sekcje:
        return "częściowa (§" + ", §".join(str(n) for n in sorted(sekcje)) + ")"
    if RE_SDS_NIE_DOTYCZY.search(tekst):
        return "nie dotyczy (karta deklaruje „SDS — nie dotyczy”)"
    return "nie"


def opis_c7(tekst: str) -> str:
    """C7 = sekcja „Warunki użycia — zdanie po zdaniu …”. Część kart ma ją bez znacznika „C7”
    w nagłówku (cała sterylizacja, część dezynfekcji), dlatego liczy się też sam tytuł."""
    naglowki = [m.group(2) for m in (RE_NAGLOWEK.match(l) for l in tekst.splitlines()) if m]
    if any("C7" in h for h in naglowki):
        return "tak (C7 w nagłówku)"
    if any(RE_WARUNKI.search(h) for h in naglowki):
        return "tak (nagłówek „Warunki użycia”, bez znacznika C7)"
    return "tak (C7 tylko w treści, bez nagłówka)" if "C7" in tekst else "nie"


def status_karty(tekst: str) -> str:
    for linia in tekst.splitlines():
        m = RE_STATUS_POLE.match(linia)
        if m:
            return m.group(1)
    return "(brak pola „Status”)"


def sekcja_karty(folder: Path, linie_ids: set[str]) -> tuple[list[str], list[Path]]:
    out: list[str] = ["## Karty", ""]
    kat_produkty = folder / "produkty"
    if not kat_produkty.is_dir():
        out += [f"Brak folderu `{rel(kat_produkty)}` — kart nie policzono ({NIE_SPRAWDZONO}).", ""]
        return out, []

    karty = sorted(kat_produkty.glob("*.md"))
    out += [
        f"Kart: **{len(karty)}** · `{rel(kat_produkty)}`",
        "",
        "| linia (plik) | status z karty | mtime | [POTWIERDZONE] | [DO POTWIERDZENIA] | [BRAK] | C7 | tabela SDS §1–§16 |",
        "|---|---|---|---:|---:|---:|---|---|",
    ]
    for karta in karty:
        tekst = czytaj(karta)
        licz = [tekst.count(z) for z in ZNACZNIKI]
        out.append(
            f"| {karta.stem} | {esc(skroc(status_karty(tekst), 80))} | {mtime_txt(karta)} | "
            f"{licz[0]} | {licz[1]} | {licz[2]} | {opis_c7(tekst)} | {esc(opis_sds(tekst))} |"
        )
    out.append("")

    stemy = {k.stem for k in karty}
    bez_karty = sorted(linie_ids - stemy)
    bez_linii = sorted(stemy - linie_ids)
    if bez_karty:
        out.append(f"- `linia_id` bez pliku karty: {', '.join('`%s`' % x for x in bez_karty)}")
    if bez_linii:
        out.append(f"- karta bez `linia_id` w CSV: {', '.join('`%s`' % x for x in bez_linii)}")
    if not bez_karty and not bez_linii:
        out.append(f"- pokrycie linia_id ↔ plik karty: pełne ({len(stemy)}/{len(stemy)}).")
    out += ["",
            f"Treść kart (czy fakty są poprawne, czy znaczniki są zasadne) — {NIE_SPRAWDZONO}; "
            f"liczby wyżej to wystąpienia literałów w tekście, nie ocena.",
            ""]
    return out, karty


# --------------------------------------------------------------------------------------------------
# 3. Raporty kontrolne
# --------------------------------------------------------------------------------------------------

def raporty_kategorii(kategoria: str) -> list[tuple[Path, str]]:
    """Zwraca [(plik, sposob_dopasowania)] posortowane po mtime malejaco."""
    if not KONTROLA.is_dir():
        return []
    aliasy = KATEGORIE[kategoria]["aliasy"]
    wszystkie_aliasy = [a for k in KATEGORIE.values() for a in k["aliasy"]]
    wynik: list[tuple[Path, str]] = []
    for plik in sorted(KONTROLA.iterdir()):
        if not plik.is_file() or not plik.name.startswith(PREFIKSY_RAPORTOW):
            continue
        nazwa = plik.name.lower()
        if any(a in nazwa for a in aliasy):
            wynik.append((plik, "nazwa"))
            continue
        # plik bez zadnego znacznika kategorii w nazwie (np. SEDZIA-v21-fakty-G3, TEST-SKRYPTU-*):
        # dopasowanie po tresci — wzmianka o folderze zrodel tej kategorii
        if not any(a in nazwa for a in wszystkie_aliasy):
            try:
                tresc = czytaj(plik)
            except Exception:
                continue
            if f"zrodla/{kategoria}/" in tresc or f"zrodla\\{kategoria}\\" in tresc:
                wynik.append((plik, "treść"))
    wynik.sort(key=lambda p: p[0].stat().st_mtime, reverse=True)
    return wynik


def werdykt_i_liczby(tekst: str) -> tuple[list[str], int, int, str]:
    """Pierwsze linie sekcji '## WERDYKT' + policzone PASS/FAIL i zakres liczenia."""
    linie = tekst.splitlines()
    start = None
    poziom = 2
    for i, l in enumerate(linie):
        if RE_WERDYKT.match(l):
            start = i
            poziom = len(RE_NAGLOWEK.match(l).group(1))
            break
    if start is None:
        return [], len(RE_PASS.findall(tekst)), len(RE_FAIL.findall(tekst)), "cały plik"

    koniec = len(linie)
    for j in range(start + 1, len(linie)):
        m = RE_NAGLOWEK.match(linie[j])
        if m and len(m.group(1)) <= poziom:
            koniec = j
            break
    blok = linie[start:koniec]
    tresc = "\n".join(blok)
    naglowek_tekst = RE_NAGLOWEK.match(blok[0]).group(2).strip()
    pierwsze = [naglowek_tekst] if naglowek_tekst.upper() not in ("WERDYKT",) else []
    for l in blok[1:]:
        if l.strip():
            pierwsze.append(l.strip())
        if len(pierwsze) >= 5:
            break
    return pierwsze, len(RE_PASS.findall(tresc)), len(RE_FAIL.findall(tresc)), "sekcja WERDYKT"


def sekcja_raporty(kategoria: str) -> tuple[list[str], list[tuple[Path, str]]]:
    out: list[str] = ["## Raporty kontrolne", ""]
    raporty = raporty_kategorii(kategoria)
    out.append(
        f"Katalog `{rel(KONTROLA)}`, prefiksy: {', '.join(p + '*' for p in PREFIKSY_RAPORTOW)}. "
        f"Dopasowanie: alias kategorii w nazwie pliku ({', '.join(KATEGORIE[kategoria]['aliasy'])}); "
        f"pliki bez żadnego aliasu kategorii w nazwie — po wzmiance o `zrodla/{kategoria}/` w treści. "
        f"Raportów dopasowanych: **{len(raporty)}**."
    )
    out.append("")
    if not raporty:
        out += [f"Brak dopasowanych raportów. Czy istnieją raporty tej kategorii pod inną nazwą — "
                f"{NIE_SPRAWDZONO}.", ""]
        return out, raporty

    for plik, sposob in raporty:
        tekst = czytaj(plik)
        pierwsze, ile_pass, ile_fail, zakres = werdykt_i_liczby(tekst)
        out.append(f"### {plik.name}")
        out.append("")
        out.append(f"- mtime: {mtime_txt(plik)} · dopasowanie: po {sposob}")
        if pierwsze:
            out.append(f"- PASS: {ile_pass} · FAIL: {ile_fail} ({zakres})")
            out.append("- „## WERDYKT” (pierwsze linie):")
            for l in pierwsze:
                out.append(f"  > {skroc(l, 400)}")
        else:
            out.append(f"- nagłówka „## WERDYKT” nie ma — PASS: {ile_pass} · FAIL: {ile_fail} ({zakres}); "
                       f"werdykt słowny — {NIE_SPRAWDZONO}")
        out.append("")
    out.append(f"Liczby PASS/FAIL to wystąpienia słów w tekście — nie są werdyktem raportu ani sumą pozycji; "
               f"interpretacja — {NIE_SPRAWDZONO}.")
    out.append("")
    return out, raporty


# --------------------------------------------------------------------------------------------------
# 4. BRAKI
# --------------------------------------------------------------------------------------------------

def sekcja_braki(kategoria: str, linie_ids: set[str]) -> list[str]:
    out: list[str] = ["## BRAKI", ""]
    if not BRAKI_PLIK.exists():
        out += [f"Brak pliku `{rel(BRAKI_PLIK)}` — {NIE_SPRAWDZONO}.", ""]
        return out

    tekst = czytaj(BRAKI_PLIK)
    etykieta = KATEGORIE[kategoria]["etykieta"].lower()
    out.append(f"Źródło: `{rel(BRAKI_PLIK)}` · mtime {mtime_txt(BRAKI_PLIK)}")
    out.append("")

    # a) wiersze tabel, w ktorych pierwsza komorka = etykieta kategorii
    wiersze = []
    for linia in tekst.splitlines():
        if not linia.strip().startswith("|"):
            continue
        komorki = [k.strip() for k in linia.strip().strip("|").split("|")]
        if komorki and komorki[0].lower() == etykieta:
            wiersze.append(komorki)
    if wiersze:
        out += [f"### Wiersze tabel z kolumną „Kategoria” = „{KATEGORIE[kategoria]['etykieta']}” ({len(wiersze)})",
                ""]
        for k in wiersze:
            out.append("- " + " · ".join(esc(x) for x in k[1:]))
        out.append("")
    else:
        out += [f"Brak wierszy tabel z kolumną „Kategoria” = „{KATEGORIE[kategoria]['etykieta']}”.", ""]

    # b) sekcje "## ", w ktorych pada linia_id tej kategorii
    sekcje: list[tuple[str, list[str]]] = []
    biezacy_tytul, biezaca_tresc = None, []
    for linia in tekst.splitlines():
        m = RE_NAGLOWEK.match(linia)
        if m and len(m.group(1)) == 2:
            if biezacy_tytul is not None:
                sekcje.append((biezacy_tytul, biezaca_tresc))
            biezacy_tytul, biezaca_tresc = m.group(2).strip(), []
        elif biezacy_tytul is not None:
            biezaca_tresc.append(linia)
    if biezacy_tytul is not None:
        sekcje.append((biezacy_tytul, biezaca_tresc))

    trafienia = []
    for tytul, tresc in sekcje:
        blok = "\n".join(tresc)
        pasujace = sorted({lid for lid in linie_ids if lid and lid in blok})
        if pasujace:
            trafienia.append((tytul, pasujace))
    if trafienia:
        out += ["### Sekcje, w których pada `linia_id` tej kategorii", ""]
        for tytul, pasujace in trafienia:
            out.append(f"- **{esc(tytul)}** — linie: {', '.join('`%s`' % x for x in pasujace)}")
        out.append("")
    else:
        out += ["Żadna sekcja `## …` pliku BRAKI nie zawiera `linia_id` tej kategorii.", ""]

    out.append(f"Pozycje BRAKI opisane wyłącznie nazwą handlową, bez etykiety kategorii i bez `linia_id` "
               f"(np. „Rejestr braków formalnych dla SKU pozostających w batchu”) — {NIE_SPRAWDZONO}.")
    out.append("")
    return out


# --------------------------------------------------------------------------------------------------
# 5. Bramki
# --------------------------------------------------------------------------------------------------

def uruchom(skrypt: Path, karty: list[Path]) -> tuple[str, str]:
    """Zwraca (status, tresc_wyjscia). status: 'ok' | 'brak' | 'timeout' | 'blad'."""
    if not skrypt.exists():
        return "brak", f"skryptu `{rel(skrypt)}` nie ma — {NIE_SPRAWDZONO}"
    if not karty:
        return "brak", f"brak kart do sprawdzenia — {NIE_SPRAWDZONO}"
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    cmd = [sys.executable, str(skrypt)] + [str(k) for k in karty]
    try:
        wynik = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=TIMEOUT_S, env=env, cwd=str(ROOT))
    except subprocess.TimeoutExpired:
        return "timeout", f"przekroczony limit {TIMEOUT_S} s — {NIE_SPRAWDZONO}"
    except Exception as e:  # noqa: BLE001
        return "blad", f"uruchomienie nie powiodło się ({e}) — {NIE_SPRAWDZONO}"
    return "ok", (wynik.stdout or "") + (("\n" + wynik.stderr) if wynik.stderr.strip() else "")


def bramka_forma(karty: list[Path]) -> list[str]:
    skrypt = SKRYPTY / "karta_forma.py"
    out = [f"### `karta_forma.py` ({len(karty)} kart)", ""]
    status, tresc = uruchom(skrypt, karty)
    if status != "ok":
        out += [f"- {tresc}", ""]
        return out
    linie = tresc.splitlines()
    podsum = []
    for i, l in enumerate(linie):
        if l.strip().startswith("== PODSUMOWANIE"):
            podsum = [x.strip() for x in linie[i + 1:] if x.strip()]
            break
    if podsum:
        for l in podsum:
            out.append(f"- {l}")
    else:
        out.append(f"- skrypt nie wypisał bloku „== PODSUMOWANIE” — {NIE_SPRAWDZONO}")
    # per-karta: "== <sciezka> — flag: N (blokujących: M)"
    per = []
    for l in linie:
        m = re.match(r"^==\s+(\S+\.md)\s+—\s+flag:\s*(\d+)\s*\(blokujących:\s*(\d+)\)", l.strip())
        if m:
            per.append((Path(m.group(1)).name, int(m.group(2)), int(m.group(3))))
    if per:
        out += ["", "| karta | flag | blokujących |", "|---|---:|---:|"]
        for nazwa, flag, blok in per:
            out.append(f"| {nazwa} | {flag} | {blok} |")
    out.append("")
    return out


def bramka_cytaty(karty: list[Path]) -> list[str]:
    skrypt = SKRYPTY / "karta_cytaty_jezyk.py"
    out = [f"### `karta_cytaty_jezyk.py` ({len(karty)} kart)", ""]
    status, tresc = uruchom(skrypt, karty)
    if status != "ok":
        out += [f"- {tresc}", ""]
        return out
    wiersze = []
    suma = Counter()
    for l in tresc.splitlines():
        m = re.match(r"^(\S+\.md):\s*(.+)$", l.strip())
        if not m or "=" not in m.group(2):
            continue
        pary = []
        for czesc in m.group(2).split(","):
            if "=" in czesc:
                k, _, v = czesc.partition("=")
                k, v = k.strip(), v.strip()
                if v.isdigit():
                    pary.append((k, int(v)))
                    suma[k] += int(v)
        if pary:
            wiersze.append((m.group(1), pary))
    if not wiersze:
        out += [f"- skrypt nie wypisał linii podsumowania per karta — {NIE_SPRAWDZONO}", ""]
        return out
    klucze = [k for k, _ in wiersze[0][1]]
    out += ["| karta | " + " | ".join(klucze) + " |",
            "|---|" + "---:|" * len(klucze)]
    for nazwa, pary in wiersze:
        d = dict(pary)
        out.append(f"| {nazwa} | " + " | ".join(str(d.get(k, "—")) for k in klucze) + " |")
    out.append("| **razem** | " + " | ".join(f"**{suma.get(k, 0)}**" for k in klucze) + " |")
    out.append("")
    return out


def sekcja_bramki(karty: list[Path]) -> list[str]:
    out = ["## Bramki", ""]
    out.append(f"Uruchomienie na kartach kategorii, limit {TIMEOUT_S} s na skrypt, `PYTHONIOENCODING=utf-8`.")
    out.append("")
    out += bramka_forma(karty)
    out += bramka_cytaty(karty)
    out.append(f"Pozostałe skrypty kontrolne z `_skrypty/` (negacje, zakresy, SHA, atrybuty SDS itd.) — "
               f"{NIE_SPRAWDZONO}; ten raport uruchamia tylko dwie bramki wymienione wyżej.")
    out.append("")
    return out


# --------------------------------------------------------------------------------------------------
# 6. Zmiany kart po ostatnim raporcie weryfikacji
# --------------------------------------------------------------------------------------------------

def sekcja_zmiany(karty: list[Path], raporty: list[tuple[Path, str]]) -> list[str]:
    out = ["## Zmiany kart po ostatnim raporcie weryfikacji", ""]
    weryfikacje = [p for p, _ in raporty if p.name.startswith("WERYFIKACJA-")]
    if not weryfikacje:
        out += [f"Brak raportu `WERYFIKACJA-*` dopasowanego do kategorii — porównania nie wykonano "
                f"({NIE_SPRAWDZONO}).", ""]
        return out
    ostatni = max(weryfikacje, key=lambda p: p.stat().st_mtime)
    prog = mtime(ostatni)
    out.append(f"Punkt odniesienia: `{ostatni.name}` · mtime {mtime_txt(ostatni)}")
    out.append("")
    nowsze = [k for k in karty if mtime(k) > prog]
    if nowsze:
        out += ["| karta | mtime karty |", "|---|---|"]
        for k in sorted(nowsze, key=lambda p: p.stat().st_mtime, reverse=True):
            out.append(f"| {k.stem} | {mtime_txt(k)} |")
        out.append("")
        out.append(f"**{len(nowsze)} z {len(karty)} kart** ma mtime późniejszy niż ten raport.")
    else:
        out.append(f"Żadna z {len(karty)} kart nie ma mtime późniejszego niż ten raport.")
    out += ["",
            f"mtime mówi tylko o zapisie pliku — czy zmiana była merytoryczna i czy dotyczyła pozycji "
            f"z raportu: {NIE_SPRAWDZONO}.",
            ""]
    return out


# --------------------------------------------------------------------------------------------------
# Wpisy reczne
# --------------------------------------------------------------------------------------------------

def zachowane_wpisy_reczne(plik: Path | None) -> str:
    """Wszystko od nagliwka '## Wpisy ręczne' w dol z poprzedniego przebiegu, bez zmian."""
    if plik is None or not plik.exists():
        return ""
    stary = czytaj(plik)
    linie = stary.splitlines()
    for i, l in enumerate(linie):
        if l.strip() == MARKER_RECZNE:
            return "\n".join(linie[i:]).rstrip() + "\n"
    return ""


# --------------------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------------------

def zbuduj(kategoria: str, plik_wy: Path | None) -> str:
    folder = ZRODLA / kategoria
    teraz = dt.datetime.now()
    czesci: list[str] = [
        f"# Status partii — {KATEGORIE[kategoria]['etykieta']} ({teraz:%Y-%m-%d})",
        "",
        f"Wygenerowane: **{teraz:%Y-%m-%d %H:%M}** przez `_skrypty/status_partii.py {kategoria}` "
        f"(dane, nie ocena orkestratora).",
        f"Źródła: `{rel(folder)}/linie.csv`, `mapa-produktow.csv`, `produkty/*.md`; "
        f"`{rel(KONTROLA)}`; `{rel(BRAKI_PLIK)}`.",
        "Wszystko poniżej jest odczytane z plików. Miejsca oznaczone "
        f"„{NIE_SPRAWDZONO}” to luki, nie werdykty.",
        "",
    ]

    bilans, dane = sekcja_bilans(folder)
    czesci += bilans

    karty_md, karty = sekcja_karty(folder, dane["linie_ids"])
    czesci += karty_md

    raporty_md, raporty = sekcja_raporty(kategoria)
    czesci += raporty_md

    czesci += sekcja_bramki(karty)
    czesci += sekcja_braki(kategoria, dane["linie_ids"])
    czesci += sekcja_zmiany(karty, raporty)

    tresc = "\n".join(czesci).rstrip() + "\n\n"
    reczne = zachowane_wpisy_reczne(plik_wy)
    if reczne:
        tresc += reczne
    else:
        tresc += (MARKER_RECZNE + "\n\n"
                  "_Sekcja dla orkestratora: decyzje, wartości podłożone sędziemu, ustalenia z Dawidem._\n"
                  "_Skrypt przy kolejnym uruchomieniu przepisuje wszystko od tego nagłówka w dół bez zmian._\n")
    return tresc


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Generuje plik statusu kategorii z danych (04-opisy-produktow).")
    ap.add_argument("kategoria", help="folder w 04-opisy-produktow/zrodla/ (%s)" % ", ".join(KATEGORIE))
    ap.add_argument("--out", help="plik wyjściowy .md; bez tego raport idzie na stdout")
    args = ap.parse_args(argv)

    if args.kategoria not in KATEGORIE:
        print(f"Nieznana kategoria: {args.kategoria}. Dozwolone: {', '.join(KATEGORIE)}", file=sys.stderr)
        return 2
    if not (ZRODLA / args.kategoria).is_dir():
        print(f"Brak folderu: {ZRODLA / args.kategoria}", file=sys.stderr)
        return 2

    plik_wy = Path(args.out).resolve() if args.out else None
    if plik_wy is not None and plik_wy.parent == KONTROLA and plik_wy.name.startswith("STATUS-") \
            and plik_wy.exists():
        print(f"Odmowa: `{plik_wy.name}` to istniejący plik STATUS-* w kontrola/ — nie nadpisuję.",
              file=sys.stderr)
        return 3

    tresc = zbuduj(args.kategoria, plik_wy)
    if plik_wy is None:
        print(tresc)
    else:
        plik_wy.parent.mkdir(parents=True, exist_ok=True)
        plik_wy.write_text(tresc, encoding="utf-8")
        print(f"Zapisano: {plik_wy}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
