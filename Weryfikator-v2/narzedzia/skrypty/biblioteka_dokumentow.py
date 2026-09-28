#!/usr/bin/env python3
"""Kontrola biblioteki dowodów: foldery `dokumenty/<marka>/` w kategoriach kart faktów.

Łapie błędy, które w poprzednich partiach kosztowały rundy poprawek — zanim trafią do karty:

  1. SKANY      .txt o rozmiarze 0 albo krótszy niż ~500 znaków przy PDF > 50 kB
                → „skan bez warstwy tekstu — wymaga renderu i transkrypcji”.
                Dodatkowo INFO: PDF > 50 kB, do którego w ogóle nie ma .txt.
  2. DUPLIKATY  pliki o tym samym sha256 pod różnymi nazwami (np. jedno zdjęcie
                podpięte pod kilka wariantów) — lista grup; na końcu także między markami.
  3. MANIFEST   pliki na dysku bez wpisu w `_manifest.csv`; wpisy bez pliku;
                wpisy z niezgodnym sha256; puste wiersze; brakujące kolumny;
                daty pobrania w przyszłości.
                PLIKI POCHODNE własnego wpisu NIE wymagają (ustalenie 2026-09-17):
                pochodna to plik, którego nazwa zaczyna się od nazwy pliku źródłowego
                mającego wpis w manifeście — `x.pdf` → `x.txt`, `x_page_3.png`, `x-crop.png`.
                Pochodna źródła, którego w manifeście NIE ma (np. render z niezapisanego
                PDF-a), jest zgłaszana jak każda sierota.
  4. RENDERS    PNG/JPG bez wpisu w manifeście i bez zapisanego źródła — dowód
                niezapisany w rejestrze.
  5. JĘZYK      dla .txt prosta detekcja PL/EN/DE i porównanie z oznaczeniem języka
                w kolumnie `rewizja` albo w końcówce nazwy pliku (`-pl`/`-en`/`-de`).
                TYLKO FLAGA — nie wpływa na kod wyjścia.

Użycie:
    python _skrypty/biblioteka_dokumentow.py <folder kategorii albo folder marki> [--napraw-manifest]

    Argumentem może być: folder kategorii (np. `zrodla/sterylizacja`), sam folder
    `.../dokumenty` albo pojedynczy folder marki (`.../dokumenty/medal`).

    --napraw-manifest   usuwa puste wiersze i przelicza sha256 TAM I TYLKO TAM, gdzie
                        wpis jest, plik jest, a suma się nie zgadza. Każda zmiana jest
                        wypisana. Nic innego w manifeście nie jest ruszane (kolejność,
                        odstępy, treść pozostałych kolumn zostają bez zmian).
                        Wpisów nie dopisuje i nie usuwa — to decyzja człowieka.

Kart (`*.md`) skrypt nie czyta i nie zmienia.
Kod wyjścia: 1, gdy są pozycje z sekcji 1–4; 0, gdy czysto (sama flaga języka nie psuje wyniku).
"""
import hashlib
import os
import re
import sys
from collections import defaultdict
from datetime import date

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

MANIFEST = "_manifest.csv"
KOLUMNY = ["url", "plik", "data_pobrania", "rewizja", "sha256"]
PDF_PROG = 50 * 1024      # PDF większy niż to → oczekujemy sensownej warstwy tekstu
TXT_PROG = 500            # mniej znaków w .txt → podejrzenie skanu
OBRAZY_DOWOD = (".png", ".jpg", ".jpeg")
DZIS = date.today()

# ── język ────────────────────────────────────────────────────────────────────
PL_ZNAKI = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
DE_ZNAKI = set("äöüßÄÖÜ")
SLOWA = {
    "pl": ("w", "i", "na", "nie", "do", "się", "jest", "oraz", "dla", "że", "przez",
           "lub", "z", "po", "przed", "produkt", "opakowanie", "stosowanie", "sterylizacji"),
    "en": ("the", "and", "of", "to", "for", "with", "is", "are", "not", "this", "that",
           "be", "as", "on", "or", "from", "product", "use"),
    "de": ("der", "die", "das", "und", "für", "mit", "von", "nicht", "ist", "werden",
           "bei", "oder", "den", "dem", "eine", "auf", "zur", "produkt"),
}
LANG_REWIZJA = re.compile(
    r"(?<![A-Za-zĄ-ż])(PL|EN|DE|polski|polska|polskie|angielski|angielska|niemiecki|niemiecka|"
    r"english|deutsch|german)(?![A-Za-zĄ-ż])", re.I)
LANG_SLOWO = {"pl": "pl", "polski": "pl", "polska": "pl", "polskie": "pl",
              "en": "en", "angielski": "en", "angielska": "en", "english": "en",
              "de": "de", "niemiecki": "de", "niemiecka": "de", "deutsch": "de", "german": "de"}
LANG_NAZWA = re.compile(r"-(pl|en|de)$", re.I)


def sha256(sciezka):
    h = hashlib.sha256()
    with open(sciezka, "rb") as f:
        for kawalek in iter(lambda: f.read(1 << 20), b""):
            h.update(kawalek)
    return h.hexdigest()


def czytaj_txt(sciezka):
    try:
        with open(sciezka, "rb") as f:
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def wykryj_jezyk(tekst):
    """Zwraca 'pl'/'en'/'de' albo None, gdy za mało danych lub remis."""
    probka = tekst[:20000]
    slowa = re.findall(r"[A-Za-zÄÖÜäöüßĄ-ż]+", probka.lower())
    if len(slowa) < 30:
        return None
    ile = len(slowa)
    punkty = {j: sum(1 for s in slowa if s in zbior) / ile for j, zbior in
              ((j, set(w)) for j, w in SLOWA.items())}
    znaki = len(probka) or 1
    punkty["pl"] += 3.0 * sum(1 for z in probka if z in PL_ZNAKI) / znaki
    punkty["de"] += 2.0 * sum(1 for z in probka if z in DE_ZNAKI) / znaki
    ranking = sorted(punkty.items(), key=lambda x: -x[1])
    (najl, p1), (_, p2) = ranking[0], ranking[1]
    if p1 < 0.02 or p1 < p2 * 1.3:      # za słabo albo zbyt blisko — nie zgaduj
        return None
    return najl


def deklarowany_jezyk(plik, rewizja):
    """Oznaczenie języka z kolumny rewizja/opis albo z końcówki nazwy pliku."""
    m = LANG_REWIZJA.search(rewizja or "")
    if m:
        return LANG_SLOWO[m.group(1).lower()], "rewizja"
    m = LANG_NAZWA.search(os.path.splitext(os.path.basename(plik))[0])
    if m:
        return m.group(1).lower(), "nazwa pliku"
    return None, None


# ── manifest ─────────────────────────────────────────────────────────────────
def wczytaj_manifest(folder):
    """Zwraca (wiersze, puste, ulomne, naglowek) albo None, gdy nie ma pliku.

    wiersz = dict(nr, url, plik, data, rewizja, sha) — `rewizja` scala pola środkowe,
    bo w opisach bywa średnik (manifest nie jest cytowany).
    """
    p = os.path.join(folder, MANIFEST)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8", errors="replace", newline="") as f:
        linie = f.read().split("\n")
    wiersze, puste, ulomne, naglowek = [], [], [], None
    for nr, linia in enumerate(linie, start=1):
        surowa = linia.rstrip("\r")
        if not surowa.strip():
            if nr < len(linie) or surowa:       # ostatnia pusta linia = zwykły koniec pliku
                puste.append(nr)
            continue
        # zwykły split, nie csv: manifest nie jest cytowany, a w opisach bywają
        # średniki i cudzysłowy — parser CSV by je zjadł
        pola = surowa.split(";")
        if naglowek is None:
            naglowek = [x.strip().lower() for x in pola]
            continue
        if len(pola) < 5:
            ulomne.append((nr, surowa))
            continue
        wiersze.append({"nr": nr, "url": pola[0].strip(), "plik": pola[1].strip(),
                        "data": pola[2].strip(), "rewizja": ";".join(pola[3:-1]).strip(),
                        "sha": pola[-1].strip().lower()})
    return wiersze, puste, ulomne, naglowek


def napraw_manifest(folder, pliki_dysk):
    """Usuwa puste wiersze, przelicza sha256 przy rozjeździe. Zwraca listę opisów zmian."""
    p = os.path.join(folder, MANIFEST)
    with open(p, encoding="utf-8", errors="replace", newline="") as f:
        tresc = f.read()
    linie = tresc.split("\n")
    wynik, zmiany, naglowek_byl = [], [], False
    for nr, linia in enumerate(linie, start=1):
        crlf = linia.endswith("\r")           # zakończenie wiersza zostaje takie, jakie było
        surowa = linia.rstrip("\r")
        if not surowa.strip():
            if nr == len(linie):
                continue                      # końcowy znak nowej linii — nie jest pustym wierszem
            zmiany.append(f"wiersz {nr}: usunięto pusty wiersz")
            continue
        pola = surowa.split(";")
        if not naglowek_byl:
            naglowek_byl = True
            wynik.append(surowa + ("\r" if crlf else ""))
            continue
        if len(pola) >= 5:
            nazwa = pola[1].strip()
            sciezka = pliki_dysk.get(nazwa.lower()) or pliki_dysk.get(os.path.basename(nazwa).lower())
            if sciezka:
                realny = sha256(sciezka)
                stary = pola[-1].strip().lower()
                if stary != realny:
                    zmiany.append(f"wiersz {nr}: {nazwa} — sha256 {stary[:12] or '(puste)'}… → {realny[:12]}…")
                    pola[-1] = realny
                    surowa = ";".join(pola)
        wynik.append(surowa + ("\r" if crlf else ""))
    if zmiany:
        # każdy element `wynik` niesie własne "\r" (albo nie) — złączenie "\n" odtwarza CRLF/LF 1:1
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write("\n".join(wynik) + "\n")
    return zmiany


# ── zbieranie plików ─────────────────────────────────────────────────────────
def pliki_marki(folder):
    """Ścieżka względna (z '/') → ścieżka bezwzględna. Pomija foldery `_*` i sam manifest."""
    wynik = {}
    for root, katalogi, pliki in os.walk(folder):
        katalogi[:] = [k for k in katalogi if not k.startswith("_")]
        for f in pliki:
            if f == MANIFEST:
                continue
            wzgl = os.path.relpath(os.path.join(root, f), folder).replace("\\", "/")
            wynik[wzgl] = os.path.join(root, f)
    return wynik


def znajdz_marki(cel):
    """Rozpoznaje, czy dostaliśmy kategorię, folder `dokumenty` czy pojedynczą markę."""
    cel = os.path.abspath(cel)
    if not os.path.isdir(cel):
        sys.exit(f"Nie ma takiego folderu: {cel}")
    if os.path.isdir(os.path.join(cel, "dokumenty")):
        cel = os.path.join(cel, "dokumenty")
    if os.path.basename(cel).lower() == "dokumenty":
        marki = [os.path.join(cel, d) for d in sorted(os.listdir(cel))
                 if os.path.isdir(os.path.join(cel, d)) and not d.startswith("_")]
        return cel, marki
    return os.path.dirname(cel), [cel]


# ── kontrola jednej marki ────────────────────────────────────────────────────
def sprawdz_marke(folder, naprawiaj):
    marka = os.path.basename(folder)
    pliki = pliki_marki(folder)
    sumy = {wzgl: sha256(sciezka) for wzgl, sciezka in sorted(pliki.items())}
    rozmiary = {wzgl: os.path.getsize(sciezka) for wzgl, sciezka in pliki.items()}
    # klucz wyszukiwania po nazwie pliku (manifest zapisuje same nazwy, bez podfolderu)
    wg_nazwy = defaultdict(list)
    for wzgl in pliki:
        wg_nazwy[os.path.basename(wzgl).lower()].append(wzgl)
        wg_nazwy[wzgl.lower()].append(wzgl)

    raport = {"marka": marka, "folder": folder, "skany": [], "info_pdf": [], "duplikaty": [],
              "manifest": [], "renders": [], "jezyk": [], "naprawy": [], "pochodne": [],
              "liczba_plikow": len(pliki), "sumy": sumy}

    # 1. SKANY
    for wzgl in sorted(pliki):
        if not wzgl.lower().endswith(".txt"):
            continue
        rozmiar = rozmiary[wzgl]
        pdf = wzgl[:-4] + ".pdf"
        pdf_duzy = pdf in rozmiary and rozmiary[pdf] > PDF_PROG
        if rozmiar == 0:
            raport["skany"].append(f"{wzgl}: 0 B — skan bez warstwy tekstu — wymaga renderu i transkrypcji")
            continue
        if pdf_duzy:
            znaki = len(czytaj_txt(pliki[wzgl]).strip())
            if znaki < TXT_PROG:
                raport["skany"].append(
                    f"{wzgl}: {znaki} znaków przy PDF {rozmiary[pdf] // 1024} kB "
                    f"— skan bez warstwy tekstu — wymaga renderu i transkrypcji")
    for wzgl in sorted(pliki):
        if wzgl.lower().endswith(".pdf") and rozmiary[wzgl] > PDF_PROG and (wzgl[:-4] + ".txt") not in pliki:
            raport["info_pdf"].append(f"{wzgl}: PDF {rozmiary[wzgl] // 1024} kB bez pliku .txt (brak transkrypcji)")

    # 2. DUPLIKATY TREŚCI
    wg_sumy = defaultdict(list)
    for wzgl, s in sumy.items():
        wg_sumy[s].append(wzgl)
    for s, lista in sorted(wg_sumy.items()):
        if len(lista) > 1:
            raport["duplikaty"].append(f"sha {s[:12]}… — {len(lista)} plików: " + ", ".join(sorted(lista)))

    # 3. MANIFEST
    dane = wczytaj_manifest(folder)
    if dane is None:
        raport["manifest"].append(f"BRAK pliku {MANIFEST} — {len(pliki)} plików bez rejestru")
        raport["wpisy"] = {}
        return raport
    wiersze, puste, ulomne, naglowek = dane
    raport["wpisy"] = {w["plik"].lower(): w for w in wiersze}

    if naglowek is None:
        raport["manifest"].append("manifest bez nagłówka kolumn")
    else:
        brak_kol = [k for k in KOLUMNY if k not in naglowek]
        if brak_kol:
            raport["manifest"].append(f"nagłówek — brakujące kolumny: {', '.join(brak_kol)} (jest: {';'.join(naglowek)})")
    for nr in puste:
        raport["manifest"].append(f"wiersz {nr}: pusty wiersz")
    for nr, tresc in ulomne:
        raport["manifest"].append(f"wiersz {nr}: brakujące kolumny ({tresc[:70]}…)")

    w_manifescie = set()
    for w in wiersze:
        nazwa = w["plik"]
        trafienia = wg_nazwy.get(nazwa.lower()) or wg_nazwy.get(os.path.basename(nazwa).lower())
        if not trafienia:
            raport["manifest"].append(f"wiersz {w['nr']}: wpis bez pliku na dysku — {nazwa}")
            continue
        wzgl = trafienia[0]
        w_manifescie.add(wzgl)
        if w["sha"] != sumy[wzgl]:
            raport["manifest"].append(
                f"wiersz {w['nr']}: sha256 niezgodny — {nazwa} "
                f"(plik {sumy[wzgl][:12]}…, manifest {w['sha'][:12] or '(puste)'}…)")
        if w["data"]:
            try:
                if date.fromisoformat(w["data"]) > DZIS:
                    raport["manifest"].append(f"wiersz {w['nr']}: data pobrania w przyszłości — {w['data']} ({nazwa})")
            except ValueError:
                raport["manifest"].append(f"wiersz {w['nr']}: data pobrania nie jest datą ISO — „{w['data']}” ({nazwa})")

    # pliki pochodne (ustalenie 2026-09-17) — nazwa zaczyna się od nazwy zapisanego źródła
    zrodla = sorted({os.path.splitext(os.path.basename(w["plik"]))[0].lower() for w in wiersze if w["plik"]},
                    key=len, reverse=True)
    bez_wpisu, sieroty = sorted(set(pliki) - w_manifescie), []
    for wzgl in bez_wpisu:
        rdzen = os.path.splitext(os.path.basename(wzgl))[0].lower()
        zrodlo = next((z for z in zrodla if rdzen == z or
                       (rdzen.startswith(z) and rdzen[len(z)] in "-_.,")), None)
        if zrodlo:
            raport["pochodne"].append(f"{wzgl} ← {zrodlo}")
        else:
            sieroty.append(wzgl)
            raport["manifest"].append(f"plik bez wpisu i bez zapisanego źródła — {wzgl}")

    # 4. RENDERS / obrazy dowodowe bez wpisu i bez zapisanego źródła
    for wzgl in sieroty:
        if wzgl.lower().endswith(OBRAZY_DOWOD):
            raport["renders"].append(f"{wzgl} — dowód niezapisany w rejestrze")

    # 5. JĘZYK (tylko flaga)
    for wzgl in sorted(pliki):
        if not wzgl.lower().endswith(".txt") or rozmiary[wzgl] == 0:
            continue
        wykryty = wykryj_jezyk(czytaj_txt(pliki[wzgl]))
        if not wykryty:
            continue
        w = raport["wpisy"].get(wzgl.lower()) or raport["wpisy"].get(os.path.basename(wzgl).lower())
        deklar, skad = deklarowany_jezyk(wzgl, w["rewizja"] if w else "")
        if deklar and deklar != wykryty:
            raport["jezyk"].append(f"{wzgl}: treść wygląda na {wykryty.upper()}, oznaczenie mówi {deklar.upper()} ({skad})")

    # NAPRAWA
    if naprawiaj:
        raport["naprawy"] = napraw_manifest(folder, {k: pliki[v[0]] for k, v in wg_nazwy.items()})
    return raport


# ── wypis ────────────────────────────────────────────────────────────────────
SEKCJE = [("skany", "1. SKANY"), ("duplikaty", "2. DUPLIKATY TREŚCI"),
          ("manifest", "3. MANIFEST"), ("renders", "4. RENDERS / obrazy bez wpisu")]


def wypisz(r):
    bledy = sum(len(r[k]) for k, _ in SEKCJE)
    stan = "OK" if bledy == 0 else f"{bledy} pozycji"
    print(f"\n=== {r['marka']}  ({r['liczba_plikow']} plików) — {stan}")
    for klucz, tytul in SEKCJE:
        if r[klucz]:
            print(f"  {tytul} [{len(r[klucz])}]")
            for x in r[klucz]:
                print(f"     - {x}")
    if r["info_pdf"]:
        print(f"  INFO (nie liczone do wyniku) [{len(r['info_pdf'])}]")
        for x in r["info_pdf"]:
            print(f"     - {x}")
    if r["pochodne"]:
        print(f"  POCHODNE bez własnego wpisu — OK wg ustalenia 2026-09-17 [{len(r['pochodne'])}]")
    if r["jezyk"]:
        print(f"  5. JĘZYK — tylko flaga [{len(r['jezyk'])}]")
        for x in r["jezyk"]:
            print(f"     - {x}")
    if r["naprawy"]:
        print(f"  NAPRAWIONO w manifeście [{len(r['naprawy'])}]")
        for x in r["naprawy"]:
            print(f"     * {x}")
    return bledy


def main():
    argumenty = [a for a in sys.argv[1:] if not a.startswith("--")]
    flagi = [a for a in sys.argv[1:] if a.startswith("--")]
    nieznane = [f for f in flagi if f != "--napraw-manifest"]
    if len(argumenty) != 1 or nieznane:
        print(__doc__)
        sys.exit(2)
    naprawiaj = "--napraw-manifest" in flagi

    baza, marki = znajdz_marki(argumenty[0])
    if not marki:
        sys.exit(f"Brak folderów marek w {baza}")
    print(f"BIBLIOTEKA DOKUMENTÓW — {baza}")
    print(f"marek: {len(marki)}   tryb: {'kontrola + naprawa manifestu' if naprawiaj else 'kontrola (tylko odczyt)'}")

    raporty, bledy_razem = [], 0
    for folder in marki:
        r = sprawdz_marke(folder, naprawiaj)
        raporty.append(r)
        bledy_razem += wypisz(r)

    # duplikaty między markami
    miedzy = defaultdict(list)
    for r in raporty:
        for wzgl, s in r["sumy"].items():
            miedzy[s].append(f"{r['marka']}/{wzgl}")
    krzyzowe = [(s, lista) for s, lista in sorted(miedzy.items())
                if len({x.split("/", 1)[0] for x in lista}) > 1]

    print("\n" + "=" * 70)
    print("PODSUMOWANIE")
    for r in raporty:
        czesci = [f"{len(r[k])} {t.split('. ', 1)[-1].split(' /')[0].lower()}" for k, t in SEKCJE if r[k]]
        stan = ", ".join(czesci) if czesci else "czysto"
        dod = []
        if r["pochodne"]:
            dod.append(f"{len(r['pochodne'])} pochodnych")
        if r["jezyk"]:
            dod.append(f"{len(r['jezyk'])} flag języka")
        if r["info_pdf"]:
            dod.append(f"{len(r['info_pdf'])} INFO")
        if r["naprawy"]:
            dod.append(f"{len(r['naprawy'])} napraw")
        print(f"  {r['marka']:<30} {stan}" + (f"   ({'; '.join(dod)})" if dod else ""))
    if krzyzowe:
        print(f"\n  DUPLIKATY MIĘDZY MARKAMI [{len(krzyzowe)}] — ten sam plik w dwóch markach:")
        for s, lista in krzyzowe:
            print(f"     - sha {s[:12]}…: " + ", ".join(sorted(lista)))
    print(f"\n  RAZEM pozycji 1–4: {bledy_razem}")
    print(f"  plików pochodnych uznanych bez wpisu: {sum(len(r['pochodne']) for r in raporty)}")
    print(f"  flag języka (poza wynikiem): {sum(len(r['jezyk']) for r in raporty)}")
    sys.exit(1 if bledy_razem else 0)


if __name__ == "__main__":
    main()
