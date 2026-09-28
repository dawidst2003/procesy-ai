# Weryfikator, czyli jak nie dać się nabrać AI — wersja 2

Przez AI przechodzi u nas coraz więcej treści i danych, a każda wpadka kosztuje czas: poprawki, tłumaczenie
się klientowi, drugie podejście. Weryfikator ma to ograniczyć. To druga wersja — zmiany wynikają z testów na
gotowych, już opublikowanych tekstach i z przeglądu badań nad tym, jak AI sprawdza AI.

Z AI jest jeden problem: pisze gładko i pewnie, nawet kiedy się myli. Błąd nie wygląda jak błąd. Dlatego nie
oceniamy na oko, tylko przepuszczamy każdą treść przez te same pytania.

Weryfikator powstał przy opisach produktów, ale te pytania pasują do każdego tekstu, FAQ czy raportu.
W jednych procesach będzie overkillem, w innych trzeba go jeszcze zaostrzyć — traktujcie go jak rdzeń.

## Siedem pytań, zanim cokolwiek wyjdzie na zewnątrz

1. **Skąd to wiadomo?** „5 lat gwarancji" musi mieć źródło, które da się otworzyć: zapisany plik, dosłowny
   cytat, strona albo linia. Jeśli źródła nie ma, zdanie wypada. W testach AI potrafiło zacytować tekst ukryty
   w kodzie strony, którego żaden klient nigdy nie zobaczył.
2. **Czy to na pewno o tym produkcie?** AI chętnie miesza podobne rzeczy. Parametry butelki 500 ml trafiają
   wtedy do opisu litrowej.
3. **Czego tu brakuje?** Najtrudniejsze, bo tekst bez ważnej informacji czyta się równie dobrze. W testach AI
   przepisało „zmyć wodą", a zgubiło „zebrać wodę z mycia"; w innych opisach z pierwszej pomocy zostały tylko
   oczy, zniknęła skóra i wdychanie. **Braki sprawdzamy z listy, nie z pytania:** najpierw wypisujemy ze źródła
   wszystko, co krytyczne, potem przy każdej pozycji „jest / nie ma". Pytanie „czy czegoś brakuje?" działa
   jak rzut monetą — także dla AI.
4. **Co AI dopisało od siebie albo powiedziało mocniej niż źródło?** „Najtrwalszy", „gwarantuje efekt",
   „oszczędza czas" brzmią dobrze, tylko nikt tego nie powiedział. Tak samo „wirusobójczy", kiedy producent
   pisze „wobec wirusów otoczkowych" — to już inna obietnica.
5. **Czy wszystko mówi to samo?** Jeśli w tabeli jest 20 kg, a w tekście 25 kg, jedno z nich jest nieprawdą.
   Jeśli skład sumuje się do 103%, coś jest pomieszane.
6. **Czy nic nie zostało w połowie?** Na przykład [DO UZUPEŁNIENIA], puste pole, urwane zdanie albo
   „wg karty charakterystyki" w tekście dla klienta.
7. **Czy wysyłamy to, co sprawdziliśmy?** Paczka do klienta albo sklepu musi być aktualną wersją — zdarza się,
   że ktoś poprawił tekst po kontroli, a wysłana poszła stara albo niesprawdzona.

## Jak pilnujemy, żeby kontrola naprawdę działała

- **Najpierw automaty, potem AI.** To, co da się sprawdzić mechanicznie (czy cytat jest w pliku, czy liczba
  się zgadza, czy pozycje krytyczne są w tekście, czy nie zostały ślady roboty), sprawdza skrypt — za darmo
  i za każdym razem. Model dostaje tylko to, co wymaga osądu.
- **Autor nie sprawdza sam siebie.** Tekst sprawdza osobny agent, który nie widział, jak tekst powstawał.
  „Przeczytaj i popraw się sam" bez źródeł nie jest weryfikacją — badania pokazują, że pogarsza wynik.
- **Każde pytanie osobno, werdykt tak / nie.** Nie „oceń jakość opisu w skali 1–5", tylko osobne zamknięte
  pytania. Jeden krytyczny błąd wystarczy, żeby tekst wrócił — bez uśredniania.
- **Sędziemu podkładamy błąd — w trzech odmianach.** Podmieniona wartość, dopisana zaleta albo usunięte
  ostrzeżenie. Błąd podkłada ktoś inny niż sędzia. Jeśli go nie znajdzie, jego ocena idzie do kosza.
- **Szukamy błędów w tym, co już przeszło.** Przy każdym nowym typie materiału bierzemy 5 „czystych" tekstów
  z zadaniem: znajdź pomyłkę. Jeśli wyjdą w dwóch albo więcej, zatrzymujemy się i poprawiamy zasady,
  nie tylko teksty.
- **Mierzymy, czy kontrola działa.** Trzymamy zbiór przypadków z prawdziwej pracy (teksty ze znanym błędem
  i teksty czyste). Każda zmiana polecenia albo modelu przechodzi najpierw przez ten zbiór: ile błędów złapała,
  ile razy fałszywie zaalarmowała.
- **Nie łatamy w nieskończoność.** Po trzech nieudanych poprawkach szukamy lepszego źródła, zamiast kolejny
  raz przerabiać to samo.

## Co wyszło w praktyce

Na opisach produktów: pierwsze wersje pisane przez AI miały błąd w co ~14. fakcie i w każdym opisie.
Po kontroli — 1–2% faktów, bez błędów krytycznych. To, co przechodziło mimo kontroli, to prawie wyłącznie
**braki** (fragmenty ostrzeżeń i pierwszej pomocy) — dlatego wersja 2 najmocniej dociska właśnie je.

Jedna rzecz na co dzień: przy każdej liczbie i każdym mocnym zdaniu zapytaj „gdzie to jest napisane?".
Jeśli coś brzmi za dobrze, pewnie jest dopisane. A jeśli tekst wydaje się kompletny — sprawdź z listy.

---

**W paczce:**
- `0-START.md` — od czego zacząć, co nowego w wersji 2,
- `1-JAK-SPRAWDZAC-FAKTY.md` — cały proces krok po kroku, bez żargonu,
- `2-SZABLON-listy-faktow.md` — tabela faktów i lista kontrolna pozycji krytycznych,
- `3-PROMPTY-do-wklejenia.md` — pięć gotowych poleceń do Claude,
- `narzedzia/` — skrypty dla osób pracujących w Claude Code (opis w `narzedzia/README.md`).

Wersja 1 (plik `WERYFIKATOR.md` z listą checków) jest zastąpiona w całości.
