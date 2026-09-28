#!/usr/bin/env python3
"""C5 — czy karta faktów ma obowiązkowe atrybuty z SDS (lista w _SZABLON-karta-produktu.md).

Heurystyka słów kluczowych: wynik to FLAGI do sprawdzenia przez kontrolę, nie werdykt.
Atrybut uznany za obecny, gdy w karcie jest co najmniej jedno słowo z grupy.
Warunek: jeśli karta wymienia H400–H413, musi mieć środek ostrożności dla środowiska.

Użycie: python _skrypty/karta_sds_atrybuty.py <karta.md> [<karta.md> ...]
"""
import re, sys

for s in (sys.stdout,):
    try:
        s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ATRYBUTY = {
    "§4 oczy": r"oczy|oczu|eye",
    "§4 skóra": r"skór|skin",
    "§4 połknięcie": r"połknię|połkni|ingest|swallow",
    "§4 wdychanie": r"wdycha|inhal|wdech",
    "§5 niewłaściwe środki gaśnicze": r"niewłaściw\w* środ|unsuitable extinguish|nie zaleca się używać wody|strumie\w* wody",
    "§6 metoda usuwania wycieku": r"absorb|chłon|zebra|zbiera|pojemnik\w* do usuni|contain",
    "§7.1 wentylacja": r"wentyl|ventilat",
    "§7.2 temperatura przechowywania": r"°C|ºC|temperatur\w* przechow|store .*temperat",
    "§7.2 niezgodności": r"niezgodn|incompatib|z dala od|oddzielnie od|separately",
    "§8.2 rękawice": r"rękawic|glove",
    "§8.2 oczy/twarz (norma)": r"EN 166|EN166|okular|gogl|goggle",
    "§9 temperatura zapłonu": r"zapłon|flash ?point|flammpunkt",
    "§9 pH": r"\bpH\b",
    "§13 zasada usuwania": r"usuwa|utyliz|dispos|odpad",
    "§14 numer UN": r"\bUN ?\d{4}|nie podlega|not regulated|nie dotyczy.*transport|nie sklasyfikowan\w* jako niebezpieczn|not classified as dangerous",
}
SRODOWISKO = r"kanalizac|środowisk|organizm\w* wodn|wodę z mycia|wody z mycia|waste water|environment"
TOKSYCZNY_WODZIE = r"\bH4(0[0-9]|1[0-3])\b"
LATWOPALNY = r"\bH22[4-6]\b|Flam\. Liq"
ATMOSFERA = r"atmosfer|inertyz|explosive atmosphere|explosionsfähig"  # sama wzmianka o uziemieniu nie wystarcza (sędzia r2, saiko-zid)


def sprawdz(p):
    t = open(p, encoding="utf-8").read()
    braki = [k for k, rx in ATRYBUTY.items() if not re.search(rx, t, re.I)]
    if re.search(TOKSYCZNY_WODZIE, t) and not re.search(SRODOWISKO, t, re.I):
        braki.append("§6 ŚRODOWISKO (karta ma H400–H413, brak środka ostrożności)")
    if re.search(LATWOPALNY, t) and not re.search(ATMOSFERA, t, re.I):
        braki.append("§7.1 ŁATWOPALNY (brak zasad antyelektrostatycznych / atmosfery wybuchowej)")
    if re.search(r"nie dotyczy — brak SDS", t):
        braki = [b for b in braki if not b.startswith("§")] or ["(brak SDS — sprawdzić uzasadnienie ręcznie)"]
    return braki


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    for p in sys.argv[1:]:
        b = sprawdz(p)
        print(f"{p}: {'OK' if not b else 'FLAGI: ' + '; '.join(b)}")
