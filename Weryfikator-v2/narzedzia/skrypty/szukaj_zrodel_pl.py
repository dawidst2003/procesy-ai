#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
szukaj_zrodel_pl.py
Szuka polskojezycznych zrodel (SDS/ulotka/IFU/strona produktowa) dla danego produktu
przez NodeHub Search API (TOP 10 Google PL), pobiera kandydatow "curl-podobnie"
(bez obchodzenia blokad) i zapisuje ich metadane do CSV, zeby agent mogl podjac
decyzje o przyjeciu do manifestu.

Uzycie:
    python szukaj_zrodel_pl.py "<nazwa produktu>" "<marka>" [--folder dokumenty/<marka>] [--limit N]

Wymagania: Python 3.12, PyMuPDF (fitz), biblioteka standardowa. Bez WebFetch.
Klucz NODESHUB_API_KEY jest wczytywany z pliku .env w katalogu projektu
(C:\\Users\\dawid\\Desktop\\projekt odniesienia-SEO\\.env) i NIGDY nie jest wypisywany.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html.parser
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
import konfig  # profil projektu: sciezki i tokeny (weryfikacja.json)

# --------------------------------------------------------------------------
# Konfiguracja
# --------------------------------------------------------------------------

NODESHUB_URL = "https://api.nodeshub.io/v1/search"
ENV_CANDIDATES = [p for p in [
    Path(konfig.wczytaj().get("env") or "") if konfig.wczytaj().get("env") else None,
    konfig.korzen() / ".env",                       # katalog projektu klienta
    Path(__file__).resolve().parent.parent / ".env",
] if p]

# Domyslna biblioteka projektu - tu ladują sie dokumenty produkcyjne (bez --katalog).
# Bez --katalog skrypt nie zgaduje, gdzie zapisac dokumenty (w projekcie moze byc wiele kategorii).
DEFAULT_LIBRARY_ROOT = konfig.korzen() / konfig.sciezki()["zrodla"]

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

SEARCH_TIMEOUT = 30
FETCH_TIMEOUT = 60
FETCH_DELAY_S = 1.2
MAX_CANDIDATES_TOTAL = 25  # twardy limit calkowity, zeby nie uciec w nieskonczonosc

BLOCK_MARKERS = [
    "captcha", "access denied", "attention required", "cloudflare",
    "are you a robot", "verify you are a human", "blocked", "403 forbidden",
]

# Zgodnie ze standardem: nazwa produktu + karta charakterystyki / ulotka / pdf / filetype:pdf.
QUERY_TEMPLATES = [
    "{produkt} karta charakterystyki",
    "{produkt} ulotka",
    "{produkt} pdf",
    "{produkt} filetype:pdf",
]

PL_DIACRITICS = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
PL_HINT_WORDS = [
    "karta charakterystyki", "ulotka", "instrukcja stosowania", "instrukcja uzytkowania",
    "dawkowanie", "zastosowanie", "producent", "dystrybutor",
]


# --------------------------------------------------------------------------
# Klucz API
# --------------------------------------------------------------------------

def load_api_key() -> str:
    for env_path in ENV_CANDIDATES:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line.startswith("NODESHUB_API_KEY="):
                    return line.split("=", 1)[1].strip()
    raise SystemExit(
        "BLAD: nie znaleziono NODESHUB_API_KEY w .env "
        f"(szukano w: {', '.join(str(p) for p in ENV_CANDIDATES)})"
    )


# --------------------------------------------------------------------------
# NodeHub search
# --------------------------------------------------------------------------

def nodeshub_search(keyword: str, api_key: str) -> list[dict]:
    """Zwraca liste organic_results (url, title, description, domain) albo [] przy bledzie."""
    params = urllib.parse.urlencode({"keyword": keyword, "gl": "pl", "hl": "pl"})
    req = urllib.request.Request(
        f"{NODESHUB_URL}?{params}",
        method="GET",
        headers={
            "Authorization": f"Bearer {api_key}",
            "User-Agent": BROWSER_UA,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=SEARCH_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        print(f"  [NodeHub] BLAD HTTP {e.code} dla zapytania: {keyword!r}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"  [NodeHub] BLAD {type(e).__name__}: {e} dla zapytania: {keyword!r}", file=sys.stderr)
        return []

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        print(f"  [NodeHub] odpowiedz nie jest poprawnym JSON dla: {keyword!r}", file=sys.stderr)
        return []

    results = (
        data.get("data", {})
        .get("results", {})
        .get("organic_results", [])
    )
    return results


# --------------------------------------------------------------------------
# Pobieranie kandydatow ("curl-podobnie", bez obchodzenia blokad)
# --------------------------------------------------------------------------

class _HTMLTextExtractor(html.parser.HTMLParser):
    """Minimalny ekstraktor tekstu z HTML (bez skryptow/stylow/komentarzy)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0 and data.strip():
            self.chunks.append(data.strip())

    def get_text(self) -> str:
        return "\n".join(self.chunks)


def fetch_url(url: str) -> tuple[int | None, bytes | None, str | None, str | None]:
    """Zwraca (status, body_bytes, content_type, error). Nie rzuca wyjatkow."""
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": BROWSER_UA})
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            body = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            return resp.status, body, ctype, None
    except urllib.error.HTTPError as e:
        body = b""
        try:
            body = e.read()
        except Exception:
            pass
        return e.code, body, e.headers.get("Content-Type", "") if e.headers else "", None
    except Exception as e:
        return None, None, None, f"{type(e).__name__}: {e}"


def is_blocked(status: int | None, body: bytes | None, ctype: str | None) -> bool:
    if status is not None and status in (401, 403, 429, 503):
        return True
    if body and (not ctype or "pdf" not in ctype.lower()):
        try:
            sample = body[:20000].decode("utf-8", errors="ignore").lower()
        except Exception:
            sample = ""
        if any(marker in sample for marker in BLOCK_MARKERS):
            return True
    return False


def extract_text_from_pdf_bytes(data: bytes, max_pages: int = 8) -> str:
    try:
        import fitz
    except ImportError:
        return ""
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception:
        return ""
    parts = []
    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        parts.append(page.get_text("text"))
    doc.close()
    return "\n".join(parts)


def extract_text_from_html_bytes(data: bytes, ctype: str | None) -> str:
    charset = "utf-8"
    if ctype:
        m = re.search(r'charset=([\w-]+)', ctype, re.IGNORECASE)
        if m:
            charset = m.group(1)
    try:
        raw = data.decode(charset, errors="replace")
    except (LookupError, UnicodeError):
        raw = data.decode("utf-8", errors="replace")
    parser = _HTMLTextExtractor()
    try:
        parser.feed(raw)
    except Exception:
        pass
    return parser.get_text()


# --------------------------------------------------------------------------
# Ocena kandydata
# --------------------------------------------------------------------------

def polish_language_score(text: str) -> float:
    """Udzial polskich znakow diakrytycznych wsrod znakow alfabetycznych (0-1)."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    pl_count = sum(1 for c in letters if c in PL_DIACRITICS)
    return pl_count / len(letters)


def normalize_for_match(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def product_name_hit(text: str, produkt: str) -> bool:
    norm_text = normalize_for_match(text)
    tokens = [t for t in re.split(r'\s+', normalize_for_match(produkt)) if len(t) >= 3]
    if not tokens:
        return False
    return all(t in norm_text for t in tokens)


def classify_type(url: str, title: str, text: str) -> str:
    blob = normalize_for_match(f"{url} {title} {text[:3000]}")
    if "karta charakterystyki" in blob or re.search(r'\bsds\b', blob) or "safety data sheet" in blob:
        return "SDS"
    if "instrukcja stosowania" in blob or "instructions for use" in blob or re.search(r'\bifu\b', blob):
        return "IFU"
    if "ulotka" in blob:
        return "ulotka"
    return "strona"


DATE_RE = re.compile(r'\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b')
VERSION_RE = re.compile(r'\b(?:wersja|version)\b\s*[:\s]\s*([0-9]+(?:\.[0-9]+)*)', re.IGNORECASE)


def guess_version_or_date(text: str) -> str:
    m = VERSION_RE.search(text[:5000])
    if m:
        return f"wersja {m.group(1)}"
    m = DATE_RE.search(text[:5000])
    if m:
        return m.group(0)
    return ""


# --------------------------------------------------------------------------
# Nazewnictwo plikow
# --------------------------------------------------------------------------

def slugify(s: str, max_len: int = 60) -> str:
    s = normalize_for_match(s)
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s[:max_len].strip('-') or "plik"


def make_filename(marka: str, url: str, ext: str) -> str:
    parsed = urllib.parse.urlparse(url)
    domain = slugify(parsed.netloc, 30)
    path = slugify(parsed.path.rsplit("/", 1)[-1] or parsed.path, 40)
    base = f"{slugify(marka, 20)}-{domain}-{path}".strip("-")
    return f"{base}{ext}"


def guess_pl_from_metadata(title: str, desc: str, domain: str) -> bool:
    """Heurystyka PL wylacznie z metadanych wyszukiwania (bez pobierania strony) -
    uzywana w trybie bez --pobierz, gdzie nic nie sciagamy."""
    if domain.lower().endswith(".pl"):
        return True
    blob_raw = f"{title} {desc}"
    if re.search(r'[ąćęłńóśźż]', blob_raw.lower()):
        return True
    blob_norm = normalize_for_match(blob_raw)
    return any(normalize_for_match(w) in blob_norm for w in PL_HINT_WORDS)


def load_existing_sha256(manifest_path: Path) -> set[str]:
    shas: set[str] = set()
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                sha = (row.get("sha256") or "").strip()
                if sha:
                    shas.add(sha)
    return shas


# --------------------------------------------------------------------------
# Glowna logika
# --------------------------------------------------------------------------

def search_candidates(produkt: str, api_key: str, limit: int) -> list[dict]:
    """Wysyla zapytania do NodeHub i zwraca liste unikalnych kandydatow (metadane
    z wyszukiwarki - bez pobierania stron)."""
    queries = [t.format(produkt=produkt) for t in QUERY_TEMPLATES]
    seen_urls: set[str] = set()
    candidates: list[dict] = []

    for i, query in enumerate(queries, 1):
        print(f"[{i}/{len(queries)}] NodeHub: {query!r}")
        results = nodeshub_search(query, api_key)
        time.sleep(1.0)  # uprzejmy odstep miedzy zapytaniami do API

        for r in results[:limit]:
            url = r.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            title = r.get("title") or ""
            desc = r.get("description") or ""
            domain = urllib.parse.urlparse(url).netloc
            is_pdf_guess = url.lower().endswith(".pdf") or "pdf" in title.lower()
            pl_hint = guess_pl_from_metadata(title, desc, domain)
            candidates.append({
                "url": url,
                "title": title,
                "domain": domain,
                "is_pdf_guess": is_pdf_guess,
                "pl_hint": pl_hint,
                "query": query,
            })
            if len(candidates) >= MAX_CANDIDATES_TOTAL:
                break
        if len(candidates) >= MAX_CANDIDATES_TOTAL:
            print(f"  (osiagnieto twardy limit {MAX_CANDIDATES_TOTAL} kandydatow - przerywam dalsze zapytania)")
            break

    return candidates


def print_candidates(candidates: list[dict]) -> None:
    print()
    print("=== KANDYDACI (metadane z wyszukiwarki, nic nie pobrano) ===")
    if not candidates:
        print("- brak wynikow")
        return
    for c in candidates:
        print(
            f"- {c['url']}\n"
            f"    tytul: {c['title']!r} | domena: {c['domain']} | "
            f"PDF (zgadywane): {'tak' if c['is_pdf_guess'] else 'nie/?'} | "
            f"sugeruje PL: {'tak' if c['pl_hint'] else 'nie'}"
        )


def download_candidates(candidates: list[dict], produkt: str, marka_slug: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "_manifest.csv"
    existing_sha256 = load_existing_sha256(manifest_path)

    manifest_rows: list[dict] = []
    n_fetched = n_blocked = n_dup = n_errors = 0
    today = dt.date.today().isoformat()

    print()
    print(f"=== POBIERANIE do: {out_dir} ===")
    for c in candidates:
        url = c["url"]
        print(f"-> {url}")
        status, body, ctype, err = fetch_url(url)
        time.sleep(FETCH_DELAY_S)  # przerwa >=1 s miedzy pobraniami

        if err:
            n_errors += 1
            print(f"   BLAD pobierania: {err}")
            continue

        if is_blocked(status, body, ctype):
            n_blocked += 1
            print(f"   ZABLOKOWANE (status={status}) - nie zapisuje strony bledu.")
            print(
                "   PROPOZYCJA wiersza do BLOKADY-zrodel.md (nie dopisuje automatycznie - "
                "tylko do wklejenia recznie po weryfikacji):"
            )
            print(
                f"   | {today} | {produkt} | {url} | {status if status else 'N/A'} | "
                f"{c.get('title') or '(brak tytulu z wyszukiwarki)'} |"
            )
            continue

        if status != 200 or not body:
            n_errors += 1
            print(f"   BLAD status={status}, brak tresci - pomijam")
            continue

        sha256 = hashlib.sha256(body).hexdigest()
        if sha256 in existing_sha256:
            n_dup += 1
            print(f"   POMINIETO - duplikat sha256 juz w manifescie ({sha256[:12]}...)")
            continue

        is_pdf = (ctype and "pdf" in ctype.lower()) or url.lower().endswith(".pdf")
        if is_pdf:
            text = extract_text_from_pdf_bytes(body)
            ext = ".pdf"
        else:
            text = extract_text_from_html_bytes(body, ctype)
            ext = ".html"

        fname = make_filename(marka_slug, url, ext)
        fpath = out_dir / fname
        i2 = 2
        while fpath.exists():
            fpath = out_dir / f"{fname[:-len(ext)]}-{i2}{ext}"
            i2 += 1
        fpath.write_bytes(body)
        txt_path = out_dir / (fpath.stem + ".txt")
        txt_path.write_text(text, encoding="utf-8")

        lang_score = polish_language_score(text)
        jezyk_pl = lang_score >= 0.005 or bool(
            re.search(r'\b(karta|charakterystyki|zagrozenia|instrukcja)\b', normalize_for_match(text[:3000]))
        )
        wersja = guess_version_or_date(text)

        manifest_rows.append({
            "url": url,
            "plik": fpath.name,
            "data_pobrania": today,
            "rewizja": wersja,
            "sha256": sha256,
        })
        existing_sha256.add(sha256)
        n_fetched += 1
        print(f"   zapisano: {fpath.name} (jezyk_pl={jezyk_pl}, rewizja={wersja or '?'})")

    if manifest_rows:
        write_header = not manifest_path.exists()
        with open(manifest_path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["url", "plik", "data_pobrania", "rewizja", "sha256"], delimiter=";")
            if write_header:
                w.writeheader()
            for row in manifest_rows:
                w.writerow(row)

    print()
    print("=== PODSUMOWANIE POBIERANIA ===")
    print(f"Zapisanych nowych plikow: {n_fetched}")
    print(f"Pominietych (duplikat sha256 w manifescie): {n_dup}")
    print(f"Zablokowanych (propozycje wypisane wyzej, nic nie zapisano automatycznie): {n_blocked}")
    print(f"Bledow pobierania: {n_errors}")
    print(f"Manifest: {manifest_path}")


def run(produkt: str, marka: str, pobierz: bool, katalog: Path | None, limit: int) -> None:
    api_key = load_api_key()
    marka_slug = slugify(marka, 30)

    candidates = search_candidates(produkt, api_key, limit)
    print_candidates(candidates)

    if not pobierz:
        print()
        print(f"Tryb bez --pobierz: {len(candidates)} kandydatow, nic nie zapisano na dysk.")
        return

    out_dir = katalog if katalog else (DEFAULT_LIBRARY_ROOT / marka_slug)
    download_candidates(candidates, produkt, marka_slug, out_dir)


def main():
    ap = argparse.ArgumentParser(description="Szuka polskich zrodel (SDS/ulotka/IFU) dla produktu przez NodeHub.")
    ap.add_argument("produkt", help="Nazwa produktu, np. 'Sekusept Aktiv'")
    ap.add_argument("--marka", required=True, help="Marka/producent (slug), np. 'ecolab'")
    ap.add_argument("--pobierz", action="store_true", help="Pobiera kandydatow na dysk (bez tego - tylko lista)")
    ap.add_argument(
        "--katalog",
        help=(
            "Folder docelowy pobierania - NADPISUJE domyslna biblioteke projektu "
            "(04-opisy-produktow/zrodla/dezynfekcja/dokumenty/<marka>/). "
            "Uzywaj do testow, zeby nie pisac do biblioteki."
        ),
    )
    ap.add_argument("--limit", type=int, default=5, help="Maks. liczba wynikow branych z KAZDEGO zapytania (domyslnie 5)")
    args = ap.parse_args()

    katalog = Path(args.katalog) if args.katalog else None
    run(args.produkt, args.marka, args.pobierz, katalog, args.limit)


if __name__ == "__main__":
    main()
