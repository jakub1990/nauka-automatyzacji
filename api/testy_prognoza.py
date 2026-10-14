"""Testy jednostkowe API prognozy temperatury."""

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from prognoza import (
    ekstrema_temperatury,
    pobierz_temperatury,
    prognoza,
    wczytaj_miasta,
    znajdz_miasto,
)


def test_wczytaj_miasta():
    """Sprawdza trzy miasta i współrzędne Krakowa ze specyfikacji."""
    miasta = wczytaj_miasta()
    assert len(miasta) == 3
    nazwy = {miasto["nazwa"] for miasto in miasta}
    assert nazwy == {"Warszawa", "Kraków", "Gdańsk"}
    krakow = znajdz_miasto(miasta, "Kraków")
    assert krakow["lat"] == 50.06
    assert krakow["lon"] == 19.94


def test_znajdz_miasto():
    """Znajduje miasto bez względu na wielkość liter i spacje; obce odrzuca."""
    miasta = wczytaj_miasta()
    warszawa = znajdz_miasto(miasta, "Warszawa")
    assert warszawa["lat"] == 52.23
    assert warszawa["lon"] == 21.01
    assert znajdz_miasto(miasta, " kraków")["nazwa"] == "Kraków"
    assert znajdz_miasto(miasta, "GDAŃSK")["nazwa"] == "Gdańsk"
    assert znajdz_miasto(miasta, "Berlin") is None


def test_ekstrema_temperatury():
    """Liczy min i max na stałych danych; przy remisie bierze wcześniejszą godzinę."""
    czasy = [
        "2026-10-14T06:00",
        "2026-10-14T12:00",
        "2026-10-14T15:00",
        "2026-10-14T18:00",
        "2026-10-15T06:00",
    ]
    temperatury = [3.0, 18.5, 18.5, 10.0, 99.0]
    najwyzsza, godzina_max, najnizsza, godzina_min = ekstrema_temperatury(czasy, temperatury)
    assert najwyzsza == 18.5
    assert godzina_max == "12:00"
    assert najnizsza == 3.0
    assert godzina_min == "06:00"


def test_pobierz_temperatury_blad_sieci():
    """Timeout lub błąd połączenia kończy się kodem 502."""
    import requests

    with patch("prognoza.time.sleep"), patch(
        "prognoza.requests.get", side_effect=requests.Timeout("timeout")
    ):
        with pytest.raises(HTTPException) as blad:
            pobierz_temperatury(50.06, 19.94)
        assert blad.value.status_code == 502
        assert blad.value.detail == "Serwis pogodowy jest niedostępny."


def test_pobierz_temperatury_ponowienie():
    """Po jednym nieudanym zapytaniu i jednym udanym funkcja zwraca dane."""
    import requests

    sukces = Mock()
    sukces.status_code = 200
    sukces.json.return_value = {
        "hourly": {
            "time": ["2026-10-14T06:00", "2026-10-14T15:00"],
            "temperature_2m": [3.0, 18.5],
        }
    }
    with patch("prognoza.time.sleep") as pauza, patch(
        "prognoza.requests.get",
        side_effect=[requests.Timeout("timeout"), sukces],
    ) as zapytanie:
        czasy, temperatury = pobierz_temperatury(50.06, 19.94)

    assert zapytanie.call_count == 2
    pauza.assert_called_once_with(1)
    assert czasy == ["2026-10-14T06:00", "2026-10-14T15:00"]
    assert temperatury == [3.0, 18.5]


def test_pobierz_temperatury_niepoprawna_odpowiedz():
    """Odpowiedź 200 bez poprawnych list godzinowych kończy się kodem 502."""
    mock_odpowiedz = Mock()
    mock_odpowiedz.status_code = 200
    mock_odpowiedz.json.return_value = {"hourly": {"time": ["2026-10-14T00:00"]}}
    with patch("prognoza.requests.get", return_value=mock_odpowiedz):
        with pytest.raises(HTTPException) as blad:
            pobierz_temperatury(50.06, 19.94)
        assert blad.value.status_code == 502
        assert blad.value.detail == "Serwis pogodowy jest niedostępny."


def test_pobierz_temperatury_null_w_temperaturach():
    """Null w liście temperatur kończy się kodem 502."""
    mock_odpowiedz = Mock()
    mock_odpowiedz.status_code = 200
    mock_odpowiedz.json.return_value = {
        "hourly": {
            "time": ["2026-10-14T06:00", "2026-10-14T15:00"],
            "temperature_2m": [3.0, None],
        }
    }
    with patch("prognoza.requests.get", return_value=mock_odpowiedz):
        with pytest.raises(HTTPException) as blad:
            pobierz_temperatury(50.06, 19.94)
        assert blad.value.status_code == 502
        assert blad.value.detail == "Serwis pogodowy jest niedostępny."


def test_prognoza_nieznane_miasto():
    """Nieznane miasto zwraca 404 z komunikatem po polsku."""
    with pytest.raises(HTTPException) as blad:
        prognoza(miasto="Paryż")
    assert blad.value.status_code == 404
    assert blad.value.detail == "Nieznane miasto."


def test_prognoza_sukces():
    """Przy stałych danych pogodowych endpoint zwraca pełny JSON."""
    stale_czasy = ["2026-10-14T06:00", "2026-10-14T15:00"]
    stale_temperatury = [3.0, 18.5]
    with patch("prognoza.pobierz_temperatury", return_value=(stale_czasy, stale_temperatury)):
        wynik = prognoza(miasto="Kraków")
    assert wynik == {
        "miasto": "Kraków",
        "najwyzsza": 18.5,
        "godzina_max": "15:00",
        "najnizsza": 3.0,
        "godzina_min": "06:00",
    }
