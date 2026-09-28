#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
karta_cytaty_zrodlo.py — sprawdza, czy cytat w karcie faktow stoi doslownie
w dokumencie, na ktory karta sie powoluje.

Uzycie:
    python karta_cytaty_zrodlo.py <karta.md> [...] [--dokumenty <folder marki>]

Domyslny folder dokumentow bierze sie z naglowka tabeli §3
("Plik lokalny (`dokumenty/<marka>/`)") wzgledem karty:
    .../<kategoria>/produkty/<karta>.md  ->  .../<kategoria>/dokumenty/<marka>/

Statusy per cytat:
    ZGODNY        — znaleziony doslownie (po normalizacji) we wskazanym dokumencie
    ROZJAZD       — znaleziony w innym brzmieniu albo w innym dokumencie niz wskazany
    BRAK_W_PLIKU  — dokument istnieje, cytatu w nim nie ma
    BRAK_PLIKU    — plik nie istnieje albo jest pusty (0 bajtow)
    TLUMACZENIE   — fragment po "(tlum.: ...)" — nie sprawdzamy w zrodle
    POMINIETO     — za krotki, sam symbol, kod CLP, REF, brak wskazania dokumentu,
                    dokument bez warstwy tekstu (render/obrazek)

Exit 1 przy ROZJAZD / BRAK_W_PLIKU / BRAK_PLIKU.
Skrypt tylko czyta karty — niczego nie zapisuje.
"""

from __future__ import annotations

import argparse
import difflib
from fnmatch import fnmatch
import html as htmllib
import os
import re
import sys
import unicodedata
from pathlib import Path
import konfig  # profil projektu: tokeny naszego serwisu, jezyk rynku (weryfikacja.json)

# ---------------------------------------------------------------- normalizacja

_TRANS = {
    0x00A0: " ", 0x2007: " ", 0x2008: " ", 0x2009: " ", 0x200A: " ",
    0x202F: " ", 0x2028: " ", 0x2029: " ", 0x3000: " ", 0x0009: " ",
    0x00AD: "", 0x200B: "", 0x200C: "", 0x200D: "", 0xFEFF: "",
    0x2010: "-", 0x2011: "-", 0x2012: "-", 0x2013: "-", 0x2014: "-",
    0x2015: "-", 0x2212: "-", 0x00B7: "-",
    0x201E: '"', 0x201C: '"', 0x201D: '"', 0x201F: '"', 0x201A: "'",
    0x00AB: '"', 0x00BB: '"', 0x2018: "'", 0x2019: "'", 0x2032: "'",
    0x2033: '"', 0x00B4: "'", 0x0060: "'",
    0x2044: "/", 0x2215: "/",
    0x00B2: "2", 0x00B3: "3", 0x00B9: "1",
    0x2070: "0", 0x2074: "4", 0x2075: "5", 0x2076: "6", 0x2077: "7",
    0x2078: "8", 0x2079: "9",
}

#  granice dopasowania: pominiecia „[...]” i wtracenia redakcyjne w nawiasie kwadratowym
_OMISSION_RE = re.compile(r"\[[^\]]{0,60}\]|…|\.\.\.")
_ELLIPSIS_ONLY = re.compile(r"^[\s.…]*$")


#  ligatury typograficzne z PDF ("classiﬁcation" vs "classification")
_LIG = {
    0xFB00: "ff", 0xFB01: "fi", 0xFB02: "fl", 0xFB03: "ffi", 0xFB04: "ffl",
    0xFB05: "st", 0xFB06: "st",
}


def norm_text(s: str) -> str:
    """Normalizacja tekstu do porownania (bez mapy pozycji)."""
    out = []
    prev_space = True
    for ch in s:
        o = ord(ch)
        c = _LIG.get(o) or _TRANS.get(o, ch)
        if not c:
            continue
        if c.isspace():
            if prev_space:
                continue
            out.append(" ")
            prev_space = True
        else:
            out.append(c.lower())
            prev_space = False
    return "".join(out).strip()


def norm_with_map(s: str, unit_of_line=True):
    """Jak norm_text, ale zwraca tez liste numerow wiersza/strony per znak."""
    out = []
    units = []
    unit = 1
    prev_space = True
    for ch in s:
        if ch == "\n":
            unit += 1
        if ch == "\f":
            unit += 1
        o = ord(ch)
        c = _LIG.get(o) or _TRANS.get(o, ch)
        if not c:
            continue
        if c.isspace():
            if prev_space:
                continue
            out.append(" ")
            units.append(unit)
            prev_space = True
        else:
            low = c.lower()
            #  ligatura rozwija sie na kilka znakow — kazdy dostaje ten sam wiersz
            for k in low:
                out.append(k)
                units.append(unit)
            prev_space = False
    return "".join(out), units


def dehyphenate(s: str) -> str:
    """Skleja miekkie lamania: 'opa- trunek' -> 'opatrunek'."""
    return re.sub(r"(\w)- (\w)", r"\1\2", s)


# ---------------------------------------------------------------- wczytywanie dokumentow

_TAG_RE = re.compile(r"(?is)<(script|style)[^>]*>.*?</\1>")
_ANY_TAG = re.compile(r"(?s)<[^>]+>")

TEXT_EXT = {".txt", ".md"}
HTML_EXT = {".html", ".htm"}
PDF_EXT = {".pdf"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".svg"}


def read_txt(p: Path) -> str:
    raw = p.read_bytes()
    for enc in ("utf-8", "cp1250", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def read_txt_doc(p: Path) -> str:
    """Tekst zrzucony z HTML bywa z encjami (&gt;, &amp;) — rozwijamy je."""
    t = read_txt(p)
    if "&" in t:
        t = htmllib.unescape(t)
    return t


def read_html(p: Path) -> str:
    t = read_txt(p)
    t = _TAG_RE.sub(" ", t)
    t = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</tr>|</h[1-6]>", "\n", t)
    t = _ANY_TAG.sub(" ", t)
    return htmllib.unescape(t)


def read_pdf(p: Path) -> str:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return ""
    try:
        doc = fitz.open(str(p))
    except Exception:
        return ""
    parts = []
    for page in doc:
        try:
            parts.append(page.get_text("text"))
        except Exception:
            parts.append("")
    doc.close()
    # \f rozdziela strony -> norm_with_map liczy strony
    return "\f".join(parts)


# litery, ktore ekstraktor PDF potrafi zgubic (ulotki producenta: "uzytku" -> "uytku")
PL_DIAC = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")


def make_variant(s: str, drop_space: bool, drop_punct: bool, drop_diac: bool = False,
                 fold: bool = False):
    """Wariant tekstu + mapa indeksow na tekst zrodlowy."""
    out = []
    idx = []
    prev_space = True
    for i, ch in enumerate(s):
        if ch == " ":
            if drop_space or prev_space:
                continue
            out.append(" ")
            idx.append(i)
            prev_space = True
            continue
        if drop_diac and ch in PL_DIAC:
            continue
        if drop_punct and not ch.isalnum():
            continue
        if fold:
            f = fold_char(ch).lower()
            if len(f) == 1:
                ch = f
        out.append(ch)
        idx.append(i)
        prev_space = False
    return "".join(out), idx


#  naglowek/stopka strony powtarzana w ekstrakcie PDF ("Seite 4 von 14", "Version: 7.0")
_PAGE_MARK_RE = re.compile(r"^\s*-{2,}\s*(?:strona|page|str)\.?\s*\d+\s*-{2,}\s*$", re.I)
_DIGITS_RE = re.compile(r"\d+")


def strip_boilerplate(raw: str):
    """Zwraca tekst z wygaszonymi wierszami naglowka/stopki (numeracja wierszy zachowana)
    albo None, gdy nic takiego nie ma. Cytat przeciety stopka PDF ma wtedy szanse sie skleic."""
    lines = raw.split("\n")
    if len(lines) < 30:
        return None
    keys = []
    counts = {}
    for ln in lines:
        s = ln.strip()
        if not s or len(s) > 120:
            keys.append(None)
            continue
        k = _DIGITS_RE.sub("#", norm_text(s))
        if len(k) < 4:
            keys.append(None)
            continue
        keys.append(k)
        counts[k] = counts.get(k, 0) + 1
    hits = [i for i, k in enumerate(keys) if k is not None and counts[k] >= 3]
    if not hits:
        return None
    out = list(lines)
    for i in hits:
        out[i] = ""
    return "\n".join(out)


def meaningful_len(raw: str) -> int:
    """Dlugosc tekstu po odrzuceniu markerow stron — '--- strona 1 ---' to nie tresc."""
    rest = [ln for ln in raw.splitlines() if not _PAGE_MARK_RE.match(ln)]
    return len(norm_text(" ".join(rest)).strip())


class DocText:
    """Tekst dokumentu z mapa pozycja -> wiersz/strona."""

    def __init__(self, path: Path, kind: str, raw: str, alt: bool = False):
        self.path = path
        self.kind = kind  # 'txt' | 'html' | 'pdf'
        self.norm, self.units = norm_with_map(raw)
        self.norm_dh = dehyphenate(self.norm)
        self._variants = {}
        self.alt = None
        if not alt:
            clean = strip_boilerplate(raw)
            if clean is not None and len(clean) < len(raw):
                self.alt = DocText(path, kind, clean, alt=True)

    def variant(self, drop_space: bool, drop_punct: bool, drop_diac: bool = False,
                fold: bool = False):
        key = (drop_space, drop_punct, drop_diac, fold)
        if key not in self._variants:
            self._variants[key] = make_variant(self.norm, drop_space, drop_punct, drop_diac, fold)
        return self._variants[key]

    @property
    def unit_label(self) -> str:
        return "str." if self.kind == "pdf" else "l."

    @property
    def src_label(self) -> str:
        return "PDF" if self.kind == "pdf" else (".txt" if self.kind == "txt" else ".html")

    def where(self, idx: int) -> str:
        if 0 <= idx < len(self.units):
            return "%s %d (%s)" % (self.unit_label, self.units[idx], self.src_label)
        return "(%s)" % self.src_label


_doc_cache: dict[Path, "DocText | None"] = {}


def load_doc(path: Path) -> "DocText | None":
    if path in _doc_cache:
        return _doc_cache[path]
    ext = path.suffix.lower()
    try:
        if ext in TEXT_EXT:
            kind, raw = "txt", read_txt_doc(path)
        elif ext in HTML_EXT:
            kind, raw = "html", read_html(path)
        elif ext in PDF_EXT:
            kind, raw = "pdf", read_pdf(path)
        else:
            kind, raw = None, ""
        #  zaslepka typu '--- strona 1 ---\n--- strona 2 ---' to nie jest tresc
        d = DocText(path, kind, raw) if kind and meaningful_len(raw) >= 20 else None
    except Exception:
        d = None
    _doc_cache[path] = d
    return d


# ---------------------------------------------------------------- parsowanie karty

def split_row(line: str):
    """Dzieli wiersz tabeli md na komorki (respektuje \\|)."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    cells = re.split(r"(?<!\\)\|", s)
    return [c.replace("\\|", "|").strip() for c in cells]


def is_sep_row(cells) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c or "-") for c in cells)


_ID_CLEAN = re.compile(r"[`*_\s]+")


def clean_id(s: str) -> str:
    s = _ID_CLEAN.sub("", s)
    s = s.lstrip("#")
    return s.lower()


FNAME_RE = re.compile(r"[\w\-\.\+*()]*?[\w\-\+*]\.(?:txt|html?|pdf|png|jpe?g|webp|gif)\b", re.I)
#  kotwice, ktore same nie sa zrodlem tekstu, ale poprzedzaja skrot '(+ .headers.txt)'
ANCHOR_RE = re.compile(r"[\w\-\.\+*()]*?[\w\-\+*]\.(?:zip|xlsx?|csv|docx?)\b", re.I)
#  rejestr zbiorczy pisany gwiazdka: `3rd-wapteka-87915.*`
STARNAME_RE = re.compile(r"[\w\-\.\+()]*?[\w\-\+]\.\*", re.I)
BARE_SUFFIX_RE = re.compile(r"(?<![\w.\-])\.(txt|html?|pdf)\b", re.I)


def parse_files_cell(cell: str):
    """Z komorki 'Plik lokalny' wyciaga nazwy plikow.
    Obsluguje skroty: '`x.html` / `.txt`', 'x.zip (+ .headers.txt, + -przeszukanie.txt)',
    '`3rd-wapteka-87915.*`' — czesciowa nazwa dokleja sie do NAJBLIZSZEJ poprzedzajacej,
    nie do ostatniej w calej komorce."""
    hits = []  # (pos, nazwa, kotwica_tylko)
    covered = []
    for rx, anchor_only in ((FNAME_RE, False), (STARNAME_RE, False), (ANCHOR_RE, True)):
        for m in rx.finditer(cell):
            covered.append((m.start(), m.end()))
            n = m.group(0).strip().strip("`'\" ,;")
            n = n.split("/")[-1].split("\\")[-1]
            if n:
                hits.append((m.start(), n, anchor_only))
    for m in BARE_SUFFIX_RE.finditer(cell):  # goly sufiks '.txt' bez rdzenia
        if not any(a <= m.start() < b for a, b in covered):
            hits.append((m.start(), "." + m.group(1).lower(), False))

    names, last_full = [], None
    for _p, n, anchor_only in sorted(hits):
        if n[0] in "-.":  # fragment: '.txt', '.headers.txt', '-przeszukanie.txt'
            if last_full is None:
                continue
            n = os.path.splitext(last_full)[0] + n
        else:
            last_full = n
            if anchor_only:
                continue
        names.append(n)
    seen, out = set(), []
    for n in names:
        k = n.lower()
        if k not in seen:
            seen.add(k)
            out.append(n)
    return out


class Doc:
    def __init__(self, ident: str, typ: str, files, url: str = ""):
        self.id = ident
        self.typ = typ
        self.url = url
        self.files = files  # lista Path (istniejacych lub nie)

    def __repr__(self):
        return "<Doc %s %s>" % (self.id, [f.name for f in self.files])


def build_index(root: Path):
    idx = {}
    if not root.exists():
        return idx
    for p in root.rglob("*"):
        if p.is_file():
            idx.setdefault(p.name.lower(), p)
    return idx


def parse_card(path: Path):
    """Zwraca (docs, rows, docs_dir_hint)."""
    lines = read_txt(path).splitlines()
    docs = []
    docs_dir_hint = None
    rows = []

    section = ""
    hdr = None
    hdr_kind = None  # 'docs' | 'facts'
    col = {}

    for i, raw in enumerate(lines, 1):
        line = raw.rstrip()
        if line.startswith("#"):
            m = re.match(r"^#{1,6}\s+(\S+)", line)
            section = m.group(1) if m else ""
            hdr = None
            continue
        if not line.lstrip().startswith("|"):
            hdr = None
            continue

        cells = split_row(line)
        if is_sep_row(cells):
            continue

        low = [c.lower() for c in cells]
        # naglowek tabeli dokumentow
        plik_i = next((j for j, c in enumerate(low) if c.startswith("plik lokalny")), None)
        if plik_i is not None and cells and cells[0].strip("# ").lower() in ("", "#", "nr", "id", "lp", "lp."):
            hdr, hdr_kind = cells, "docs"
            col = {"plik": plik_i,
                   "typ": next((j for j, c in enumerate(low) if c.startswith("typ")), None),
                   "url": next((j for j, c in enumerate(low) if c.startswith("url")), None)}
            m = re.search(r"dokumenty[\\/]([^`)\s]+)", cells[plik_i])
            if m:
                docs_dir_hint = m.group(1).strip("/\\ `")
            continue
        # naglowek tabeli faktow
        if "dok." in low and "cytat" in low:
            hdr, hdr_kind = cells, "facts"
            col = {"dok": low.index("dok."), "cytat": low.index("cytat")}
            continue

        if hdr is None:
            continue
        if len(cells) != len(hdr):
            continue

        if hdr_kind == "docs":
            ident = clean_id(cells[0])
            if not ident or ident in ("-", "—"):
                continue
            typ = cells[col["typ"]] if col.get("typ") is not None else ""
            url = cells[col["url"]] if col.get("url") is not None else ""
            docs.append((ident, typ, parse_files_cell(cells[col["plik"]]), url))
        elif hdr_kind == "facts":
            dok = cells[col["dok"]]
            cyt = cells[col["cytat"]]
            label = cells[0]
            if cyt:
                rows.append({"line": i, "dok": dok, "cytat": cyt,
                             "label": label, "section": section})
    return docs, rows, docs_dir_hint


# ---------------------------------------------------------------- rejestr dokumentow

def resolve_docs(raw_docs, docs_dir: Path, fallback_index):
    docs = {}
    for ident, typ, names, url in raw_docs:
        paths = []
        for n in names:
            if "*" in n:  # rejestr bywa zbiorczy: `projekt odniesienia-elastopor-steril-*.html/.txt`
                g = sorted(docs_dir.glob(n))
                if not g:  # folder marki inny niz domyslny — szukamy w calym drzewie
                    g = sorted(q for k, q in fallback_index.items() if fnmatch(k, n.lower()))
                paths.extend(g)
                continue
            p = docs_dir / n
            if not p.exists():
                q = fallback_index.get(n.lower())
                if q is not None:
                    p = q
            paths.append(p)
        docs[ident] = Doc(ident, typ, paths, url)
    return docs


def pick_sources(doc: Doc, limit: int = 14):
    """Wszystkie pliki tekstowe dokumentu (jeden rejestr bywa wieloplikowy).
    Zwraca (lista DocText, status, opis)."""
    srcs = []
    first = pick_source(doc)
    if first[0] is None:
        return [], first[1], first[2]
    #  jeden plik na "pien" nazwy: .txt przed .pdf przed .html (HTML ma smieci nawigacji)
    by_stem = {}
    for p in list(doc.files) + [p.with_suffix(".txt") for p in doc.files
                                if p.suffix.lower() in PDF_EXT | HTML_EXT]:
        ext = p.suffix.lower()
        if ext in IMG_EXT or not p.exists():
            continue
        rank = 0 if ext in TEXT_EXT else (1 if ext in PDF_EXT else 2)
        key = str(p.with_suffix("")).lower()
        if key not in by_stem or rank < by_stem[key][0]:
            by_stem[key] = (rank, p)
    for _rank, p in sorted(by_stem.values(), key=lambda t: str(t[1])):
        d = load_doc(p)
        if d is not None:
            srcs.append(d)
        if len(srcs) >= limit:
            break
    if not srcs:
        srcs = [first[0]]
    #  plik wybrany jako glowny idzie pierwszy
    srcs.sort(key=lambda d: 0 if d.path == first[0].path else 1)
    return srcs, "OK", str(first[0].path)


def pick_source(doc: Doc):
    """Wybiera plik tekstowy dokumentu. Zwraca (DocText|None, status, opis)."""
    cands = list(doc.files)
    # 1) .txt (rowniez towarzysz .pdf/.html, nawet jesli karta go nie wymienia)
    extra = []
    for p in cands:
        if p.suffix.lower() in PDF_EXT | HTML_EXT:
            t = p.with_suffix(".txt")
            if t.exists():
                extra.append(t)
    order = ([p for p in cands if p.suffix.lower() in TEXT_EXT] + extra
             + [p for p in cands if p.suffix.lower() in PDF_EXT]
             + [p for p in cands if p.suffix.lower() in HTML_EXT])
    seen, order2 = set(), []
    for p in order:
        if p not in seen:
            seen.add(p)
            order2.append(p)

    if not order2:
        if cands and all(p.suffix.lower() in IMG_EXT for p in cands):
            return None, "POMINIETO", "dokument tylko jako render/obrazek — brak warstwy tekstu"
        return None, "BRAK_PLIKU", "brak pliku tekstowego w rejestrze §3"

    empty = []
    missing = []
    for p in order2:
        if not p.exists():
            missing.append(p)
            continue
        if p.stat().st_size == 0:
            empty.append(p)
            continue
        d = load_doc(p)
        if d is None:
            empty.append(p)
            continue
        return d, "OK", str(p)

    if empty:
        return None, "BRAK_PLIKU", "%s — plik pusty / bez tekstu (skan bez warstwy tekstu?)" % empty[0].name
    return None, "BRAK_PLIKU", "%s — plik nie istnieje" % missing[0].name


# ---------------------------------------------------------------- cytaty

OPEN_Q = "„"
CLOSE_Q = "”“\"»"

MIN_LEN = 15
CLP_RE = re.compile(r"^(?:euh\s?\d{3}|[hp]\s?\d{3}(?:\s*\+\s*[hp]\s?\d{3})*[a-z]?)[\s.:,-]*$", re.I)
#  kod / REF: jeden token bez spacji, z cyframi (np. Z-URO-ZAR-WOR-LEW-1.5L-10)
REF_RE = re.compile(r"^(?:ref|reorder\s*no\.?|nr\s*kat\.?|symbol|kod)?[\s.:№#]*"
                    r"(?:[\w\-/\.]{1,14}|[A-Z0-9][A-Z0-9\-\./]{5,40})$", re.I)
TEMPLATE_RE = re.compile(r"\[[^\]]*/[^\]]*\]")
NEGATIVE_RE = re.compile(r"brak (?:wzmianki|s[łl]owa|sformu[łl]owania|okre[śs]lenia|zapisu|informacji o s[łl]ow)|"
                         r"nie (?:wyst[ęe]puj|zawiera s[łl]ow|pada|podaje s[łl]ow|u[żz]ywa s[łl]ow|ma s[łl]ow)|"
                         r"bez s[łl]ow[aa]|nigdzie nie", re.I)
SYMBOL_RE = re.compile(r"^[\W\d\s]+$", re.U)


AFTER_CLOSE_OK = set(' \t;,.)/]}:-–—!?»„*_…')
#  cudzyslow zamykajacy po cyfrze bywa oznaczeniem cala: „…250 8” strips…”
INCH_NEXT_RE = re.compile(r"\s*(?:strips?|inch|cali|cala|x\b|×)", re.I)


def _is_closer(cell: str, j: int) -> bool:
    """Czy znak na pozycji j domyka cytat (a nie jest calem/np. 8” = 8 cali)."""
    ch = cell[j]
    if ch not in CLOSE_Q:
        return False
    nxt = cell[j + 1] if j + 1 < len(cell) else ""
    prv = cell[j - 1] if j > 0 else ""
    if prv.isdigit() and INCH_NEXT_RE.match(cell[j + 1:j + 14]):
        return False  # cal: 250 8” strips
    if nxt and nxt not in AFTER_CLOSE_OK and not nxt.isspace():
        return False
    return True


ATTR_AFTER_RE = re.compile(r"^\s*\(([^)]{1,120})\)")


def attr_spans(cell: str):
    """Zakresy nawiasow-przypisow tuz po cytacie: „…” (D3, §9.1, „SKŁAD CHEMICZNY”).
    Cytat, ktory stoi w srodku takiego nawiasu, jest wskazaniem MIEJSCA w dokumencie,
    nie cytatem faktu."""
    spans = []
    for q, _lab, _attr, pos in extract_quotes(cell):
        j = pos + len(q) + 2  # za znakiem zamykajacym
        k = j
        while k < len(cell) and cell[k] in " \t":
            k += 1
        if k >= len(cell) or cell[k] != "(":
            continue
        depth, e = 0, k
        while e < len(cell):
            if cell[e] == "(":
                depth += 1
            elif cell[e] == ")":
                depth -= 1
                if depth == 0:
                    break
            e += 1
        spans.append((k, e))
    return spans


def extract_quotes(cell: str):
    """[(quote, label_before, attr_after, start_index)]."""
    out = []
    i = 0
    last_end = 0
    n = len(cell)
    while i < n:
        if cell[i] == OPEN_Q:
            j = i + 1
            depth = 0
            while j < n:
                if cell[j] == OPEN_Q:
                    depth += 1
                elif _is_closer(cell, j):
                    if depth == 0:
                        break
                    depth -= 1
                j += 1
            q = cell[i + 1:j]
            label = cell[last_end:i]
            m = ATTR_AFTER_RE.match(cell[min(j + 1, n):])
            attr = m.group(1) if m else ""
            out.append((q, label, attr, i))
            last_end = min(j + 1, n)
            i = j + 1
        else:
            i += 1
    return out


_TLUM_WORD = r"(?:t[łl]um\.?|t[łl]umaczenie(?:\s+robocze)?|przek[łl]ad|dos[łl]\.|dos[łl]ownie)"
#  marker bywa nie tuz po '(', lecz w srodku szerszego nawiasu:
#  "(brak polskiej wersji ... ; tłum.: „…”)" — wtedy zasieg konczy pierwszy niesparowany ')'
TLUM_RE = re.compile(r"\(\s*%s\s*[:.]?|(?<![\w])%s\s*[:.]" % (_TLUM_WORD, _TLUM_WORD), re.I)


def in_translation(cell: str, pos: int) -> bool:
    """Czy cytat na pozycji pos stoi wewnatrz '(tlum.: ...)'."""
    for m in TLUM_RE.finditer(cell):
        if m.start() > pos:
            continue
        depth = 1
        k = m.end()
        while k < len(cell) and depth:
            if cell[k] == "(":
                depth += 1
            elif cell[k] == ")":
                depth -= 1
            k += 1
        end = k if depth == 0 else len(cell)
        if m.start() < pos < end:
            return True
    return False


BRACKET_ONLY = re.compile(r"^\s*[\[\(](?:symbol|piktogram|ikona|znak)?\b[^\]\)]*[\]\)]\s*$", re.I)


def skip_reason(q: str):
    qn = norm_text(q).strip(' "\'.,;:-')
    if len(qn) < MIN_LEN:
        return "krótszy niż %d znaków" % MIN_LEN
    if BRACKET_ONLY.match(q.strip()):
        return "opis symbolu / piktogramu w nawiasie, nie cytat"
    if TEMPLATE_RE.search(q):
        return "zbiorczy zapis wariantów ([a/b/c]), nie dosłowny cytat"
    if SYMBOL_RE.fullmatch(qn):
        return "sam symbol / liczby"
    if CLP_RE.match(qn):
        return "kod CLP"
    if REF_RE.fullmatch(qn):
        return "REF / kod"
    return None


# ---------------------------------------------------------------- wskazanie dokumentu

DOKID_RE = re.compile(r"#\s?(\d+[a-z]?)|(?<![\w])([A-Z]{1,3}-?\d+[a-z]?)(?![\w])")

#  ---- dopasowanie identyfikatora dokumentu do rejestru §3 tej karty ----
#  rejestr uzywa roznych konwencji: '1', 'D2', 'D6b', 'D2-PL', 'D-SDS-GB', 'M-KAT-PL', 'D3a/b'.
#  Budujemy alternatywe z realnych identyfikatorow karty, od najdluzszego — inaczej
#  'D2-PL' zostaje wziete za 'D2' (inny dokument, czesto w innym jezyku).
_idrx_cache = {}


def _ident_pattern(ident: str) -> str:
    out = []
    for ch in ident:
        if ch in "-_":
            out.append(r"[-_– ]?")
        elif ch == "/":
            out.append(r"\s*/\s*")
        else:
            out.append(re.escape(ch))
    return "".join(out)


def _ident_regex(docs):
    key = tuple(sorted(i for i in docs if ":" not in i))
    rx = _idrx_cache.get(key)
    if rx is not None:
        return rx
    alts = []
    idents = [i for i in docs if ":" not in i]
    for ident in sorted(idents, key=lambda s: (-len(s), s)):
        pat = _ident_pattern(ident)
        if ident[0].isdigit():
            alts.append(r"(?P<g%d>#\s?%s)" % (len(alts), pat))  # goly numer tylko z '#'
        else:
            alts.append(r"(?P<g%d>#?\s?%s)" % (len(alts), pat))
        m = re.match(r"^[a-z]+([\d/].*)$", ident)
        if m:  # 'D2' bywa pisane jako '#2'
            alts.append(r"(?P<g%d>#\s?%s)" % (len(alts), _ident_pattern(m.group(1))))
    order = []
    for ident in sorted(idents, key=lambda s: (-len(s), s)):
        order.append(ident)
        if re.match(r"^[a-z]+([\d/].*)$", ident):
            order.append(ident)
    rx = (re.compile(r"(?<![A-Za-z0-9])(?:%s)(?![A-Za-z0-9])" % "|".join(alts), re.I), order)
    _idrx_cache[key] = rx
    return rx

SOFT_LABELS = [
    *[(_t, (_t,)) for _t in konfig.tokeny_wlasne()],
    ("sds", ("sds", "karta charakterystyki", "charakterystyk")),
    ("karta charakterystyki", ("sds", "karta charakterystyki", "charakterystyk")),
    ("ifu", ("ifu", "instrukcja")),
    ("instrukcja", ("ifu", "instrukcja")),
    ("etykieta", ("etykiet",)),
    ("katalog", ("katalog",)),
    ("ulotka", ("ulotka",)),
    ("certyfikat", ("certyfikat",)),
    ("deklaracja", ("deklaracj",)),
    ("strona producenta", ("strona producenta", "producent")),
]


def ids_from_text(s: str, docs):
    found = []
    if docs:
        rx, order = _ident_regex(docs)
        for m in rx.finditer(s):
            for i, ident in enumerate(order):
                if m.group("g%d" % i) is not None:
                    if ident not in found:
                        found.append(ident)
                    break
    if found:
        return found
    for m in DOKID_RE.finditer(s):  # zapas: konwencja '#2' / 'D2' bez rejestru
        tok = (m.group(1) or m.group(2) or "").lower().replace("-", "")
        for cand in (tok, tok.lstrip("d"), "d" + tok):
            if cand in docs and cand not in found:
                found.append(cand)
                break
    return found


def ids_from_files(s: str, docs):
    """Dopasowanie po nazwie pliku (np. 'katalog-1.pdf str.33')."""
    found = []
    for m in FNAME_RE.finditer(s):
        name = m.group(0).strip().lower()
        for ident, d in docs.items():
            for f in d.files:
                if f.name.lower().endswith(name) or name in f.name.lower():
                    if ident not in found:
                        found.append(ident)
                    break
    return found


TOKEN_RE = re.compile(r"(?<![\w])([A-Za-z]{1,4}[-_ ]?\d{1,4}[a-z]?)(?![\w])")


def ids_from_token(text: str, docs):
    """Kod dokumentu uzyty zamiast numeru (np. 'TD-16' = ulotka o tym symbolu)."""
    found = []
    for m in TOKEN_RE.finditer(text):
        tok = re.sub(r"[-_ ]", "", m.group(1)).lower()
        if len(tok) < 3 or tok.isdigit():
            continue
        for ident, d in docs.items():
            hay = re.sub(r"[-_ /\\.]", "", (d.url + " " + " ".join(f.name for f in d.files)).lower())
            if tok in hay and ident not in found:
                found.append(ident)
    return found


DOMAIN_RE = re.compile(r"(?<![\w.])([a-z0-9][a-z0-9\-]{2,})\.(?:pl|com|eu|it|de|net|org|info)(?:\.pl)?(?![\w])", re.I)


def ids_from_domain(label: str, docs):
    found = []
    for m in DOMAIN_RE.finditer(label):
        dom = m.group(1).lower()
        for ident, d in docs.items():
            hay = (d.url + " " + " ".join(f.name for f in d.files)).lower()
            if dom in hay and ident not in found:
                found.append(ident)
    return found


def ids_from_soft(label: str, docs):
    lab = label.lower()
    found = []
    for key, needles in SOFT_LABELS:
        if key not in lab:
            continue
        for ident, d in docs.items():
            hay = (d.typ + " " + d.url + " " + " ".join(f.name for f in d.files)).lower()
            if any(nd in hay for nd in needles) and ident not in found:
                found.append(ident)
    return found


LABEL_TAIL_RE = re.compile(r"([^;]{0,110}):\s*$")
XREF_RE = re.compile(r"(?:patrz|zob\.|por\.|jak w wierszu|wg wiersza|patrz wiersz)[^;]{0,40}$", re.I)
#  nazwa symbolu wg normy ("symbol wg ISO 7000-1051 „Nie używać ponownie”") to nie cytat z dokumentu
SYMBOL_NAME_RE = re.compile(r"symbol(?:u|em)?\s+(?:wg|zgodn\w+\s+z)\s+[A-Z][\w\s/:-]{2,30}$|"
                            r"(?:wg|zgodnie z)\s+(?:ISO|EN|PN)[\s\w./-]{2,20}$", re.I)
#  wskazanie miejsca w dokumencie: naglowek zapisany wersalikami albo odsylacz do sekcji
IS_HEADING_RE = re.compile(r"^(?=.*[A-ZĄĆĘŁŃÓŚŹŻ])[^a-ząćęłńóśźż]{2,45}$")
SECTION_PTR_RE = re.compile(r"(?:§\s*\d|sekcj\w*|panel\w*|rozdzia\w*|dzia[łl]\w*|"
                            r"\bs\.\s*\d|\bstr\.\s*\d|\bpkt\b|\btab\.)[^„]{0,24}$", re.I)
IMG_HINT_RE = re.compile(r"zdj[eę]ci|render|wycin|foto|\.png|\.webp|\.jpe?g|etykiet[ay]?\s*\(", re.I)


_ATTR_NOISE = re.compile(r"#\s?\d+[a-z]?|[A-Z]{1,3}-?\d+[a-z]?|\b(?:str|s|pkt|sekcja|§|tab|ust)\.?\s*\d+|"
                         r"\b(?:symbol|render|etykieta|wycinek|zdj[eę]cie|okładka|katalog|i|oraz)\b|" +
                         "|".join(r"\b%s\b" % _t for _t in konfig.tokeny_wlasne()) + "|" +
                         r"[\s,;/()\.\-–—]+", re.I)


def is_attribution(attr: str) -> bool:
    """Czy '(...)' po cytacie to przypis do dokumentu, a nie komentarz autora karty."""
    rest = _ATTR_NOISE.sub("", attr)
    return len(rest) <= 12


LABEL_HEAD_RE = re.compile(r"^\s*([^:;]{1,110}):")


def label_segment(label: str):
    """Fragment etykiety wskazujacy dokument. Najpierw ogon zakonczony dwukropkiem
    ('… D4: '), a gdy go nie ma — poczatek klauzuli przed pierwszym dwukropkiem
    ('D6 etykieta 5 L: 3 piktogramy … + ')."""
    tail = label.rsplit(";", 1)[-1]
    m = LABEL_TAIL_RE.search(tail)
    if m:
        return m.group(1)
    m = LABEL_HEAD_RE.match(tail)
    return m.group(1) if m else ""


def candidates_for(quote_label: str, attr_after: str, dok_cell: str, docs, seg_override=None):
    """(primary_ids, secondary_ids, soft_flag)"""
    row = []
    for fn in (ids_from_text, ids_from_files, ids_from_token, ids_from_domain):
        for i in fn(dok_cell, docs):
            if i not in row:
                row.append(i)
    if not row:
        row = ids_from_soft(dok_cell, docs)

    prim, soft = [], False
    if attr_after and is_attribution(attr_after):
        prim = ids_from_text(attr_after, docs) or ids_from_files(attr_after, docs)
        if not prim:
            p = ids_from_domain(attr_after, docs) or ids_from_soft(attr_after, docs)
            if p:
                prim, soft = p, True
    if not prim:
        seg = seg_override if seg_override is not None else label_segment(quote_label)
        if seg:
            prim = ids_from_text(seg, docs) or ids_from_files(seg, docs) or ids_from_token(seg, docs)
            if not prim:
                p = ids_from_domain(seg, docs) or ids_from_soft(seg, docs)
                if p:
                    prim, soft = p, True

    if not prim:
        return row, [], False
    sec = [i for i in row if i not in prim]
    return prim, sec, soft


# ---------------------------------------------------------------- szukanie cytatu

STOP = set("i oraz w we z ze na do od za po the and of for to a o u przy nie lub albo jest są być ten ta to".split())


def anchors(q: str, k=6):
    words = re.findall(r"[\w°%]+", q)
    words = [w for w in words if len(w) >= 5 and w not in STOP]
    words.sort(key=len, reverse=True)
    return words[:k]


#  warianty porownania: (drop_space, drop_punct, drop_diac) — od najostrzejszego
PASSES = [(False, False, False), (False, True, False), (True, True, False), (True, True, True)]

#  karty sklejaja pola tabeli w jeden cytat: "REF / rozmiar / szt." albo "Etykieta: wartość"
FIELD_SEP_RE = re.compile(r"\s+/\s+|\s+[•|]\s+|:\s+|\s*;\s*|\s+[—–]\s+|\s+[×x]\s+(?=[„\"])")


def find_literal(doc: DocText, part: str, start: int, drop_space: bool, drop_punct: bool,
                 drop_diac: bool = False):
    """Szuka fragmentu w wariancie tekstu; zwraca (start_norm, end_norm) w indeksach doc.norm."""
    dtext, dmap = doc.variant(drop_space, drop_punct, drop_diac)
    qtext, _ = make_variant(part, drop_space, drop_punct, drop_diac)
    if not qtext:
        return -1, -1
    # 'start' jest w indeksach doc.norm -> przelicz na indeks wariantu
    lo = 0
    if start > 0:
        while lo < len(dmap) and dmap[lo] < start:
            lo += 1
    i = dtext.find(qtext, lo)
    if i < 0 and not drop_space and not drop_punct:
        j = doc.norm_dh.find(dehyphenate(part), start)
        if j >= 0:
            return j, j + len(part)
        return -1, -1
    if i < 0:
        return -1, -1
    end = i + len(qtext) - 1
    return dmap[i], dmap[min(end, len(dmap) - 1)] + 1


_FOLD_MAP = {"ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ø": "o", "Ø": "O", "ß": "ss"}


def fold_char(ch: str) -> str:
    if ch in _FOLD_MAP:  # 'ł' nie ma dekompozycji NFKD
        return _FOLD_MAP[ch]
    d = unicodedata.normalize("NFKD", ch)
    return "".join(c for c in d if not unicodedata.combining(c)) or ch


def loose_pattern(part: str):
    """Regex tolerujacy zgubione/zamienione polskie znaki (ekstrakcja PDF:
    'uzytku' -> 'uytku', 'spolka' -> 'spolka'/'splka')."""
    out = []
    for ch in part:
        if ch == " " or not ch.isalnum():
            continue
        if ch in PL_DIAC:
            out.append("%s?" % re.escape(fold_char(ch).lower()))
        else:
            out.append(re.escape(fold_char(ch).lower()))
    return "".join(out)


def find_loose(doc: DocText, part: str, start: int):
    dtext, dmap = doc.variant(True, True, False, fold=True)
    pat = loose_pattern(part)
    if len(pat) < 10:
        return -1, -1
    lo = 0
    if start > 0:
        while lo < len(dmap) and dmap[lo] < start:
            lo += 1
    try:
        m = re.compile(pat).search(dtext, lo)
    except re.error:
        return -1, -1
    if not m:
        return -1, -1
    return dmap[m.start()], dmap[min(m.end() - 1, len(dmap) - 1)] + 1


def _parts(q: str, split_fields: bool, minlen: int = 0):
    chunks = _OMISSION_RE.split(q)
    minlen = minlen or (4 if split_fields else 8)
    if split_fields:
        out = []
        for ch in chunks:
            out.extend(FIELD_SEP_RE.split(ch))
        chunks = out
    pn = [norm_text(p).strip() for p in chunks]
    return [p for p in pn if len(p.strip(' "\'.,;:-')) >= minlen]


def _ordered_hit(doc: DocText, pn):
    for pas in PASSES + ["loose", "padded"]:
        pos, first, ok = 0, -1, True
        for p in pn:
            if pas == "loose":
                a, b = find_loose(doc, p, pos)
            elif pas == "padded":
                a, b = find_padded(doc, p, pos)
            else:
                a, b = find_literal(doc, p, pos, *pas)
            if a < 0:
                ok = False
                break
            if first < 0:
                first = a
            pos = b
        if ok:
            return first
    return -1


def _unordered_hit(doc: DocText, pn):
    found_at = []
    for p in pn:
        a = -1
        for pas in PASSES:
            a, _b = find_literal(doc, p, 0, *pas)
            if a >= 0:
                break
        if a < 0:
            a, _b = find_loose(doc, p, 0)
        if a < 0:
            return -1
        found_at.append(a)
    return min(found_at) if found_at else -1


def _alnum(s: str) -> str:
    return "".join(fold_char(c).lower() for c in s if c.isalnum())


PAD_MAXRUN = 10  # dluzsza wstawka to juz nie smiec ekstraktora, tylko pominiete zdanie


def find_padded(doc: "DocText", part: str, start: int, maxrun: int = PAD_MAXRUN):
    """Fragment stoi w zrodle, ale ekstraktor wcisnal miedzy jego znaki smieci:
    numery krokow listy ('… use. 2 store …'), odnosniki przypisow ('en 167772',
    '2adenowirusy'), numery wierszy ('sp.zo.o. 3 michalowicza 12 4 43-300'),
    podpisy rysunku ('2x orotol 3 fill'). Fragment musi byc PODCIAGIEM zrodla,
    kazda wstawka <= maxrun znakow, lacznie <= 12 % dlugosci fragmentu."""
    dtext, dmap = doc.variant(True, True, False, fold=True)
    qa, _ = make_variant(part, True, True, False, fold=True)
    if not dtext or not qa:
        return -1, -1
    if len(qa) < 25:  # za krotkie na luzne dopasowanie — wymagamy ciaglosci
        return find_literal(doc, part, start, True, True)
    budget = max(2, int(0.12 * len(qa)))
    lo = 0
    if start > 0:
        while lo < len(dmap) and dmap[lo] < start:
            lo += 1
    anchor = qa[:10]
    st, tries = lo, 0
    while tries < 25:
        i = dtext.find(anchor, st)
        if i < 0:
            return -1, -1
        st = i + 1
        tries += 1
        p, skipped, ok = i, 0, True
        for ch in qa:
            j = dtext.find(ch, p, p + maxrun + 1)
            if j < 0:
                ok = False
                break
            skipped += j - p
            if skipped > budget:
                ok = False
                break
            p = j + 1
        if ok:
            return dmap[i], dmap[min(p - 1, len(dmap) - 1)] + 1
    return -1, -1


def is_degraded_source(quote: str, snippet: str) -> bool:
    """Czy roznica to gubienie znakow przez ekstraktor (zrodlo jest podciagiem cytatu)."""
    if not snippet:
        return False
    q = _alnum(quote)
    s = _alnum(snippet)
    if not q or not s or len(s) < 0.8 * len(q) or len(s) > 1.4 * len(q):
        return False
    i = maxrun = skipped = used = 0
    for ch in s:
        j = q.find(ch, i)
        if j < 0:
            break  # ogon okna poza cytatem
        maxrun = max(maxrun, j - i)
        skipped += j - i
        i = j + 1
        used += 1
    #  gubienie pojedynczych znakow = wada ekstrakcji; ciagly blok = inne brzmienie.
    #  Warunek "i >= len(q) - 2" wymaga, by zrodlo pokrywalo CALY cytat po kolei.
    return (maxrun <= 4 and skipped <= 0.10 * len(q)
            and i >= len(q) - 2 and len(s) - used <= 12)


def _locate(doc: DocText, q: str):
    """Wszystkie proby doslownego dopasowania w jednym widoku dokumentu. -1 = brak."""
    pn = _parts(q, False)
    if not pn:
        #  cytat z „…” miedzy krotkimi fragmentami („A H1N1 … – 30 sek.”) — nizszy prog,
        #  ale tylko z zachowaniem kolejnosci i tylko gdy fragmentow jest co najmniej dwa
        short = _parts(q, False, minlen=4)
        pn = short if len(short) >= 2 else [norm_text(q).strip()]
    hit = _ordered_hit(doc, pn)
    if hit >= 0:
        return hit
    if len(pn) >= 2:
        hit = _unordered_hit(doc, pn)
        if hit >= 0:
            return hit

    # wiersze tabel przepisane z PDF: pola rozdzielone " / ", " ; ", ": "
    if FIELD_SEP_RE.search(q):
        pf = _parts(q, True)
        raw_fields = len([x for x in FIELD_SEP_RE.split(_OMISSION_RE.sub(" ", q)) if x.strip()])
        if len(pf) >= 2 or (pf and raw_fields >= 3):
            hit = _ordered_hit(doc, pf)
            if hit >= 0:
                return hit
            # ekstrakcja PDF rozsypuje kolumny — dopuszczamy dowolna kolejnosc pol
            hit = _unordered_hit(doc, pf)
            if hit >= 0:
                return hit

    return -1


def find_quote(doc: DocText, q: str):
    """Zwraca (status, pozycja, najlepsze_brzmienie_ze_zrodla, ratio, uwaga)."""
    hit = _locate(doc, q)
    if hit >= 0:
        return "ZGODNY", hit, None, 1.0, ""
    #  cytat przeciety naglowkiem/stopka strony — widok bez powtarzalnej ramki
    if doc.alt is not None:
        hit = _locate(doc.alt, q)
        if hit >= 0:
            return "ZGODNY", hit, None, 1.0, ""

    # przyblizenie
    qn = norm_text(_OMISSION_RE.sub(" ", q))
    qn = re.sub(r"\s+", " ", qn).strip()
    best = (0.0, -1, "")
    L = len(qn)
    positions = []
    for w in anchors(qn):
        st = 0
        cnt = 0
        while cnt < 40:
            i = doc.norm.find(w, st)
            if i < 0:
                break
            positions.append(i)
            st = i + len(w)
            cnt += 1
        if len(positions) > 200:
            break
    seen = set()
    for i in positions:
        for off in (0, L // 3, 2 * L // 3):
            s = max(0, i - off)
            key = s // 20
            if key in seen:
                continue
            seen.add(key)
            win = doc.norm[s:s + int(L * 1.35) + 20]
            if not win:
                continue
            r = difflib.SequenceMatcher(None, qn, win).quick_ratio()
            if r < 0.6:
                continue
            sm = difflib.SequenceMatcher(None, qn, win)
            r = sm.ratio()
            if r > best[0]:
                m = sm.find_longest_match(0, len(qn), 0, len(win))
                a0 = max(0, m.b - m.a)
                snippet = win[a0:a0 + L]
                best = (r, s + a0, snippet)
    if best[0] >= 0.55 and is_degraded_source(q, best[2]):
        return ("POMINIETO", best[1], best[2], best[0],
                "źródło zgubiło znaki przy ekstrakcji (tekst źródła jest podciągiem cytatu) — do oceny ręcznej")
    if best[0] >= 0.72:
        return "ROZJAZD", best[1], best[2], best[0], ""
    return "BRAK_W_PLIKU", -1, best[2] if best[0] >= 0.55 else None, best[0], ""


# ---------------------------------------------------------------- sprawdzanie karty

STATUSES = ["ZGODNY", "ROZJAZD", "BRAK_W_PLIKU", "BRAK_PLIKU", "TLUMACZENIE", "POMINIETO"]
FAIL = {"ROZJAZD", "BRAK_W_PLIKU", "BRAK_PLIKU"}

#  Gdy wiersz wskazuje kilka dokumentów i zaden nie jest wskazany przy samym cytacie,
#  nie wolno twierdzic, ze cytatu "nie ma" — skoro czesci dokumentow (skan, render)
#  nie da sie przeczytac, brak dowodu na nieobecnosc jest slabszy niz brak pliku.
AMBIG_RANK = {"ZGODNY": 0, "ROZJAZD": 1, "POMINIETO": 2, "BRAK_PLIKU": 3,
              "TLUMACZENIE": 4, "BRAK_W_PLIKU": 5}


def _rank(status: str, ambiguous: bool) -> int:
    return AMBIG_RANK[status] if ambiguous else STATUSES.index(status)


def shorten(s, n=160):
    s = re.sub(r"\s+", " ", (s or "").strip())
    return s if len(s) <= n else s[:n - 1] + "…"


def check_card(card: Path, docs_dir_override: Path | None):
    raw_docs, rows, hint = parse_card(card)

    if docs_dir_override is not None:
        docs_dir = docs_dir_override
    else:
        base = card.parent.parent / "dokumenty"
        docs_dir = base
        if hint:
            h = hint.strip("/\\")
            for cand in (card.parent.parent / h,
                         base / h.split("/")[-1].split("\\")[-1]):
                if cand.exists() and cand.is_dir():
                    docs_dir = cand
                    break
    fallback_index = build_index(card.parent.parent / "dokumenty")
    docs = resolve_docs(raw_docs, docs_dir, fallback_index)

    results = []
    for row in rows:
        cell = row["cytat"]
        carry = ""  # etykieta „D8 (wycinek …): „a”, „b”, „c”” obowiazuje do nastepnej etykiety
        aspans = attr_spans(cell)
        for q, label, attr, pos in extract_quotes(cell):
            res = {"line": row["line"], "quote": q, "label": shorten(label, 70),
                   "row_label": row["label"], "dok": row["dok"]}
            if in_translation(cell, pos):
                res.update(status="TLUMACZENIE", note="fragment po „(tłum.: …)”")
                results.append(res)
                continue
            sr = skip_reason(q)
            if sr:
                res.update(status="POMINIETO", note=sr)
                results.append(res)
                continue
            #  cytat w srodku nawiasu-przypisu to wskazanie miejsca w dokumencie
            #  („…” (D3, „SKŁAD CHEMICZNY”)), nie cytat faktu
            box = next(((a, b) for a, b in aspans if a < pos < b), None)
            if box and (IS_HEADING_RE.match(q.strip()) or
                        SECTION_PTR_RE.search(cell[box[0]:pos])):
                res.update(status="POMINIETO",
                           note="wskazanie miejsca w dokumencie wewnątrz przypisu, nie cytat faktu")
                results.append(res)
                continue
            seg = label_segment(label)
            if seg:
                carry = seg
            elif not label.strip(" ”\"',.;:"):
                #  kolejny cytat tej samej wyliczanki („X: „a”, „b”, „c””) — etykieta trwa
                seg = carry
            else:
                carry = ""  # miedzy cytatami stoi inna tresc — lancuch przerwany
            after = cell[pos + len(q) + 2:pos + len(q) + 60]
            if NEGATIVE_RE.search(label[-80:]) or NEGATIVE_RE.search(after):
                res.update(status="POMINIETO",
                           note="cytat o nieobecności sformułowania w źródle (brak wzmianki / nie występuje)")
                results.append(res)
                continue
            tail = label.rsplit(";", 1)[-1].strip()
            if XREF_RE.search(tail):
                res.update(status="POMINIETO", note="odsyłacz do innego wiersza karty, nie cytat ze źródła")
                results.append(res)
                continue
            if SYMBOL_NAME_RE.search(tail.rstrip(" :")):
                res.update(status="POMINIETO", note="nazwa symbolu wg normy, nie cytat z dokumentu")
                results.append(res)
                continue

            prim, sec, soft = candidates_for(label, attr, row["dok"], docs, seg)
            #  cytat porownawczy z pliku podanego z nazwy, a nieobecnego w rejestrze §3
            #  (np. „Fortis TDS: …” z `QMS-IFU-TDS-52_...txt` wymienionym w kolumnie Dok.)
            for nm in parse_files_cell(" ".join([seg, label, attr, row["dok"]])):
                p = fallback_index.get(nm.lower())
                if p is None or p.suffix.lower() in IMG_EXT:
                    continue
                if any(p in d.files for d in docs.values()):
                    continue
                key = "plik:" + nm.lower()
                docs.setdefault(key, Doc(key, "", [p], ""))
                if key not in sec and key not in prim:
                    sec.append(key)
                    soft = True  # plik wskazany z nazwy — zgodnosc w nim wystarczy
            if not prim:
                res.update(status="POMINIETO", note="nie wskazano dokumentu (Dok.: %s)" % (row["dok"] or "—"))
                results.append(res)
                continue

            #  brak wskazania przy cytacie + kilka dokumentow w wierszu = wskazanie niepewne
            ambiguous = len(prim) > 1
            best = None
            for ident in prim:
                d = docs.get(ident)
                srcs, st, info = pick_sources(d)
                if not srcs:
                    cand = {"status": st, "doc": ident, "note": info}
                    if best is None or _rank(st, ambiguous) < _rank(best["status"], ambiguous):
                        best = cand
                    continue
                hit = None
                for src in srcs:
                    status, ppos, snippet, ratio, fnote = find_quote(src, q)
                    cand = {"status": status, "doc": ident, "note": fnote,
                            "where": src.where(ppos) if ppos >= 0 else "", "found": snippet,
                            "ratio": ratio, "file": src.path.name}
                    if hit is None or STATUSES.index(status) < STATUSES.index(hit["status"]):
                        hit = cand
                    if status == "ZGODNY":
                        break
                if hit["status"] == "ZGODNY":
                    best = hit
                    break
                if best is None or _rank(hit["status"], ambiguous) < _rank(best["status"], ambiguous):
                    best = hit

            # cytat nie stoi we wskazanym dokumencie — sprawdz pozostale z wiersza
            if best and best["status"] in ("BRAK_W_PLIKU", "ROZJAZD", "BRAK_PLIKU") and sec:
                for ident in sec:
                    d = docs.get(ident)
                    srcs, st, info = pick_sources(d)
                    status = None
                    for src in srcs:
                        status, ppos, snippet, ratio, _fn = find_quote(src, q)
                        if status == "ZGODNY":
                            break
                    if status == "ZGODNY":
                        if soft:
                            # etykieta byla miekka ("katalog:", "przykład:") — to nie bylo
                            # twarde wskazanie dokumentu, wiec zgodnosc wystarcza
                            best = {"status": "ZGODNY", "doc": ident, "note": "",
                                    "where": src.where(ppos), "found": None,
                                    "ratio": 1.0, "file": src.path.name}
                        elif best["status"] == "BRAK_PLIKU":
                            # wskazany dokument to skan — nie wiemy, czy cytatu w nim NIE ma,
                            # wiec to nie jest rozjazd, tylko brak czym zweryfikowac
                            best = dict(best, note="%s; to samo brzmienie stoi w %s (%s)"
                                        % (best.get("note", ""), ident.upper(), src.where(ppos)))
                        else:
                            best = {"status": "ROZJAZD", "doc": prim[0], "note":
                                    "cytat stoi doslownie w %s (%s), nie w podanym #%s"
                                    % (ident.upper(), src.where(ppos), prim[0].upper()),
                                    "where": src.where(ppos), "found": None,
                                    "ratio": 1.0, "file": src.path.name}
                        break
            best = best or {"status": "BRAK_PLIKU", "note": "brak dokumentu"}
            # cytat z renderu / zdjęcia etykiety — nie ma warstwy tekstu do sprawdzenia
            if best["status"] in ("BRAK_W_PLIKU", "BRAK_PLIKU"):
                #  wskazanie renderu/wycinka stoi w calej klauzuli przed cytatem
                #  ("D2 PL (booklet, `burs_booklet_p1_300dpi.png`, panel PL, sekcja „SKŁAD”):"),
                #  nie tylko w ogonie etykiety po dwukropku
                pre = cell[:pos]
                clause = pre[max(pre.rfind(";"), len(pre) - 250) + 1:]
                hint_txt = " ".join([seg, clause, attr, row["dok"]])
                if IMG_HINT_RE.search(hint_txt):
                    best = {"status": "POMINIETO", "doc": best.get("doc"),
                            "note": "cytat z renderu / zdjęcia (bez warstwy tekstu) — do oceny ręcznej"}
            res.update(best)
            results.append(res)
    return results, docs, docs_dir


def print_card_report(card: Path, results, docs_dir, verbose=False):
    counts = {s: 0 for s in STATUSES}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    problems = [r for r in results if r["status"] in FAIL]

    print("=" * 78)
    print("KARTA: %s" % card)
    print("dokumenty: %s" % docs_dir)
    print("cytatów: %d | %s" % (len(results),
                                " | ".join("%s: %d" % (s, counts.get(s, 0)) for s in STATUSES if counts.get(s))))
    if not problems:
        print("OK — brak problemów")
    for r in problems:
        print("-" * 78)
        print("  l.%-4d [%s] dok. %s   (wiersz: %s)" % (
            r["line"], r["status"], (r.get("doc") or r.get("dok") or "—"), shorten(r.get("row_label"), 50)))
        print("    karta : „%s”" % shorten(r["quote"], 220))
        if r["status"] == "ROZJAZD":
            if r.get("found"):
                print("    źródło: „%s”" % shorten(r["found"], 220))
            print("    miejsce: %s  %s  (podobieństwo %.2f)" % (
                r.get("where") or "?", r.get("file", ""), r.get("ratio", 0)))
            if r.get("note"):
                print("    uwaga : %s" % r["note"])
        elif r["status"] == "BRAK_W_PLIKU":
            print("    źródło: nie znaleziono w %s" % (r.get("file") or r.get("doc")))
            if r.get("found"):
                print("    najbliższe: „%s” (%.2f)" % (shorten(r["found"], 180), r.get("ratio", 0)))
        else:
            print("    źródło: %s" % r.get("note", ""))
    if verbose:
        for r in results:
            if r["status"] not in FAIL:
                print("  l.%-4d [%s] %s — „%s”" % (r["line"], r["status"], r.get("note", ""),
                                                   shorten(r["quote"], 90)))
    return counts, problems


def main(argv=None):
    ap = argparse.ArgumentParser(description="Czy cytat w karcie stoi doslownie w cytowanym dokumencie.")
    ap.add_argument("karty", nargs="+", help="pliki kart .md")
    ap.add_argument("--dokumenty", default=None, help="folder marki z dokumentami (nadpisuje §3)")
    ap.add_argument("-v", "--verbose", action="store_true", help="wypisz też cytaty bez problemu")
    args = ap.parse_args(argv)

    override = Path(args.dokumenty).resolve() if args.dokumenty else None

    total = {s: 0 for s in STATUSES}
    bad_cards = 0
    all_problems = 0
    for name in args.karty:
        card = Path(name).resolve()
        if not card.exists():
            print("BRAK KARTY: %s" % card, file=sys.stderr)
            bad_cards += 1
            continue
        results, docs, docs_dir = check_card(card, override)
        counts, problems = print_card_report(card, results, docs_dir, args.verbose)
        for s in STATUSES:
            total[s] += counts.get(s, 0)
        if problems:
            bad_cards += 1
            all_problems += len(problems)

    print("=" * 78)
    print("PODSUMOWANIE: kart %d | cytatów %d | %s" % (
        len(args.karty), sum(total.values()),
        " | ".join("%s: %d" % (s, total[s]) for s in STATUSES)))
    print("kart z problemami: %d | problemów: %d" % (bad_cards, all_problems))
    return 1 if all_problems or bad_cards else 0


if __name__ == "__main__":
    sys.exit(main())
