#!/usr/bin/env python3
"""Forma karty faktów — łapie klasy błędów, które sędziowie całości wykrywali ręcznie (rundy do 2026-09-17).

Klasy flag:
  K1 ślad procesu / historii edycji w treści (sędzia, kanarek, agent, runda, „dopisano”, ID znalezisk (B-1) …)
     — w cytacie „…” oznaczone „w cytacie” (niższa waga, nie wpływa na exit code)
  K2 wiersz tabeli z inną liczbą komórek (niezescape'owanych „|”) niż nagłówek
  K3 kolumna „Znacznik” / „Pewność”: komórka nie zaczyna się od [POTWIERDZONE] / [DO POTWIERDZENIA] / [BRAK]
  K3i pusta komórka znacznika, ale znacznik jest w innej komórce wiersza albo wiersz jest odsyłaczem
      („Szczegóły §4.1”, „patrz §4.2”) — informacyjnie
  K4 [BRAK] w wierszu bez „szukano” (ani w wierszu, ani w kolumnie „Szukano w”)  — ostrzeżenie, bez exit 1
  K5 data YYYY-MM-DD późniejsza niż dziś (poza kontekstem ważności/terminu — patrz WAZNOSC)
  K6 „(cytat jw.)” / „(cytaty jw.)”
  K7 tabela faktów w §4 z brakującą kolumną albo kolumnami w innej kolejności niż w szablonie
     (fakt/pole · wartość · znacznik · Dok. · cytat; tabele specjalne §4.1–§4.4, spektrum, C7 — własne wzorce)
  K8 brak wiersza wymaganego przez grupę typu wyrobu (4A + grupa z pola „Typ wyrobu (grupy §4)” /
     z nagłówków „### 4B…”; dla kart dezynfekcji — wiersze §4 szablonu chemii)

Fakty spoza szablonu są dozwolone — nadmiarowe wiersze i kolumny NIE są zgłaszane (szablon to minimum, nie limit).

Pomijane: wiersz „| Status | DO SĘDZIEGO |”, „Status karty: DO SĘDZIEGO”, sekcja „Historia …” ze wskaźnikiem
do folderu kontrola/ (szablon), separatory tabel |---|, bloki kodu ```.
K7/K8 pomijają tabele pomocnicze w §4 (porównania dokumentów, transkrypcja SDS — od tej jest
`karta_sds_atrybuty.py`) — sprawdzane są tylko tabele rozpoznane po nagłówku sekcji.

Exit 1, gdy jest flaga K1 (poza cytatem), K2, K3, K5, K6, K7 lub K8.
Użycie: python _skrypty/karta_forma.py <karta.md> [<karta.md> ...] [--dzis YYYY-MM-DD] [--cicho]
"""
import datetime as dt
import glob
import os
import re
import sys
import unicodedata

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# --- K1: ślady procesu -------------------------------------------------------------------------------------
# (nazwa, wzorzec); dopasowanie bez rozróżniania wielkości liter, chyba że wzorzec ma (?-i)
SLADY = [
    ("sędzia", r"s[ęe]dzi"),
    ("weryfikacja", r"weryfikac"),
    ("kanarek", r"kanar"),
    ("podłożony", r"podłożon"),
    ("scratchpad", r"scratchpad"),
    ("agent", r"\bagent(?:a|em|ów|owi|om|ami|y|ach)?\b"),
    ("sesja", r"\bsesj(?:a|i|ę|ą)\b"),
    ("brief", r"\bbrief"),
    ("odchudzanie", r"odchudzan"),
    ("orkestrator", r"orke?strator"),
    ("runda", r"\brundzie\b"),
    ("iteracja", r"iteracj"),
    ("próg N", r"\bpr[óo]g\s*\d+(?![\d,.]*\s*(?:%|‰|t\b|kg|mg|g\b|ppm|/|m[l³]?\b))"),
    ("poprzednia wersja karty", r"poprzedni\w* wersj\w* karty"),
    ("wcześniej…", r"wcześniej(?:sz\w*)? (?:założeni|wpis|pominię)"),
    ("dopisano", r"\bdopisano\b"),
    ("dodane wyżej", r"\bdodan\w* wyżej"),
    ("nie było w karcie", r"nie było w karcie"),
    ("usunięto dubel", r"usunięto dubel"),
    ("dubel językowy", r"dubel językow"),
    ("jedno źródło wystarcza", r"jedno źródło\b[^|.]{0,60}?wystarcza"),
    ("dotąd nieujęte", r"dotąd (?:nieujęt|nieobecn)"),
    ("nowy wiersz", r"\bnowy wiersz"),
    ("nazwa skryptu", r"karta_[a-z_]+\.py"),
    ("Flaga skryptu", r"flag[aię] skryptu"),
    ("ID znaleziska", r"(?-i:\((?:[A-Z]{1,2}\d|[A-Z])-[A-Z]{0,2}\d{1,2}[a-z]?(?:\s*[,;/]\s*(?:[A-Z]{1,2}\d|[A-Z])-[A-Z]{0,2}\d{1,2}[a-z]?)*\))"),
]
SLADY_RE = [(n, re.compile(p, re.I)) for n, p in SLADY]

# wyjątki K1 (kontekst dopasowania → nie jest śladem procesu)
WYJATKI = {
    # „do weryfikacji” = otwarta niepewność dla klienta; „weryfikacja 04.2023” / „data weryfikacji” = rewizja SDS
    "weryfikacja": re.compile(r"do (?:dalszej |ręcznej )?weryfikac|weryfikac\w*\s*(?::\s*)?\d|dat\w* weryfikac|"
                              r"weryfikacj\w* (?:produktu|partii|procesu|sterylizacji|skuteczno)", re.I),
    # EN „cleaning agent”, „antimicrobial agents” itp. — słowo angielskie tuż przed
    "agent": re.compile(r"\b(?:[a-z]+ing|active|antimicrobial|oxidi[sz]ing|chelating|wetting|masking|reducing|"
                        r"cleaning|bleaching|surface[- ]active|biocidal|infectious|chemical|the|an?|of)\**\s+\**agents?\b|"
                        r"\bagents?\s+(?:de|of|for|and)\b", re.I),
}

CYTAT_RE = re.compile(r"„[^„”\"]*[”\"]")          # „…” albo „…" (w kartach często zamknięte prostym ")
# pole statusu: „| Status | DO SĘDZIEGO … |” oraz „Status karty: **DO SĘDZIEGO**.” — tylko samo pole, reszta linii nie istnieje
STATUS_RE = re.compile(r"^\|\s*\**Status\**\s*\|\s*\**DO S[ĘE]DZIEGO\b[^|]*\|?\s*$|^\s*\**Status karty:?\**\s*\**DO S[ĘE]DZIEGO\**\.?\s*$", re.I)

# --- tabele ----------------------------------------------------------------------------------------------
SEPARATOR = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
ZNACZNIK_KOL = re.compile(r"znacznik|pewno", re.I)
SZUKANO_KOL = re.compile(r"szukano", re.I)
MARKER_OK = re.compile(r"^\*{0,2}\[(?:POTWIERDZONE|DO POTWIERDZENIA|BRAK)\]")
MARKER_W_NAWIASIE = re.compile(r"\[(?:POTWIERDZONE|DO POTWIERDZENIA|BRAK)\s*[—–:,;-][^\]]*\]")
ODSYLACZ = re.compile(r"\**(?:szczegóły|patrz|zob\.|wg wariantu)\b[^|]{0,40}?§\s?\d", re.I)
MARKER_GOLY = re.compile(r"^\*{0,2}(?:POTWIERDZONE|DO POTWIERDZENIA|BRAK)\b")

# --- K5 / K6 ---------------------------------------------------------------------------------------------
DATA_RE = re.compile(r"(?<![\d-])(20\d\d)-(\d\d)-(\d\d)(?![\d])")
# daty przyszłe dopuszczalne: ważność certyfikatu / terminy przydatności partii / zakresy „od – do”
WAZNOSC = re.compile(r"ważn|termin|przydatno|expir|\bEXP\b|valid|gültig|verfall|scaden|do dnia|"
                     r"\d{4}-\d\d-\d\d\s*[–—-]\s*$", re.I)
JW_RE = re.compile(r"\(cytat[y]? jw\.?\)", re.I)
BRAK_RE = re.compile(r"\[BRAK\]")
SZUKANO_RE = re.compile(r"szukan", re.I)
# inne wskazanie przeszukania (słownik jak w karta_negacje.py + „brak w D1–D15”, „nie podano w M4”, „grep”)
INNE_WSKAZANIE = re.compile(r"sprawdzon\w* w|przeczytan|\bgrep\b|"
                            r"(?:brak|nie pod\w*|nie zawier\w*|nie wymieni\w*)\s+(?:w|na)\s+(?:dok\.?\s*)?(?:[DWM]\d|#\d)|"
                            r"(?:\b[DWM]\d{1,2}\b|#\d+)[^|\n]{0,60}?(?:§|\bs\.|str\.|sekcj|\bl\.|\bw\.|stron)", re.I)

EXIT_KLASY = {"K2", "K3", "K5", "K6", "K7", "K8"}

# --- K7: wymagane kolumny tabel §4 -------------------------------------------------------------------------
# (nazwa w raporcie, wzorzec nagłówka kolumny); kolumny nadmiarowe są dozwolone, liczy się obecność i kolejność
KOL_ZNACZNIK = ("Znacznik", r"znacznik|pewno")
KOL_DOK = ("Dok.", r"^\**dok|dokument|źród[łl]o")
KOL_CYTAT = ("Cytat", r"cytat")
UKLAD = {
    "fakty": [("Wartość", r"warto[śs][ćc]|tre[śs][ćc]"), KOL_ZNACZNIK, KOL_DOK, KOL_CYTAT],
    "4.1": [("Wariant", r"wariant|rozmiar|wymiar"), ("REF", r"\bref\b|symbol|\bkod\b|indeks"),
            ("Sztuk w opak.", r"sztuk"), ("Opak. zbiorcze", r"zbiorcz|transportow"), ("Jałowy", r"ja[łl]ow"),
            ("EAN / UDI-DI", r"\bean\b|\budi"), ("SKU sklepu", r"\bsku\b"), KOL_ZNACZNIK, KOL_DOK, KOL_CYTAT],
    "4.2": [("Norma", r"norma"), ("Typ / klasa / zakres", r"\btyp\b|klas|zakres"),
            ("Czego dotyczy", r"dotyczy|czego"), KOL_ZNACZNIK, KOL_DOK, KOL_CYTAT],
    "4.3": [("Wskaźnik", r"wska[źz]nik"), ("Typ / klasa wg normy", r"\btyp\b|klas"), ("Proces", r"proces"),
            ("Temperatura", r"temperatur"), ("Czas", r"czas"), ("Inne", r"inne|ci[śs]nieni|st[ęe][żz]eni"),
            ("Kolor przed → po", r"kolor"), KOL_ZNACZNIK, KOL_DOK, KOL_CYTAT],
    "4.4": [("Marka urządzenia", r"marka"), ("Model / seria", r"model|seria"),
            ("REF oryginału / przyłącze", r"\bref\b|przy[łl][ąa]cz"), KOL_ZNACZNIK, KOL_DOK, KOL_CYTAT],
    "spektrum": [("Drobnoustrój / zakres", r"drobnoustr|szczep|zakres"), ("Norma EN", r"norma|metoda"),
                 ("Czas", r"czas"), ("Stężenie", r"st[ęe][żz]eni"), ("Warunki", r"warunk|obci[ąa][żz]"),
                 KOL_ZNACZNIK, KOL_DOK, KOL_CYTAT],
    "c7": [("#", r"^\**#|^lp"), ("Zdanie źródła", r"zdani"), ("Dokument", r"dokument|^\**dok"),
           ("W karcie", r"w karcie|wiersz karty")],
}
UKLAD_RE = {k: [(n, re.compile(p, re.I)) for n, p in v] for k, v in UKLAD.items()}

# rozpoznanie rodzaju tabeli po nagłówku sekcji (### …) wewnątrz §4
SEK_GRUPA = re.compile(r"^#{3,4}\s*\**4([A-J])\b", re.I)          # ### 4A. …
SEK_PODNR = re.compile(r"^#{3,4}\s*\**4\.(\d)\b")                  # ### 4.1 …
SEK_SPEKTRUM = re.compile(r"^#{3,4}.*spektrum", re.I)
SEK_C7 = re.compile(r"^#{3,4}.*warunki u[żz]ycia", re.I)
SEK_SDS = re.compile(r"^#{3,4}.*(\bSDS\b|karta charakterystyki)", re.I)
SEK4 = re.compile(r"^##\s*\**4[\.\sa-z]")                          # „## 4. Fakty”, „## 4.0 …”, „## 4a. Fakty — …”
SEK2 = re.compile(r"^##\s+\**(?!4[\.\sa-z])\d")                    # koniec §4: nagłówek §5 / §7 / §8 …
TYP_POLE = re.compile(r"^\|\s*\**Typ wyrobu[^|]*\|\s*(.*?)\s*\|?\s*$", re.I)
GRUPA_LIT = re.compile(r"\b4\s?([A-J])\b")

# --- K8: wymagane wiersze wg szablonu ----------------------------------------------------------------------
KORZEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SZABLON_WYROBY = os.path.join(KORZEN, "04-opisy-produktow", "zrodla", "_wyroby", "_SZABLON-karta-wyrobu.md")
SZABLON_DEZ = os.path.join(KORZEN, "04-opisy-produktow", "zrodla", "dezynfekcja", "_SZABLON-karta-produktu.md")


def norm(s):
    """Klucz porównawczy etykiety wiersza: bez znaków diakrytycznych, bez interpunkcji, małe litery."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("ł", "l").replace("Ł", "L")
    return re.sub(r"[^a-z0-9]", "", s.lower())


def bez_nawiasow(etykieta):
    t = re.sub(r"\(.*?\)", " ", etykieta.strip().strip("*"))
    return re.sub(r"\s+", " ", t)


def rdzenie(tekst):
    """Znaczące słowa etykiety jako 6-literowe rdzenie (odporne na odmianę: deklaracja / deklaracje).

    Próg 3 znaków zostawia skróty niosące treść pola: CLP, SDS, REF, EAN, UDI, IFU."""
    return [t[:6] for t in re.findall(r"[a-z0-9]+", norm_spacja(tekst)) if len(t) >= 3]


def norm_spacja(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("ł", "l").replace("Ł", "L")
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def klucz_etykiety(etykieta):
    """Rdzenie etykiety wiersza karty (bez treści w nawiasach)."""
    return rdzenie(bez_nawiasow(etykieta))


def klucze_pola(etykieta):
    """Warianty pola z szablonu: część przed „:”, bez nawiasów, rozbita po „/”, „;”, „,” — każdy jako rdzenie."""
    t = bez_nawiasow(etykieta).split(":")[0]
    return [r for r in (rdzenie(a) for a in re.split(r"[/;,]| lub ", t)) if r]


def pasuje(alt, klucz, wyrozniki=frozenset()):
    """Wiersz karty (`klucz`) pokrywa wariant pola z szablonu (`alt`) — oba jako listy rdzeni.

    Karty skracają i łączą etykiety szablonu („Skład INCI / substancja czynna”, „Jałowość / metoda sterylizacji /
    system bariery jałowej”), więc wystarczą dwa pierwsze znaczące słowa wariantu; przy etykiecie skróconej do
    jednego–dwóch słów („Ostrzeżenia”, „Deklaracje”) wystarczy pierwsze. Karty przestawiają też szyk
    („Grupy użytkowników” → „Użytkownik”, „Docelowi użytkownicy”) — wtedy wystarczy słowo, które w tej grupie
    szablonu występuje tylko w tym jednym polu (`wyrozniki`)."""
    if not alt:
        return False
    if any(s in wyrozniki and s in klucz for s in alt):
        return True
    if alt[0] not in klucz:
        return False
    return len(alt) == 1 or len(klucz) <= 2 or alt[1] in klucz


def wiersze_tabeli(linie, i):
    """Etykiety (pierwsza komórka) wierszy tabeli zaczynającej się w linii i (nagłówek)."""
    out = []
    for l in linie[i + 1:]:
        if not l.lstrip().startswith("|"):
            break
        if SEPARATOR.match(l.strip()):
            continue
        k = komorki(l)
        if k:
            out.append(k[0])
    return out


def wczytaj_szablon(sciezka, tryb):
    """{grupa: [etykiety wierszy]} z szablonu. tryb 'wyroby' → 4A…4J; 'dez' → jedna grupa 'DEZ' (§4)."""
    if not os.path.exists(sciezka):
        return None
    linie = open(sciezka, encoding="utf-8").read().splitlines()
    grupy, biezaca = {}, None
    w4 = False
    for i, l in enumerate(linie):
        if SEK4.match(l):
            w4 = True
            biezaca = "DEZ" if tryb == "dez" else None
            continue
        if w4 and SEK2.match(l):
            break
        if not w4:
            continue
        if l.startswith("###"):
            m = SEK_GRUPA.match(l)
            biezaca = ("4" + m.group(1).upper()) if (m and tryb == "wyroby") else None
            continue
        if biezaca and l.lstrip().startswith("|") and grupy.get(biezaca) is None:
            kom = komorki(l)
            if len(kom) >= 2 and re.match(r"atrybut|sekcja", kom[0], re.I):
                grupy[biezaca] = wiersze_tabeli(linie, i)
    return grupy


SZABLON = {}


def szablony():
    if not SZABLON:
        SZABLON["wyroby"] = wczytaj_szablon(SZABLON_WYROBY, "wyroby") or {}
        SZABLON["dez"] = wczytaj_szablon(SZABLON_DEZ, "dez") or {}
    return SZABLON


def kolumny_ok(naglowek, uklad):
    """Zwraca listę komunikatów o brakach / złej kolejności kolumn (kolumny nadmiarowe są OK)."""
    braki = []
    ostatni = -1
    for nazwa, rx in UKLAD_RE[uklad]:
        trafienia = [k for k, c in enumerate(naglowek) if rx.search(c.strip().strip("*"))]
        if not trafienia:
            braki.append(f"brak kolumny „{nazwa}”")
            continue
        po = [k for k in trafienia if k > ostatni]
        if po:
            ostatni = po[0]
        else:
            braki.append(f"kolumna „{nazwa}” poza kolejnością (poz. {trafienia[0] + 1})")
    return braki


def sekcja4(linie):
    """(start, koniec) sekcji §4 albo None."""
    start = None
    for i, l in enumerate(linie):
        if start is None and SEK4.match(l):
            start = i
        elif start is not None and SEK2.match(l):
            return start, i
    return (start, len(linie)) if start is not None else None


def sprawdz_forme4(sciezka, linie, dodaj):
    """K7 (układ kolumn tabel §4) + K8 (kompletność wierszy wg grupy typu wyrobu)."""
    zakres = sekcja4(linie)
    if not zakres:
        return
    a, b = zakres
    tpl = szablony()

    # typ wyrobu z nagłówka karty
    deklarowane = []
    for l in linie[:a]:
        m = TYP_POLE.match(l)
        if m:
            deklarowane = ["4" + g.upper() for g in GRUPA_LIT.findall(m.group(1))]
            break

    sekcja = "gl"            # „gl” = tabela bezpośrednio pod „## 4.”
    tabele_grup = {}         # 4X → (nr linii nagłówka, indeks w `linie`)
    kod = False
    naglowek_otwarty = False
    for i in range(a + 1, b):        # a = nagłówek „## 4. …”; sekcja „gl” = tabela bezpośrednio pod nim
        l = linie[i]
        if l.strip().startswith("```"):
            kod = not kod
            continue
        if kod:
            continue
        if l.startswith("#"):
            naglowek_otwarty = False
            m = SEK_GRUPA.match(l)
            if m:
                sekcja = "4" + m.group(1).upper()
                continue
            m = SEK_PODNR.match(l)
            if m:
                sekcja = "4." + m.group(1)
                continue
            sekcja = ("sds" if SEK_SDS.match(l) else "c7" if SEK_C7.match(l)
                      else "spektrum" if SEK_SPEKTRUM.match(l) else "inne")
            continue
        if not l.lstrip().startswith("|"):
            naglowek_otwarty = False
            continue
        if naglowek_otwarty:
            continue
        naglowek_otwarty = True
        if i + 1 >= len(linie) or not SEPARATOR.match(linie[i + 1].strip()):
            continue            # wiersz bez separatora pod spodem to nie nagłówek tabeli (K2 łapie takie wiersze)
        kom = komorki(l)
        if len(kom) < 2:
            continue
        # rodzaj tabeli → wzorzec kolumn
        if sekcja in ("4.1", "4.2", "4.3", "4.4", "c7", "spektrum"):
            uklad = sekcja
        elif sekcja != "sds" and re.match(r"atrybut|pole|fakt", kom[0].strip().strip("*"), re.I):
            uklad = "fakty"         # tabela faktów — także pod własnym nagłówkiem karty chemii
            tabele_grup.setdefault(sekcja, []).append(i)
        else:
            continue                # SDS, tabele porównawcze („Cecha”, „Wartość”) — poza zakresem K7
        for opis in kolumny_ok(kom, uklad):
            dodaj(i + 1, "K7", f"{opis} (tabela §{sekcja if sekcja != 'gl' else '4'})", l[:110])

    # wiersze tabel spoza §4 (do rozróżnienia „brak faktu” / „fakt w innej sekcji”)
    poza4, sek_poza = [], "nagłówek karty"
    for i, l in enumerate(linie):
        if a <= i < b:
            continue
        if l.startswith("##"):
            sek_poza = l.lstrip("# ").strip()[:40]
        elif l.lstrip().startswith("|") and not SEPARATOR.match(l.strip()):
            kom = komorki(l)
            if kom:
                poza4.append((klucz_etykiety(kom[0]), sek_poza))

    # ---------- K8 ----------
    obecne_grupy = [g for g in tabele_grup if re.fullmatch(r"4[A-J]", g)]
    if obecne_grupy or deklarowane:
        wymagane = sorted(set(deklarowane) | set(obecne_grupy) | {"4A"})
        zrodlo = tpl["wyroby"]
    elif tabele_grup:
        wymagane, zrodlo = ["DEZ"], tpl["dez"]
    else:
        return
    if not zrodlo:
        return
    for g in wymagane:
        pola = zrodlo.get(g)
        if not pola:
            continue
        # karta chemii nie ma stałych podsekcji §4 — wiersze zbieramy ze wszystkich tabel faktów w §4
        starty = ([i for lista in tabele_grup.values() for i in lista] if g == "DEZ"
                  else tabele_grup.get(g))
        if not starty:
            dodaj(a + 1, "K8", f"brak tabeli grupy {g} (typ zadeklarowany w nagłówku karty)",
                  f"wymaganych pól: {len(pola)}")
            continue
        etykiety = [klucz_etykiety(e) for s in sorted(starty) for e in wiersze_tabeli(linie, s)]
        licznik = {}
        for p2 in pola:
            for s in set(rdzenie(bez_nawiasow(p2))):
                licznik[s] = licznik.get(s, 0) + 1
        wyrozniki = frozenset(s for s, n in licznik.items() if n == 1 and len(s) >= 3)
        for pole in pola:
            alts = klucze_pola(pole)
            if not alts:
                continue
            if any(pasuje(al, e, wyrozniki) for al in alts for e in etykiety):
                continue
            # fakt bywa zapisany w innej sekcji karty (np. użytkownik w §2) — wiersza w §4 to nie zastępuje,
            # ale odróżnia „przenieś wiersz” od „nie ma tego faktu w karcie”
            gdzie = next((sek for klucz, sek in poza4 if any(pasuje(al, klucz, wyrozniki) for al in alts)), None)
            opis = f"brak wiersza wymaganego w {g}" + (f" — pole jest poza §4 ({gdzie})" if gdzie else "")
            dodaj(sorted(starty)[0] + 1, "K8", opis, pole[:100])


def komorki(linia):
    """Podział wiersza tabeli na komórki po niezescape'owanych |."""
    s = linia.strip()
    czesci = re.split(r"(?<!\\)\|", s)
    if s.startswith("|"):
        czesci = czesci[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        czesci = czesci[:-1]
    return [c.strip() for c in czesci]


def w_cytacie(linia, start, end):
    for m in CYTAT_RE.finditer(linia):
        if m.start() <= start and end <= m.end():
            return True
    return False


def ctx(linia, start, end, szer=45):
    a = max(0, start - szer)
    b = min(len(linia), end + szer)
    t = linia[a:b].replace("\n", " ")
    return ("…" if a else "") + t + ("…" if b < len(linia) else "")


def sprawdz(sciezka, dzis):
    with open(sciezka, encoding="utf-8") as f:
        linie = f.read().splitlines()
    flagi = []  # (nr, klasa, opis, kontekst, w_cytacie)

    def dodaj(nr, klasa, opis, kontekst, cyt=False):
        flagi.append((nr, klasa, opis, kontekst, cyt))

    kod = False
    naglowek = None      # komórki nagłówka bieżącej tabeli
    kol_zn = []          # indeksy kolumn znacznika
    kol_sz = []          # indeksy kolumn „szukano”
    for i, linia in enumerate(linie, 1):
        if linia.strip().startswith("```"):
            kod = not kod
            continue
        if kod:
            continue
        if STATUS_RE.search(linia):
            continue

        # ---------- tabele ----------
        jest_tabela = linia.lstrip().startswith("|")
        kom = None
        if jest_tabela:
            if naglowek is None:
                naglowek = komorki(linia)
                kol_zn = [k for k, c in enumerate(naglowek) if ZNACZNIK_KOL.search(c)]
                kol_sz = [k for k, c in enumerate(naglowek) if SZUKANO_KOL.search(c)]
                kom = None
            elif SEPARATOR.match(linia.strip()):
                pass
            else:
                kom = komorki(linia)
                if len(kom) != len(naglowek):
                    dodaj(i, "K2", f"{len(kom)} komórek, nagłówek ma {len(naglowek)}", linia[:90])
                for k in kol_zn:
                    if k >= len(kom) or len(kom) != len(naglowek):
                        continue
                    c = kom[k]
                    kolnazwa = naglowek[k]
                    if MARKER_OK.match(c):
                        m = MARKER_W_NAWIASIE.search(c)
                        if m:
                            dodaj(i, "K3", f"dopisek wewnątrz nawiasu znacznika ({kolnazwa})", m.group(0)[:70])
                        continue
                    m = MARKER_W_NAWIASIE.match(c)
                    if m:
                        opis = "dopisek wewnątrz nawiasu znacznika"
                    elif MARKER_GOLY.match(c):
                        opis = "znacznik bez nawiasów"
                    elif re.match(r"[—–-]?\s*nie dotyczy", c, re.I):
                        opis = "gołe „nie dotyczy” zamiast znacznika"
                    elif c in ("", "—", "-", "–"):
                        if any(MARKER_OK.match(x) for j, x in enumerate(kom) if j != k):
                            dodaj(i, "K3i", f"pusta komórka znacznika, znacznik w innej kolumnie ({kolnazwa})",
                                  linia[:80])
                            continue
                        opis = ("wiersz „nie dotyczy” bez znacznika" if any(re.match(r"\**nie dotyczy", x, re.I) for x in kom)
                                else "pusta komórka znacznika (brak znacznika w całym wierszu)")
                    else:
                        opis = "komórka nie zaczyna się od znacznika"
                    # wiersz-odsyłacz („Szczegóły §4.1”, „patrz §4.2”) — znacznik stoi w tabeli docelowej
                    if opis.startswith(("pusta", "komórka nie")) and (
                            ODSYLACZ.match(c) or (c in ("", "—", "-", "–") and len(kom) > 1 and ODSYLACZ.match(kom[1]))):
                        dodaj(i, "K3i", f"wiersz-odsyłacz bez znacznika ({kolnazwa})", linia[:80])
                        continue
                    dodaj(i, "K3", f"{opis} ({kolnazwa})", c[:70] or "(pusto)")
        else:
            naglowek = None

        # ---------- K1 ślady procesu ----------
        for nazwa, rx in SLADY_RE:
            for m in rx.finditer(linia):
                wyj = WYJATKI.get(nazwa)
                if wyj:
                    okno = linia[max(0, m.start() - 30): m.end() + 30]
                    trafione = False
                    for w in wyj.finditer(okno):
                        # wyjątek musi obejmować to dopasowanie
                        ws = max(0, m.start() - 30) + w.start()
                        we = max(0, m.start() - 30) + w.end()
                        if ws <= m.start() < we or ws < m.end() <= we:
                            trafione = True
                            break
                    if trafione:
                        continue
                cyt = w_cytacie(linia, m.start(), m.end())
                dodaj(i, "K1", nazwa + (" [w cytacie]" if cyt else ""), ctx(linia, m.start(), m.end()), cyt)

        # ---------- K4 [BRAK] bez „szukano” ----------
        if BRAK_RE.search(linia) and not SZUKANO_RE.search(linia):
            ok = False
            if jest_tabela and kom is not None and kol_sz:
                ok = any(k < len(kom) and kom[k] not in ("", "—", "-", "–") for k in kol_sz)
            if not ok and not (jest_tabela and kom is None):
                m = BRAK_RE.search(linia)
                dok = kom is not None and any(
                    k < len(kom) and kom[k] not in ("", "—", "-", "–")
                    for k, h in enumerate(naglowek or []) if re.match(r"dok", h, re.I))
                opis = ("[BRAK] bez „szukano” (jest inne wskazanie źródła)" if dok or INNE_WSKAZANIE.search(linia)
                        else "[BRAK] bez „szukano” i bez wskazania, gdzie szukano")
                dodaj(i, "K4", opis, ctx(linia, m.start(), m.end(), 60))

        # ---------- K5 daty w przyszłości ----------
        for m in DATA_RE.finditer(linia):
            try:
                d = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                dodaj(i, "K5", "nieistniejąca data", m.group(0))
                continue
            if d > dzis:
                okno = linia[max(0, m.start() - 60): m.start()]
                if WAZNOSC.search(okno):
                    continue
                dodaj(i, "K5", f"data w przyszłości ({m.group(0)} > {dzis})", ctx(linia, m.start(), m.end()))

        # ---------- K6 ----------
        for m in JW_RE.finditer(linia):
            dodaj(i, "K6", "„(cytat jw.)” zamiast cytatu", ctx(linia, m.start(), m.end()))

    # ---------- K7 / K8 (osobne przejście po §4) ----------
    sprawdz_forme4(sciezka, linie, dodaj)
    flagi.sort(key=lambda f: (f[0], f[1]))
    return flagi


def main(argv):
    dzis = dt.date.today()
    cicho = False
    pliki = []
    it = iter(argv)
    for a in it:
        if a == "--dzis":
            dzis = dt.date.fromisoformat(next(it))
        elif a == "--cicho":
            cicho = True
        else:
            pliki.extend(sorted(glob.glob(a)) or [a])
    if not pliki:
        print(__doc__)
        return 2

    suma = {}
    blad = False
    karty_z_bledem = 0
    for p in pliki:
        flagi = sprawdz(p, dzis)
        twarde = [f for f in flagi if (f[1] in EXIT_KLASY) or (f[1] == "K1" and not f[4])]
        if twarde:
            blad = True
            karty_z_bledem += 1
        for f in flagi:
            klucz = f[1] + (" (w cytacie)" if f[4] else "")
            suma[klucz] = suma.get(klucz, 0) + 1
        if cicho and not flagi:
            continue
        print(f"== {p} — flag: {len(flagi)} (blokujących: {len(twarde)})")
        for nr, kl, opis, kontekst, cyt in flagi:
            print(f"  w.{nr} {kl}{'' if (kl in EXIT_KLASY or (kl == 'K1' and not cyt)) else '~'} {opis}: {kontekst}")
    print("\n== PODSUMOWANIE")
    print(f"kart: {len(pliki)}, z flagami blokującymi: {karty_z_bledem}")
    for k in sorted(suma):
        print(f"  {k}: {suma[k]}")
    print("(~ = flaga informacyjna, nie wpływa na exit code: K1 w cytacie, K3i, K4)")
    return 1 if blad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
