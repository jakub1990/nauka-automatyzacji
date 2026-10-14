"""Małe API prognozy temperatury dla wybranych miast."""

import json
import logging
import time
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException, Query

logger = logging.getLogger(__name__)

app = FastAPI()

# Ścieżka do listy miast obok tego pliku
SCIEZKA_MIASTA = Path(__file__).resolve().parent / "miasta.json"
URL_OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_SEKUND = 15
KOMUNIKAT_502 = "Serwis pogodowy jest niedostępny."


def wczytaj_miasta(sciezka=SCIEZKA_MIASTA):
    """Wczytuje listę miast z pliku JSON."""
    with open(sciezka, encoding="utf-8") as plik:
        return json.load(plik)


def znajdz_miasto(miasta, nazwa):
    """Szuka miasta po nazwie; ignoruje wielkość liter i spacje na brzegach."""
    szukana = nazwa.strip().casefold()
    for miasto in miasta:
        if miasto["nazwa"].strip().casefold() == szukana:
            return miasto
    return None


def ekstrema_temperatury(czasy, temperatury):
    """
    Z list godzinowych zwraca min i max temperatury dnia pierwszej próbki.

    Przy remisie wygrywa wcześniejsza godzina. Godziny w formacie HH:MM.
    """
    data_dnia = czasy[0][:10]
    pary = []
    for czas, temperatura in zip(czasy, temperatury):
        if czas[:10] == data_dnia:
            # Fragment HH:MM z znacznika ISO, np. 2026-10-14T15:00
            pary.append((temperatura, czas[11:16]))

    # max/min przy równych wartościach zwracają pierwszą napotkaną parę
    najwyzsza, godzina_max = max(pary, key=lambda para: para[0])
    najnizsza, godzina_min = min(pary, key=lambda para: para[0])
    return najwyzsza, godzina_max, najnizsza, godzina_min


def pobierz_temperatury(lat, lon):
    """Pobiera godzinowe temperatury z Open-Meteo; błędy zgłasza jako 502.

    Jedno ponowienie po 1 sekundzie przy timeout, błędzie połączenia albo kodzie 5xx.
    """
    parametry = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m",
        "timezone": "Europe/Warsaw",
        "forecast_days": 1,
    }
    for proba in range(2):
        try:
            odpowiedz = requests.get(URL_OPEN_METEO, params=parametry, timeout=TIMEOUT_SEKUND)
        except (requests.Timeout, requests.ConnectionError) as blad:
            if proba == 0:
                time.sleep(1)
                continue
            logger.exception("Nie udało się pobrać temperatur z Open-Meteo")
            raise HTTPException(status_code=502, detail=KOMUNIKAT_502) from blad
        except requests.RequestException as blad:
            logger.exception("Nie udało się pobrać temperatur z Open-Meteo")
            raise HTTPException(status_code=502, detail=KOMUNIKAT_502) from blad

        # Kody 5xx ponawiamy raz; 4xx i pozostałe błędy od razu kończą funkcję
        if odpowiedz.status_code >= 500 and proba == 0:
            time.sleep(1)
            continue

        if odpowiedz.status_code != 200:
            logger.error(
                "Open-Meteo zwróciło kod %s: %s",
                odpowiedz.status_code,
                odpowiedz.text,
            )
            raise HTTPException(status_code=502, detail=KOMUNIKAT_502)

        try:
            dane = odpowiedz.json()
            if not isinstance(dane, dict):
                raise ValueError("Odpowiedź Open-Meteo nie jest obiektem JSON")
            godzinowe = dane.get("hourly")
            if not isinstance(godzinowe, dict):
                raise ValueError("Odpowiedź Open-Meteo nie zawiera hourly")
            czasy = godzinowe.get("time")
            temperatury = godzinowe.get("temperature_2m")
            if not isinstance(czasy, list) or not isinstance(temperatury, list):
                raise ValueError("Brak list time lub temperature_2m")
            if not czasy or not temperatury or len(czasy) != len(temperatury):
                raise ValueError("Listy time i temperature_2m są puste albo różnej długości")
            if any(
                isinstance(temperatura, bool) or not isinstance(temperatura, (int, float))
                for temperatura in temperatury
            ):
                raise ValueError("Lista temperature_2m zawiera wartość inną niż liczba")
            return czasy, temperatury
        except ValueError as blad:
            logger.exception("Nie udało się pobrać temperatur z Open-Meteo")
            raise HTTPException(status_code=502, detail=KOMUNIKAT_502) from blad


@app.get("/prognoza")
def prognoza(miasto: str = Query(...)):
    """Zwraca najniższą i najwyższą temperaturę dnia dla podanego miasta."""
    miasta = wczytaj_miasta()
    znalezione = znajdz_miasto(miasta, miasto)
    if znalezione is None:
        raise HTTPException(status_code=404, detail="Nieznane miasto.")

    czasy, temperatury = pobierz_temperatury(znalezione["lat"], znalezione["lon"])
    najwyzsza, godzina_max, najnizsza, godzina_min = ekstrema_temperatury(czasy, temperatury)
    return {
        "miasto": znalezione["nazwa"],
        "najwyzsza": najwyzsza,
        "godzina_max": godzina_max,
        "najnizsza": najnizsza,
        "godzina_min": godzina_min,
    }
