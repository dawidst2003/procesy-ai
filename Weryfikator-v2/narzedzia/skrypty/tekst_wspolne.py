#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wspólna część bramek TREŚĆ ⇄ KARTA (tekst_*.py).

Bramki karty (karta_*.py) sprawdzają kartę faktów względem dokumentów. Bramki treści sprawdzają
gotowy tekst (opis, podstronę, sekcję raportu) względem karty faktów, z której powstał:
  - tekst_pokrycie.py       — czy pozycje krytyczne z karty [POTWIERDZONE] są w treści (pominięcia, R14a),
  - tekst_niepotwierdzone.py — czy do treści weszła wartość z wiersza bez [POTWIERDZONE] (R14b),
  - tekst_zawezenia.py      — czy treść nie uogólnia faktu ponad zawężenie ze źródła (R14c),
  - tekst_sklad.py          — czy procenty w tabeli składu nie sumują się ponad 100 (R14d).

Co jest „pozycją krytyczną", jakie są pary zawężeń i zakazane wzorce — to nie jest wiedza skryptu.
Czyta się to z profilu (`profile/<nazwa>-tekst.json`, wybór: pole `profil_tekstu` w weryfikacja.json)
i z sekcji `tekst` w weryfikacja.json projektu (listy dopisywane do profilu, wartości proste nadpisują).

Pary treść → karta:
  - argumenty pozycyjne parami: `opis.md karta.md [opis2.md karta2.md …]`,
  - albo `--pary plik.csv` z kolumnami `opis;karta` (ścieżki względem korzenia projektu, czyli folderu
    z weryfikacja.json). Plik par generuje projekt, bo tylko projekt wie, jak opis łączy się z kartą.

Bez zależności poza biblioteką standardową.
"""
from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import konfig  # noqa: E402

MODUL = Path(__file__).resolve().parent.parent

RX_ZNACZNIK = re.compile(r"\[(POTWIERDZONE|DO POTWIERDZENIA|BRAK)\]")


# ----------------------------------------------------------------------------------------- tekst

def norm(t: str) -> str:
    """Postać porównywalna: NFKC, małe litery, bez markdownu i HTML, jednolite myślniki i spacje."""
    t = unicodedata.normalize("NFKC", t or "")
    t = re.sub(r"<[^>]+>", " ", t)
    t = t.replace(" ", " ").replace(" ", " ").replace(" ", " ")
    t = re.sub(r"[–—−]", "-", t)
    t = re.sub(r"[*_`#]", "", t)
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip().lower()


def rx(wzorzec: str) -> re.Pattern:
    return re.compile(wzorzec, re.I)


# ------------------------------------------------------------------------------------- konfiguracja

def _konfig_od_par(argv: list[str]) -> None:
    """Gdy weryfikacja.json nie znalazł się od argumentów (np. plik par leży poza projektem),
    szukaj go w górę od pierwszego opisu z pliku par."""
    konfig.wczytaj(argv)
    if konfig.sciezka_konfigu() is not None:
        return
    plik = opcja(argv, "--pary")
    if not plik or not Path(plik).is_file():
        return
    with Path(plik).open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            o = Path(r["opis"])
            kand = o if o.is_absolute() else Path.cwd() / o
            if kand.exists():
                konfig._cache = None  # noqa: SLF001 — ponowne szukanie od ścieżki opisu
                konfig.wczytaj(["-", str(kand)])
            return


def ustawienia(argv: list[str] | None = None, wymagane: tuple[str, ...] = ()) -> dict:
    """Profil tekstu scalony z sekcją `tekst` z weryfikacja.json projektu.

    `wymagane` — klucze, bez których bramka nie ma reguł. Ich brak kończy skrypt kodem 2:
    cisza bez reguł wyglądałaby jak czysty wynik.
    """
    _konfig_od_par(list(sys.argv[1:] if argv is None else argv))
    k = konfig.wczytaj()
    wynik: dict = {}
    nazwa = k.get("profil_tekstu")
    if nazwa:
        plik = MODUL / "profile" / f"{nazwa}-tekst.json"
        if plik.is_file():
            wynik = json.loads(plik.read_text(encoding="utf-8"))
        else:
            print(f"[tekst] brak profilu {plik} — biorę tylko sekcję `tekst` projektu", file=sys.stderr)
    for klucz, wart in (k.get("tekst") or {}).items():
        if isinstance(wart, list) and isinstance(wynik.get(klucz), list):
            wynik[klucz] = wynik[klucz] + wart
        elif isinstance(wart, dict) and isinstance(wynik.get(klucz), dict):
            scal = dict(wynik[klucz])
            for k2, v2 in wart.items():
                scal[k2] = scal[k2] + v2 if isinstance(v2, list) and isinstance(scal.get(k2), list) else v2
            wynik[klucz] = scal
        else:
            wynik[klucz] = wart
    brak = [w for w in wymagane if not wynik.get(w)]
    if brak:
        print(f"BŁĄD: brak reguł {brak} — nie znalazłem profilu tekstu (weryfikacja.json: "
              f"{konfig.sciezka_konfigu() or 'nie znaleziony'}, profil_tekstu: {k.get('profil_tekstu')!r}). "
              f"Podaj --konfig <weryfikacja.json projektu>.", file=sys.stderr)
        sys.exit(2)
    return wynik


# ------------------------------------------------------------------------------------------- karta

def _komorki(linia: str) -> list[str]:
    s = linia.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def wiersze_karty(sciezka: Path) -> list[dict]:
    """Wiersze tabel karty, które mają znacznik pewności.

    Zwraca: {nr, atrybut, wartosc, tekst, znaczniki, potwierdzony, sekcja}.
    `wartosc` = komórka z kolumny „Wartość/Treść" (wg nagłówka tabeli), inaczej druga komórka.
    Tabele bez żadnego znacznika (np. dosłowne transkrypcje dokumentów) są pomijane.
    """
    wynik = []
    sekcja = ""
    idx_wart = 1
    naglowek = False
    for nr, linia in enumerate(sciezka.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if linia.startswith("#"):
            sekcja = linia.lstrip("#").strip()
            continue
        if not linia.lstrip().startswith("|"):
            naglowek = False
            continue
        kom = _komorki(linia)
        if all(re.fullmatch(r":?-{2,}:?", c or "--") for c in kom):
            continue
        if not naglowek:
            naglowek = True
            nazwy = [norm(c) for c in kom]
            idx_wart = next((i for i, n in enumerate(nazwy)
                             if re.match(r"(wartość|wartosc|treść|tresc)", n)), 1)
            if not RX_ZNACZNIK.search(linia):
                continue
        zn = set(RX_ZNACZNIK.findall(linia))
        if not zn:
            continue
        wynik.append({
            "nr": nr,
            "atrybut": kom[0] if kom else "",
            "wartosc": kom[idx_wart] if idx_wart < len(kom) else "",
            "tekst": " ".join(kom),
            "znaczniki": zn,
            "potwierdzony": "POTWIERDZONE" in zn,
            "sekcja": sekcja,
        })
    return wynik


# -------------------------------------------------------------------------------------------- opis

def jednostki_opisu(sciezka: Path) -> list[dict]:
    """Opis pocięty na jednostki: wiersz listy / wiersz tabeli / zdanie akapitu. {nr, sekcja, tekst}."""
    wynik = []
    sekcja = ""
    for nr, linia in enumerate(sciezka.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        s = linia.strip()
        if not s:
            continue
        if s.startswith("#"):
            sekcja = s.lstrip("#").strip()
            wynik.append({"nr": nr, "sekcja": sekcja, "tekst": sekcja, "naglowek": True})
            continue
        if s.startswith("|") or re.match(r"^([-*]|\d+\.)\s", s):
            wynik.append({"nr": nr, "sekcja": sekcja, "tekst": s, "naglowek": False})
            continue
        for zd in re.split(r"(?<=[.!?])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ„\"(])", s):
            wynik.append({"nr": nr, "sekcja": sekcja, "tekst": zd, "naglowek": False})
    return wynik


def tekst_opisu(sciezka: Path) -> str:
    return norm(sciezka.read_text(encoding="utf-8", errors="replace"))


# -------------------------------------------------------------------------------------------- pary

OPCJE_Z_WARTOSCIA = ("--pary", "--konfig", "--lista", "--tylko")


def pary(argv: list[str]) -> list[tuple[Path, Path]]:
    """Pary (opis, karta): z --pary plik.csv (kolumny opis;karta) i/lub z argumentów pozycyjnych parami."""
    wynik: list[tuple[Path, Path]] = []
    plik = opcja(argv, "--pary")
    if plik:
        baza = konfig.korzen()
        with Path(plik).open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f, delimiter=";"):
                o, k = Path(r["opis"]), Path(r["karta"])
                wynik.append((o if o.is_absolute() else baza / o, k if k.is_absolute() else baza / k))
    poz = argumenty_pozycyjne(argv, OPCJE_Z_WARTOSCIA)
    for i in range(0, len(poz) - 1, 2):
        wynik.append((Path(poz[i]), Path(poz[i + 1])))
    tylko = opcja(argv, "--tylko")
    if tylko:
        wynik = [p for p in wynik if re.search(tylko, str(p[0]), re.I)]
    return wynik


def opcja(argv: list[str], nazwa: str, domyslna: str | None = None) -> str | None:
    if nazwa in argv:
        i = argv.index(nazwa)
        if i + 1 < len(argv):
            return argv[i + 1]
    return domyslna


def argumenty_pozycyjne(argv: list[str], z_wartoscia: tuple[str, ...]) -> list[str]:
    """Argumenty bez opcji i bez wartości opcji z listy `z_wartoscia`."""
    wynik, pomin = [], False
    for a in argv:
        if pomin:
            pomin = False
            continue
        if a in z_wartoscia:
            pomin = True
            continue
        if a.startswith("--"):
            continue
        wynik.append(a)
    return wynik


def wypisz_wynik(nazwa: str, flagi: list[dict], blokujace: set[str], sprawdzono: int) -> int:
    """Jednolity wydruk: jedna linia na flagę + podsumowanie. Kod wyjścia 1, gdy jest flaga blokująca."""
    baza = konfig.korzen().resolve()
    for f in flagi:
        p = Path(f["plik"])
        try:
            p = p.resolve().relative_to(baza)
        except ValueError:
            p = Path(p.name) if len(str(p)) > 90 else p
        print(f"{p.as_posix()}:{f.get('linia', '-')}  {f['kod']}  {f['opis']}")
    blok = sum(1 for f in flagi if f["kod"] in blokujace)
    info = len(flagi) - blok
    print(f"\n{nazwa}: sprawdzono {sprawdzono} par opis-karta · flagi blokujące {blok} · informacyjne {info}")
    return 1 if blok else 0
