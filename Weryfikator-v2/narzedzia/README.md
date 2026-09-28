# Narzędzia — skrypty dla osób pracujących w Claude Code

Nie musisz ich używać, żeby stosować weryfikator — cały proces da się zrobić poleceniami z
`3-PROMPTY-do-wklejenia.md`. Skrypty robią za darmo i w sekundę to, co da się sprawdzić mechanicznie,
żeby model zajmował się tylko osądem.

**Wymagania:** Python 3.12, bez dodatkowych bibliotek (PDF: `PyMuPDF`). W Windows przed uruchomieniem:
`set PYTHONIOENCODING=utf-8` (inaczej polskie znaki się potną). Skrypty niczego nie zmieniają w Twoich plikach.

## Start w projekcie

1. Skopiuj `weryfikacja.przyklad.json` do głównego folderu projektu jako `weryfikacja.json` i uzupełnij:
   nazwę klienta, słowa, po których poznać **nasz** sklep/stronę (to źródło handlowe, nie producenta),
   język rynku. `profil_tekstu: "produkty"` włącza reguły dla opisów produktów (`profile/produkty-tekst.json`).
2. Wyjątki projektu wpisuj w sekcji `tekst` — i zawsze zapisz obok, dlaczego (decyzja klienta, data).

## Co uruchamiasz i kiedy

| Moment | Skrypt | Pytanie, na które odpowiada |
|---|---|---|
| po zrobieniu listy faktów | `karta_forma.py`, `karta_cytaty_zrodlo.py`, `karta_negacje.py`, `karta_znacznik_zrodlo.py` | czy lista jest porządna, czy cytaty naprawdę stoją w plikach, czy „brak" nie jest nieprawdą |
| **przed pisaniem tekstu** | `tekst_pokrycie.py --lista <karta>` | co krytycznego **musi** się znaleźć w tekście |
| po napisaniu tekstu | `tekst_pokrycie.py`, `tekst_niepotwierdzone.py`, `tekst_zawezenia.py`, `tekst_sklad.py` | czy niczego krytycznego nie brakuje, czy nic nie weszło z niepewnych wierszy, czy tekst nie mówi szerzej niż źródło, czy liczby się domykają |
| przed wysłaniem do sprawdzającego | `kanarek.py --do <folder> --klucz <plik>` | podkłada jeden błąd w kopii (sprawdzającemu nie mówisz gdzie) |
| po raporcie sprawdzającego | `kanarek.py --sprawdz <klucz> <raport>` | czy sprawdzający go znalazł |
| **przed wgraniem / wysłaniem** | `zamek_publikacji.py --paczka <plik.csv> …` | czy wysyłamy dokładnie to, co sprawdziliśmy, bez śladów roboty |

Pełny opis każdego skryptu i jego opcji: `skrypty/README.md` oraz nagłówek każdego pliku.

## Jak czytać wynik

- **Blokujące** (kod wyjścia 1) — tekst nie idzie dalej, dopóki nie poprawisz albo świadomie nie odhaczysz
  fałszywego alarmu.
- **Informacyjne** (oznaczone `i` albo `?`) — spójrz, nie blokują.
- **Kod 2 / „brak reguł"** — skrypt nie znalazł `weryfikacja.json` albo profilu. Nie traktuj tego jak
  czystego wyniku; podaj `--konfig <ścieżka do weryfikacja.json>`.
- **Zero trafień nie dowodzi, że tekst jest dobry.** Skrypt łapie to, co mechaniczne. Osąd, sprawdzenie
  z dokumentem i test przecieku zostają.
