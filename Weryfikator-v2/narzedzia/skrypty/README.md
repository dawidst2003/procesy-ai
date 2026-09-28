# Skrypty — bramki deterministyczne

Wszystkie skrypty: **tylko czytają**, niczego nie zmieniają w artefaktach, nie chodzą do sieci (wyjątek:
`szukaj_zrodel_pl.py`; `kanarek.py` zapisuje wyłącznie kopie w podanym folderze kontrolera) i nie wymagają
zależności poza standardową biblioteką — poza obsługą PDF (`PyMuPDF`).
Python 3.12. Kodowanie: ustaw `PYTHONIOENCODING=utf-8`, inaczej Windows potnie polskie znaki.

**Wynik skryptu to lista miejsc do sprawdzenia, nie werdykt.** 0 trafień nie dowodzi poprawności
(inne słownictwo, inny język, treść na obrazku). Skrypt zdejmuje z kontroli pracę mechaniczną, nie osąd.

## Konfiguracja projektu

Skrypty czytają `weryfikacja.json` (szukanie: `--konfig` → `WERYFIKACJA_KONFIG` → najbliższy plik w górę
drzewa od podanej ścieżki → wartości domyślne). Wzór: `../weryfikacja.przyklad.json`.
Sprawdzenie, co skrypty widzą: `python skrypty/konfig.py <ścieżka do karty>`.

## Bramki blokujące (warunek wejścia do sędziego)

| Skrypt | Co sprawdza | Blokuje przy |
|---|---|---|
| `karta_forma.py` | forma karty: ślad procesu w treści (K1), rozjechana tabela (K2), znacznik w złej kolumnie (K3), `[BRAK]` bez „szukano" (K4, ostrzeżenie), data z przyszłości (K5), „cytat jw." (K6), brakująca/przestawiona kolumna (K7), brak wiersza wymaganego przez szablon (K8) | K1 poza cytatem, K2, K3, K5, K6, K7, K8 |
| `karta_cytaty_zrodlo.py` | czy cytat stoi **dosłownie** w dokumencie, na który karta się powołuje | ROZJAZD / BRAK_W_PLIKU / BRAK_PLIKU |
| `karta_znacznik_zrodlo.py` | znacznik × typ dokumentu: `[POTWIERDZONE]` wyłącznie na źródle handlowym | flaga Z1 |
| `karta_negacje.py` | negacja = dowód: „brak / nie podaje / `[BRAK]`" przeczone przez dokument z biblioteki | flaga N1 (`--bramka`) |
| `karta_cytaty_jezyk.py` | cytat obcojęzyczny przy istniejącej wersji w języku rynku, ten sam fakt w dwóch językach, brak tłumaczenia | OBCY / DUBEL / BRAK_TŁUM |
| `baza_fakt_wiersz.py` | cytat karty vs komórka w zamrożonej bazie CSV (profil bazy wiedzy) | ROZJAZD / BRAK_W_BAZIE / ZŁY_WIERSZ |

## Bramki informacyjne (flagi do rozliczenia)

| Skrypt | Co sprawdza |
|---|---|
| `karta_wartosc_cytat.py` | czy każda liczba z kolumny wartości występuje w cytacie tego samego wiersza |
| `karta_zakresy.py` | wartości poza zakresem sensu (% > 100, odwrócony zakres, pH poza 0–14, temperatura, czas) |
| `karta_znaczniki_spojnosc.py` | ten sam atrybut z dwoma różnymi znacznikami w różnych sekcjach |
| `karta_manifest_sha.py` | czy pliki, na które powołuje się karta, istnieją i mają zgodny wpis w `_manifest.csv` |
| `biblioteka_dokumentow.py` | stan biblioteki: skany bez warstwy tekstu, duplikaty sha256, rozjazdy z manifestem |
| `karta_sds_atrybuty.py` | (profil chemii) czy karta ma obowiązkowe atrybuty z karty charakterystyki |

## Bramki treści — gotowy tekst względem karty faktów (od 2026-09-25)

Karta może być bez zarzutu, a tekst i tak ją przekręci. Te skrypty sprawdzają **opis / podstronę / sekcję
raportu** względem karty, z której powstały. Reguły (co jest krytyczne, pary zawężeń, zakazane słowa) nie są
w kodzie — czyta się je z profilu `profile/<profil>-tekst.json` (pole `profil_tekstu` w `weryfikacja.json`)
i z sekcji `tekst` projektu. **Bez profilu skrypty kończą się błędem (kod 2)** — cisza bez reguł wyglądałaby
jak czysty wynik.

Pary opis → karta: `--pary pary.csv` (kolumny `opis;karta`, ścieżki względem korzenia projektu) albo
argumenty parami. Plik par generuje projekt, bo tylko projekt wie, jak opis łączy się z kartą.

| Skrypt | Co sprawdza | Blokuje przy |
|---|---|---|
| `tekst_pokrycie.py` | **pominięcia:** każda pozycja krytyczna z wierszy `[POTWIERDZONE]` (drogi pierwszej pomocy, kody H) jest w treści; `--lista karta.md` drukuje listę kontrolną dla autora **przed** pisaniem | P1 (brak elementu), P2 (brak kodu H); P2i/P3i informacyjnie |
| `tekst_niepotwierdzone.py` | wartość z wiersza bez `[POTWIERDZONE]` (adres, liczba z jednostką, fraza w cudzysłowie) weszła do treści | N1 |
| `tekst_zawezenia.py` | treść uogólnia ponad źródło (np. „wirusobójczy" przy źródle „wobec wirusów otoczkowych") — każde zdanie osobno | Z1 |
| `tekst_sklad.py` | dokładne wartości % w tabeli składu sumują się ponad 100 | S1 |

Metoda w `tekst_pokrycie.py` to „najpierw lista ze źródła, potem jest / nie ma per pozycja" — jedyna, która
w badaniach realnie poprawia wykrywanie braków (sędzia-model bez listy wykrywa je na poziomie zgadywania).
Wykrywa część braków, nie wszystkie: test przecieku zostaje obowiązkowy.

Regresja przy wdrożeniu (projekt odniesienia, 2026-09): każdy skrypt złapał swój znany, udowodniony błąd
z testu przecieku; opis sprawdzony jako czysty przeszedł bez flagi blokującej.

## Kanarek i zamek publikacji

| Skrypt | Do czego |
|---|---|
| `kanarek.py` | **podłożenie** błędu przez orkiestratora (nigdy przez kontrolera): kopie do folderu kontrolera, jeden błąd typu podmiana / usunięcie / dopisanie, wyrównane daty, klucz poza folderem. `--sprawdz klucz raport.md` — czy raport go wskazał (WYKRYTY / NIE WYKRYTY / DO OCENY) |
| `zamek_publikacji.py` | ostatnia bramka przed wgraniem / wysłaniem: paczka = świeża regeneracja z artefaktów (Z1), nic nowszego niż paczka (Z2), kody unikalne, bez pustych, sierotki (Z3), zakazane wzorce i tagi HTML (Z4), zmiany po ostatnim raporcie kontroli (Z5). Wynik: ZAMEK OTWARTY / ZAMKNIĘTY |

## Narzędzia pomocnicze

| Skrypt | Do czego |
|---|---|
| `status_partii.py` | **generuje** plik statusu partii z danych (karty, raporty, bramki, zmiany po weryfikacji). Sekcja „Wpisy ręczne" przepisywana bez zmian |
| `sds_pl_do_karty.py` | dosłowna transkrypcja karty charakterystyki §1–§16 do karty faktów — robi to skrypt, nie model |
| `szukaj_zrodel_pl.py` | szukanie dokumentów w języku rynku przez API wyszukiwarki + pobranie kandydatów (model tylko ocenia dopasowanie). Wymaga klucza w `.env`. **Blokad nie obchodzi** |
| `konfig.py` | wspólny odczyt `weryfikacja.json` |

## Typowe użycie (partia)

```bash
export PYTHONIOENCODING=utf-8
K=zrodla/<kategoria>/produkty
D=zrodla/<kategoria>/dokumenty

python skrypty/karta_forma.py $K/*.md
python skrypty/karta_cytaty_zrodlo.py $K/*.md
python skrypty/karta_znacznik_zrodlo.py $K/*.md
python skrypty/karta_cytaty_jezyk.py $K/*.md
for k in $K/*.md; do python skrypty/karta_negacje.py "$k" $D --bramka; done
python skrypty/biblioteka_dokumentow.py zrodla/<kategoria>
python skrypty/status_partii.py <kategoria> --out kontrola/STATUS-<kategoria>.md
```

## Pochodzenie i stan

Skrypty pochodzą z partii 87 kart faktów (wrzesień 2026) i zostały tu **odcięte od nazwy klienta**
(wszystko, co było „projekt odniesienia", czyta się teraz z `weryfikacja.json`). Regresja na tej samej partii: wyniki
identyczne z oryginałami — poza jedną zmianą treści komunikatu i poza poprawką niżej.

**Poprawka przy przenoszeniu:** w oryginałach `karta_negacje.py` (13 miejsc) i `karta_cytaty_zrodlo.py`
(5 miejsc) w regexach zamiast `\b` stał **bajt 0x08** (backspace) — efekt wklejania przez narzędzie, które
zjadło ukośnik. Te alternatywy nigdy nie mogły trafić (regex wymagał literalnego znaku backspace w tekście):
m.in. `\bkart`, `\bIFU\b`, `\bSDS\b`, `\bplik`, `\bnie\b` w `karta_negacje.py`. Po naprawie na tej samej
partii (45 kart): **N1 77 → 84** — siedem dodatkowych trafień „negacja przeczona przez dokument" na kartach,
które przeszły 6 rund poprawek. Część z nich wygląda na trafne (`EN 374`, temperatura przechowywania,
„wyłącznie w oryginalnym pojemniku"), część na szum — wymagają przejrzenia.
