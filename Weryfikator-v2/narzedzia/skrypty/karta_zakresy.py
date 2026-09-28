#!/usr/bin/env python3
"""K5 bez modelu: wartości poza zakresem sensu w tabelach faktów karty.

Flagi (do sprawdzenia w źródle, nie werdykt):
  - procent > 100 albo g/100 g > 100,
  - zakres „a–b” (%, g, min, °C), gdzie a > b,
  - pH < 0 lub > 14,
  - temperatura < -60 °C lub > 650 °C (w trybie SDS: < -100 °C lub > 650 °C),
  - czas działania: sekundy > 3600, minuty > 1440, godziny > 72 — POMIJANE w trybie SDS.
Pomijane: sekcje 9–12 (rejestr pracy), wiersze-separatory tabel, numery norm (EN 14476), CAS, daty.

Tryb SDS (2026-09-16): wiersze dosłownej transkrypcji karty charakterystyki — sekcja
„### Karta charakterystyki §1–16" (i warianty „— sekcje uzupełniające §11/§12/§16") oraz
pojedyncze wiersze faktów oznaczone „(SDS §9)"/„(SDS §11)"/„(SDS §12)" — mają wyłączoną regułę
„czas poza zakresem" (testy ekotoksykologiczne 96 h/168 h/192 h/504 h to normalne czasy trwania
testów LC50/EC50, nie błąd) i poszerzoną dolną granicę temperatury do -100 °C (temperatury
topnienia bywają bardzo niskie). Nadal sprawdzane w tym trybie: % > 100, g/100 > 100, zakres
odwrócony, pH poza 0–14 — to błędy niepodważalne niezależnie od kontekstu.

Użycie: python _skrypty/karta_zakresy.py <karta.md> [<karta.md> ...]
"""
import os, re, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

L = r"(\d+(?:[.,]\d+)?)"
POMIN = re.compile(r"^#{2,}\s*(?:9|10|11|12)\b|poprawki|historia|ślad kroków", re.I)
NAGLOWEK_SDS = re.compile(r"karta charakterystyki", re.I)  # cała tabela dosłownej transkrypcji SDS §1–16
WIERSZ_SDS = re.compile(r"\(?\bSDS\s?§\s?(?:9|11|12)\b", re.I)  # pojedynczy wiersz faktów z SDS §9/§11/§12
SMIECI = re.compile(r"\b(?:PN-)?(?:EN|ISO|PN|DIN)\s?-?\d[\d\-:+ ]*|\b\d{2,7}-\d{2,3}-\d\b|\b\d{1,2}\.\d{1,2}\.\d{2,4}\b|\b(?:19|20)\d{2}\b")
BEZ_KODU = r"(?<![\w.,-])(?<![A-Za-z]\s)"  # liczba nie jest częścią kodu („FD 322”, „fd-322”) ani ułamka („0,5–4 %”)


def f(x):
    return float(x.replace(",", "."))


def sprawdz_linie(l, w_sds=False):
    s = SMIECI.sub(" ", re.sub(r"https?://\S+|%[0-9A-Fa-f]{2}", " ", l))  # adresy URL i kodowanie %20 to nie wartości
    fl = []
    for m in re.finditer(L + r"\s?%", s):
        if f(m.group(1)) > 100:
            fl.append(f"% > 100: {m.group(0)}")
    for m in re.finditer(L + r"\s?g\s?/\s?100\s?(?:g|ml)", s):
        if f(m.group(1)) > 100:
            fl.append(f"g/100 > 100: {m.group(0)}")
    for m in re.finditer(BEZ_KODU + L + r"\s?[–-]\s?<?\s?" + L + r"\s?(%|g\b|min\b|°C|ºC)", s):
        if f(m.group(2)) < f(m.group(1)) <= 1000:
            fl.append(f"zakres odwrócony: {m.group(0)}")
    # zakres czasu z jednostką powtórzoną przy obu liczbach („5 min–1 min”, „10 h–2 h”) — odwrócony zakres, sprawdzane zawsze (też w trybie SDS)
    for m in re.finditer(BEZ_KODU + L + r"\s?(sek(?:und)?\w*|min(?:ut)?\w*|godz\w*|h)\s?[–-]\s?" + L + r"\s?(sek(?:und)?\w*|min(?:ut)?\w*|godz\w*|h)", s, re.I):
        j1, j2 = m.group(2).lower()[:3], m.group(4).lower()[:3]
        if j1 == j2 and f(m.group(3)) < f(m.group(1)):
            fl.append(f"zakres odwrócony (czas): {m.group(0)}")
    # pH: pierwsza liczba po „pH” w obrębie 12 znaków, która nie jest stężeniem ani temperaturą pomiaru („pH (50 g/l)”, „pH w 20 °C”)
    PO = r"(?![\d.,])(?!\s?(?:g\s?/?\s?l|g\b|°|ºC|%|ml|mg|kg))"
    for m in re.finditer(r"\bpH\b[^\d\n]{0,12}?" + BEZ_KODU + L + PO + r"(?:\s?[–-]\s?" + L + PO + r")?", s):
        for g in (m.group(1), m.group(2)):
            if g and not 0 <= f(g) <= 14:
                fl.append(f"pH poza 0–14: {m.group(0)}")
    # temperatura: samozapłon bywa > 400 °C, więc górna granica 650 °C; w trybie SDS dolna -100 °C (topnienie bywa bardzo niskie)
    dol_temp = -100 if w_sds else -60
    for m in re.finditer(r"((?<![\d\s])-\s?\d+(?:[.,]\d+)?|(?<![\d.,])\d+(?:[.,]\d+)?)\s?(?:°C|ºC|° C)", s):
        v = f(m.group(1).replace(" ", ""))
        if v < dol_temp or v > 650:
            fl.append(f"temperatura poza {dol_temp}…650 °C: {m.group(0)}")
    # czas działania: w trybie SDS pomijane — 96/168/192/504 h to normalne czasy testów LC50/EC50 (SDS §11–12), nie błąd
    if not w_sds:
        for m in re.finditer(L + r"\s?(sek(?:und)?\w*|s\b|min(?:ut)?\w*|h\b|godz\w*)", s):
            v, j = f(m.group(1)), m.group(2).lower()
            if (j.startswith("s") and v > 3600) or (j.startswith("min") and v > 1440) or (j in ("h",) or j.startswith("godz")) and v > 72:
                fl.append(f"czas poza zakresem: {m.group(0)}")
    return fl


def sprawdz(karta):
    wynik, pomijaj, poziom = [], False, 0
    sds_tryb, sds_poziom = False, 0
    for nr, l in enumerate(open(karta, encoding="utf-8"), 1):
        s = l.lstrip()
        if s.startswith("#"):
            lvl = len(s) - len(s.lstrip("#"))
            if pomijaj and lvl <= poziom:
                pomijaj = False
            if sds_tryb and lvl <= sds_poziom:
                sds_tryb = False
            if not pomijaj and POMIN.search(s):
                pomijaj, poziom = True, lvl
            elif not pomijaj and not sds_tryb and NAGLOWEK_SDS.search(s):
                sds_tryb, sds_poziom = True, lvl
            continue
        if pomijaj or not s.startswith("|") or re.match(r"^\|[\s:|-]+\|?\s*$", s):
            continue
        w_sds = sds_tryb or bool(WIERSZ_SDS.search(l))
        for x in sprawdz_linie(l, w_sds):
            wynik.append(f"w.{nr}: {x}")
    return wynik


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    zle = 0
    for k in sys.argv[1:]:
        fl = sprawdz(k)
        zle += bool(fl)
        print(f"{os.path.basename(k)}: {'OK' if not fl else str(len(fl)) + ' FLAG K5'}")
        for x in fl:
            print("   ", x)
    sys.exit(1 if zle else 0)
