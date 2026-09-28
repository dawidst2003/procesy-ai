#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sds_pl_do_karty.py
Wyciaga z polskiej karty charakterystyki (format UE, SEKCJA 1-16) tresc doslowna
sekcji + metadane + wartosci kluczowe do weryfikacji + flagi jakosci.

Uzycie:
    python sds_pl_do_karty.py <plik SDS PL .pdf lub .txt> [--wyjscie plik.md]

Wymagania: Python 3.12, PyMuPDF (fitz), biblioteka standardowa.
Bez WebFetch, bez sieci - dziala wylacznie na pliku lokalnym.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

# --------------------------------------------------------------------------
# Wzorce
# --------------------------------------------------------------------------

# Litery "SEKCJA" z opcjonalnymi pojedynczymi spacjami miedzy nimi (case-insensitive) -
# niektore PDF-y maja zle metadane kerningu i PyMuPDF wstawia losowa spacje w srodku
# slowa (np. "Se kcja 3:" zamiast "Sekcja 3:"), inaczej naglowek sekcji ginie w calosci.
# UWAGA (2026-09-16): numer MUSI byc calą sekcja (1-16), NIE podsekcja - "(?!\.?\d)" po
# numerze odrzuca np. "sekcja 10.5." (odnosnik w biegnacym tekscie typu "Wiecej informacji
# patrz sekcja 10.5.", zlamany przez ekstrakcje PDF na osobna linie zaczynajaca sie od
# "sekcja") i "sekcja 160" (przypadkowa 3-cia cyfra). Bez tego straznika "sekcja 10.5"
# byla lapana jako naglowek SEKCJA 10 i psula przypisanie tresci do sekcji (patrz
# WERYFIKACJA-RUNDA4-saiko-2026-09-16.md, wiersz SEKCJA 10 zawieral tresc §7.3).
SEC_RE = re.compile(r'^[\*\-·•]?\s*S\s?E\s?K\s?C\s?J\s?A\s+(\d{1,2})(?!\.?\d)\s*[.:]?\s*(.*)$', re.IGNORECASE)
SUB1_RE = re.compile(r'^[\*\-·•]?\s*1\.1\b')
CONT_RE = re.compile(r'\(ci\S{0,3}g dalszy[^)]*\)', re.IGNORECASE)

PAGE_MARK_RE = re.compile(
    r'^\s*(?:===\s*strona\s*\d+\s*===|---\s*(?:PAGE|strona)\s*\d+\s*---)\s*$',
    re.IGNORECASE,
)
JUNK_LINE_PATTERNS = [
    # "1 / 16" - spacje wokol "/" sa wymagane, zeby nie lapac realnych danych typu
    # numer rejestracji "7675/19" (bez spacji), ktore wygladaja podobnie
    re.compile(r'^\d{1,4}\s+/\s+\d{1,4}$'),
    re.compile(r'^strona\s*:?\s*\d+\s*/\s*\d+$', re.IGNORECASE),
    re.compile(r'^---\s*(PAGE|strona)\s*\d+\s*---$', re.IGNORECASE),
    re.compile(r'^===\s*strona\s*\d+\s*===$', re.IGNORECASE),
    re.compile(r'^\(ci\S{0,3}g dalszy[^)]*\)$', re.IGNORECASE),
    # "- Kontynuacja na następnej stronie -" - artefakt paginacji wstawiany przez
    # niektore SDS (medisept, saiko-med) na dole KAZDEJ strony poza ostatnia; w
    # przeciwienstwie do "Strona N/M" tresc jest identyczna na kazdej stronie, ale
    # bywa poza strefa naglowka/stopki liczona przez collect_boilerplate (patrz
    # HEADER_ZONE/FOOTER_ZONE), wiec lapiemy ja tez wprost jako smiec liniowy.
    re.compile(r'^[-–—]\s*Kontynuacja\s+na\s+nast[eę]pnej\s+stronie\s*[-–—]$', re.IGNORECASE),
]

CAS_RE = re.compile(r'(?<![\d-])\d{2,7}-\d{2}-\d(?!-\d)')
_CMP_OP = r'(?:>=|<=|>|<|≥|≤)'  # ASCII >=/<=/</>  +  Unicode ≥/≤
# UWAGA: odstep miedzy liczba a "%" to celowo [ \t]* (BEZ \n) - zwykle \s* przeskakuje
# przez koniec linii i sklejalby np. ostatnia cyfre numeru WE "...-578-6" z "%" ktore
# nalezy do zupelnie innego, dalszego zdania w kolejnej linii ("% (m/m) >=50: ..."),
# dajac fikcyjny procent "6 %". Prawdziwy zapis "50 - <75 %" zawsze siedzi w jednej linii.
_GAP = r'[ \t]*'
PERC_RE = re.compile(
    rf'(?:{_CMP_OP}{_GAP})?\d{{1,3}}(?:[.,]\d+)?{_GAP}%'                                          # "43%", "<10 %", "≤10 %"
    rf'|(?:{_CMP_OP}{_GAP})?\d{{1,3}}(?:[.,]\d+)?{_GAP}-{_GAP}(?:{_CMP_OP}{_GAP})?\d{{1,3}}(?:[.,]\d+)?{_GAP}%'  # "50 - <75 %" (musi konczyc sie %)
    rf'|{_CMP_OP}{_GAP}\d{{1,3}}(?:[.,]\d+)?{_GAP}-{_GAP}{_CMP_OP}?{_GAP}\d{{1,3}}(?:[.,]\d+)?'          # ">= 30 - < 50" / "≥ 3 - < 8" (bez %, wymaga operatora)
)
# UWAGA: bez wymogu "%" LUB operatora >=/<=/</> zwykly wzorzec "liczba-liczba" lapalby
# fragmenty numerow WE/REACH (np. "201-069" z "201-069-1") jako fikcyjny procent.
H_CODE_RE = re.compile(r'\bH\d{3}[a-zA-Z]?\b')
P_CODE_RE = re.compile(r'\bP\d{3}(?:\s*\+\s*P\d{3}){0,3}\b')
GHS_RE = re.compile(r'\bGHS0\d\b')
DATE_RE = re.compile(r'\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b')
UFI_RE = re.compile(r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b')

SECTION_TITLES_PL = {
    1: "Identyfikacja substancji/mieszaniny i identyfikacja przedsiebiorstwa",
    2: "Identyfikacja zagrozen",
    3: "Sklad/informacja o skladnikach",
    4: "Srodki pierwszej pomocy",
    5: "Postepowanie w przypadku pozaru",
    6: "Postepowanie w przypadku niezamierzonego uwolnienia do srodowiska",
    7: "Postepowanie z substancjami i mieszaninami oraz ich magazynowanie",
    8: "Kontrola narazenia/srodki ochrony indywidualnej",
    9: "Wlasciwosci fizyczne i chemiczne",
    10: "Stabilnosc i reaktywnosc",
    11: "Informacje toksykologiczne",
    12: "Informacje ekologiczne",
    13: "Postepowanie z odpadami",
    14: "Informacje dotyczace transportu",
    15: "Informacje dotyczace przepisow prawnych",
    16: "Inne informacje",
}

HEADER_ZONE = 6
FOOTER_ZONE = 6
MIN_BOILER_LEN = 3


# --------------------------------------------------------------------------
# Heurystyka jezykowa (flaga "dokument nie po polsku")
# --------------------------------------------------------------------------

# Proste markery slowne dla 3 najczesciej spotykanych jezykow SDS w tym projekcie
# (PL/DE/EN). To nie jest wykrywanie jezyka klasy produkcyjnej - to szybka heurystyka
# licznikowa (\b-slowa charakterystyczne), wystarczajaca zeby zlapac oczywista pomylke
# pliku (np. wgranie SDS_DE zamiast SDS_PL).
_LANG_MARKERS = {
    "polski": [
        r'\bsekcja\b', r'\boraz\b', r'\bnalezy\b', r'\bmieszanin[ay]\b',
        r'\bzagrozen\b', r'\bsubstancj\w*\b', r'\bnie\b', r'\bsie\b', r'\bdla\b',
        r'\bkarta charakterystyki\b',
    ],
    "niemiecki": [
        r'\babschnitt\b', r'\bsicherheitsdatenblatt\b', r'\bgemass\b', r'\bund\b',
        r'\bnicht\b', r'\bfur\b', r'\bgefahrenhinweise\b', r'\bmischung\b',
    ],
    "angielski": [
        r'\bsection\b', r'\bsafety data sheet\b', r'\band\b', r'\bnot\b',
        r'\bwith\b', r'\bhazard statements\b', r'\bmixture\b',
    ],
}


def _strip_diacritics(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def detect_language(full_text: str) -> tuple[str, dict[str, int]]:
    """Zwraca (jezyk_o_najwyzszym_wyniku, wszystkie_wyniki). Dziala na tekscie
    bez polskich znakow diakrytycznych (usuwamy je tez z wzorcow), zeby literowki
    OCR / brak diakrytykow w PDF nie psuly wyniku dla polskiego."""
    low = _strip_diacritics(full_text).lower()
    scores: dict[str, int] = {}
    for lang, pats in _LANG_MARKERS.items():
        scores[lang] = sum(len(re.findall(p, low)) for p in pats)
    best = max(scores, key=lambda k: scores[k])
    return best, scores


def language_flag(full_text: str) -> str | None:
    if len(full_text.strip()) < 200:
        return None  # za malo tekstu - juz zaflagowane osobno (skan bez OCR)
    best, scores = detect_language(full_text)
    if best != "polski" and scores[best] > scores.get("polski", 0):
        inne = ", ".join(f"{k}={v}" for k, v in sorted(scores.items(), key=lambda kv: -kv[1]))
        return (
            f"dokument prawdopodobnie NIE jest po polsku (heurystyka jezykowa) - "
            f"najwyzszy wynik: '{best}' (wyniki wzorcow: {inne})"
        )
    if scores["polski"] == 0 and sum(scores.values()) > 0:
        inne = ", ".join(f"{k}={v}" for k, v in sorted(scores.items(), key=lambda kv: -kv[1]))
        return (
            f"dokument prawdopodobnie NIE jest po polsku (heurystyka jezykowa) - "
            f"zero trafien wzorcow polskich (wyniki: {inne})"
        )
    return None


# --------------------------------------------------------------------------
# Porownanie nazwy produktu z karta (--karta)
# --------------------------------------------------------------------------

def normalize_for_match(s: str) -> str:
    s = _strip_diacritics(s)
    return s.lower()


def name_matches_karta(sds_nazwa: str, karta_text: str) -> bool:
    """True gdy wszystkie "znaczace" tokeny nazwy z SDS wystepuja gdziekolwiek
    w tresci karty (naglowek, wiersz SKU, opis wariantu itd.). To celowo tolerancyjne
    dopasowanie - karta i SDS niemal nigdy nie zapisuja nazwy identycznie znak-w-znak."""
    norm_karta = normalize_for_match(karta_text)
    tokens = [t for t in re.split(r'\s+', normalize_for_match(sds_nazwa)) if len(t) >= 2]
    if not tokens:
        return True
    return all(t in norm_karta for t in tokens)


# --------------------------------------------------------------------------
# Wczytanie pliku -> lista "stron" (kazda strona = lista linii)
# --------------------------------------------------------------------------

def load_pages(path: Path) -> list[list[str]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            import fitz  # PyMuPDF
        except ImportError as e:
            raise SystemExit(
                "Brak biblioteki PyMuPDF (fitz). Zainstaluj: pip install PyMuPDF"
            ) from e
        doc = fitz.open(str(path))
        pages = [p.get_text("text").split("\n") for p in doc]
        doc.close()
        return pages
    elif suffix in (".txt", ".md"):
        raw = path.read_text(encoding="utf-8", errors="replace")
        parts = PAGE_MARK_RE.split(raw)
        # re.split z pattern bez grup: usuwa separatory, zwraca kawalki miedzy nimi
        parts = [p for p in parts]
        if len(parts) > 1:
            return [p.split("\n") for p in parts]
        return [raw.split("\n")]
    else:
        raise SystemExit(f"Nieobslugiwane rozszerzenie pliku: {suffix} (oczekiwano .pdf lub .txt)")


# --------------------------------------------------------------------------
# Usuwanie powtarzanych stopek/naglowkow stron
# --------------------------------------------------------------------------

def collect_boilerplate(pages: list[list[str]]) -> set[str]:
    n = len(pages)
    if n < 2:
        return set()
    cnt: Counter[str] = Counter()
    for lines in pages:
        nonempty = [l.strip() for l in lines if l.strip()]
        zone = set(nonempty[:HEADER_ZONE]) | set(nonempty[-FOOTER_ZONE:])
        for s in zone:
            if len(s) >= MIN_BOILER_LEN:
                cnt[s] += 1
    threshold = max(2, (n + 1) // 2)
    boiler = set()
    for s, c in cnt.items():
        # UWAGA (2026-09-16): naglowki SEKCJA N (w tym "(Ciag dalszy)") NIE sa juz
        # wykluczone z usuwania - jesli identyczny naglowek powtarza sie w strefie
        # naglowka/stopki na wiekszosci stron (np. jako biezacy banner strony), to
        # boilerplate jak kazdy inny; usuniecie powtorzen nie zmienia przypisania
        # tresci do sekcji (naglowek i tak nigdy nie trafia do tresci - patrz
        # split_sections), a chroni przed przypadkowym ponownym "odpaleniem" tego
        # samego naglowka gdzie indziej w strefie naglowka/stopki kolejnych stron.
        if c >= threshold:
            boiler.add(s)
    return boiler


def clean_pages(pages: list[list[str]]) -> tuple[list[str], set[str]]:
    """Usuwa powtarzajace sie naglowki/stopki stron.

    WAZNE (2x):
    1) dopasowanie do zbioru `boiler` jest ograniczone do strefy naglowka/stopki KAZDEJ
       strony (pierwsze/ostatnie kilka niepustych linii), a nie do calego dokumentu -
       inaczej wartosc pola (np. nazwa handlowa powtorzona tez w tresci sekcji 1)
       zostalaby blednie skasowana wszedzie tam, gdzie sie pojawia.
    2) PIERWSZE wystapienie kazdej powtarzajacej sie linii jest zachowywane (nie usuwane) -
       tylko powtorzenia na kolejnych stronach sa kasowane. Niektore dokumenty (np. gdy
       caly banner z metadanymi - "Aktualizacja", "Numer wersji" - powtarza sie w naglowku
       KAZDEJ strony) maja te dane WYLACZNIE w tej powtarzanej strefie; zachowanie pierwszego
       wystapienia pozwala pozniej wyciagnac z niego metryke, a nie tylko usunac caly banner.
    """
    boiler = collect_boilerplate(pages)
    seen_once: set[str] = set()
    out: list[str] = []
    for lines in pages:
        idxs = [i for i, l in enumerate(lines) if l.strip()]
        zone_idxs = set(idxs[:HEADER_ZONE]) | set(idxs[-FOOTER_ZONE:] if idxs else [])
        for i, raw in enumerate(lines):
            s = raw.strip()
            if not s:
                out.append("")
                continue
            if i in zone_idxs and s in boiler:
                if s not in seen_once:
                    seen_once.add(s)
                else:
                    continue
            if any(p.match(s) for p in JUNK_LINE_PATTERNS):
                continue
            # usun fragment "(ciag dalszy ...)" wewnatrz linii, zachowaj reszte
            s2 = CONT_RE.sub("", raw).rstrip()
            out.append(s2)
    return out, boiler


def collapse_blanks(lines: list[str]) -> list[str]:
    out = []
    blank_run = 0
    for l in lines:
        if l.strip() == "":
            blank_run += 1
            if blank_run <= 1:
                out.append("")
        else:
            blank_run = 0
            out.append(l)
    # przytnij puste na poczatku/koncu
    while out and out[0].strip() == "":
        out.pop(0)
    while out and out[-1].strip() == "":
        out.pop()
    return out


# --------------------------------------------------------------------------
# Podzial na sekcje SEKCJA 1..16
# --------------------------------------------------------------------------

def split_sections(lines: list[str]) -> tuple[dict[int, list[str]], list[int]]:
    """UWAGA (2026-09-16, regresja SEKCJA 10/7.3): testowano tez wariant, w ktorym
    naglowek SEKCJA N z numerem NIZSZYM niz najwyzszy dotychczas napotkany jest
    odrzucany (twarde wymuszenie rosnacej kolejnosci) - empirycznie ten wariant NIE
    poprawia mapowania: na saiko-zid.txt (linie 639/641 w wersji po czyszczeniu, patrz
    REGRESJA-sds_pl_do_karty-sekcje-2026-09-16.md) tylko PRZESUWA blad - sekcja 9
    zaczyna zawierac prawdziwa tresc sekcji 10, a sekcja 10 przejmuje prawdziwa
    (kontynuowana) tresc sekcji 9, plus dosluchowuje sie do tresci literalny naglowek
    odrzuconej linii. Bez tego wariantu (ponizej) sekcja 10 wychodzi PUSTA i zostaje
    poprawnie zaflagowana (patrz build_flags) - uczciwszy wynik niz cichy zly przydzial.
    Prawdziwa przyczyna to nakladajace sie kolumny PDF (tresc sekcji drukowana PRZED
    jej wlasnym naglowkiem) - tego nie da sie naprawic samym porownaniem numerow
    sekcji w liniowym strumieniu tekstu; zostaje to uczciwie zaflagowane zamiast
    zgadywane. Numer sekcji NIE musi wiec byc rosnacy, zeby zostac zaakceptowany -
    kolejnosc napotkania jest tylko raportowana (patrz `order_found` i flaga "zla
    kolejnosc" w build_flags), nie wymuszana."""
    sections: dict[int, list[str]] = {i: [] for i in range(1, 17)}
    order_found: list[int] = []
    current: int | None = None
    implicit1_done = False

    for raw in lines:
        s = raw.strip()
        m = SEC_RE.match(s)
        if m:
            num = int(m.group(1))
            if 1 <= num <= 16:
                current = num
                if current not in order_found:
                    order_found.append(current)
                continue  # nie dodajemy samej linii naglowka jako tresci (duplikat z kolumny "Sekcja")
        if current is None:
            if not implicit1_done and SUB1_RE.match(s):
                current = 1
                implicit1_done = True
                order_found.append(1)
            else:
                continue
        sections[current].append(raw)

    return sections, order_found


def section_text(lines: list[str]) -> str:
    return "\n".join(collapse_blanks(lines)).strip()


# --------------------------------------------------------------------------
# Pola metryki (nazwa, kod, UFI, wersja, data)
# --------------------------------------------------------------------------

_PL_LETTERS = "A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ"

# Niektore SDS (np. sekcja 14 transport w formacie omnident/durr) wstawiaja miedzy
# etykieta pola a rzeczywista wartoscia dodatkowy podnaglowek wyliczajacy przepisy,
# np. "ADR, IMDG, IATA" albo goly "Klasa"/"Nalepka" - to trzeba pominac tak samo jak
# pusta linie czy sam dwukropek.
_FILLER_TOKENS = {"adr", "imdg", "iata", "adn", "rid", "klasa", "nalepka"}

# Niektore SDS (np. Durr) powtarzaja pod etykieta "14.3 Klasa(-y) zagrozenia w
# transporcie" osobny podnaglowek dla kazdego trybu transportu ("Transport ladowy
# (ADR/RID)", "Transport morski (IMDG)", "Transport lotniczy (ICAO-TI / IATA-DGR)")
# PRZED faktyczna wartoscia "Klasa(y): 3" - bez pominiecia tego podnaglowka
# extract_field bierze go za wartosc pola.
_FILLER_LINE_RE = re.compile(
    r'^transport\s+(l[ąa]dowy|morski|lotniczy|drogowy|kolejowy)\b', re.IGNORECASE,
)


def _is_filler_line(ln: str) -> bool:
    low = re.sub(r'^[\*\-·•]\s*', '', ln.strip()).rstrip(":").strip().lower()
    if not low:
        return False
    if _FILLER_LINE_RE.match(low):
        return True
    parts = [p.strip() for p in low.split(",")]
    # "Klasa(y)" / "Klasa (-y)" to ten sam filler co "klasa" - zdejmij koncowke
    # wyliczajaca liczbe mnoga przed porownaniem.
    norm_parts = [re.sub(r'\(-?y\)$', '', p).strip() for p in parts]
    return all(p in _FILLER_TOKENS for p in norm_parts)


def extract_field(lines: list[str], labels: list[str], validate: "re.Pattern|None" = None) -> tuple[str | None, str | None]:
    """Zwraca (wartosc, etykieta_zrodlowa) - pierwsza etykieta z listy priorytetowej,
    ktorej ktorekolwiek wystapienie przejdzie walidacje (jesli podana).

    Dziala na calym polaczonym tekscie (nie linia-po-linii), bo etykiety w PDF-ach
    czesto zawijaja sie na dwie linie (np. "Data" / "sporzadzenia/przegladu:").
    Etykieta moze wystapic wielokrotnie w dokumencie (np. "Wersja" jako nazwa wariantu
    produktu w sekcji 1 vs. wersja samej karty w metryce) - iterujemy wszystkie
    wystapienia i bierzemy pierwsze, ktore przejdzie walidacje.
    """
    full = "\n".join(lines)
    for label in labels:
        pat_txt = re.escape(label).replace(r"\ ", r"\s+")
        pat = re.compile(rf'(?<![{_PL_LETTERS}])' + pat_txt + r'\b', re.IGNORECASE)
        for m in pat.finditer(full):
            tail = full[m.end():m.end() + 400]
            # przejrzyj kolejne linie po etykiecie: pomin puste, "goly" dwukropek
            # i czysto-nawiasowe kwalifikatory (np. "(Aktualizacja)"), az do PIERWSZEJ
            # linii z realna trescia - to jest jedyny kandydat dla TEGO wystapienia etykiety.
            cand = None
            for cand_line in tail.split("\n")[:8]:
                ln = re.sub(r'^\s*:\s*', '', cand_line.strip()).strip()
                if not ln:
                    continue
                if re.fullmatch(r'\([^)]{0,60}\)\s*:?', ln):
                    continue
                if _is_filler_line(ln):
                    continue
                cand = ln
                break
            if cand is None:
                continue
            # PDF-y czesto zrzucaja kilka pol w jednej fizycznej linii, oddzielonych
            # dlugim odstepem (kolumny) - np. "11.04.2019            Aktualizacja: ...".
            # Ale dlugi odstep bywa tez czystym wyrownaniem liczba+jednostka (np.
            # "23     °C") - tu NIE wolno przycinac. Tniemy tylko wtedy, gdy po
            # odstepie widac kolejna etykiete (fragment tekstu zakonczony dwukropkiem).
            gap = re.search(r'\s{3,}', cand)
            if gap and re.match(r'^[^\n:]{1,40}:', cand[gap.end():]):
                val = cand[:gap.start()].strip()
            else:
                val = re.sub(r'\s{2,}', ' ', cand).strip()
            if not val:
                continue
            if validate and not validate.search(val):
                # ta wartosc nie przechodzi walidacji - probujemy KOLEJNE wystapienie
                # tej samej etykiety (nie kolejna linie w tym samym miejscu, bo to
                # prowadzi do przypadkowego dopasowania odleglej tresci)
                continue
            return val, label
    return None, None


def extract_metryka(all_lines: list[str]) -> dict[str, str]:
    nazwa, _ = extract_field(all_lines, [
        "Nazwa handlowa", "Nazwa wyrobu", "Nazwa produktu", "Identyfikator produktu",
    ])
    kod, kod_label = extract_field(all_lines, [
        "Kod produktu", "Numer artykulu", "Numer artykułu", "Numer produktu",
        "Numer wyrobu", "Numer rejestracji produktu",
    ])
    ufi, _ = extract_field(all_lines, ["UFI"], validate=UFI_RE)
    if not ufi:
        full = "\n".join(all_lines)
        m = UFI_RE.search(full)
        if m:
            ufi = m.group(0)
    wersja, _ = extract_field(all_lines, ["Wersja", "Numer wersji"], validate=re.compile(r'^\(?\d'))
    data_akt, data_label = extract_field(all_lines, [
        "Aktualizacja", "Data aktualizacji", "Data sporzadzenia/przegladu",
        "Data sporządzenia/przeglądu", "Data sporzadzenia", "Data sporządzenia",
    ], validate=DATE_RE)

    out = {
        "Nazwa handlowa": nazwa or "[BRAK]",
        "Kod / nr artykulu": (kod or "[BRAK]") + (f" (etykieta zrodlowa: {kod_label})" if kod_label and kod_label not in ("Kod produktu", "Numer artykulu", "Numer artykułu") else ""),
        "UFI": ufi or "[BRAK]",
        "Wersja": wersja or "[BRAK]",
        "Data aktualizacji": (data_akt or "[BRAK]") + (f" (etykieta zrodlowa: {data_label})" if data_label and data_label not in ("Aktualizacja", "Data aktualizacji") else ""),
    }
    return out


# --------------------------------------------------------------------------
# Wartosci kluczowe do weryfikacji
# --------------------------------------------------------------------------

_COMPOSITION_LABEL_ONLY_RE = re.compile(
    r'^(nr\.?\s*)?(cas|we|reach|indeksu|numer indeksu|numer cas)\s*:?$', re.IGNORECASE
)

# Linia zlozona WYLACZNIE z etykiety identyfikatora (CAS/WE/EC/EINECS/RTECS/REACH/
# numer indeksowy/numer rejestracji), z lub bez "Nr"/"Numer" na poczatku i dwukropka
# na koncu - np. "CAS:", "EC:", "Numer indeksowy:", "Reg.nr.:". Szersza niz
# _COMPOSITION_LABEL_ONLY_RE (ktora nie lapala np. "Numer WE:" czy "Numer indeksowy:").
_IDENT_CORE = r'(cas|we|ec|einecs|rtecs|reach|reg\.?\s*nr\.?|index(?:u|owy)?|indeksu|indeksowy|rejestracji(?:\s+reach)?)'
_IDENT_LABEL_ONLY_RE = re.compile(
    rf'^(?:nr\.?\s*|numer\s*)?{_IDENT_CORE}\s*:?$', re.IGNORECASE,
)
# To samo, ale dopuszcza dowolna wartosc PO etykiecie na tej samej linii (np. "CAS: 64-17-5",
# "EINECS: 200-578-6", "Reg.nr.: 01-...") - do pomijania calych linii "etykieta: wartosc"
# przy szukaniu nazwy DO PRZODU (patrz _forward_scan_name).
_IDENT_LABEL_START_RE = re.compile(
    rf'^(?:nr\.?\s*|numer\s*)?{_IDENT_CORE}\b', re.IGNORECASE,
)
# Czysta wartosc identyfikatora bez etykiety w tej samej linii - numer WE/EINECS
# ("200-578-6"), numer indeksowy UE ("603-002-00-5"), numer rejestracji REACH
# ("01-2119457610-43-XXXX" w calosci, albo w 2 liniach po zawinieciu: "01-2119457610-43-"
# i "XXXX" osobno). Uzywane tylko przy szukaniu nazwy DO PRZODU, po samym numerze CAS.
_IDENT_VALUE_ONLY_RE = re.compile(
    r'^(?:\d{2,7}-\d{2}-\d'                        # CAS-owy ksztalt
    r'|\d{3}-\d{3}-\d{2}-\d'                        # numer indeksowy UE, np. "603-002-00-5"
    r'|\d{3}-\d{3}-\d(?:-\d{1,3})?'                 # numer WE/EINECS, np. "200-578-6"
    r'|\d{2}-\d{6,12}(?:-\d{1,3})?-?(?:X{2,4})?'    # numer rejestracji REACH, calosc lub bez koncowki XXXX
    r'|X{3,4}'                                      # sama kontynuacja "XXXX" po zawinieciu REACH na 2 linie
    r')[.,]?$',
    re.IGNORECASE,
)
# Poczatek zdania klasyfikacji GHS/CLP skladnika (np. "Flam. Liq. 2: H225", "Rozporzadzenie
# 1272/2008", "Specyficzne stezenia graniczne") - jesli szukanie nazwy DO PRZODU trafi na
# taka linie zanim znajdzie realna nazwe, przerywamy (nazwy tam juz nie ma, dalej jest sam
# % udzialu skladnika).
_CLASSIFICATION_START_RE = re.compile(
    r'^(rozporz|klasyfikacj|flam\.?\b|eye\b|skin\b|stot\b|acute\b|carc\.?\b|muta\.?\b|repr\.?\b|'
    r'aquatic\b|asp\.?\b|ghs0|specyficzn\w*\s+st[eę]żeni|swoist\w*\s+st[eę]żeni)',
    re.IGNORECASE,
)
# Etykieta doklejona na KONCU tej samej linii co nazwa skladnika (format Durr/Alpro,
# np. "Nitrylotrioctan trisodu Numer CAS:" albo "1-PROPANOL ; Nr REACH : ... ; Nr CAS : ")
# - usuwamy ja, zeby zostala sama nazwa.
_TRAILING_LABEL_RE = re.compile(
    rf'\s*;?\s*(?:nr\.?\s*|numer\s*)?{_IDENT_CORE}\s*:?\s*$', re.IGNORECASE,
)
# Odnosniki/przypisy doklejone do nazwy skladnika w niektorych SDS - albo jako
# unikodowy indeks gorny ("etanol⁽¹⁾"), albo jako zwykly ASCII "etanol1)" (Medilab) -
# nie sa czescia nazwy chemicznej.
_FOOTNOTE_SUFFIX_RE = re.compile(r'(?:[\s⁽⁾⁰¹²³⁴⁵⁶⁷⁸⁹]|\(\d{1,2}\)|\d{1,2}\))+$')

# Linie ktore w praktyce NIGDY nie sa nazwa skladnika, mimo ze nie pasuja do zadnej
# etykiety identyfikatora - naglowki kolumn tabeli skladu ("Stężenie", "Identyfikacja"),
# odpowiedzi tabelaryczne z dalszych podsekcji §3 (toksykologia: "Szczur", "Nie dotyczy")
# ktore CAS_RE tez znajduje (ten sam CAS bywa POWTORZONY w §3.2 "Specyficzne stezenia
# graniczne" i w tabeli toksykologii ostrej - patrz dedup w extract_composition).
# Normalizacja: bez polskich znakow diakrytycznych, malymi literami, bez koncowego
# dwukropka - patrz _looks_like_junk_line.
_NAME_BLOCKLIST = {
    "zadne", "nie dotyczy", "tak", "nie", "brak", "szczur", "mysz", "krolik", "swinka morska",
    "identyfikacja", "nazwa chemiczna", "nazwa chemiczna/klasyfikacja", "stezenie", "% wagowy",
    "klasyfikacja", "rodzaj", "ld50 ustna", "ld50 skorna", "lc50 wdychanie oparow",
    "informacje dodatkowe", "inne informacje", "specyficzne stezenie graniczne",
    "specyficzne stezenia graniczne", "udzial wagowy", "zawartosc", "ostra toksycznosc",
    "skladniki niebezpieczne", "skladniki", "mieszaniny", "substancje", "opis chemiczny", "opis",
}


def _strip_leading_bullet(s: str) -> str:
    return re.sub(r'^[\*\-·•]\s*', '', s).strip()


def _looks_like_junk_line(s: str) -> bool:
    s2 = _strip_leading_bullet(s).rstrip(":").strip()
    if not s2:
        return True
    if _IDENT_LABEL_ONLY_RE.match(s2 + ":"):
        return True
    if PERC_RE.fullmatch(s2):
        # linia to WYLACZNIE wartosc procentowa (np. "43%", zawartosc POPRZEDNIEGO
        # skladnika stojaca tuz nad etykieta "CAS:" kolejnego skladnika w ukladzie
        # kolumnowym - patrz przypadek testowy) - nigdy nie jest nazwa.
        return True
    return normalize_for_match(s2) in _NAME_BLOCKLIST


def _clean_name_candidate(raw: str) -> str | None:
    """Sprowadza surowa linie-kandydata do samej nazwy skladnika, albo zwraca None
    jesli linia okazuje sie etykieta/naglowkiem/wartoscia bez nazwy."""
    s = _strip_leading_bullet(raw)
    if not s:
        return None
    # Format "NAZWA ; Nr REACH : ... ; Nr WE : ... ; Nr CAS : " (Durr) - nazwa to
    # pierwszy czlon przed pierwszym ';'.
    if ';' in s:
        first = s.split(';')[0].strip()
        if first and not _looks_like_junk_line(first):
            s = first
    # Format "NAZWA Numer CAS:" / "NAZWA Nr WE:" (Alpro, gdy nazwa i etykieta
    # nastepnego pola siedza w jednej linii) - zdejmij doklejona etykiete z konca.
    stripped = _TRAILING_LABEL_RE.sub('', s).strip()
    if stripped:
        s = stripped
    s = _FOOTNOTE_SUFFIX_RE.sub('', s).strip()
    if not s or _looks_like_junk_line(s):
        return None
    return s


def _forward_scan_name(sec3_text: str, pos: int) -> str:
    """Niektore SDS (Medisept, Omnident) drukuja tabele skladu kolumnowo: najpierw
    etykiety/wartosci identyfikatorow (CAS/WE/Index/REACH), a dopiero PO nich nazwa
    chemiczna skladnika - patrz test na dwóch kartach testowych. Szukamy wtedy nazwy
    DO PRZODU od numeru CAS, pomijajac kolejne linie identyfikatorow, az do pierwszej
    linii ktora wyglada na realna nazwe (nie jest etykieta, czystym kodem ani juz
    poczatkiem klasyfikacji GHS/CLP)."""
    tail = sec3_text[pos:pos + 400]
    for raw in tail.split("\n")[:12]:
        s = _strip_leading_bullet(raw)
        if not s:
            continue
        if _IDENT_LABEL_START_RE.match(s):
            continue
        if _IDENT_VALUE_ONLY_RE.match(s):
            continue
        if _CLASSIFICATION_START_RE.match(s) or H_CODE_RE.search(s) or '%' in s:
            break
        cand = _clean_name_candidate(s)
        return cand or ""
    return ""


def _guess_component_name(sec3_text: str, cas_match: "re.Match") -> str:
    """Zgaduje nazwe skladnika dla danego dopasowania CAS w sekcji 3. Obsluguje 3
    ukladu spotykane w praktyce:
    - nazwa PRZED CAS w tej samej linii, oddzielona ';' (Durr): "1-PROPANOL ; Nr REACH..."
    - nazwa na WLASNEJ linii bezposrednio przed linia z etykieta CAS (Alpro): "2-Aminoetanol\\nNumer CAS: ..."
      (w tym warianty, gdzie etykieta kolejnego pola jest doklejona do nazwy w tej samej linii)
    - nazwa PO calym bloku identyfikatorow CAS/WE/Index/REACH (Medisept, Omnident) - patrz _forward_scan_name.
    """
    line_start = sec3_text.rfind('\n', 0, cas_match.start()) + 1
    prefix = sec3_text[line_start:cas_match.start()]
    cand = _clean_name_candidate(prefix)
    if cand:
        return cand
    if line_start > 0:
        prev_line_end = line_start - 1
        prev_line_start = sec3_text.rfind('\n', 0, prev_line_end) + 1
        prev_line = sec3_text[prev_line_start:prev_line_end]
        cand = _clean_name_candidate(prev_line)
        if cand:
            return cand
    return _forward_scan_name(sec3_text, cas_match.end())


# Etykieta faktycznego udzialu skladnika w mieszaninie (w odroznieniu od progow
# klasyfikacji GHS / specyficznych stezen granicznych, ktore tez zawieraja %
# w tym samym bloku, np. "Specyficzne stezenia graniczne: Eye Irrit. 2 ; H319: C >= 50 %").
_CONC_LABEL_RE = re.compile(
    r'(udzia[łl]\s+wagow\w*|zawarto[śs][ćc]|st[eę]żeni\w*)\b', re.IGNORECASE
)

# Marker "specyficznego/swoistego stezenia granicznego" (SCL) - prog klasyfikacji GHS
# przypisany do konkretnego zwrotu H (np. "Eye Irrit. 2 H319: C >= 50 %"), NIE jest to
# udzial skladnika w mieszaninie, mimo ze tez wyraza sie w %. Odmiana koncowki bywa
# rozna ("stezenia"/"stezenie"/"stezeniowy"), stad koncowka otwarta \w*.
# UWAGA: marker NIE moze konsumowac operatora porownania (>=/<=/</>/≥/≤) - PERC_RE
# zaczyna dopasowanie WLASNIE od tego operatora, wiec gdyby marker go polkngal,
# marker_m.end() wypadlby ZA poczatkiem dopasowania % (nakladanie sie zakresow) i
# wyszukiwanie "pierwszego % po markerze" przypadkowo przeskoczyloby na KOLEJNY %.
_SCL_MARKER_RE = re.compile(
    r'(specyficzn\w*|swoist\w*)\s+st[eę]żeni\w*\s+graniczn\w*|st[eę]żeni\w*\s+graniczn\w*'
    r'|H\d{3}[a-zA-Z]?\s*:\s*C\b',
    re.IGNORECASE,
)


def extract_composition(sec3_text: str) -> list[dict]:
    entries: list[dict] = []
    seen_cas: dict[str, int] = {}  # cas -> indeks w entries, dla deduplikacji
    matches = list(CAS_RE.finditer(sec3_text))
    for i, m in enumerate(matches):
        cas = m.group(0)
        name = _guess_component_name(sec3_text, m)
        end_ctx = matches[i + 1].start() if i + 1 < len(matches) else min(len(sec3_text), m.end() + 400)
        val_ctx = sec3_text[m.end():end_ctx]
        # W bloku miedzy dwoma CAS-ami moze wystapic wiecej niz jeden %: realny udzial
        # skladnika w mieszaninie ORAZ specyficzne stezenia graniczne klasyfikacji GHS
        # (np. "Specyficzne stezenia graniczne: Eye Irrit. 2 ; H319: C >= 50 %"), ktore
        # NIE sa udzialem skladnika. Kolejnosc tych dwoch bywa rozna miedzy dokumentami,
        # wiec zamiast zgadywac po pozycji (pierwszy/ostatni), najpierw ODRZUCAMY %
        # ktore siedza tuz obok markera SCL (progu klasyfikacji), a z pozostalych
        # bierzemy ten powiazany z etykieta "Udzial wagowy / Zawartosc / Stezenie",
        # albo pierwszy pozostaly - to jest realny % udzialu skladnika.
        # Wykluczamy TYLKO pierwszy % wystepujacy PO kazdym markerze SCL (to jest %
        # tego konkretnego progu klasyfikacji) - kolejny % w tym samym bloku (np. realny
        # udzial skladnika wypisany zaraz PO wzmiance o progu SCL) NIE jest wykluczany.
        pcts = list(PERC_RE.finditer(val_ctx))
        excluded_starts = set()
        for marker_m in _SCL_MARKER_RE.finditer(val_ctx):
            for pm in pcts:
                if pm.start() >= marker_m.end():
                    excluded_starts.add(pm.start())
                    break
        real_pcts = [pm for pm in pcts if pm.start() not in excluded_starts]
        candidates = real_pcts if real_pcts else pcts

        pct = None
        label_m = _CONC_LABEL_RE.search(val_ctx)
        if label_m:
            after_label = [pm for pm in candidates if pm.start() >= label_m.start()]
            if after_label:
                pct = after_label[0].group(0).strip()
        if pct is None and candidates:
            pct = candidates[0].group(0).strip()

        entry = {
            "cas": cas,
            "nazwa_szac": name,
            "procent": pct,
            "wiele_wartosci_procent": len(pcts) > 1,
        }
        if cas in seen_cas:
            # Ten sam CAS pojawia sie ponownie w SEKCJI 3 - w praktyce to NIE jest
            # drugi skladnik, tylko powtorne przywolanie tego samego skladnika w
            # podsekcji "Specyficzne stezenia graniczne" albo w tabeli toksykologii
            # ostrej (np. "CAS: 64-17-5 ... LD50 skorna ... Nie dotyczy"), gdzie nie
            # ma jego realnego % udzialu w mieszaninie, tylko dane inne (progi GHS,
            # dawki toksyczne). Dodanie tego jako osobnego wpisu produkowalo w
            # praniu duplikaty z bledna nazwa ("Szczur", "Nie dotyczy", nazwa naglowka
            # kolumny) i pustym %. Zamiast tego: NIE dodajemy duplikatu, tylko
            # ewentualnie donadpisujemy brakujacy % w juz zapisanym (pierwszym) wpisie,
            # jesli akurat to powtorzenie go podaje.
            prev = entries[seen_cas[cas]]
            if prev["procent"] is None and entry["procent"] is not None:
                prev["procent"] = entry["procent"]
                prev["wiele_wartosci_procent"] = prev.get("wiele_wartosci_procent") or entry["wiele_wartosci_procent"]
            continue
        seen_cas[cas] = len(entries)
        entries.append(entry)
    return entries


def extract_kluczowe(all_lines: list[str], sections: dict[int, list[str]]) -> dict:
    full_text = "\n".join(all_lines)
    sec2 = section_text(sections.get(2, []))
    sec3 = section_text(sections.get(3, []))
    sec9 = section_text(sections.get(9, []))
    sec14 = section_text(sections.get(14, []))

    haslo_labels = ["Hasła ostrzegawcze", "Hasło ostrzegawcze", "Hasla ostrzegawcze", "Haslo ostrzegawcze"]
    haslo, _ = extract_field(sec2.split("\n"), haslo_labels)
    if not haslo:
        haslo, _ = extract_field(all_lines, haslo_labels)
    if not haslo:
        # Niektore SDS (np. Medisept) nie maja w §2.2 jawnej etykiety "Hasło
        # ostrzegawcze:" - haslo (jedno z dwoch oficjalnych slow sygnalowych CLP)
        # stoi samo w linii, zaraz po "Rozporzadzenie nr 1272/2008 (CLP):". Bez tego
        # fallbacku pole wychodzi [BRAK], mimo ze wartosc jest wprost w tekscie.
        for cand_line in sec2.split("\n"):
            cs = cand_line.strip()
            if cs in ("Uwaga", "Niebezpieczeństwo", "Niebezpieczenstwo"):
                haslo = cs
                break

    ghs = sorted(set(GHS_RE.findall(sec2 or full_text)))

    # Zwroty H/P MIESZANINY biora sie WYLACZNIE z §2.1/§2.2 (klasyfikacja i elementy
    # oznakowania samej mieszaniny) - NIE z §3 (klasyfikacja poszczegolnych skladnikow,
    # ktora zwykle jest szersza/inna) ani z §16 (tam bywaja spis wszystkich H uzytych
    # w calej karcie, do skladnikow wlacznie). Mieszanie tych zrodel dawalo np. dla
    # jednej z kart testowych H319+H226 (poprawne) rozszerzone o H225+H336 skladnikow (blad
    # znaleziony w kontroli orkestratora 2026-09-15).
    h_codes = list(dict.fromkeys(H_CODE_RE.findall(sec2 or full_text)))
    p_codes = list(dict.fromkeys(P_CODE_RE.findall(sec2 or full_text)))
    # H skladnikow - osobne pole, tylko do wglądu/porownania z §3.2 (klasyfikacja
    # KAZDEGO skladnika, nie mieszaniny) - nigdy nie mieszane z "zwroty_h" powyzej.
    h_skladnikow = list(dict.fromkeys(H_CODE_RE.findall(sec3))) if sec3 else []

    temp_zaplonu, _ = extract_field(sec9.split("\n"), ["Temperatura zaplonu", "Temperatura zapłonu"])

    un, _ = extract_field(sec14.split("\n"), [
        "14.1 Numer UN lub numer identyfikacyjny ID", "Numer UN lub numer identyfikacyjny ID", "Numer UN",
    ])
    klasa_transp, _ = extract_field(sec14.split("\n"), [
        "14.3 Klasa(-y) zagrozenia w transporcie", "Klasa(-y) zagrozenia w transporcie",
        "Klasa(-y) zagrożenia w transporcie", "Klasa zagrozenia w transporcie",
    ])

    return {
        "skladniki": extract_composition(sec3),
        "haslo_ostrzegawcze": haslo or "[BRAK]",
        "piktogramy_ghs": ghs,
        "zwroty_h": h_codes,
        "zwroty_h_skladnikow": h_skladnikow,
        "zwroty_p": p_codes,
        "temp_zaplonu": temp_zaplonu or "[BRAK]",
        "numer_un": un or "[BRAK]",
        "klasa_transportowa": klasa_transp or "[BRAK]",
    }


# --------------------------------------------------------------------------
# Flagi jakosci
# --------------------------------------------------------------------------

def build_flags(sec_texts: dict[int, str], order_found: list[int], kluczowe: dict, total_chars: int,
                 full_text: str = "", karta_path: "Path|None" = None, karta_flag: str | None = None) -> list[str]:
    flags = []
    if total_chars < 800:
        flags.append(
            f"UWAGA: bardzo malo tekstu w calym dokumencie ({total_chars} znakow) - "
            "podejrzenie skanu bez warstwy tekstowej (brak OCR)."
        )
    lang_flag = language_flag(full_text)
    if lang_flag:
        flags.append(lang_flag)
    if order_found != sorted(order_found):
        flags.append(
            f"sekcje w zlej kolejnosci w dokumencie (kolejnosc napotkania: {order_found}, "
            "oczekiwano rosnaco 1..16)"
        )
    if karta_flag:
        flags.append(karta_flag)
    for n in range(1, 17):
        txt = sec_texts.get(n, "")
        if n not in order_found:
            flags.append(f"brak sekcji {n} (naglowek SEKCJA {n} nie znaleziony w dokumencie)")
            continue
        if txt.strip() == "":
            flags.append(f"sekcja {n} pusta (naglowek znaleziony, tresci brak)")
        elif len(txt.strip()) < 20:
            flags.append(f"sekcja {n} krotsza niz 20 znakow: {txt.strip()!r}")

    if not kluczowe["piktogramy_ghs"] and kluczowe["haslo_ostrzegawcze"] not in ("[BRAK]",):
        flags.append(
            "piktogramy GHS: brak kodu GHS0x w warstwie tekstowej sekcji 2 - "
            "piktogramy sa czesto tylko grafika bez alt-tekstu w PDF - sprawdz wizualnie (render strony)"
        )

    if kluczowe["skladniki"]:
        for e in kluczowe["skladniki"]:
            if e["procent"] is None:
                flags.append(
                    f"podejrzenie rozjechanej tabeli w sekcji 3: CAS {e['cas']} bez wykrytego %"
                )
            elif e.get("wiele_wartosci_procent"):
                flags.append(
                    f"sekcja 3: CAS {e['cas']} ma kilka wartosci % w poblizu w tekscie "
                    f"(prawdopodobnie % udzialu obok specyficznych stezen granicznych GHS) - "
                    f"wzieto wartosc przy etykiecie udzialu/stezenia jesli znaleziona, inaczej pierwsza "
                    f"({e['procent']}), zweryfikuj w PDF"
                )
    return flags


# --------------------------------------------------------------------------
# Markdown output
# --------------------------------------------------------------------------

def md_escape_cell(text: str) -> str:
    text = text.replace("|", "\\|")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\n", "<br>")
    return text


def render_markdown(path: Path, metryka: dict, sec_texts: dict[int, str], order_found: list[int],
                     kluczowe: dict, flags: list[str], boiler: set[str]) -> str:
    lines = []
    lines.append(f"# SDS PL - {path.name}")
    lines.append("")
    lines.append("## Metryka")
    for k, v in metryka.items():
        lines.append(f"- **{k}:** {v}")
    lines.append("")
    lines.append("## Sekcje SDS (tresc doslowna)")
    lines.append("")
    lines.append("| Sekcja | Tresc doslowna |")
    lines.append("|---|---|")
    for n in range(1, 17):
        title = SECTION_TITLES_PL[n]
        label = f"SEKCJA {n}. {title}"
        txt = sec_texts.get(n, "")
        if n not in order_found:
            cell = "*(brak sekcji w dokumencie)*"
        elif txt.strip() == "":
            cell = "*(sekcja pusta)*"
        else:
            cell = md_escape_cell(txt)
        lines.append(f"| {label} | {cell} |")
    lines.append("")
    lines.append("## Wartosci kluczowe do sprawdzenia przez sedziego")
    lines.append("")
    if kluczowe["skladniki"]:
        lines.append("**Skladniki (CAS / % wg sekcji 3):**")
        for e in kluczowe["skladniki"]:
            pct = e["procent"] if e["procent"] else "[BRAK % - sprawdz PDF]"
            nazwa = e["nazwa_szac"] or "[nazwa niepewna]"
            lines.append(f"- {nazwa} — CAS {e['cas']} — {pct}")
    else:
        lines.append("- Skladniki (CAS/%): brak wykrytych wpisow CAS w sekcji 3.")
    lines.append(f"- Haslo ostrzegawcze: {kluczowe['haslo_ostrzegawcze']}")
    lines.append(f"- Piktogramy GHS: {', '.join(kluczowe['piktogramy_ghs']) if kluczowe['piktogramy_ghs'] else '[BRAK]'}")
    lines.append(f"- Zwroty H (mieszaniny, §2.1/§2.2): {', '.join(kluczowe['zwroty_h']) if kluczowe['zwroty_h'] else '[BRAK]'}")
    lines.append(f"- H skladnikow (§3.2, informacyjnie - NIE mylic z H mieszaniny powyzej): {', '.join(kluczowe['zwroty_h_skladnikow']) if kluczowe['zwroty_h_skladnikow'] else '[BRAK]'}")
    lines.append(f"- Zwroty P: {', '.join(kluczowe['zwroty_p']) if kluczowe['zwroty_p'] else '[BRAK]'}")
    lines.append(f"- Temperatura zaplonu: {kluczowe['temp_zaplonu']}")
    lines.append(f"- Numer UN: {kluczowe['numer_un']}")
    lines.append(f"- Klasa transportowa: {kluczowe['klasa_transportowa']}")
    lines.append("")
    lines.append("## FLAGI")
    lines.append("")
    if flags:
        for f in flags:
            lines.append(f"- {f}")
    else:
        lines.append("- brak flag - wszystkie sekcje 1-16 znalezione i niepuste (>=20 znakow)")
    lines.append("")
    lines.append(f"*(usunieto {len(boiler)} unikalnych linii powtarzajacego sie naglowka/stopki strony)*")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Ekstrakcja polskiej karty charakterystyki (SDS) do markdown.")
    ap.add_argument("plik", help="Sciezka do pliku SDS PL (.pdf lub .txt)")
    ap.add_argument("--karta", help="Sciezka do karty produktu .md - sprawdza rozjazd nazwy produktu SDS vs karta")
    ap.add_argument("--wyjscie", help="Sciezka pliku wyjsciowego .md (domyslnie: stdout)")
    args = ap.parse_args()

    path = Path(args.plik)
    if not path.exists():
        print(f"BLAD: plik nie istnieje: {path}", file=sys.stderr)
        sys.exit(1)

    pages = load_pages(path)
    cleaned, boiler = clean_pages(pages)
    sections, order_found = split_sections(cleaned)
    sec_texts = {n: section_text(sections.get(n, [])) for n in range(1, 17)}

    metryka = extract_metryka(cleaned)
    kluczowe = extract_kluczowe(cleaned, sections)
    total_chars = sum(len(t) for t in sec_texts.values())
    full_text = "\n".join(cleaned)

    karta_flag = None
    if args.karta:
        karta_path = Path(args.karta)
        if not karta_path.exists():
            karta_flag = f"BLAD: podana karta nie istnieje: {karta_path} (porownanie nazwy pominiete)"
        else:
            karta_text = karta_path.read_text(encoding="utf-8", errors="replace")
            sds_nazwa = metryka.get("Nazwa handlowa", "[BRAK]")
            if sds_nazwa and sds_nazwa != "[BRAK]" and not name_matches_karta(sds_nazwa, karta_text):
                karta_flag = (
                    f"rozjazd nazwy produktu: SDS podaje '{sds_nazwa}', "
                    f"nie znaleziono (w calosci, dopasowanie tokenowe) w karcie {karta_path.name}"
                )

    flags = build_flags(sec_texts, order_found, kluczowe, total_chars, full_text=full_text, karta_flag=karta_flag)

    md = render_markdown(path, metryka, sec_texts, order_found, kluczowe, flags, boiler)

    if args.wyjscie:
        out_path = Path(args.wyjscie)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md, encoding="utf-8")
        print(f"Zapisano: {out_path}")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(md)


if __name__ == "__main__":
    main()
