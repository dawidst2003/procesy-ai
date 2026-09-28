# Jak sprawdzać fakty w treściach pisanych z AI

Jak sprawdzać fakty w treściach pisanych z AI, żeby dało się je obronić przed klientem.
Dokument jest samodzielny — nie trzeba niczego doczytywać. **Wersja 2 (wrzesień 2026).**

Działa tak samo, kiedy sprawdzasz kartę techniczną producenta, wewnętrzną bazę wiedzy klienta,
zescrapowaną stronę, własny crawl, wpis blogowy albo liczbę do raportu. **Zmienia się tylko odpowiedź
na cztery pytania ze startu.**

---

## Najpierw: cztery pytania (5 minut, raz na projekt)

Bez tych odpowiedzi nie da się nic sprawdzić, bo nie wiadomo, co z czym porównujesz.

**1. Co jest faktem?**
Jedno twierdzenie, które da się osobno potwierdzić albo obalić. „Wózek waży 1080 kg" — tak.
„Wózek jest nowoczesny i wydajny" — nie, tego nie da się sprawdzić.

**2. Co jest dokumentem?**
To, w czym fakt ma stać. Karta PDF. Zamrożona kopia pliku CSV. Zapisany HTML strony. Eksport z GSC.
**Warunek zawsze ten sam: plik na dysku, z datą pobrania.** Link nie jest dokumentem — jutro pokaże co innego.

**3. Co jest lokalizacją?**
Jak wskazujesz miejsce w dokumencie: strona w PDF, numer linii w tekście, numer wiersza w tabeli,
zakres dat i filtr w eksporcie. Bez tego nikt nie sprawdzi Twojego sprawdzenia.

**4. Co jest krytyczne?**
Lista rzeczy, których błąd albo **brak** jest nieodwracalny: liczby, normy, certyfikaty, terminy,
ostrzeżenia i pierwsza pomoc, przeciwwskazania, warunki użycia, twierdzenia o bezpieczeństwie i zgodności,
nazwy własne, cytaty przypisane osobom. **Te sprawdzasz w stu procentach — i te muszą się znaleźć w tekście.**
Reszta może być próbką — byle podać jaką.

---

## Potem: dziewięć kroków

Kroki 1–7 dotyczą listy faktów. Kroki 8–9 — gotowego tekstu, który z niej powstał.

### 1. Znajdź i ściągnij źródła do plików
Pliki, nie zakładki. Do każdego zapisz skąd, kiedy i w jakiej wersji.
PDF bez warstwy tekstu (sam obrazek) nie jest jeszcze źródłem — najpierw trzeba go odczytać.

**Jak szukać, żeby nie ściągnąć nie tego:**

- **Szukaj kodem i typem dokumentu, nie nazwą ogólną.** „XR-2000 karta charakterystyki", „XR-2000 pdf",
  „<numer katalogowy> instrukcja" — a nie „drukarka etykiet parametry".
- **Kolejność ważności:** dokument producenta → importera → rejestr publiczny → dystrybutor, który
  wystawia dokument producenta → własna strona klienta. Sklep, marketplace, porównywarka i blog branżowy
  to źródła handlowe albo wtórne: mogą coś podpowiedzieć, ale nie potwierdzają.
- **Wynik wyszukiwarki nie jest źródłem.** Ani zajawka, ani podsumowanie AI. Źródłem jest pobrany plik.
- **Sprawdź, czy to na pewno ten** — zanim cokolwiek przepiszesz: nazwa, kod, wersja, pojemność, rok.
  Karta rodziny produktów zawiera dane wielu wariantów; wzięcie nie tego wiersza to najczęstszy błąd
  przy pracy z kartami technicznymi.
- **Nowsza rewizja wygrywa**, a wyszukiwarka nie sortuje po dacie. Datę sprawdzaj w dokumencie.
- **Język dokumentu, nie domena.** Polski dokument na zagranicznym serwerze producenta jest polską wersją.
  Jeśli wersji w języku rynku nie ma — bierzesz oryginał i zapisujesz, że szukałeś.
- **Blokad nie obchodzimy.** Logowanie, captcha, płatny dostęp → zapisujesz, czego nie dało się pobrać,
  i szukasz dalej. Strona błędu zapisana jako dokument to gotowy fałszywy dowód.
- **Czego nie znalazłeś, to też wynik.** „Szukałem tego i tego, nie ma" jest pełnoprawną odpowiedzią
  i musi trafić do listy. Milczenie wygląda potem jak przeoczenie.

### 2. Zrób listę faktów
Jeden wiersz = jeden fakt: **co · skąd · cytat słowo w słowo · gdzie dokładnie · czy krytyczny**.
Nie zaczynaj od pisania tekstu. Tekst powstaje z listy, nie odwrotnie.

### 3. Puść po niej to, co da się sprawdzić maszynowo
Czy cytat naprawdę jest w tym pliku. Czy liczba z faktu stoi w cytacie. Czy wartość ma sens
(prędkość w milimetrach nie istnieje). Czy „tego nie ma w dokumencie" nie jest nieprawdą.
To kosztuje sekundy i zdejmuje większość drobiazgów. **Model dostaje dopiero to, czego nie złapał skrypt.**

### 4. Daj to komuś, kto tego nie pisał
Osobna sesja, czysty kontekst, dostęp do dokumentów. Czyta źródła sam i orzeka o każdym fakcie osobno:
**zgodny / sprzeczny / nie ma tego w dokumencie / nie da się sprawdzić / złe źródło**.
Werdykt bez cytatu nie istnieje. Autor nigdy nie sprawdza własnej roboty — model, który ocenia własny tekst,
zwykle go broni, a „przeczytaj i popraw się sam" bez dokumentów pogarsza wynik zamiast go poprawiać.

### 5. Podłóż jeden błąd
Zanim wyślesz do sprawdzenia, zrób kopię i wprowadź w niej **jeden** błąd. Zmieniaj typ z przebiegu na przebieg:

| Typ | Przykład | Co sprawdza |
|---|---|---|
| **podmiana** | „15 min" → „10 min" | czy sprawdzający porównuje wartości |
| **usunięcie** | wycięte jedno ostrzeżenie albo zdanie pierwszej pomocy | czy sprawdzający widzi **braki** — to najtrudniejsze |
| **dopisanie** | dodana zaleta, której nie ma w żadnym dokumencie | czy łapie twierdzenia bez źródła |

Jeśli sprawdzający tego nie znajdzie, jego „wszystko się zgadza" nic nie znaczy i przebieg trzeba powtórzyć.
**Błąd podkłada ktoś, kto nie sprawdza** — sprawdzający, który sam podłożył sobie błąd, wie, gdzie go szukać.
Wybieraj wartości wiarygodne: „5 lat gwarancji" zamiast „250 miesięcy" — absurd zdradza się sam.

### 6. Sprawdź, czego brakuje — z listy, nie z pytania
Wszystkie poprzednie kroki idą w jedną stronę: od listy do dokumentu. Teraz **w drugą**.

To jest najsłabsze miejsce każdej kontroli, także automatycznej. Badania i nasza praca mówią to samo:
sprawdzający (człowiek i model) dobrze widzi błąd, który **jest** w tekście, a braku prawie nie widzi —
tekst bez ostrzeżenia czyta się zupełnie normalnie. Pytanie „czy czegoś brakuje?" działa jak rzut monetą,
a lepsze sformułowanie ani głosowanie kilku sprawdzających tego nie naprawia.

Działa tylko jedno: **najpierw wypisz z dokumentu wszystkie pozycje krytyczne** (każde ostrzeżenie, każda
droga pierwszej pomocy, każde przeciwwskazanie, warunek, parametr), **potem przy każdej zadaj zamknięte
pytanie: jest / nie ma.** Pozycja po pozycji, z odhaczaniem. Nawet tak wyłapiesz część braków, nie wszystkie —
dlatego krok 7 jest obowiązkowy.

### 7. Sprawdź, ile przepuściłeś
Wszystko powyżej mówi, ile błędów **złapałeś**. Nie mówi nic o tym, ile przeszło.

Dlatego na koniec: weź **pięć pozycji, które przeszły czysto**, i daj je świeżej osobie z poleceniem
*„w tym zestawie jest co najmniej jeden błąd — znajdź go i pokaż zdanie ze źródła, które mu przeczy"*.
Liczy się tylko znalezisko z cytatem; reszta to szum.

| Wynik | Co to znaczy | Co robisz |
|---|---|---|
| 0 na 5 | warstwy trzymają | materiał idzie dalej |
| 1 na 5 | pojedynczy przeciek | dopisujesz tę klasę błędu do listy i idziesz dalej |
| 2 i więcej | kontrola przecieka | **stop** — nie ogłaszasz, że sprawdzone, dopóki klasa nie zostanie zamknięta |

Bez tego kroku nie wolno mówić „materiał jest sprawdzony". Wolno mówić „sprawdzony, przeciek zmierzony
na tyle a tyle". Robisz to co najmniej raz na każdy nowy typ materiału (nową kategorię, nowego klienta).

Dopiero teraz powstaje tekst — i tylko z faktów, które przeszły.

### 8. Sprawdź gotowy tekst względem listy
Lista może być bez zarzutu, a tekst i tak ją przekręci. Tu są cztery osobne kontrole — **każda to osobne,
zamknięte pytanie, nie jedna ocena „czy tekst jest dobry"**:

1. **Wierność:** każde zdanie tekstu ma swój wiersz na liście. Zdanie bez wiersza wypada.
2. **Kompletność:** każda pozycja krytyczna z listy jest w tekście (tak samo jak w kroku 6: lista → jest / nie ma).
   Brak jednej pozycji krytycznej = tekst do poprawy. **Nie uśredniaj** („92% pokrycia") — jeden brakujący
   fakt na czterdzieści ginie w średniej, a to może być właśnie ostrzeżenie.
3. **Nic ponad źródło:** tekst nie mówi szerzej niż dokument. Źródło: „działa na wirusy otoczkowe", zaleta:
   „wirusobójczy" — to już inna obietnica. Każde zdanie osobno musi nieść zastrzeżenie, nie tylko tabela.
4. **Nic z niepewnych wierszy i nic sprzecznego wewnątrz:** do tekstu nie wchodzi wartość oznaczona jako
   niepotwierdzona; tabela, proza i FAQ mówią to samo; liczby się domykają (skład nie sumuje się do 103%).

Zgodność z briefem, tonem i wytycznymi klienta to **osobna** kontrola — werdykt tak / nie z krótkim
uzasadnieniem, najlepiej na przykładach ocen osoby, która zna klienta. Nie mieszaj jej z faktami.

### 9. Przed wysłaniem — zamek
Ostatnie sprawdzenie, zanim tekst pójdzie do klienta albo do sklepu. Sprawdzasz **paczkę, która naprawdę
wychodzi**, nie pliki robocze:

- wysyłana wersja = aktualna wersja tekstu (nikt nic nie zmienił po kontroli; paczka nie jest starsza od plików),
- żadnych śladów roboty: nazw dokumentów źródłowych („wg karty charakterystyki"), znaczników `[BRAK]`,
  „szukano w", „do potwierdzenia", notatek o procesie, podłożonego błędu,
- każda pozycja jest raz, żadna nie zginęła, żadna nie weszła bez kontroli.

To w większości sprawdza skrypt w sekundę. Jeśli najdroższy sprawdzający zgłasza głównie takie rzeczy —
zamek nie zadziałał przed nim.

---

## Skąd wiesz, że kontrola działa

Podłożony błąd mówi, czy sprawdzający patrzył. Nie mówi, **ile dobrych tekstów niepotrzebnie odrzuca** ani
czy zmiana polecenia coś poprawiła. Do tego służy mały **zbiór testowy**:

- zbierasz przypadki z prawdziwej pracy: teksty ze znanym, udowodnionym błędem **i** teksty sprawdzone jako czyste,
- każdą zmianę polecenia, modelu albo skryptu puszczasz najpierw na ten zbiór i zapisujesz **dwie liczby**:
  ile znanych błędów złapała i ile razy fałszywie zaalarmowała,
- **nie poprawiasz polecenia na tych samych przykładach, na których potem je oceniasz** — poprawa „na własnej
  próbce" potrafi okazać się pogorszeniem na nowych danych,
- 10–20 przykładów to za mało na pewny wniosek; celuj w 30–50 każdego rodzaju i dokładaj z każdą partią.

Liczba „zgodność 95%" nic nie znaczy, gdy błędów jest mało: sprawdzający, który zawsze mówi „OK",
przy 5% błędów ma 95% zgodności.

---

## Kto to robi i czym — żeby nie przepalać pieniędzy

Zasada: **każdą rzecz robi najtańsze narzędzie, które da radę.** Najdroższy sprawdzający nie ma poprawiać
przecinków.

| Czynność | Czym |
|---|---|
| Ściągnięcie plików, daty, sumy kontrolne | **skrypt** — sekundy, zero myślenia |
| Czy cytat stoi w pliku, czy liczba jest w cytacie, czy wartość ma sens | **skrypt** |
| Czy pozycje krytyczne z listy są w tekście, czy do tekstu nie weszło nic niepotwierdzonego, zamek | **skrypt** |
| Przepisanie tabeli albo dokumentu do listy faktów | **tańszy model** — dużo czytania, mało osądu |
| Porównanie dwóch wersji po poprawkach | **tańszy model** |
| Orzekanie: czy fakt zgadza się ze źródłem, czego brakuje, co jest sklejone | **najmocniejszy model** — tu jest osąd |
| Decyzja, co publikujemy i co idzie do klienta | **człowiek** |

Trzy rzeczy z tego wynikają:

1. **Jeśli najmocniejszy model zgłasza głównie literówki i formatowanie — coś jest źle ustawione.**
   Znaczy to, że tania warstwa nie zadziałała przed nim.
2. **Czytanie kosztuje od dokumentu, nie od faktu.** Jeden dokument czyta się raz i rozstrzyga wszystkie
   fakty, które się na niego powołują. Dlatego sprawdzenie stu faktów potrafi kosztować tyle, co ośmiuset —
   i dlatego próbka rzadko się opłaca.
3. **Człowiek nie sprawdza wszystkiego**, tylko decyduje w miejscach, gdzie modele zgłosiły rozbieżność
   albo gdzie stawką jest nazwisko, pieniądze lub zgodność z przepisami.

Przy ważnych materiałach warto, żeby ostatni sprawdzający był **modelem innej firmy** niż ten, który pisał —
modele wyżej oceniają teksty w „swoim" stylu. Przy danych klienta: tylko za jego zgodą.

---

## Jak to uruchomić w Claude — praktycznie

Cały proces stoi na jednej rzeczy technicznej: **sprawdza inna rozmowa niż ta, która pisała.**
Ta sama rozmowa broni tego, co przed chwilą napisała — widzi własne uzasadnienia i traktuje je jak fakty.

| Krok | Jak to zrobić |
|---|---|
| lista faktów | jedna rozmowa, dokumenty w załączniku albo w folderze |
| sprawdzanie | **nowa rozmowa** (albo podagent, jeśli pracujesz w Claude Code) — dostaje dokumenty i listę, **nie dostaje** Twoich uzasadnień ani poprzednich werdyktów |
| podłożony błąd | kopiujesz listę albo tekst, wprowadzasz jeden błąd (podmiana / usunięcie / dopisanie), zapisujesz sobie jaki — sprawdzającemu nie mówisz nic |
| co brakuje | nowa rozmowa: najpierw lista pozycji krytycznych z dokumentu, potem jest / nie ma przy każdej |
| ile przepuściłeś | jeszcze jedna rozmowa, nastawiona adwersaryjnie |
| tekst względem listy | nowa rozmowa: cztery kontrole z kroku 8, każda osobno |

**Do przepisywania dokumentów wystarczy tańszy model. Do orzekania bierz najmocniejszy** — tam jest osąd,
a nie czytanie. Gotowe polecenia: `3-PROMPTY-do-wklejenia.md`.

Jeśli pracujesz w Claude Code, część kroków robią skrypty z folderu `narzedzia/` (opis w środku).

---

## Co się zmienia w zależności od wariantu

| Sprawdzasz | Dokumentem jest | Lokalizacją jest | Najczęstsza pułapka |
|---|---|---|---|
| **kartę techniczną / PDF producenta** | plik PDF + jego wersja tekstowa | strona, linia | tabela rozjeżdża się przy odczycie i wartość trafia do złego parametru |
| **wewnętrzną bazę klienta (CSV)** | zamrożona kopia pliku z datą | numer wiersza | baza jest źródłem wtórnym — mówi, co klient twierdzi, nie co wykazało badanie |
| **stronę WWW (scrape)** | zapisany HTML i tekst | linia + adres + data | cytat z ukrytego bloku albo z „przeczytaj także" zamiast z treści |
| **własny crawl** | zapisana podstrona | adres + data + pole/selektor | licznik mierzy co innego, niż mówi zdanie obok |
| **liczby z narzędzi** | eksport z zapytania | zakres dat, filtr, wiersz | ta sama liczba w dwóch narzędziach znaczy co innego |
| **wpis blogowy / tekst gotowy** | dokumenty, z których powstał | jak wyżej | fakt prawdziwy, ale mocniejszy niż źródło |

---

## Siedem rzeczy, które wychodzą zawsze — pilnuj ich osobno

**Pominięte ostrzeżenie.** Karta ma pierwszą pomoc dla oczu, skóry i przy wdychaniu, tekst podaje tylko oczy.
Czyta się dobrze, więc nikt nie zauważa. Najczęstszy błąd, który przechodzi przez pełną kontrolę.
Łapie go tylko lista pozycji krytycznych (krok 6 i 8).

**Zgubione zastrzeżenie.** Źródło: „około 800 kg, zależnie od konfiguracji". Tekst: „800 kg".
Albo: źródło „wobec wirusów otoczkowych", zaleta „wirusobójczy". Fakt wchodzi do tekstu **razem
z zastrzeżeniem** albo nie wchodzi — w każdym zdaniu, nie tylko w tabeli.

**Wartość z niepewnego źródła.** Adres, wymiar albo kolor wzięty tylko ze sklepu i oznaczony na liście jako
„do potwierdzenia" — a w tekście podany jak pewnik. Jeden taki wiersz potrafi przejść do kilkudziesięciu tekstów naraz.

**Zgubiona struktura dokumentu.** Zdanie w dokumencie dotyczyło trzech pozycji z wypunktowania, a po
zamianie strony na zwykły tekst wygląda na ogólne — bo znikły myślniki listy i pogrubienia. Tak zakres
twierdzenia rozszerza się sam, bez niczyjej złej woli.
Dlatego: **przy zamianie strony na tekst zostawiaj listy i akapity**, a przy faktach zaczynających się od
„urządzenia", „produkty", „modele", „nasze rozwiązania" sprawdzaj w oryginale, ilu pozycji naprawdę dotyczą.

**Złe źródło przy dobrym fakcie.** Bywa, że jeden link jest podpięty pod kilkadziesiąt faktów naraz.
Fakty są prawdziwe, ale nie da się ich obronić. Sprawdzaj nie tylko „czy to prawda", ale też
„czy stoi tam, gdzie mówimy, że stoi".

**Sklejka.** Dwa sąsiednie zdania połączone w jedno, które brzmi lepiej niż każde z osobna.
Test: czy da się wskazać jedno miejsce, w którym stoi całe twierdzenie?

**Cudze słowa.** Twierdzenie przypisane osobie z nazwiska albo firmie. Sprawdzaj oddzielnie i zawsze:
czy to naprawdę jej wypowiedź, i czy nie dokleiliśmy do niej superlatywu.

---

## Kiedy przerwać

- Sprawdzający nie znalazł podłożonego błędu → przebieg nieważny, powtórz z kimś innym.
- Test przecieku (krok 7) dał 2 na 5 albo więcej → stop, najpierw zamknij klasę błędu.
- Ta sama pozycja wraca z tym samym błędem trzeci raz → odkładasz ją i szukasz nowego źródła.
  Czwarta poprawka na tych samych danych niczego nie doda.
- Więcej niż dwie trzecie uwag dotyczy formy, nie treści → materiał jest do przepisania, nie do łatania.
- Błędów merytorycznych jest więcej niż ~1% sprawdzonych faktów → partia wraca do autora do przepisania,
  a nie do kolejnej rundy łatania.

## Ile to kosztuje (żeby dobrze wycenić)

Koszt liczy się **od dokumentów, nie od faktów**. Jeden dokument czyta się raz i rozstrzyga wszystkie
fakty, które się na niego powołują. Dlatego sprawdzenie stu faktów potrafi kosztować tyle, co sprawdzenie
ośmiuset — i dlatego **próbka rzadko się opłaca**.

Zmierzone na realnej robocie (wrzesień 2026): 3703 fakty w 431 dokumentach — około 4,6 mln tokenów
i półtorej godziny przy dziewięciu sprawdzających naraz. Test przecieku na 5 gotowych tekstach — około
250–380 tys. tokenów. Skrypty — zero.

## Co to daje (zmierzone)

Na opisach produktów z dokumentacji producentów: pierwsze wersje pisane przez AI miały błędny co ~14. fakt
(ok. 7%) i błąd w każdym opisie. Po całej kontroli — około 1–2% faktów, bez błędów krytycznych (fakty z innej
wersji produktu, pomylony status). Tym, co zostało, były prawie wyłącznie **braki**: pominięte fragmenty
ostrzeżeń i pierwszej pomocy. Stąd krok 6 i 8 w obecnej postaci.

## Czego to nie załatwi

- **Błędu w samym źródle.** Jeśli karta producenta podaje prędkość w milimetrach, dostaniesz ją z cytatem.
  Sprawdzamy zgodność ze źródłem, nie prawdę o świecie. Rozjazd między dokumentami wychodzi, błąd wewnątrz
  jednego — nie.
- **Braku dokumentów.** Fakt bez zapisanego źródła zostaje niepotwierdzony i tak trzeba go oznaczyć.
  To uczciwy stan, nie porażka.
- **Wszystkich braków.** Nawet najlepsza znana metoda wyłapuje część pominięć. Dlatego mierzysz przeciek (krok 7),
  zamiast zakładać, że go nie ma.
