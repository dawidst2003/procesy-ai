#!/usr/bin/env python3
"""C6 — negacja = dowód (+ twierdzenia zgodności K4b). Wypisuje każde twierdzenie negatywne karty ([BRAK], „brak",
„nie podaje", „sekcja pusta", „nie zawiera", „nie dotyczy", „nie określ…") oraz twierdzenia zgodności („ta sama karta",
„identyczne", „wyklucza") i dla każdego szuka słów kluczowych wiersza w plikach .txt/.html marki.

To lista do ręcznej weryfikacji, nie werdykt: trafienia = miejsca, które kontrola MUSI otworzyć; 0 trafień nie dowodzi
braku (inne słownictwo, inny język, obraz). Brak wskazania „szukano w" / dokumentu z miejscem w wierszu = flaga.

v2 (2026-09-14) — mniej szumu, te same twierdzenia o faktach. Pomijane, bo to nie są twierdzenia autora o faktach:
  - sekcje „9. Ślad kroków”, „10. Poprawki…”, „11.”, „12.” i każda sekcja z „Poprawki” / „Historia” w nagłówku,
  - wiersze tabeli C7 (dosłowne zdania źródła); uwagi autora pod tabelą zostają,
  - nagłówki tabel i wiersze-separatory.
Wskazanie źródła rozpoznaje numerację dokumentów D#, W#, M#, #n z miejscem (§, s., str., l., w., sekcja).
Regresja v1→v2: znane błędy z testu szczelności 2026-09-14 i kontroli Dürr nadal są na liście.

v3 (2026-09-17) — dołożona sekcja **N: negacja = dowód** (klasa E04 taksonomii). Część v2 działa bez zmian.
Sekcja N bierze tylko mocne negacje („żaden dokument nie…", „brak w dokumentach", „nie występuje w żadnym",
„nie deklaruje", „katalog nie podaje"), wyciąga z wiersza słowo kluczowe (fraza po „nie" / cytowany termin /
symbol), sprawdza je w plikach .txt dokumentów z §3 karty (i w transkrypcjach renderów) i zgłasza FLAGĘ
„negacja przeczona przez dokument" z plikiem i linią. N1 = trafienie w dokumencie, o którym mówi wiersz;
N2~ = trafienie poza zadeklarowanym zakresem wiersza (informacyjne). Dokumenty bez warstwy tekstu są
zgłaszane osobno jako „nieweryfikowalne — skan".

Użycie: python _skrypty/karta_negacje.py <karta.md> <folder dokumenty/marka albo .../dokumenty>
        [--tylko-n] [--bramka]      (--bramka: exit 1 przy flagach N1; domyślnie exit 0 jak w v2)
"""
import glob, html, os, re, sys
import konfig  # profil projektu: tokeny naszego serwisu, jezyk rynku (weryfikacja.json)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

NEG = re.compile(r"\[BRAK\]|\bbrak\b|nie poda|nie podano|sekcja pusta|pust[ay]\b|nie zawiera|nie dotyczy|nie określ|"
                 r"nie wymienia|nie deklaruj|not (?:available|applicable|determined|specified)|keine angaben|"
                 r"nicht (?:anwendbar|bestimmt)|ta sama karta|te same sformułowania|identyczn|wyklucza", re.I)
POMIN_SEKCJE = re.compile(r"^#{2,}\s*(?:9|10|11|12)\b|poprawki|historia|ślad kroków", re.I)
C7 = re.compile(r"\bC7\b")
SEPARATOR = re.compile(r"^\|[\s:|-]+\|?\s*$")
WSKAZANIE = re.compile(r"szukano w|sprawdzono w|przeczytano|"
                       r"(?:\b[DWM]\d{1,2}\b|#\d+)[^|\n]{0,60}?(?:§|\bs\.|str\.|sekcj|\bl\.|\bw\.|stron)|"
                       r"§\s?\d+(?:\.\d+)?[^|\n]{0,20}\b[DWM]\d{1,2}\b", re.I)
STOP = set("brak nie podaje podano sekcja pusta zawiera dotyczy określono określa wymienia deklaruje dokument dokumencie "
           "szukano karta karty jest oraz lub dla przy bez tego ta ten się jako potwierdzone potwierdzenia sds ulotka "
           "strona producenta wartość cytat sama same identyczne wyklucza".split())


def korpus(folder):
    teksty = {}
    for p in glob.glob(os.path.join(folder, "*.txt")) + glob.glob(os.path.join(folder, "*.htm*")):
        t = open(p, encoding="utf-8", errors="replace").read()
        if p.lower().endswith((".htm", ".html")):
            t = re.sub(r"<!--.*?-->|<(script|style)\b.*?</\1>", " ", t, flags=re.S | re.I)
            t = html.unescape(re.sub(r"<[^>]+>", " ", t))
        teksty[os.path.basename(p)] = re.sub(r"\s+", " ", t).lower()
    return teksty


def slowa(wiersz):
    kom = [k.strip() for k in wiersz.strip("|").split("|")]
    glowa = kom[0] if len(kom) > 1 else wiersz
    w = re.findall(r"[a-ząćęłńóśźżäöüß]{4,}|§\s?\d+(?:\.\d+)?|\b[HP]\d{3}\b", glowa.lower())
    return [x for x in w if x not in STOP][:4]


def twierdzenia(linie):
    """Numery linii (od 1) z twierdzeniami do sprawdzenia, po pominięciu rejestru pracy, wierszy tabeli C7
    (cytaty źródła) i nagłówków tabel. Uwagi autora pod tabelą C7 (np. „żadne źródło nie zawiera…”) zostają na liście."""
    wynik, pomijaj, poziom, c7, poziom_c7 = [], False, 0, False, 0
    for i, l in enumerate(linie):
        s = l.lstrip()
        if s.startswith("#"):
            lvl = len(s) - len(s.lstrip("#"))
            if pomijaj and lvl <= poziom:
                pomijaj = False
            if c7 and lvl <= poziom_c7:
                c7 = False
            if not pomijaj and POMIN_SEKCJE.search(s):
                pomijaj, poziom = True, lvl
            elif not c7 and C7.search(s):
                c7, poziom_c7 = True, lvl
            continue
        if pomijaj or (c7 and s.startswith("|")) or s.startswith(">") or not NEG.search(l):
            continue
        if s.startswith("|") and (SEPARATOR.match(s) or (i + 1 < len(linie) and SEPARATOR.match(linie[i + 1].lstrip()))):
            continue
        wynik.append(i + 1)
    return wynik


def main(karta, folder):
    teksty = korpus(folder)
    linie = open(karta, encoding="utf-8").read().splitlines()
    n = bez_wsk = 0
    for nr in twierdzenia(linie):
        l = linie[nr - 1]
        n += 1
        wsk = bool(WSKAZANIE.search(l))
        bez_wsk += not wsk
        kl = slowa(l)
        traf = [f"{p}({t.count(k)})" for k in kl for p, t in teksty.items() if k in t][:6]
        print(f"L{nr}{'' if wsk else ' [BEZ „szukano w”]'}: {l.strip()[:160]}")
        print(f"    słowa: {kl} → trafienia: {', '.join(traf) if traf else '0'}")
    print(f"\n{os.path.basename(karta)}: negacji {n}, bez wskazania źródła {bez_wsk}. Każdą sprawdź ręcznie w pliku.")


# =============================================================================================================
# v3 (2026-09-17) — sekcja N: „negacja = dowód" zamknięta mechanicznie.
# Powyższa część (v2) pozostaje bez zmian: wypisuje WSZYSTKIE twierdzenia negatywne i szuka słów wiersza
# w całej bibliotece marki — to lista do przeglądu. Sekcja N robi coś węższego i rozstrzygającego:
# bierze tylko mocne negacje („żaden dokument nie…", „brak w dokumentach", „nie występuje w żadnym",
# „nie deklaruje", „katalog nie podaje"), wyciąga z wiersza SŁOWO KLUCZOWE (fraza po „nie", cytowany termin,
# symbol/akronim — nie całe zdanie) i sprawdza je w plikach .txt dokumentów wymienionych w §3 karty
# (wraz z transkrypcjami renderów). Trafienie = FLAGA „negacja przeczona przez dokument", z plikiem i linią.
# Dokumenty bez warstwy tekstu są pomijane w wyszukiwaniu i zgłaszane osobno jako „nieweryfikowalne — skan".
# =============================================================================================================

# mocne negacje; grupa 0 to fraza sygnalna, ogon zdania (po niej) jest źródłem słów kluczowych
N_TRIGGER = re.compile(
    r"żaden\s+(?:\w+\s+){0,3}?nie\s+\w+|"
    r"(?:w\s+)?żadn(?:ym|ego|ej)\s+(?:\w+\s+){0,2}?(?:dokument\w*|źród\w*|kart\w*|katalog\w*|plik\w*)|"
    r"\bbrak\s+w\s+(?:dokument\w*|źród\w*|żadnym)|"
    # \b przed „nie" jest konieczne: bez niego „opakowanie zawiera" pasowało do „nie zawiera"
    r"\bnie\s+(?:występuje|figuruje|pojawia\s+się|stwierdzono|znaleziono|deklaruj\w*|podaje|podano|"
    r"zawiera|zawierają|wymienia|wymieni\w*|określa|precyzuje|wspomina|opisuje)", re.I)

# cytowany termin: „…" / «…» / "…"
CYTOWANE = re.compile(r"[„«\"]([^„”«»\"]{2,60})[”»\"]")
# symbol / akronim / numer normy: CE, LATEX, PHT, UDI-DI, EN ISO 8669-2, SARS-CoV-2, H410
AKRONIM = re.compile(r"\b[A-ZĄĆĘŁŃÓŚŹŻ][A-ZĄĆĘŁŃÓŚŹŻ0-9]{1,}(?:[-\s/][A-ZĄĆĘŁŃÓŚŹŻ0-9]{1,}){0,3}\b")
SLOWO = re.compile(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż][A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż-]{4,}")

# akronimy, które NIE są faktem wyrobu (znaczniki karty, nazwy pól, oznaczenia dokumentów)
STOP_AKRO = {"BRAK", "DO", "POTWIERDZENIA", "POTWIERDZONE", "NIE", "TAK", "PDF", "HTML", "TXT", "PNG", "URL",
             "SKU", "REF", "EAN", "UWAGA", "SEKCJA", "PL", "EN", "DE", "FR", "II", "III", "IV", "XX", "NR",
             "IFU", "SDS", "TD", "ND", "BD", "JW"}
STOP_SLOWA = STOP | set(
    "dokument dokumencie dokumentach dokumenty dokumentu dokumentów żaden żadnym żadnego żadnej producenta "
    "producent wytwórcy wytwórca katalog katalogu katalogi karcie kartach etykiecie etykiety instrukcji "
    "ulotce ulotki strona stronie strony źródle źródła żadne wprost tylko także również nigdzie osobno wyłącznie "
    "natomiast ponieważ jednak zatem czyli przy tego tych temu jest była było były znaleziono stwierdzono "
    "występuje figuruje wymieniona wymieniony podana podano deklaruje określa precyzuje wspomina opisuje "
    "informacji informacja informacje danych dane pole pola wartość wartości znacznik znacznika formuła formuły "
    "zdanie zdania słowa słowo fraza frazy szukano sprawdzono przeczytano render renderu transkrypcja "
    # rzeczowniki zbyt ogólne, żeby ich trafienie cokolwiek znaczyło (test 2026-09-17: same fałszywe alarmy)
    "wyrób wyrobu wyrobie wyroby wyrobów produkt produktu produkcie produkty termin terminu terminie "
    "klasa klasy klasie klasą reguła reguły numer numeru numery symbol symbolu symbole opis opisu opisie "
    "nazwa nazwy nazwie wersja wersji wersję rozmiar rozmiaru rozmiary wariant wariantu warianty ilość "
    "ilości dostępność dostępności sposób sposobu metoda metody metodzie działanie działania działaniu "
    "zastosowanie zastosowania przeznaczenie przeznaczenia użytku użycia stosowanie stosowania właściwości "
    "wzmianki wzmianka wzmiankę określenia określenie sformułowanie sformułowania podziału podział "
    "wskazań wskazania rewizja rewizji zakres zakresu zakresie miejsce miejsca postać postaci punkt punktu "
    "sekcja sekcji sekcję tabela tabeli tabelę kolumna kolumny wiersz wiersza wierszu plik pliku pliki "
    "importer importera importerem importerzy resellera reseller dystrybutor dystrybutora "
    "materiału materiałem opakowaniem pakowanie klasyfikacji klasyfikacja rozciągniętym profesjonalista sprzedaje "
    "organizmowi pojemności niedostępny antybiotyku powierzchnię dotyczących chemiczny chemiczna "
    "adres adresu adresie firma firmy spółka spółki katalogu katalogiem blokady "
    "użytkownik użytkownika użytkownikiem użytkownicy deklaracja deklaracji deklarację zgodności zgodność "
    "dokumentacja dokumentacji producenta producentem wytwórcą wytwórcę oznakowanie oznakowania "
    "opakowanie opakowania opakowaniu opakowań jednostkowe jednostkowego handlowe handlowego "
    "medyczny medycznego medycznych medyczne wyrobem".split())

# czasownik pozytywnej atrybucji tuż przed cytatem: to kontr-fakt („które wymieniają tylko …”),
# nie przedmiot negacji
POZYTYW = re.compile(r"wymieni\w*|podaj\w*|podaje|zawiera\w*|deklaruj\w*|cytuj\w*|stoi\b|"
                     r"m\u00f3wi\b|opisuj\w*|wskazuj\w*|\btylko\b|\bjest\b|\bto\b|tekst|fragment|brzmieni|"
                     r"podobn\w*|dos\u0142own\w*|szukan\w*|\bgrep\b|fraz\w*|pe\u0142ny\b", re.I)
POMIN_N = re.compile(r"^#{2,}\s*(?:1|3)[.\s]")   # §1 odcisk wariantu (tekst projekt odniesienia), §3 rejestr dokumentów
# wiersz transkrypcji dokumentu (tabela SDS §1–§16, „SEKCJA 10. …") — treść źródła, nie twierdzenie autora
TRANSKRYPCJA = re.compile(r"^\**\s*(?:§|SEKCJA\b|SECTION\b)\s*\d|^\**\s*\d{1,2}\.\d\b", re.I)
TOK_DOK = re.compile(r"#\s*(\d+[a-z]?)")
TOK_ZAKRES_N = re.compile(r"#\s*(\d+)\s*[–—-]\s*#?\s*(\d+)")
PLIK_W_TEKSCIE = re.compile(r"[\w\-.]+\.(?:pdf|html?|txt|png|jpe?g|webp)", re.I)
TD_W_TEKSCIE = re.compile(r"\bTD[-\s]?(\d+)\b", re.I)
SEK3_NAGL = re.compile(r"^#{2,}\s*3[.\s]")
SEPAR_N = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
WYTWORCA_N = re.compile(
    r"\bifu\b|instrukcj|ulotk|etykiet|karta techn|karta danych|product data sheet|\btds\b|\btd[-\s]?\d|"
    r"\bsds\b|karta charakterystyk|deklaracj|certyfikat|katalog|\bnorma\b|dokument\w*\s+(?:wytwórc|producent)|"
    r"stron[ay][^,;()]{0,18}(?:producent|wytwórc|marki|importer)|autoryzowan|\bimporter|\bwytwórc|\burpl\b|eudamed",
    re.I)


def kom_n(linia):
    s = linia.strip()
    cz = re.split(r"(?<!\\)\|", s)
    if s.startswith("|"):
        cz = cz[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        cz = cz[:-1]
    return [c.strip() for c in cz]


def sekcja3(linie):
    """{id -> {'opis','pliki':[nazwa], 'wytworca':bool}} z tabeli §3 karty."""
    dok, w3, nagl, idx = {}, False, None, {}
    for l in linie:
        s = l.strip()
        if s.startswith("#"):
            w3 = bool(SEK3_NAGL.match(s))
            nagl = None
            continue
        if not w3 or not s.startswith("|") or SEPAR_N.match(s):
            continue
        k = kom_n(l)
        if nagl is None:
            low = [c.lower() for c in k]
            if any(re.match(r"^\**#\**$|^\**nr\**$", c) for c in low) and any(c.startswith("typ") or c.startswith("**typ") for c in low):
                nagl = k
                idx = {"nr": next(i for i, c in enumerate(low) if re.match(r"^\**#\**$|^\**nr\**$", c)),
                       "typ": next(i for i, c in enumerate(low) if c.startswith("typ") or c.startswith("**typ")),
                       "plik": next((i for i, c in enumerate(low) if "plik" in c), None),
                       "url": next((i for i, c in enumerate(low) if "url" in c), None)}
            continue
        if len(k) <= idx["typ"]:
            continue
        ident = re.sub(r"[^0-9a-z]", "", k[idx["nr"]].lower())
        if not ident:
            continue
        pliki_kom = (k[idx["plik"]] if idx["plik"] is not None and idx["plik"] < len(k) else "")
        opis = k[idx["typ"]]
        nazwy = PLIK_W_TEKSCIE.findall(pliki_kom + " " + opis)
        # zapis „`x.html` / `.txt`" — doklej wariant .txt
        for n in list(nazwy):
            nazwy.append(os.path.splitext(n)[0] + ".txt")
        dok[ident] = {"opis": opis, "pliki": sorted(set(nazwy)), "wytworca": bool(WYTWORCA_N.search(opis)),
                      "td": [m.lower() for m in TD_W_TEKSCIE.findall(opis)]}
    return dok


def znajdz(nazwa, korzen, cache={}):
    klucz = (nazwa.lower(), korzen)
    if klucz not in cache:
        tr = [p for p in glob.glob(os.path.join(korzen, "**", nazwa), recursive=True)]
        if not tr:
            tr = [p for p in glob.glob(os.path.join(korzen, "**", "*"), recursive=True)
                  if os.path.basename(p).lower() == nazwa.lower()]
        cache[klucz] = tr[0] if tr else None
    return cache[klucz]


def linie_pliku(sciezka, cache={}):
    if sciezka not in cache:
        t = open(sciezka, encoding="utf-8", errors="replace").read()
        if sciezka.lower().endswith((".htm", ".html")):
            t = re.sub(r"<!--.*?-->|<(script|style)\b.*?</\1>", " ", t, flags=re.S | re.I)
            t = html.unescape(re.sub(r"<[^>]+>", " ", t))
        cache[sciezka] = t.splitlines()
    return cache[sciezka]


def tekst_dokumentu(d, korzen):
    """[(nazwa, linie)] dla dokumentu §3 — tylko pliki z warstwą tekstu. ('' , None) = skan / brak pliku."""
    wynik, bez_tekstu = [], []
    for n in d["pliki"]:
        if not n.lower().endswith((".txt", ".html", ".htm")):
            continue
        p = znajdz(n, korzen)
        if not p:
            continue
        try:
            rozmiar = os.path.getsize(p)
        except OSError:
            continue
        # skan bez warstwy tekstu: .txt pusty, albo znikomy przy dużym PDF (kryterium z biblioteka_dokumentow.py)
        if n.lower().endswith(".txt"):
            pdf = znajdz(os.path.splitext(n)[0] + ".pdf", korzen)
            duzy_pdf = bool(pdf) and os.path.getsize(pdf) > 50_000
            if rozmiar < 20 or (duzy_pdf and rozmiar < 500):
                bez_tekstu.append(n)
                continue
        wynik.append((os.path.basename(p), linie_pliku(p)))
    # transkrypcje renderów: <render>.png → <render>.txt (już doklejone wyżej), plus *_images.txt pomijamy
    if not wynik:
        for n in d["pliki"]:
            if n.lower().endswith((".pdf", ".png", ".jpg", ".jpeg", ".webp")):
                bez_tekstu.append(n)
    return wynik, sorted(set(bez_tekstu))


def rdzen(w):
    w = w.strip(" .,;:()[]{}\"'„”«»")
    return w[:max(5, len(w) - 3)].lower() if len(w) > 5 else w.lower()


def slowa_kluczowe(okno, po_negacji):
    """(klucze, rodzaj) — rodzaj: 'cytat' / 'symbol' / 'slowo'.
    Cytowany termin > symbol/akronim > goly rzeczownik. Cytat poprzedzony POZYTYWNYM czasownikiem
    („ktore wymieniaja tylko ...") jest kontr-faktem, nie przedmiotem negacji — pomijany.
    Gole rzeczowniki daja w tej bibliotece prawie same falszywe alarmy, wiec ich trafienia sa
    tylko informacyjne (N3), nie blokujace."""
    kand = []
    for m in CYTOWANE.finditer(okno):
        przed = okno[max(0, m.start() - 35):m.start()]
        if POZYTYW.search(przed) and not re.search(r"\bnie\b|\bbrak\b|\bzaden|\bzadn", przed, re.I):
            continue
        for cz in re.split(r"\s*[/,]\s*|\s+ani\s+", m.group(1)):
            cz = cz.strip(" .;:-")
            if len(cz) < 4 or PLIK_W_TEKSCIE.search(cz):
                continue
            if cz.lower().startswith(("szukano", "brak", "sprawdzono", "nie ")):
                continue
            if all(w.lower() in STOP_SLOWA for w in re.findall(r"[^\W\d_]+", cz)):
                continue
            kand.append(cz)
    if kand:
        return kand[:4], "cytat"
    for m in AKRONIM.finditer(okno):
        t = m.group(0).strip()
        if t.upper() in STOP_AKRO or re.match(r"^TD[-\s]?\d", t, re.I) or len(t) < 3:
            continue
        if re.fullmatch(r"[A-Z\u0104\u0106\u0118\u0141\u0143\u00d3\u015a\u0179\u017b]{1,2}", t):
            continue
        kand.append(t)
    if kand:
        return kand[:3], "symbol"
    for m in SLOWO.finditer(po_negacji or okno):
        w = m.group(0).strip("-")
        if len(w) < 9 or w.lower() in STOP_SLOWA:
            continue
        kand.append(w)
        if len(kand) >= 2:
            break
    return kand, "slowo"


def linie_n(linie):
    """Numery linii z MOCNĄ negacją, z tym samym pomijaniem co `twierdzenia()` (rejestr pracy, tabela C7,
    nagłówki i separatory tabel), plus §1 (odcisk wariantu) i §3 (rejestr dokumentów) — i z węższym
    wzorcem N_TRIGGER."""
    wynik, pomijaj, poziom, c7, poziom_c7 = [], False, 0, False, 0
    for i, l in enumerate(linie):
        s = l.lstrip()
        if s.startswith("#"):
            lvl = len(s) - len(s.lstrip("#"))
            if pomijaj and lvl <= poziom:
                pomijaj = False
            if c7 and lvl <= poziom_c7:
                c7 = False
            if not pomijaj and (POMIN_SEKCJE.search(s) or POMIN_N.match(s)):
                pomijaj, poziom = True, lvl
            elif not c7 and C7.search(s):
                c7, poziom_c7 = True, lvl
            continue
        if pomijaj or (c7 and s.startswith("|")) or s.startswith(">") or not N_TRIGGER.search(l):
            continue
        if s.startswith("|") and (SEPARATOR.match(s) or (i + 1 < len(linie) and SEPARATOR.match(linie[i + 1].lstrip()))):
            continue
        wynik.append(i + 1)
    return wynik


def zakres_wiersza(linia, dok):
    """Dokumenty, o ktorych mowi wiersz: tokeny #N, nazwy plikow (dopasowanie w obie strony:
    „katalog-1.pdf” = „producent-pl-katalog-1.pdf”), TD-nn. Pusty wynik = cale §3."""
    ids = []
    for a, b in TOK_ZAKRES_N.findall(linia):
        ids += [str(x) for x in range(int(a), int(b) + 1)]
    ids += TOK_DOK.findall(TOK_ZAKRES_N.sub(" ", linia))
    low = linia.lower()
    nazwy_w_wierszu = [m.group(0).lower() for m in PLIK_W_TEKSCIE.finditer(linia)]
    for i, d in dok.items():
        for n in d["pliki"]:
            nl = n.lower()
            if len(nl) > 6 and (nl in low or any(len(x) > 6 and (x in nl or nl.endswith(x)) for x in nazwy_w_wierszu)):
                ids.append(i)
                break
        if any(("td-" + t) in low.replace(" ", "-") for t in d["td"]):
            ids.append(i)
    wynik, widz = [], set()
    for i in ids:
        k = re.sub(r"[^0-9a-z]", "", i.lower())
        if k in dok and k not in widz:
            widz.add(k)
            wynik.append(k)
    return wynik


STRONA_WYTWORCY = re.compile(r"producent|wytwórc|\bIFU\b|instrukcj|etykiet|karta techn|katalog", re.I)
STRONA_WLASNA = konfig.rx_wlasne()   # nasz serwis/sklep wg weryfikacja.json
# negacja musi dotyczyć DOKUMENTU, nie samego wyrobu: „nie zawiera lateksu" to fakt o produkcie,
# „katalog nie zawiera tego adresu" to twierdzenie o dokumencie — sprawdzam tylko to drugie
DOKUMENTALNA = re.compile(r"dokumen|źród|katalog|\bkart|karci|\bIFU\b|\bSDS\b|etykie|ulot|instrukcj|"
                          r"stron|#\s?\d|\bTD[-\s]?\d|deklaracj|producen|wytwórc|importer|" +
                          "|".join(konfig.tokeny_wlasne()) + r"|"
                          r"render|transkrypc|\bplik", re.I)


def zawez_do_strony(fraza, klauzula, zakres, dok):
    """Negacja nazywa stronę („żaden dokument PRODUCENTA…", „karta projekt odniesienia tego nie podaje") — wtedy
    sprawdzam tylko dokumenty tej strony; pierwszeństwo ma strona nazwana w samej frazie negacji.
    Pusty wynik = w zadeklarowanym zakresie nie ma dokumentu tej strony → trafienia idą do N2~.
    Bez tego trafienie na stronie projekt odniesienia „przeczyło" negacji o dokumentach wytwórcy (test 2026-09-17)."""
    for tekst in (fraza, klauzula):
        lim, wyt = bool(STRONA_WLASNA.search(tekst)), bool(STRONA_WYTWORCY.search(tekst))
        if lim and not wyt:
            return [i for i in zakres if konfig.jest_wlasny(dok[i]["opis"])]
        if wyt and not lim:
            return [i for i in zakres if dok[i]["wytworca"]]
    return zakres


MAX_TRAFIEN = 8   # słowo obecne w bibliotece kilkanaście razy jest jej terminem własnym, nie faktem z wiersza


def szukaj(klucz, teksty):
    """(plik, nr_linii, fragment) pierwszego trafienia albo None.
    Rdzeń dopasowywany od GRANICY SŁOWA (bez tego „prawn" łapało „sprawną"), fraza wielowyrazowa — po zwinięciu
    spacji. Słowo trafione częściej niż MAX_TRAFIEN razy uznaję za termin własny biblioteki i nie zgłaszam."""
    r = rdzen(klucz)
    if len(r) < 4:
        return None
    if len(klucz.split()) > 1:
        wzor = re.compile(re.escape(klucz.strip()).replace(r"\ ", r"\s+"), re.I)
    else:
        wzor = re.compile(r"(?<![0-9A-Za-ząćęłńóśźż])" + re.escape(r), re.I)
    pierwsze, ile = None, 0
    for nazwa, linie in teksty:
        for i, l in enumerate(linie, 1):
            if wzor.search(l):
                ile += 1
                if pierwsze is None:
                    pierwsze = (nazwa, i, re.sub(r"\s+", " ", l.strip())[:120])
                if ile > MAX_TRAFIEN:
                    return None
    return pierwsze


def negacje_dowod(karta, korzen):
    """Sekcja N. Zwraca (flagi, skany) — flagi: (nr_linii, klucz, plik, linia, fragment, poza_zakresem)."""
    linie = open(karta, encoding="utf-8").read().splitlines()
    dok = sekcja3(linie)
    teksty, skany = {}, {}
    for i, d in dok.items():
        t, bt = tekst_dokumentu(d, korzen)
        teksty[i] = t
        if bt and not t:
            skany[i] = bt
    flagi = []
    for nr in linie_n(linie):
        l = linie[nr - 1]
        kom_wiersza = kom_n(l) if l.strip().startswith("|") else [l]
        # wiersz transkrypcji źródła (SDS §1–§16, „SEKCJA 10…") to cytat dokumentu, nie twierdzenie autora
        if kom_wiersza and TRANSKRYPCJA.match(kom_wiersza[0]):
            continue
        for kom in kom_wiersza:
            m = N_TRIGGER.search(kom)
            if not m:
                continue
            # tylko zdanie składowe, w którym stoi negacja — cytat z sąsiedniego zdania to zwykle
            # POZYTYWNE powołanie się na źródło, nie przedmiot negacji (test 2026-09-17: główne źródło FP)
            a = max((kom.rfind(z, 0, m.start()) + len(z) for z in ("; ", ". ", " — ", " – ", ") ")), default=0)
            b = min([x for x in (kom.find(z, m.end()) for z in ("; ", ". ", " — ", " – ")) if x > 0] or [len(kom)])
            okno, po = kom[a:b], kom[m.end():b]
            if not DOKUMENTALNA.search(kom):      # negacja o samym wyrobie, nie o dokumencie — poza zakresem N
                continue
            # odsyłacze do plików roboczych w `backtickach` nie są faktem wyrobu
            okno = re.sub(r"`[^`]*`", " ", okno)
            po = re.sub(r"`[^`]*`", " ", po)
            klucze, rodzaj = slowa_kluczowe(okno, po)
            if not klucze:
                continue
            zakres = zawez_do_strony(m.group(0), okno, zakres_wiersza(l, dok) or list(dok), dok)
            poza = [i for i in dok if i not in zakres]
            for k in klucze:
                tr = szukaj(k, [x for i in zakres for x in teksty.get(i, [])])
                if tr:
                    # goły rzeczownik = klasa informacyjna N3 (nie dowodzi przeczenia, tylko wskazuje miejsce)
                    flagi.append((nr, k, tr[0], tr[1], tr[2], "N3" if rodzaj == "slowo" else "N1"))
                    break
                tr2 = szukaj(k, [x for i in poza for x in teksty.get(i, [])])
                if tr2:
                    flagi.append((nr, k, tr2[0], tr2[1], tr2[2], "N2"))
                    break
            break
    return flagi, skany, dok


def main_n(karta, korzen, bramka=False):
    flagi, skany, dok = negacje_dowod(karta, korzen)
    print(f"\n-- N: negacja = dowód ({os.path.basename(karta)}; dokumentów §3: {len(dok)})")
    GDZIE = {"N1": "w dokumencie wiersza", "N2": "poza zadeklarowanym zakresem wiersza",
             "N3": "gołe słowo — tylko wskazanie miejsca, nie dowód"}
    for nr, k, plik, lin, frag, kl in flagi:
        print(f"  L{nr} {kl}{'' if kl == 'N1' else '~'} negacja przeczona przez dokument ({GDZIE[kl]}): "
              f"słowo „{k}” → {plik} l.{lin}: {frag}")
    for i, pliki in sorted(skany.items()):
        print(f"  #{i} ~ nieweryfikowalne — skan (brak warstwy tekstu): {', '.join(pliki)}")
    twarde = [f for f in flagi if f[5] == "N1"]
    print(f"  N1 (blokujące): {len(twarde)} · N2~ (poza zakresem): {sum(1 for f in flagi if f[5] == 'N2')} · "
          f"N3~ (gołe słowo): {sum(1 for f in flagi if f[5] == 'N3')} · "
          f"dokumentów bez warstwy tekstu: {len(skany)}")
    return 1 if (bramka and twarde) else 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flagi_cli = {a for a in sys.argv[1:] if a.startswith("--")}
    if len(args) != 2:
        print(__doc__); sys.exit(1)
    if "--tylko-n" not in flagi_cli:
        main(args[0], args[1])
    sys.exit(main_n(args[0], args[1], bramka="--bramka" in flagi_cli))
