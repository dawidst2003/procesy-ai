#!/usr/bin/env python3
"""P1 + F10 bez modelu: czy pliki, na które powołuje się karta, istnieją i mają zgodny wpis w _manifest.csv.

Dla każdej nazwy pliku z karty (.pdf .txt .html .png .jpg .webp .xlsx .zip .csv .json):
  - P1: plik istnieje w folderze marki (także w podfolderach),
  - F10: jest wiersz manifestu z tą nazwą, z URL (lub opisem pochodzenia), datą pobrania i rewizją,
  - F10: sha256 pliku = sha256 z manifestu.
Nazwa, która występuje w karcie wyłącznie jako końcówka adresu URL i nie ma takiego pliku, jest pomijana (to link, nie dowód).
Wynik = FLAGI do sprawdzenia przez kontrolę. Zastępuje ręczne liczenie sha256 przez agenta (od 2026-09-14).

Użycie: python _skrypty/karta_manifest_sha.py <karta.md> <folder dokumenty/marka> [<karta.md> <folder> ...]
"""
import csv, hashlib, io, os, re, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

EXT = r"(?:pdf|txt|html?|png|jpe?g|webp|xlsx|zip|csv|json)"
NAZWA = re.compile(r"[\w.,()+%\-]+\." + EXT + r"\b", re.I)
SHA = re.compile(r"^[0-9a-f]{64}$")


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def manifest(folder):
    """plik (lower) → lista wierszy (url, data, rewizja, sha)."""
    wynik = {}
    p = os.path.join(folder, "_manifest.csv")
    if not os.path.exists(p):
        return None
    for w in csv.reader(io.StringIO(open(p, encoding="utf-8", errors="replace").read()), delimiter=";"):
        if len(w) < 5 or w[1].strip().lower() in ("plik", "file"):
            continue
        sha = w[-1].strip().lower()
        wynik.setdefault(w[1].strip().lower(), []).append((w[0].strip(), w[2].strip(), ";".join(w[3:-1]).strip(), sha))
    return wynik


def pliki_folderu(folder):
    wynik = {}
    for root, _, files in os.walk(folder):
        if os.path.basename(root).startswith("_sedzia"):
            continue
        for f in files:
            wynik.setdefault(f.lower(), os.path.join(root, f))
    return wynik


def sprawdz(karta, folder):
    tekst = open(karta, encoding="utf-8").read()
    man = manifest(folder)
    pliki = pliki_folderu(folder)
    flagi, ok = [], 0
    if man is None:
        return [f"brak _manifest.csv w {folder}"], 0
    nazwy = {}
    for m in NAZWA.finditer(tekst):
        n = m.group(0)
        if n.lower() == "_manifest.csv":
            continue
        przed = tekst[max(0, m.start() - 1):m.start()]
        nazwy.setdefault(n.lower(), {"n": n, "poza_url": False})
        if przed != "/":
            nazwy[n.lower()]["poza_url"] = True
    # P1 tylko dla nazw w `backtickach` (tak autor wskazuje zapisany plik); nazwy z HTML sklepu, adresów i CSV z 01-dane pomijane
    w_backtick = {n.lower() for n in re.findall(r"`[^`\n]*?([\w.,()+%\-]+\." + EXT + r")`", tekst, re.I)}
    for klucz, info in sorted(nazwy.items()):
        if klucz not in pliki:
            # skróty typu „(+ `_clean.txt`)” to przyrostek do nazwy wyżej, nie osobny plik
            if (info["poza_url"] and klucz in w_backtick and not klucz.startswith(("produkty-", "_", "."))
                    and klucz not in ("linie.csv", "mapa-produktow.csv")  # pliki projektu, nie dowody
                    and ".." not in klucz and "…" not in klucz):  # nazwa skrócona wielokropkiem to odwołanie, nie plik
                flagi.append(f"P1 brak pliku: {info['n']}")
            continue
        wiersze = man.get(klucz)
        if not wiersze:
            flagi.append(f"F10 brak wpisu w manifeście: {info['n']}")
            continue
        s = sha256(pliki[klucz])
        if not any(w[3] == s for w in wiersze):
            zapis = ", ".join(w[3][:12] for w in wiersze)
            flagi.append(f"F10 sha256 niezgodny: {info['n']} (plik {s[:12]}…, manifest {zapis}…)")
            continue
        w = next(w for w in wiersze if w[3] == s)
        braki = [nazwa for nazwa, v in (("URL/pochodzenie", w[0]), ("data", w[1]), ("rewizja", w[2])) if not v]
        if braki:
            flagi.append(f"F10 niepełny wpis ({', '.join(braki)}): {info['n']}")
            continue
        ok += 1
    return flagi, ok


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2 or len(a) % 2:
        print(__doc__); sys.exit(2)
    zle = 0
    for karta, folder in zip(a[0::2], a[1::2]):
        flagi, ok = sprawdz(karta, folder)
        zle += bool(flagi)
        print(f"{os.path.basename(karta)}: plików zgodnych {ok}, flag {len(flagi)}")
        for f in flagi:
            print("   ", f)
    sys.exit(1 if zle else 0)
