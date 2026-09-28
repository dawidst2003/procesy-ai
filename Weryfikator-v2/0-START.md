# Sprawdzanie faktów w treściach pisanych z AI — paczka startowa (wersja 2, wrzesień 2026)

Trzy pliki, w tej kolejności:

1. **1-JAK-SPRAWDZAC-FAKTY.md** — cały proces: cztery pytania na start, dziewięć kroków (lista faktów,
   sprawdzenie, podłożony błąd, braki, przeciek, tekst względem listy, zamek przed wysłaniem), jak zmierzyć,
   czy kontrola działa, podział roboty według kosztu, warianty źródeł, siedem pułapek, progi zatrzymania.
2. **2-SZABLON-listy-faktow.md** — tabela do wypełnienia i lista kontrolna pozycji krytycznych.
   Tekst powstaje z niej, nie odwrotnie.
3. **3-PROMPTY-do-wklejenia.md** — pięć gotowych poleceń i sposób na podłożony błąd.

## Jeśli masz przeczytać tylko jedno zdanie

Każdy fakt w treści musi mieć **zapisany plik, dosłowny cytat i wskazanie miejsca** — a sprawdza go
**inna rozmowa niż ta, która pisała**.

## Jeśli dwa

Braki sprawdzasz **z listy, nie z pytania**: najpierw wypisujesz z dokumentu wszystko, co krytyczne,
potem przy każdej pozycji pytasz „jest / nie ma". Pytanie „czy czegoś brakuje?" działa jak rzut monetą.

## Co nowego w wersji 2

- Krok 8: gotowy tekst sprawdzany względem listy faktów — cztery osobne kontrole (wierność, kompletność,
  nic ponad źródło, spójność), werdykt zaliczone / niezaliczone, bez uśredniania.
- Krok 9: zamek przed wysłaniem — wysyłana wersja = aktualna, zero śladów roboty.
- Podłożony błąd w trzech odmianach, w tym **usunięcie** ostrzeżenia — bo braki przeciekają najczęściej.
- Zbiór testowy: jak zmierzyć, czy zmiana polecenia albo modelu coś poprawiła.

## Skąd te reguły

Z realnej pracy, nie z teorii: 3703 sprawdzone fakty w 431 dokumentach, dwa różne rodzaje materiału
(karty techniczne producentów w PDF i baza wiedzy w arkuszu), oraz testy przecieku na opublikowanych
opisach produktów. Każda reguła ma za sobą konkretną klasę błędu, która na tym materiale wystąpiła.
Tam, gdzie to się pokrywa, zgadza się z badaniami nad automatyczną oceną tekstów AI (m.in. rozbijanie
na pojedyncze fakty, słabe wykrywanie braków przez sędziów-modele, szkodliwość samokorekty bez źródła).

## Czego ten proces nie załatwi

Błędu, który siedzi w samym źródle. Jeśli karta producenta podaje złą wartość, dostaniesz ją
z poprawnym cytatem. Sprawdzamy zgodność ze źródłem, nie prawdę o świecie.
