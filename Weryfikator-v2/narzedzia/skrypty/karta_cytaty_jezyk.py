#!/usr/bin/env python3
"""v2 (2026-09-17) - zmiany wzgledem karta_cytaty_jezyk.py (raport: 04-opisy-produktow/kontrola/
TEST-SKRYPTU-karta_cytaty_jezyk_v2-2026-09-17.md):
  V2-1 napisy symboli z etykiet/katalogow (NON STERILE, STERILE R/EO, LATEX, PHT, CE 0123, REF, LOT,
       "[symbol: ...]") nie sa tekstem obcojezycznym - usuwane przed wykrywaniem jezyka;
  V2-2 dokument z jezykiem z kolumny "Jezyk" = tylko PL: pojedyncze obce slowo funkcyjne (np. "non") nie
       przebija jezyka dokumentu - potrzeba >=2 roznych obcych slow funkcyjnych;
  V2-3 cytat bedacy terminem wyszukiwania ("szukano ... „Biozid”", "0 wzmianek „active substance”",
       "pod katem „...”", "nie zawiera ... „...”") nie jest cytatem faktu;
  V2-4 kody klasyfikacji CLP/GHS (Met. Corr. 1, Eye Irrit. 2, H290, P280, EUH208) usuwane przed wykrywaniem;
  V2-5 rejestr dokumentow bez zaleznosci od jednego slowa: opis zaczynajacy sie od "Strona" w
       kolumnie Typ ("Strona SDS ..." = strona, nie SDS); jezyk PL z opisu odrzucany, gdy domena URL
       wskazuje obcy kraj, a plik nie ma kodu PL; typ "inne" jest polskim odpowiednikiem tylko dla siebie;
       dodatkowe frazy nieudanego szukania ("tylko DE/GB");
  V2-6 split wierszy tabeli nie tnie na "\\|" (escapowana kreska w tresci komorki).

C - bramka jezykowa cytatow (STANDARD-KARTY-PL-v2.md par.1/par.1a): cytat obcojezyczny (EN/DE/IT/FR/NL/ES/NO/PT/...)
przy fakcie, gdy karta ma polski dokument TEGO SAMEGO TYPU, oraz ten sam fakt cytowany w dwoch jezykach naraz.

Z tabeli dokumentow (par.3 karty) buduje mape: identyfikator dokumentu (D1, D2a, #3, "3" bez prefiksu, W16 ...)
-> typ (SDS / ulotka-IFU / etykieta / strona / katalog / URPL / projekt odniesienia / inne, heurystyka z kolumny "Typ" + URL/
nazwy pliku) -> jezyk (kolumna "Jezyk", gdy jest; w przeciwnym razie z kolumny "Typ"/nazwy pliku/URL: kody "PL",
"EN", "DE"... oddzielone _ - . / ( ) lub spacja). "projekt odniesienia" i "URPL" bez wykrytego jezyka domyslnie PL (sklep i
rejestr sa polskie).

W wierszach tabel faktow (par.2, par.4, spektrum, C7, par.5, par.7, par.8 - numeracja wg tresci naglowka, nie
tylko numeru, bo karty numeruja niespojnie) szuka cytatow w cudzyslowie ( "..." / "..." ) w komorce "Cytat"
(albo w C7: "Zdanie zrodla (doslownie)", gdzie caly wiersz to cytat). Dokument cytatu: etykieta "D5:"/"#4:"/
"D2 (PL):" tuz przed cytatem w tej samej komorce; brak etykiety -> kolumna "Dok." (parsowana pozycyjnie, gdy
liczba tokenow = liczbie cytatow, w przeciwnym razie pierwszy pasujacy token dla wszystkich).

Jezyk cytatu: polskie znaki diakrytyczne / slowa funkcyjne PL, EN, DE, IT, FR, NL, ES, NO, PT. Krotkie cytaty
bez ciagu liter >=3 (liczby, kody, normy) = "neutralny" i sa pomijane. Znacznik jezykowy w nawiasie tuz przy
etykiecie dokumentu (np. "D2 (NO):", "D5 (PL, l.223-224):") ma pierwszenstwo przed heurystyka tresci.

FLAGI:
  A OBCY_PRZY_PL - cytat obcojezyczny, dok. tego typu ma polska wersje w bibliotece karty (projekt odniesienia i inne
    dokumenty oznaczone jako "nie zrodlo faktow" nie licza sie jako ta polska wersja). Zasada ostroznosci:
    wiersz z adnotacja o rozjezdzie rewizji/wersji ("rozjazd"/"rewizj"/"roznic"/"rozbiez"/"sprzeczn"/"vs"/
    "podaje inaczej"/dwa numery wersji "v7...v8") albo o braku polskiego odpowiednika DLA TEGO FAKTU ("brak
    polsk..."/"rynek DE") -> OBCY_UZASADNIONY? (informacyjne, nie liczy sie do exit 1), nie FAIL.
  B DUBEL_JEZYKOWY - ten sam wiersz cytuje ten sam fakt w >=2 jezykach. Ta sama zasada ostroznosci ->
    DUBEL_UZASADNIONY? (informacyjne, nie liczy sie do exit 1).
  C BRAK_TLUMACZENIA (slabsza, informacyjna) - cytat obcy bez slowa "tlum"/"tlumaczenie" w wierszu.
  D DO_PRZEGLADU (informacyjna) - cytat bez jednoznacznej atrybucji do dokumentu (kolumna "Dok." ma wiecej
    niz jeden token, liczba nie zgadza sie z liczba nierozwiazanych cytatow) - nie zgadujemy dokumentu, ale
    tez nie gubimy cicho sygnalu do recznego sprawdzenia.

To lista do REGCZNEJ weryfikacji, nie werdykt: trafienie nie dowodzi samo w sobie naruszenia standardu (patrz
raport testowy skryptu), a 0 trafien nie dowodzi zgodnosci (inny styl cytowania, jezyk spoza listy, literowka).

Uzycie: python _skrypty/karta_cytaty_jezyk_v2.py <karta.md> [<karta2.md> ...]
"""
import os
import re
import sys
import konfig  # profil projektu: tokeny naszego serwisu, jezyk rynku (weryfikacja.json)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SEPARATOR = re.compile(r"^\|[\s:|-]+\|?\s*$")
QUOTE_RE = re.compile(r"[„\"]([^„”\"\n]{2,600})[”\"]")
KNOWN_LANGS = {
    "PL", "EN", "DE", "GB", "IT", "FR", "NL", "ES", "NO", "PT", "RU", "CZ", "SK",
    "SE", "DK", "FI", "HU", "RO", "BG", "HR", "SI", "LT", "LV", "EE", "GR", "TR",
}
RECONCILED_RE = re.compile(
    r"rozjazd|rewizj|różnic|rozbież|\bvs\b|podaje inaczej|sprzeczn|niezgodn\w*\s+z\s+pozwoleniem|"
    r"\bv\d+\b[^|]{0,40}\bv\d+\b",  # np. "PL v7 ... EN v8" - rozjazd wersji bez slowa "rozjazd"
    re.I,
)
TLUM_RE = re.compile(r"tlum|tłum", re.I)
TLUM_INLINE_RE = re.compile(r"(tłumaczenie robocze|tlumaczenie robocze|tłum\.?|tlum\.?)\s*:?\s*$", re.I)
EXCLUDE_DOC_RE = re.compile(
    r"nie jest źódł|nie źródło|nie stanowi źródła|"
    r"tylko do porównania|nieaktualn|stara (wersja|receptura)|inna receptura|przestarzał|"
    r"nie dotyczy (tego|naszego) sku|wariant(u)? siostrzan|nie używan[ay] jako źródło|"
    r"chronion|zabezpieczon|hasłem|niedostępn|niedostepn|brak treści|brak tresci",
    re.I,
)
# Fakt oznaczony przez autora jako nieposiadajacy polskiego odpowiednika (rynek DE/EN, brak polskiej
# wersji tego szczegolu) - standard nie wymaga PL dla takiego faktu, wiec flaga A jest tu falszywym
# alarmem (heurystyka dziala na poziomie typu dokumentu, nie faktu - patrz raport testowy pkt 6).
FACT_NO_PL_RE = re.compile(
    r"brak polsk|nie ma polsk|nie posiada polsk|"
    r"rynk\w*\s+(DE|EN|GB|FR|IT|ES|NL|NO|PT)\b",  # "rynek/rynku/rynkowy DE" - dowolna odmiana
    re.I,
)

LANG_WORDS = {
    "PL": {"nie", "jest", "oraz", "przez", "który", "która", "które", "moze", "może",
           "nalezy", "należy", "mozna", "można", "jezeli", "jeżeli", "tylko", "takze", "także",
           "bez", "przy", "stosowac", "stosować", "uzycia", "użycia", "produktu", "wodq", "wodą",
           "dzialanie", "działanie", "dzialania", "działania", "sie", "się", "dla", "gdy",
           "bezbarwny", "bezbarwna", "przezroczysty", "przezroczysta", "charakterystyczny", "charakterystyczna",
           "ciecz", "staly", "stały", "ciekly", "ciekły", "zapach", "barwa", "kolor", "gestosc",
           "gęstość", "temperatura", "wyglad", "wygląd", "postac", "postać",
           "rozpuszczalnosc", "rozpuszczalność", "brak", "dane", "niedostepne", "niedostępne",
           "zawartosc", "zawartość", "wlasciwosci", "właściwości"},
    "EN": {"the", "and", "for", "with", "this", "that", "shall", "must", "should", "not", "are", "use",
           "from", "which", "product", "instructions", "contains", "concentration", "minutes", "after",
           "before", "following", "container", "label", "warning", "leave", "minimum", "maximum", "months",
           "value", "point", "flash", "density", "colour", "color", "odour", "odor", "solubility", "soluble",
           "melting", "boiling", "flammable", "temperature", "appearance", "physical", "state", "clear",
           "liquid", "yellow", "white", "advised", "against", "section", "available", "data"},
    "DE": {"der", "die", "das", "und", "mit", "für", "nicht", "ist", "sind", "oder", "auf", "von", "zu",
           "bei", "nach", "sich", "eine", "einen", "kann", "muss", "wird", "werden", "nur", "auch", "alle",
           "diese", "dieser", "produkt", "achtung", "gebrauch", "anwendung"},
    "IT": {"il", "la", "di", "che", "non", "per", "con", "una", "sono", "del", "alla", "degli", "delle",
           "dei", "gli", "questo", "questa", "sul", "dalla", "prodotto", "utilizzare", "dopo", "prima"},
    "FR": {"le", "les", "des", "est", "pour", "avec", "dans", "sur", "pas", "une", "vous", "ne", "ce",
           "du", "au", "aux", "produit", "utiliser", "après", "avant"},
    "NL": {"het", "een", "van", "voor", "niet", "met", "zijn", "wordt", "kan", "moet", "deze", "dit",
           "gebruik", "product"},
    "ES": {"el", "los", "las", "de", "que", "para", "con", "no", "es", "una", "este", "esta", "producto",
           "después", "antes"},
    "NO": {"og", "ikke", "for", "med", "som", "kan", "skal", "inneholder", "produkt", "etter", "denne"},
    "PT": {"não", "para", "com", "que", "de", "este", "esta", "produto", "após", "antes",
           "contêm", "contém"},
}
PL_DIACRITICS = re.compile(r"[ąćęłńóśźż]")
WORD_RE = re.compile(r"[a-zàâäéèêëïîôöùûü"
                      r"çąćęłńóśźż]+", re.I)
ALPHA_RUN_RE = re.compile(r"[a-zA-ZÀ-ſ]{3,}")

# Podzbior PRAWDZIWIE funkcyjnych slow (spojniki/przyimki/zaimki/czasowniki modalne) z LANG_WORDS,
# bez tresciowych dodatkow (kolory, przymiotniki SDS typu "liquid"/"flammable", "produkt"/"gebrauch"
# itp.), ktore tam trafily po to, by lapac realna proze fizykochemiczna ("Appearance: clear liquid").
# Uzywany WYLACZNIE w _pl_override ponizej: pojedyncze trafienie tresciowego slowa (np. "white" w
# nazwie zapachu "White Flower", "liquid"/"flammable" w nazwie przewozowej UN) nie dowodzi zdania w
# obcym jezyku - prawdziwe slowo funkcyjne (np. angielskie "and") dowodzi (raport testowy, poprawka
# tlumaczenia/nazw wlasnych 2026-09-16, velox-spray L133 "White Flower" i durr-id-220 L87 UN name).
CORE_FUNC_WORDS = {
    "EN": {"the", "and", "for", "with", "this", "that", "shall", "must", "should", "not", "are",
           "from", "which", "before", "after", "following", "against"},
    "DE": {"der", "die", "das", "und", "mit", "für", "nicht", "ist", "sind", "oder", "auf", "von",
           "zu", "bei", "nach", "sich", "eine", "einen", "kann", "muss", "wird", "werden", "nur",
           "auch", "alle", "diese", "dieser"},
    "IT": {"il", "la", "di", "che", "non", "per", "con", "una", "sono", "del", "alla", "degli",
           "delle", "dei", "gli", "questo", "questa", "sul", "dalla", "dopo", "prima"},
    "FR": {"le", "les", "des", "est", "pour", "avec", "dans", "sur", "pas", "une", "vous", "ne",
           "ce", "du", "au", "aux", "après", "avant"},
    "NL": {"het", "een", "van", "voor", "niet", "met", "zijn", "wordt", "kan", "moet", "deze", "dit"},
    "ES": {"el", "los", "las", "de", "que", "para", "con", "no", "es", "una", "este", "esta",
           "después", "antes"},
    "NO": {"og", "ikke", "for", "med", "som", "kan", "skal", "etter", "denne"},
    "PT": {"não", "para", "com", "que", "de", "este", "esta", "após", "antes"},
}
# Markery "to jest zapis techniczny/rejestrowy, nie zdanie" - numer CAS/WE/REACH (cyfry-myslnik-cyfry),
# etykiety "Nr"/"CAS"/"WE"/"REACH", zakres procentowy (%, >=, <). Przy takich markerach dopuszczamy w
# cytacie jedno prawdziwe obce slowo funkcyjne (np. "and" w oficjalnej nazwie INCI "branched and
# linear") bez odrzucania nadpisania na PL - to wciaz nazwa/wpis rejestrowy, nie proza.
TECH_MARKER_RE = re.compile(r"\bCAS\b|\bWE\b|\bREACH\b|\bNr\.?\b|\d+-\d+-\d+|\d+\s*%|≥|≤", re.I)

TYPE_RULES = [
    ("wlasny", tuple(konfig.tokeny_wlasne())),
    ("URPL", ("urpl",)),
    ("SDS", ("sds", "karta charakterystyki")),
    ("ulotka-IFU", ("ifu", "ulotk", "instrukcj", "gebrauchsanweisung", "booklet")),
    ("etykieta", ("etykiet", "label")),
    ("katalog", ("katalog", "broszur", "folder", "techniczna", "karta produktu", "depliant", "scheda",
                 "fact sheet", "factsheet", "sell sheet", "tds", "plakat")),
    ("strona", ("stron",)),
]
# "website" USUNIETE z kluczy "strona": to artefakt sciezki URL (ecolabhealthcare.de/website/...),
# ktory pojawia sie identycznie w linkach do stron I do plikow PDF (np. tabeli dozowania) - lapal
# PDF jako "strona" i falszywie porownywal go z polska strona producenta (raport testowy, sekusept-
# activ D7/L80). Typ "strona" ma teraz zrodlo wylacznie w kolumnie "Typ" (slowo "strona"/"witryna").


# Wiersz §3 opisujacy NIEUDANE poszukiwanie polskiego dokumentu (np. "ponowne sprawdzenie PL" bez
# wyniku, "bez PDF", "brak statycznych linkow do pobrania") nie jest sam w sobie polskim dokumentem -
# to opis SZUKANIA polskiej wersji, nie polska wersja. Bez tego wyjatku slowo "PL" w takim opisie
# (albo w kolumnie Jezyk skopiowanej z niego) rejestrowalo caly wiersz jako "polski dokument tego
# typu" (dodatkowy blad: omnisept D13 "Strona SDS Omnident (ponowne sprawdzenie PL)" -> typ SDS falszywie
# oznaczony jako majacy polski odpowiednik -> 71 falszywych OBCY_PRZY_PL dla kazdego niemieckiego
# cytatu z SDS DE tego samego typu; D14/D15 analogicznie dla typu "inne" przez slowo "PL" w nazwie
# dystrybutora/sekcji "Downloads PL", mimo ze oba wiersze wprost mowia "bez PDF"/"brak statycznych
# linkow"). Wymagamy "brak" + konkretny rzeczownik (nie goly "brak" - ten pojawia sie niewinnie
# wszedzie, np. "brak daty", "brak towaru", i nie moze kasowac PL prawdziwym dokumentom, patrz raport
# testowy retest zeta-3-wipes/prosept-jet-forte, gdzie "strona producenta PL ... brak daty" MUSI
# zostac polskim dokumentem typu "strona").
DOC_UNRESOLVED_RE = re.compile(
    r"nie znaleziono|nie znalazł\w*|\bszukano\b|ponowne sprawdzenie|"
    r"brak\s+(?:pdf|wersji|dokumentu|pliku|statycznych)|bez\s+pdf|"
    # V2-5: "grep „x” — tylko DE/GB" = strona z lista wylacznie obcych wersji (omnisept D13)
    r"tylko\s+(?-i:DE|EN|GB|IT|FR|NL|ES)(?:\s*[/,]\s*(?-i:DE|EN|GB|IT|FR|NL|ES))*\b(?!\s*\d)",
    re.I,
)
# V2-5: domena URL w obcym kraju = sprzeczny sygnal dla "PL" wzietego tylko z opisu w kolumnie Typ.
FOREIGN_TLD = {"de": "DE", "it": "IT", "fr": "FR", "nl": "NL", "es": "ES", "uk": "EN", "no": "NO",
               "pt": "PT", "at": "DE", "ch": "DE", "cz": "CZ", "se": "SE", "dk": "DK", "fi": "FI"}
HOST_RE = re.compile(r"https?://([^/\s|]+)", re.I)
# V2-5: typy, ktore moga byc "polskim odpowiednikiem tego samego typu". "inne" to worek (certyfikat,
# deklaracja, strona dystrybutora z linkami) - porownanie "ten sam typ" nie ma tam sensu.
PL_COUNTERPART_TYPES = {"SDS", "ulotka-IFU", "etykieta", "katalog", "strona", "URPL"}
# Wiersz bez pliku dokumentu wcale (kolumna "Plik lokalny" bez rozszerzenia pdf/txt/html/png) tez nie
# moze byc polskim dokumentem tego typu - to samo zabezpieczenie z drugiej strony (nie opis awarii,
# tylko brak jakiegokolwiek pliku do przypisania).
DOC_FILE_EXT_RE = re.compile(r"\.(pdf|txt|html?|png)\b", re.I)


NEGATED_TYPE_RE = re.compile(
    r"inny typ dokumentu niż\s+\S+|różny\w* (?:typ\w* )?(?:dokumentu )?od\s+\S+|"
    r"nie jest (?:to )?\S+", re.I)
# "Render/zrzut/widok strony N" to zdjecie STRONICY innego dokumentu (np. SDS), nie osobny dokument
# typu "strona internetowa" - bez tego "stron" jako goly podciag lapie odmiane "strony" (numer
# stronicy) i falszywie typuje render SDS jako "strona" (raport testowy, sekusept-activ D9/D7 - patrz
# tez URL-owy artefakt "/website/" nizej w classify_type).
RENDER_OF_PAGE_RE = re.compile(r"(render|zrzut|widok|screenshot|\bskan\w*)\w*\s+stron\w*", re.I)


STRONA_HEAD_RE = re.compile(r"^[\s*_`„\"(\[]*(?:pod)?stron[aey]\b", re.I)


def _classify_from_keys(t):
    # V2-5: "projekt odniesienia" i "URPL" wygrywaja zawsze (odcisk sklepu / rejestr). Opis ZACZYNAJACY sie od
    # "Strona"/"Podstrona" to strona internetowa, nawet gdy dalej wymienia SDS/IFU ("Strona SDS
    # Omnident" = strona z lista SDS, nie SDS; "strona producenta PL — sprawdzone: API ... SDS").
    # Dawniej wygrywal typ wczesniejszy na liscie TYPE_RULES, wiec kazda wzmianka "SDS" w opisie strony
    # robila z niej SDS (omnisept D13). Celowo waskie: ogolna regula "najwczesniejsze slowo" zmieniala
    # typ "Karta techniczna / IFU" i "broszura" na katalog i przestawiala flagi w 5 kartach.
    for typ, keys in TYPE_RULES[:2]:
        if any(k in t for k in keys):
            return typ
    if STRONA_HEAD_RE.match(t):
        return "strona"
    for typ, keys in TYPE_RULES[2:]:
        if any(k in t for k in keys):
            return typ
    return None


def classify_type(typ_text, secondary_text=""):
    """Klasyfikacja typu dokumentu. Kolumna "Typ" (typ_text) ma pierwszenstwo - dopiero gdy nic tam
    nie pasuje, dokladamy URL/nazwe pliku (secondary_text). Bez tego np. link PDF-a zawierajacy w
    sciezce segment "/website/" (artefakt URL, nie tresc dokumentu) byl klasyfikowany jako "strona"
    mimo ze kolumna Typ mowi "Tabela dozowania" - falszywy alarm OBCY_PRZY_PL, bo skrypt porownywal
    PDF z tabela do niepowiazanej polskiej strony producenta (raport testowy, sekusept-activ L80)."""
    primary = NEGATED_TYPE_RE.sub(" ", typ_text).lower()
    primary = RENDER_OF_PAGE_RE.sub(" ", primary)
    if re.search(r"\bpi\b", primary) and not any(k in primary for k in ("sds", *konfig.tokeny_wlasne())):
        return "ulotka-IFU"
    found = _classify_from_keys(primary)
    if found is not None:
        return found
    if secondary_text:
        combined = NEGATED_TYPE_RE.sub(" ", secondary_text).lower()
        combined = RENDER_OF_PAGE_RE.sub(" ", combined)
        found = _classify_from_keys(combined)
        if found is not None:
            return found
    return "inne"


CZESC_RE = re.compile(r"\bcz\.?\s*(?=[IVX\d])", re.I)


def parse_langs(text):
    text = CZESC_RE.sub(" ", text)  # polskie "cz. I / cz. II" (czesc) != jezyk CZ
    cleaned = re.sub(r"[_\-./(),]", " ", text)
    langs = set()
    for tok in re.findall(r"\b([A-Za-z]{2})\b", cleaned):
        tu = tok.upper()
        if tu == "GB":
            tu = "EN"
        if tu == "CH":
            continue
        if tu in KNOWN_LANGS:
            langs.add(tu)
    return langs


def detect_lang(text):
    if not ALPHA_RUN_RE.search(text):
        return "neutral"
    low = text.lower()
    if PL_DIACRITICS.search(low):
        return "PL"
    words = set(WORD_RE.findall(low))
    if not words:
        return "neutral"
    # Slowa 2-literowe (np. FR "ce", "du", "le", "ne", "au") pomijamy w liczeniu trafien - to najczestsze,
    # najbardziej przypadkowe dopasowania (np. samodzielne "CE" - oznakowanie CE - trafia w FR "ce" = "to"
    # i potrafilo sklasyfikowac caly, skads polski, krotki cytat jako francuski). Slowa >=3-literowe
    # (np. niemieckie "und") zostaja jednym trafieniem wystarczajacym - to realne, jednoznaczne slowa
    # funkcyjne danego jezyka (raport testowy - dodatkowo znaleziony blad, velox-spray L119).
    words3 = {w for w in words if len(w) >= 3}
    scores = {lang: len(words3 & wl) for lang, wl in LANG_WORDS.items()}
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "neutral"
    ranked = sorted(scores.values(), reverse=True)
    if len(ranked) > 1 and ranked[0] == ranked[1]:
        return "neutral"
    return best


def split_row(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    # V2-6: "\|" to kreska w tresci komorki, nie granica kolumny
    return [c.strip() for c in re.split(r"(?<!\\)\|", s)]


def build_doc_registry(lines):
    registry = {}
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if line.lstrip().startswith("|") and i + 1 < n and SEPARATOR.match(lines[i + 1].strip()):
            header = split_row(line)
            header_low = [h.lower() for h in header]
            has_typ = "typ" in header_low
            has_url_or_plik = any("url" in h or "plik lokalny" in h for h in header_low)
            if has_typ and has_url_or_plik:
                idx_typ = header_low.index("typ")
                idx_jezyk = next((k for k, h in enumerate(header_low) if "język" in h or "jezyk" in h), None)
                idx_plik = [k for k, h in enumerate(header_low) if "plik lokalny" in h]
                idx_url = [k for k, h in enumerate(header_low) if "url" in h and "plik lokalny" not in h]
                j = i + 2
                while j < n and lines[j].lstrip().startswith("|"):
                    if SEPARATOR.match(lines[j].strip()):
                        j += 1
                        continue
                    row = split_row(lines[j])
                    if len(row) < 2:
                        j += 1
                        continue
                    doc_id = row[0].strip(" `*")
                    typ_text = row[idx_typ] if idx_typ < len(row) else ""
                    extra = " ".join(row[k] for k in idx_plik if k < len(row))
                    url_raw = " ".join(row[k] for k in idx_url if k < len(row))
                    url_text = re.sub(r"https?://[^/\s]+", " ", url_raw)
                    context = typ_text + " " + extra + " " + url_text
                    explicit = row[idx_jezyk].strip() if idx_jezyk is not None and idx_jezyk < len(row) else ""
                    # V2-2: kolumna "Jezyk" ma pierwszenstwo przed heurystyka; gdy nie daje sie
                    # odczytac (np. "—"), dopiero wtedy opis/plik/URL
                    explicit_langs = parse_langs(explicit) if explicit else set()
                    lang_src = "kolumna" if explicit_langs else "heurystyka"
                    langs = explicit_langs if explicit_langs else parse_langs(context)
                    if lang_src == "heurystyka" and langs == {"PL"}:
                        # V2-5: "PL" tylko z opisu, plik/sciezka bez kodu PL, a domena obca -> sprzecznosc
                        file_url_langs = parse_langs(extra + " " + url_text)
                        tlds = {FOREIGN_TLD.get(h.rsplit(".", 1)[-1].lower())
                                for h in HOST_RE.findall(url_raw)} - {None}
                        if "PL" not in file_url_langs and tlds:
                            langs = set()
                    type_cat = classify_type(typ_text, extra + " " + url_text)
                    if type_cat in ("wlasny", "URPL") and not langs:
                        langs = {"PL"}
                    row_text_all = " ".join(row)
                    doc_missing = not DOC_FILE_EXT_RE.search(extra)
                    if DOC_UNRESOLVED_RE.search(row_text_all) or doc_missing:
                        langs = langs - {"PL"}
                    excluded = bool(EXCLUDE_DOC_RE.search(row_text_all))
                    if doc_id and not SEPARATOR.match(lines[j].strip()):
                        registry[doc_id] = {"type": type_cat, "langs": langs, "raw": typ_text,
                                             "excluded": excluded, "lang_src": lang_src}
                    j += 1
                i = j
                continue
        i += 1
    return registry


ALLOWED_NUM = {"2", "4", "5", "7", "8"}
ALLOWED_KEYWORD_RE = re.compile(r"spektrum|\bC7\b|warunki użycia|warunki uzycia", re.I)


def heading_allowed(text):
    m = re.match(r"\s*(\d+)[.\)]", text)
    if m and m.group(1) in ALLOWED_NUM:
        return True
    return bool(ALLOWED_KEYWORD_RE.search(text))


NORM_REF_RE = re.compile(r"^[A-Za-z]{2,4}[\s-]?\d")


def find_inline_lang_tag(gap_text):
    # Znacznik jezyka jest TUZ przy etykiecie dokumentu ("D2 (NO):", "D5 (PL, l.223-224):") - dopuszczamy
    # tylko kilka znakow separatora (spacja, dwukropek, przecinek) miedzy etykieta a nawiasem. Bez tej
    # kotwicy re.search znajdowalby PIERWSZY nawias gdziekolwiek w gap_text, ktorym czesto jest przypadkowo
    # cytowana norma typu "(EN 374)" / "(EN 166)" nalezaca do WCZESNIEJSZEGO cytatu w tej samej komorce -
    # "EN" jest jednoczesnie kodem jezyka i prefiksem norm europejskich, wiec bez tego zabezpieczenia
    # kazda norma EN w poprzednim cytacie falszywie "zarazala" jezykiem angielskim kolejny (nieoznaczony)
    # cytat w tym samym wierszu (patrz raport testowy - zeta-3-wipes L115, "(EN 374)" z cytatu dok. 7
    # nadpisywalo jezyk kolejnego, polskiego zdania tego samego dokumentu).
    m = re.match(r"^[\s:,]{0,4}\(([^)]{1,24})\)", gap_text)
    if not m:
        return None
    inner = m.group(1).strip()
    if NORM_REF_RE.match(inner):
        return None  # np. "EN 374", "EN 14476" - numer normy, nie jezyk
    langs = parse_langs(inner)
    if len(langs) == 1:
        return next(iter(langs))
    return None


def dok_tokens(dok_cell, registry):
    if not dok_cell:
        return []
    parts = re.split(r"[;,/]|\s+oraz\s+|\s+i\s+|×", dok_cell)
    toks = []
    # Najdluzsze klucze najpierw: zlozony identyfikator typu "D2-PL" ma byc dopasowany W CALOSCI, a nie
    # uciety przez ogolny regex \d+[a-z]? do samego "D2" - gdy w rejestrze ISTNIEJE osobny wpis "D2"
    # (inny dokument/jezyk niz "D2-PL"), stare ciecie cicho podstawialo zly dokument (raport testowy,
    # dodatkowo znaleziony blad: wl-cid-wl-dry miesza D2/D2-PL, D8/D8-PL).
    keys_by_len = sorted(registry.keys(), key=len, reverse=True)
    for p in parts:
        p = p.strip().lstrip("#").strip()
        cand = None
        for k in keys_by_len:
            if p == k or p.startswith(k + " ") or p.startswith(k + "§") or p.startswith(k + "."):
                cand = k
                break
        if cand is None:
            m = re.match(r"([A-Za-z]*\d+[a-z]?)", p)
            cand = m.group(1) if m else p
        if cand in registry:
            toks.append(cand)
    return toks


def attribute_quotes(cell_text, dok_cell, registry, inline_ref_re):
    matches = list(QUOTE_RE.finditer(cell_text))
    results = []
    unresolved_idx = []
    ambiguous_idx = set()
    for m in matches:
        preceding_all = cell_text[max(0, m.start() - 30):m.start()]
        # "(tlum.: „...")" / "(tlumaczenie robocze: „...")" tuz przed cytatem = tlumaczenie robocze
        # autora, nie osobny cytat z dokumentu (par.1a) - NIE liczy sie do DUBEL/OBCY/BRAK_TLUMACZENIA
        # (patrz filtr is_translation w analyze()). WAZNE: mimo to zostaje w `results`/`unresolved_idx`
        # jako "slot" z doc_id=None, zamiast byc cicho pomijany (dawne `continue`) - jego zniknieciu
        # zawdzieczal sie dawny blad: gdy 2 realne cytaty w tym samym wierszu nie mialy wlasnej etykiety
        # w oknie 80 znakow (fallback na kolumne "Dok."), a tlumaczenie miedzy nimi znikalo z liczenia,
        # liczba "nierozwiazanych" cytatow PRZYPADKOWO zrownywala sie z liczba tokenow w "Dok." i skrypt
        # parowal je 1:1 w kolejnosci - myląc dokument OSTATNIEGO realnego cytatu z dokumentem tlumaczenia
        # (raport testowy, poprawka tlumaczen 2026-09-16: durr-id-212-forte L62, cytat D2 EN "For
        # instruments..." dostawal blednie doc=D10 tylko dlatego, ze tlumaczenie tuz po nim znikalo z puli).
        is_translation = bool(TLUM_INLINE_RE.search(preceding_all))
        # V2-3: wzorzec wyszukiwania traktujemy jak tlumaczenie robocze - slot zostaje (dla liczenia
        # fallbacku "Dok."), ale nie jest cytatem faktu
        if not is_translation and is_search_term(cell_text, m.start(), inline_ref_re):
            is_translation = True
        doc_id, lang_tag = None, None
        if inline_ref_re is not None and not is_translation:
            preceding = cell_text[max(0, m.start() - 80):m.start()]
            refs = list(inline_ref_re.finditer(preceding))
            chosen = None
            for cand in reversed(refs):
                token = cand.group(0).lstrip("#")
                after_char = preceding[cand.end():cand.end() + 1]
                # Etykieta jest ZAWSZE otwierajaca ("D2:", "D2 (PL):") - jesli zaraz po niej jest ")",
                # to znaczy, ze ten identyfikator jest WEWNATRZ cudzego nawiasu objasniajacego (np. "D1
                # (dane, ktorych brak w D2): "), a nie samodzielna etykieta - w takim razie to NIE jest
                # etykieta tego cytatu, nawet jesli jest blizej niz prawdziwa (dodatkowo znaleziony blad,
                # nie z listy raportu: prosept-jet-forte L94, cytat D1 blednie lapany przez blizsze "D2"
                # wewnatrz nawiasu "(dane, ktorych brak w D2)").
                if after_char == ")":
                    continue
                if token.isdigit():
                    before_char = preceding[cand.start() - 1] if cand.start() > 0 else ""
                    after_text = preceding[cand.end():cand.end() + 2]
                    # before_char=="" (dopasowanie na poczatku komorki) NIE oznacza poprzedzenia
                    # znakiem sekcji - "" in "§.,-" jest zawsze True w Pythonie, wiec bez warunku
                    # before_char != "" poprawna etykieta na starcie komorki bylaby odrzucana
                    # (patrz raport testowy blad 2).
                    if (before_char != "" and before_char in "§.,-") or re.match(r"^[.,]\d", after_text):
                        continue
                if token in registry:
                    chosen = cand
                    break
            if chosen is not None:
                doc_id = chosen.group(0).lstrip("#")
                lang_tag = find_inline_lang_tag(preceding[chosen.end():])
        results.append([m.group(1), doc_id, lang_tag, is_translation])
        if doc_id is None:
            unresolved_idx.append(len(results) - 1)
    if unresolved_idx:
        fallback = dok_tokens(dok_cell, registry)
        if len(fallback) == 1:
            for idx in unresolved_idx:
                results[idx][1] = fallback[0]
        elif len(fallback) == len(unresolved_idx):
            for idx, doc in zip(unresolved_idx, fallback):
                results[idx][1] = doc
        else:
            # Liczba tokenow w "Dok." nie zgadza sie z liczba nierozwiazanych cytatow (0, albo >1
            # bez jednoznacznego dopasowania 1:1) - nie zgadujemy pierwszego tokenu dla wszystkich
            # (dawny blad 3, fabrykowal zle dopasowanie). Zostawiamy doc_id=None; gdy jest choc jeden
            # kandydat w "Dok.", oznaczamy jako DO_PRZEGLADU zamiast cicho gubic sygnal.
            if len(fallback) >= 1:
                ambiguous_idx.update(unresolved_idx)
    return results, ambiguous_idx


def _pl_override(text, doc_id, content, registry):
    """STANDARD-KARTY-PL-v2 par.1a: cytat z pojedynczymi nazwami obcymi (INCI/CAS/UN, nazwa
    handlowa/zapach, skrot do 4 liter) w dokumencie zarejestrowanym jako jednoznacznie PL nie jest
    dowodem obcego jezyka - to nazwa/wpis rejestrowy, nie zdanie. Prog: PL-owych trafien slow (peuny
    LANG_WORDS) tyle samo albo wiecej niz obcych (majority), ALBO zero PRAWDZIWIE funkcyjnych obcych
    slow (waskie CORE_FUNC_WORDS, bez tresciowych typu "liquid"/"white") - ewentualnie dopuszczajac
    jedno takie slowo, gdy cytat ma marker rejestrowy (CAS/WE/REACH/Nr/zakres %) swiadczacy, ze to
    zapis techniczny, nie proza. Bez tego zabezpieczenia jedno przypadkowe tresciowe trafienie
    (nazwa zapachu "White Flower", nazwa przewozowa UN "FLAMMABLE LIQUID, CORROSIVE") przebijalo
    jezyk calego, skads polskiego dokumentu (raport testowy, poprawka 2026-09-16)."""
    if not doc_id:
        return content
    info = registry.get(doc_id)
    if not info or info["langs"] != {"PL"}:
        return content
    low = text.lower()
    words3 = {w for w in WORD_RE.findall(low) if len(w) >= 3}
    pl_hits = len(words3 & LANG_WORDS["PL"])
    f_hits = len(words3 & LANG_WORDS.get(content, set()))
    if pl_hits >= f_hits:
        return "PL"
    core_f_hits = len(words3 & CORE_FUNC_WORDS.get(content, set()))
    if core_f_hits == 0:
        return "PL"
    if core_f_hits == 1 and TECH_MARKER_RE.search(text):
        return "PL"
    # V2-2: jezyk PL podany wprost w kolumnie "Jezyk" tabeli dokumentow ma pierwszenstwo przed
    # heurystyka tresci - pojedyncze obce slowo funkcyjne (np. IT "non" w napisie z katalogu producenta) nie
    # wystarcza; zdanie obce ma zwykle >=2 rozne slowa funkcyjne.
    if core_f_hits == 1 and info.get("lang_src") == "kolumna":
        return "PL"
    return content


# V2-1: napisy symboli z etykiet/katalogow (ISO 15223-1 i pokrewne) - nie sa proza w zadnym jezyku.
SYMBOL_BRACKET_RE = re.compile(r"\[\s*symbol[^\]]*\]", re.I)
SYMBOL_TOKEN_RE = re.compile(
    r"\b(?:non[\s-]?sterile|sterile(?:\s+(?:EO|R|A)\b)?|do\s+not\s+resterili[sz]e|"
    r"latex(?:\s+free)?|PHT|DEHP|CE(?:\s*\d{4})?|REF|LOT|SN|UDI|MD|IVD|STERILIZE)\b",
    re.I,
)
# V2-4: klasy zagrozenia CLP/GHS i kody H/P/EUH - skroty urzedowe, nie tekst obcojezyczny.
CLP_RE = re.compile(
    r"\b(?:Met\.?\s*Corr|Skin\s+Corr|Skin\s+Irrit|Skin\s+Sens|Eye\s+Dam|Eye\s+Irrit|Resp\.?\s*Sens|"
    r"Aquatic\s+(?:Acute|Chronic)|Acute\s+Tox|Asp\.?\s*Tox|STOT\s+(?:SE|RE)|Flam\.?\s*(?:Liq|Sol|Gas|Aerosol)|"
    r"Ox\.?\s*(?:Liq|Sol|Gas)|Press\.?\s*Gas|Self-?react|Pyr\.?\s*(?:Liq|Sol)|Carc|Muta|Repr|Lact|"
    r"Expl|Org\.?\s*Perox)\.?\s*(?:\d[A-C]?)?|\b(?:EUH|H|P)\d{3}(?:\s*\+\s*[HP]\d{3})*\b",
    re.I,
)


def clean_for_lang(text):
    """Usuwa z cytatu elementy bez jezyka (symbole etykiet, kody CLP/H/P) przed wykrywaniem jezyka."""
    t = SYMBOL_BRACKET_RE.sub(" ", text)
    t = CLP_RE.sub(" ", t)
    t = SYMBOL_TOKEN_RE.sub(" ", t)
    return t


# V2-3: cytat bedacy WZORCEM WYSZUKIWANIA, nie zdaniem zrodla. Marker musi stac blizej cytatu niz
# ostatnia etykieta dokumentu (np. "D5/D6: 0 wzmianek „active substance”" - marker po etykiecie).
SEARCH_MARKER_RE = re.compile(
    r"szukan\w*|przeszuk\w*|\bgrep\w*|pod\s+kątem|pod\s+katem|wzmian\w*|\b0\s+trafie\w*|"
    r"brak\s+trafie\w*|nie\s+zawiera\w*|wyszukiw\w*",
    re.I,
)


def is_search_term(cell_text, start, inline_ref_re):
    preceding = cell_text[max(0, start - 160):start]
    markers = list(SEARCH_MARKER_RE.finditer(preceding))
    if not markers:
        return False
    last_marker = markers[-1].end()
    # miedzy markerem a cytatem nie moze byc zdania z innym cytatem-faktem: dopuszczamy tylko
    # separatory list wzorcow (przecinek, ukosnik, "i", "lub", "ani", inne cytaty-wzorce)
    between = preceding[last_marker:]
    between_wo_quotes = QUOTE_RE.sub(" ", between)
    if re.search(r"[.;]\s|\)\s*[:—–-]", between_wo_quotes):
        return False
    if inline_ref_re is not None:
        refs = [m for m in inline_ref_re.finditer(preceding)
                if preceding[m.end():m.end() + 1] != ")"]
        if refs and refs[-1].start() > last_marker:
            # etykieta dokumentu blizej niz marker: to cytat z dokumentu, chyba ze po etykiecie
            # stoi znowu lista wzorcow (etykieta w srodku "szukano w D2, D3 pod katem ...")
            return False
    return True


def quote_lang(text, doc_id, lang_tag, registry):
    text = clean_for_lang(text)
    if not ALPHA_RUN_RE.search(text):
        return "neutral"
    if lang_tag:
        return lang_tag
    content = detect_lang(text)
    if content != "neutral":
        return _pl_override(text, doc_id, content, registry)
    # Fallback na jezyk calego dokumentu ma sens dla realnej prozy bez rozpoznanych slow funkcyjnych, ale
    # nie dla golych skrotow/nazw list (np. "VAH", "IHO", "RKI", "DVV") - to nie sa zdania w jakimkolwiek
    # jezyku, wiec naciaganie ich jezykiem calego dokumentu tworzylo cytaty "obce" z tresci, ktora nie
    # wymaga tlumaczenia (raport testowy, dodatkowo znaleziony blad: manisoft L78). Wymagamy choc jednego
    # dwuliterowego ciagu MALYCH liter jako sygnalu, ze to faktycznie proza.
    if not re.search(r"[a-ząćęłńóśźż]{2,}", text):
        return "neutral"
    if doc_id and doc_id in registry:
        langs = registry[doc_id]["langs"]
        if len(langs) == 1:
            return next(iter(langs))
    return "neutral"


def is_fact_source(doc_id, registry):
    """"Karta projekt odniesienia" (typ projekt odniesienia) i dokumenty oznaczone w tabeli jako nie-zrodlo faktow /
    nieaktualne (EXCLUDE_DOC_RE) nie licza sie ani jako polski odpowiednik dla flagi A, ani jako
    jezyk do liczenia dubli w DUBEL_JEZYKOWY (raport testowy, pkt 5: projekt odniesienia to odcisk sklepu, nie
    zrodlo faktow producenta)."""
    info = registry.get(doc_id)
    if not info:
        return False
    if info["type"] == "wlasny":
        return False
    if info.get("excluded"):
        return False
    return True


def analyze(path):
    text = open(path, encoding="utf-8").read()
    lines = text.splitlines()
    registry = build_doc_registry(lines)
    type_pl_doc = {}
    for doc_id, info in registry.items():
        if ("PL" in info["langs"] and is_fact_source(doc_id, registry)
                and info["type"] in PL_COUNTERPART_TYPES):
            type_pl_doc.setdefault(info["type"], doc_id)
    if registry:
        keys_sorted = sorted(registry.keys(), key=len, reverse=True)
        # (?<!\w) PRZED alternatywa: bez tego np. "2" dopasowywaloby sie wewnatrz "...12" (koncowka
        # wiekszej liczby, np. daty), bo \b PO alternatywie sam nie pilnuje poczatku dopasowania
        # (patrz raport testowy blad 1).
        inline_ref_re = re.compile(r"(?<!\w)#?(?:" + "|".join(re.escape(k) for k in keys_sorted) + r")\b")
    else:
        inline_ref_re = None

    flags_a, flags_a_ok, flags_b, flags_b_ok, flags_c, flags_review = [], [], [], [], [], []
    in_scope = False
    scope_level = None
    header_low, idx_cytat, idx_dok = None, None, None
    n = len(lines)
    i = 0
    while i < n:
        raw = lines[i]
        stripped = raw.lstrip()
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            heading_text = stripped.lstrip("#").strip()
            if scope_level is None or level <= scope_level:
                in_scope = heading_allowed(heading_text)
                scope_level = level
            elif heading_allowed(heading_text):
                in_scope = True
            # deeper subheading that doesn't itself match: inherit current in_scope
            header_low, idx_cytat, idx_dok = None, None, None
            i += 1
            continue
        if not stripped.startswith("|"):
            header_low, idx_cytat, idx_dok = None, None, None
            i += 1
            continue
        if not in_scope:
            i += 1
            continue
        if i + 1 < n and SEPARATOR.match(lines[i + 1].strip()):
            header = split_row(raw)
            header_low = [h.lower() for h in header]
            idx_cytat = next((k for k, h in enumerate(header_low)
                               if "cytat" in h or "zdanie źródła" in h or "zdanie zrodla" in h), None)
            idx_dok = next((k for k, h in enumerate(header_low) if "dok" in h), None)
            i += 2
            continue
        if SEPARATOR.match(stripped):
            i += 1
            continue
        if header_low is None or idx_cytat is None:
            i += 1
            continue
        row = split_row(raw)
        if len(row) <= idx_cytat:
            i += 1
            continue
        cytat_cell = row[idx_cytat]
        dok_cell = row[idx_dok] if idx_dok is not None and idx_dok < len(row) else ""
        is_c7_style = "zdanie" in header_low[idx_cytat]
        ambiguous_idx = set()
        if is_c7_style and not QUOTE_RE.search(cytat_cell):
            whole = cytat_cell.strip().strip("„”\"")
            items = [[whole, None, None, False]] if whole else []
            if items and idx_dok is not None:
                toks = dok_tokens(dok_cell, registry)
                if toks:
                    items[0][1] = toks[0]
                    items[0][2] = find_inline_lang_tag(dok_cell)
        else:
            items, ambiguous_idx = attribute_quotes(cytat_cell, dok_cell, registry, inline_ref_re)

        line_no = i + 1
        row_label = row[0][:60] if row else ""
        for idx in ambiguous_idx:
            txt, _doc_id, _lang_tag, is_translation = items[idx]
            # Tlumaczenie robocze "(tlum.: ...)" bez wlasnej etykiety dokumentu nie jest sygnalem do
            # recznej weryfikacji atrybucji - to nie cytat z dokumentu, tylko notatka autora karty.
            if is_translation:
                continue
            if ALPHA_RUN_RE.search(txt):
                flags_review.append((line_no, row_label, txt))

        resolved = []
        for txt, doc_id, lang_tag, is_translation in items:
            if is_translation:
                continue  # tlumaczenie robocze - nie liczy sie jako cytat (par.1a)
            if doc_id is None or doc_id not in registry:
                continue
            if not is_fact_source(doc_id, registry):
                continue
            lang = quote_lang(txt, doc_id, lang_tag, registry)
            if lang == "neutral":
                continue
            resolved.append((doc_id, lang, txt))

        if resolved:
            reconciled = bool(RECONCILED_RE.search(raw))
            no_pl_fact = bool(FACT_NO_PL_RE.search(raw))
            has_tlum = bool(TLUM_RE.search(raw))
            for doc_id, lang, txt in resolved:
                if lang == "PL":
                    continue
                type_cat = registry[doc_id]["type"]
                pl_doc = type_pl_doc.get(type_cat)
                own_langs = registry[doc_id]["langs"]
                if pl_doc is None and "PL" in own_langs and is_fact_source(doc_id, registry):
                    # V2-5: typ "inne" nie jest odpowiednikiem dla INNYCH dokumentow, ale dokument z
                    # sekcja PL (np. deklaracja MDR "wielojezyczna, w tym PL"), z ktorego cytowano obcy
                    # fragment, jest polskim odpowiednikiem dla samego siebie (jak w oryginale)
                    pl_doc = doc_id
                if pl_doc is not None:
                    entry = (line_no, row_label, doc_id, lang, txt, type_cat, pl_doc)
                    # Zasada ostroznosci (standard PL v2 par.1): flaga A tylko gdy NIE ma w wierszu
                    # adnotacji o rozjezdzie rewizji (RECONCILED_RE, jak dla B - dawny blad 4) ani
                    # adnotacji, ze TEN fakt nie ma polskiego odpowiednika (FACT_NO_PL_RE, np. "rynek
                    # DE" / "brak polskiej wersji tego szczegolu") - w przeciwnym razie to zgodne ze
                    # standardem, nie naruszenie; ladujemy do OBCY_UZASADNIONY (informacyjne).
                    if reconciled or no_pl_fact:
                        flags_a_ok.append(entry)
                    else:
                        flags_a.append(entry)
                elif not has_tlum:
                    flags_c.append((line_no, row_label, doc_id, lang, txt))
            row_langs = sorted(set(l for _, l, _ in resolved))
            if len(row_langs) >= 2:
                snippet = raw.strip()[:180]
                if reconciled:
                    flags_b_ok.append((line_no, row_label, row_langs, snippet))
                else:
                    flags_b.append((line_no, row_label, row_langs, snippet))
        i += 1

    return registry, flags_a, flags_a_ok, flags_b, flags_b_ok, flags_c, flags_review


def main(paths):
    any_ab = False
    for path in paths:
        registry, flags_a, flags_a_ok, flags_b, flags_b_ok, flags_c, flags_review = analyze(path)
        name = os.path.basename(path)
        print(f"=== {name} ===")
        print(f"dokumentow w rejestrze: {len(registry)}")
        for ln, label, doc_id, lang, txt, type_cat, pl_doc in flags_a:
            print(f"L{ln} [OBCY_PRZY_PL] {label!r} dok={doc_id} jezyk={lang} typ={type_cat} "
                  f"(karta ma PL: {pl_doc}): „{txt[:140]}”")
        for ln, label, doc_id, lang, txt, type_cat, pl_doc in flags_a_ok:
            print(f"L{ln} [OBCY_UZASADNIONY?] {label!r} dok={doc_id} jezyk={lang} typ={type_cat} "
                  f"(karta ma PL: {pl_doc}): „{txt[:140]}”")
        for ln, label, langs, snippet in flags_b:
            print(f"L{ln} [DUBEL_JEZYKOWY] {label!r} jezyki={langs}: {snippet}")
        for ln, label, langs, snippet in flags_b_ok:
            print(f"L{ln} [DUBEL_UZASADNIONY?] {label!r} jezyki={langs}: {snippet}")
        for ln, label, doc_id, lang, txt in flags_c:
            print(f"L{ln} [BRAK_TLUMACZENIA] {label!r} dok={doc_id} jezyk={lang}: „{txt[:140]}”")
        for ln, label, txt in flags_review:
            print(f"L{ln} [DO_PRZEGLADU] {label!r} atrybucja niejednoznaczna (kilka dok. w \"Dok.\", "
                  f"brak jednoznacznej etykiety): „{txt[:140]}”")
        n_a, n_aok, n_b, n_bok, n_c, n_rev = (len(flags_a), len(flags_a_ok), len(flags_b),
                                               len(flags_b_ok), len(flags_c), len(flags_review))
        print(f"{name}: OBCY_PRZY_PL={n_a}, OBCY_UZASADNIONY?={n_aok}, DUBEL_JEZYKOWY={n_b}, "
              f"DUBEL_UZASADNIONY?={n_bok}, BRAK_TLUMACZENIA={n_c}, DO_PRZEGLADU={n_rev}")
        print()
        if n_a or n_b:
            any_ab = True
    sys.exit(1 if any_ab else 0)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1:])
