#!/usr/bin/env python3
"""Znacznik × typ dokumentu (§1a) — klasa E05 z taksonomii 2026-09-17.

Reguła §1a: `[POTWIERDZONE]` wolno postawić tylko na dokumencie wytwórcy (producenta), importera,
autoryzowanego przedstawiciela tego wyrobu albo na rejestrze publicznym (URPL, EUDAMED).
Karta projekt odniesienia, reseller, dystrybutor-sklep, marketplace i „odcisk wariantu" to źródła handlowe —
same nie wystarczą.

Skrypt czyta tabelę dokumentów §3 (kolumny `#` / `Typ` / `URL` / `Plik lokalny`), przypisuje każdemu
dokumentowi typ, a potem dla każdego wiersza tabeli faktów (dowolna tabela z kolumną znacznika
i kolumną „Dok.") sprawdza znacznik wobec typów dokumentów tego wiersza.

Klasy flag:
  Z1  [POTWIERDZONE] w wierszu, w którym ŻADEN dokument z kolumny „Dok." nie jest typu
      wytwórca / importer / autoryzowany przedstawiciel / rejestr publiczny      — BLOKUJĄCA
  Z2~ [DO POTWIERDZENIA] w wierszu, który powołuje się WYŁĄCZNIE na dokument wytwórcy
      i NIE podaje powodu obniżenia (możliwe zaniżenie znacznika)                — informacyjna
  Z3~ [POTWIERDZONE] bez wskazania dokumentu albo z dokumentem, którego typu nie da się
      rozstrzygnąć z §3 (nierozpoznany token kolumny „Dok.")                     — informacyjna

Trafienie nie dowodzi naruszenia, a 0 trafień nie dowodzi zgodności: skrypt czyta TYP dokumentu
z §3, a nie jego treść. Wiersz mieszany (`[POTWIERDZONE] / [DO POTWIERDZENIA]`) jest liczony jako
[POTWIERDZONE] — jeśli w wierszu nie ma żadnego dokumentu właściwego typu, jest to flaga niezależnie
od tego, której części wiersza dotyczy.

Exit 1, gdy jest choć jedna flaga Z1.
Użycie: python _skrypty/karta_znacznik_zrodlo.py <karta.md> [<karta.md> ...] [--cicho] [--rejestr]
"""
import glob
import os
import re
import sys
import konfig  # profil projektu: tokeny naszego serwisu, jezyk rynku (weryfikacja.json)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# --- typy dokumentów ---------------------------------------------------------------------------------------
# rejestr publiczny — zawsze OK
REJESTR = re.compile(r"\burpl\b|eudamed|rejestr\w*\s+(?:wyrob|publiczn|medyczn)|"
                     r"europejsk\w*\s+baz\w*\s+danych", re.I)

# strona handlowa / sprzedawca — sama nie wystarczy pod [POTWIERDZONE]
HANDEL = re.compile("|".join(r"\b%s\b" % _t for _t in konfig.tokeny_wlasne()) +
                    r"|reseller|resellera|dystrybutor|sklep|marketplace|allegro|"
                    r"hurtowni|apteka|aptecz|\bsprzedawc|odcisk wariantu|e-?commerce", re.I)

# dokument wytwórcy — rozpoznawany po RODZAJU dokumentu, niezależnie od tego, kto go hostuje
# („dystrybutor z dokumentem wytwórcy" = OK: ulotka/IFU/karta techniczna na serwerze resellera)
WYTWORCA_MOCNE = re.compile(
    r"\bifu\b|instrukcj|ulotk|etykiet|karta techn|karta danych|product data sheet|\btds\b|\btd[-\s]?\d|"
    r"\bsds\b|karta charakterystyk|deklaracj|certyfikat|katalog|\bnorma\b|\bnormy\b|"
    r"dokument\w*\s+(?:wytwórc|producent)|stron[ay][^,;()]{0,18}(?:producent|wytwórc|marki|importer)|"
    r"autoryzowan|\bec\s?rep\b|\bimporter\b|\bimportera\b|\bwytwórc", re.I)

# rodzaje „średnie" — liczą się jako dokument wytwórcy tylko wtedy, gdy w opisie nie ma strony handlowej
WYTWORCA_SREDNIE = re.compile(r"opakowani|pudełk|\brender\b|renderu|piktogram|symbol", re.I)

ODNIESIENIE = re.compile(r"(?:odniesienie do|wycinek\s+(?:renderu|z)|jak\s+w|to samo co)\s*#\s*([0-9]+[a-z]?)", re.I)


def typ_dokumentu(opis, rozwiaz=None, glebokosc=0):
    """'rejestr' / 'wytworca' / 'handel' / '?' — z tekstu kolumny „Typ" (plus URL, jeśli podany w opisie)."""
    t = (opis or "").strip()
    if not t or t in {"—", "-", "–"}:
        return "?"
    m = ODNIESIENIE.search(t)
    if m and rozwiaz and glebokosc < 3:
        inny = rozwiaz(m.group(1))
        if inny:
            return typ_dokumentu(inny, rozwiaz, glebokosc + 1)
    if REJESTR.search(t):
        return "rejestr"
    handel = bool(HANDEL.search(t))
    if WYTWORCA_MOCNE.search(t):
        return "wytworca"
    if handel:
        return "handel"
    if WYTWORCA_SREDNIE.search(t):
        return "wytworca"
    return "?"


OK_TYPY = {"wytworca", "rejestr"}

# --- tabele ------------------------------------------------------------------------------------------------
SEPARATOR = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
KOL_ZNACZNIK = re.compile(r"znacznik|pewno", re.I)
KOL_DOK = re.compile(r"^\**dok\b|^\**dokument|^\**źród[łl]o", re.I)
KOL_NR = re.compile(r"^\**#\**$|^\**nr\**$|^\**lp\.?\**$", re.I)
KOL_TYP = re.compile(r"^\**typ\b", re.I)
KOL_URL = re.compile(r"url|adres|link", re.I)
KOL_PLIK = re.compile(r"plik", re.I)
SEK3 = re.compile(r"^#{2,}\s*3\.\s|^#{2,}\s*3\s*[.—–-]|dokumenty\s*$", re.I)

# Z2: wiersz, w którym autor PODAŁ powód obniżenia znacznika (dokument ogólny / inny REF / rozjazd /
# tożsamość nierozstrzygnięta / brak etykiety …), nie jest zaniżeniem — flaga jest wtedy tłumiona.
# Bez tego filtru Z2 na kartach sterylizacji i higieny dawało 57 trafień, wszystkie z uzasadnieniem w wierszu.
UZASADNIENIE = re.compile(
    r"ogóln|generyczn|poglądow|kontekstow|\bwniosek\b|wnioskowan|ekstrapolacj|nierozstrzygni|nieustalon|"
    r"rozjazd|nie przypisuje|nie powtarza|nie zawiera|nie precyzuje|nie określa|nie deklaruje|nie wskazano|"
    r"nie podaje|nie podano|nie wymienia|nie używa|nie opis|inn(?:y|ego|ym) (?:REF|wariant\w*|rozmiar\w*|SKU)|"
    r"tylko (?:strona|stronie|sklep|karta|karcie|zdjęci|wstęp|tekst|opis|#|z )|"
    r"\bbez\s|\bbrak\b|\[BRAK\]|\bpartii\b|niepotwierdzon|\bwprost\b|szukano|nie dotyczy|dla tego REF|"
    r"nie ten |nierozpoznan|jeśli |nie jest opisem", re.I)

POTW = re.compile(r"\[POTWIERDZONE\]")
DOPOT = re.compile(r"\[DO POTWIERDZENIA\]")
BRAK = re.compile(r"\[BRAK\]")

TOK_ZAKRES = re.compile(r"#\s*(\d+)\s*[–—-]\s*#?\s*(\d+)")
TOK_ID = re.compile(r"#\s*(\d+[a-z]?)")
TOK_TD = re.compile(r"\bTD[-\s]?(\d+)\b", re.I)


def komorki(linia):
    s = linia.strip()
    czesci = re.split(r"(?<!\\)\|", s)
    if s.startswith("|"):
        czesci = czesci[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        czesci = czesci[:-1]
    return [c.strip() for c in czesci]


def rejestr_dokumentow(linie):
    """{id -> (typ, opis)} z tabeli §3. Dodatkowo zwraca listę (id, opis, url, pliki) do dopasowań tekstowych."""
    surowe = {}          # id -> dict(opis, url, pliki)
    kod = False
    w_sek3 = False
    naglowek = None
    idx = {}
    for linia in linie:
        s = linia.strip()
        if s.startswith("```"):
            kod = not kod
            continue
        if kod:
            continue
        if s.startswith("#"):
            w_sek3 = bool(SEK3.search(s)) or bool(re.match(r"^#{2,}\s*3[.\s]", s))
            naglowek = None
            continue
        if not w_sek3 or not s.startswith("|"):
            if not s.startswith("|"):
                naglowek = None
            continue
        kom = komorki(linia)
        if SEPARATOR.match(s):
            continue
        if naglowek is None:
            if any(KOL_NR.match(c) for c in kom) and any(KOL_TYP.match(c) for c in kom):
                naglowek = kom
                idx = {
                    "nr": next(i for i, c in enumerate(kom) if KOL_NR.match(c)),
                    "typ": next(i for i, c in enumerate(kom) if KOL_TYP.match(c)),
                    "url": next((i for i, c in enumerate(kom) if KOL_URL.search(c)), None),
                    "plik": next((i for i, c in enumerate(kom) if KOL_PLIK.search(c)), None),
                }
            continue
        if len(kom) <= idx["typ"]:
            continue
        ident = re.sub(r"[^0-9a-z]", "", kom[idx["nr"]].lower())
        if not ident:
            continue
        surowe[ident] = {
            "opis": kom[idx["typ"]],
            "url": kom[idx["url"]] if idx["url"] is not None and idx["url"] < len(kom) else "",
            "plik": kom[idx["plik"]] if idx["plik"] is not None and idx["plik"] < len(kom) else "",
        }

    def rozwiaz(i):
        d = surowe.get(re.sub(r"[^0-9a-z]", "", i.lower()))
        return d["opis"] if d else None

    typy = {i: typ_dokumentu(d["opis"], rozwiaz) for i, d in surowe.items()}
    return typy, surowe


def pliki_dokumentu(d):
    """nazwy plików / domeny, po których można rozpoznać dokument w tekście kolumny „Dok.”."""
    klucze = set()
    for m in re.finditer(r"[\w\-.]+\.(?:pdf|html?|txt|png|jpe?g|webp)", d["plik"] + " " + d["url"], re.I):
        klucze.add(m.group(0).lower())
        klucze.add(os.path.splitext(m.group(0))[0].lower())
    for m in re.finditer(r"https?://(?:www\.)?([\w.-]+)", d["url"], re.I):
        klucze.add(m.group(1).lower())
    for m in TOK_TD.finditer(d["opis"]):
        klucze.add("td-" + m.group(1))
    return {k for k in klucze if len(k) >= 5}


def dokumenty_wiersza(tekst, typy, surowe):
    """[(etykieta, typ)] dla kolumny „Dok.”. Gdy nie ma tokenów #N — dopasowanie po pliku/domenie,
    a w ostateczności klasyfikacja samego tekstu komórki."""
    t = (tekst or "").strip()
    if not t or t in {"—", "-", "–", "n/d", "nie dotyczy"}:
        return []
    znalezione = []
    for a, b in TOK_ZAKRES.findall(t):
        for n in range(int(a), int(b) + 1):
            znalezione.append(str(n))
    bez_zakresow = TOK_ZAKRES.sub(" ", t)
    znalezione += TOK_ID.findall(bez_zakresow)
    wynik, widziane = [], set()
    for i in znalezione:
        k = re.sub(r"[^0-9a-z]", "", i.lower())
        if k in widziane:
            continue
        widziane.add(k)
        wynik.append(("#" + i, typy.get(k, "?")))
    if wynik:
        return wynik
    low = t.lower()
    for i, d in surowe.items():
        if any(k in low for k in pliki_dokumentu(d)):
            wynik.append(("#" + i, typy.get(i, "?")))
    if wynik:
        return wynik
    return [(t[:40], typ_dokumentu(t))]


def sprawdz(sciezka):
    with open(sciezka, encoding="utf-8") as f:
        linie = f.read().splitlines()
    typy, surowe = rejestr_dokumentow(linie)
    flagi = []   # (nr, klasa, opis, kontekst)

    kod = False
    w_sek3 = False
    naglowek = None
    kol_zn = kol_dok = None
    for nr, linia in enumerate(linie, 1):
        s = linia.strip()
        if s.startswith("```"):
            kod = not kod
            continue
        if kod:
            continue
        if s.startswith("#"):
            w_sek3 = bool(re.match(r"^#{2,}\s*3[.\s]", s))
            naglowek = None
            continue
        if not s.startswith("|"):
            naglowek = None
            continue
        if SEPARATOR.match(s):
            continue
        kom = komorki(linia)
        if naglowek is None:
            naglowek = kom
            kol_zn = next((i for i, c in enumerate(kom) if KOL_ZNACZNIK.search(c)), None)
            kol_dok = next((i for i, c in enumerate(kom) if KOL_DOK.search(c)), None)
            continue
        if w_sek3 or kol_zn is None or kol_dok is None:
            continue
        if kol_zn >= len(kom):
            continue
        zn = kom[kol_zn]
        dok_txt = kom[kol_dok] if kol_dok < len(kom) else ""
        if not (POTW.search(zn) or DOPOT.search(zn)):
            continue
        dokumenty = dokumenty_wiersza(dok_txt, typy, surowe)
        opisy = ", ".join(f"{e}={t}" for e, t in dokumenty) or "brak"
        pole = kom[0][:40] if kom else ""
        if POTW.search(zn):
            if not dokumenty:
                flagi.append((nr, "Z3", "[POTWIERDZONE] bez dokumentu w kol. Dok.", f"{pole} | Dok.: „{dok_txt[:40]}”"))
            elif any(t in OK_TYPY for _, t in dokumenty):
                continue
            elif all(t == "?" for _, t in dokumenty):
                flagi.append((nr, "Z3", "[POTWIERDZONE], typu dokumentu nie da się rozstrzygnąć z §3",
                              f"{pole} | {opisy}"))
            else:
                flagi.append((nr, "Z1", "[POTWIERDZONE] wyłącznie na źródle handlowym (nasz serwis/reseller/sklep)",
                              f"{pole} | {opisy}"))
        else:  # [DO POTWIERDZENIA] bez [POTWIERDZONE]
            if dokumenty and all(t in OK_TYPY for _, t in dokumenty) and not UZASADNIENIE.search(linia):
                flagi.append((nr, "Z2", "[DO POTWIERDZENIA] wyłącznie na dokumencie wytwórcy — możliwe zaniżenie",
                              f"{pole} | {opisy}"))
    return flagi, typy, surowe


EXIT_KLASY = {"Z1"}


def main(argv):
    cicho = False
    pokaz_rejestr = False
    pliki = []
    for a in argv:
        if a == "--cicho":
            cicho = True
        elif a == "--rejestr":
            pokaz_rejestr = True
        else:
            pliki.extend(sorted(glob.glob(a)) or [a])
    if not pliki:
        print(__doc__)
        return 2

    suma = {}
    blad = False
    karty_z_bledem = 0
    for p in pliki:
        flagi, typy, surowe = sprawdz(p)
        twarde = [f for f in flagi if f[1] in EXIT_KLASY]
        if twarde:
            blad = True
            karty_z_bledem += 1
        for f in flagi:
            suma[f[1]] = suma.get(f[1], 0) + 1
        if cicho and not flagi:
            continue
        print(f"== {p} — flag: {len(flagi)} (blokujących: {len(twarde)})")
        if pokaz_rejestr:
            for i in sorted(typy, key=lambda x: (len(x), x)):
                print(f"   §3 #{i}: {typy[i]:9s} ← {surowe[i]['opis'][:90]}")
        for nr, kl, opis, kontekst in flagi:
            print(f"  w.{nr} {kl}{'' if kl in EXIT_KLASY else '~'} {opis}: {kontekst}")
    print("\n== PODSUMOWANIE")
    print(f"kart: {len(pliki)}, z flagami blokującymi: {karty_z_bledem}")
    for k in sorted(suma):
        print(f"  {k}: {suma[k]}")
    print("(~ = flaga informacyjna, nie wpływa na exit code: Z2, Z3)")
    return 1 if blad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
