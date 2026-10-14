# Prognoza temperatur

Małe API w FastAPI: dla miasta z listy zwraca najniższą i najwyższą temperaturę dnia (dane z Open-Meteo).

Wymagany Python 3.9 lub nowszy.

## Instalacja

Pobierz repozytorium i wejdź do folderu projektu:

```bash
git clone https://github.com/jakub1990/nauka-automatyzacji.git
cd nauka-automatyzacji/api
```

Utwórz środowisko:

```bash
python3 -m venv .venv
```

Aktywuj je na macOS i Linux:

```bash
source .venv/bin/activate
```

albo na Windows:

```bash
.venv\Scripts\activate
```

Zainstaluj zależności:

```bash
pip install -r requirements.txt
```

## Uruchomienie serwera

```bash
uvicorn prognoza:app --reload
```

Serwer startuje pod adresem `http://127.0.0.1:8000`. Dokumentacja API z możliwością testowania zapytań jest pod adresem `http://127.0.0.1:8000/docs`.

## Testy

```bash
pytest
```

## Przykład

Zapytanie:

```bash
curl "http://127.0.0.1:8000/prognoza?miasto=Kraków"
```

Przykładowa odpowiedź (wartości zależą od aktualnej prognozy):

```json
{
  "miasto": "Kraków",
  "najwyzsza": 18.5,
  "godzina_max": "15:00",
  "najnizsza": 3.0,
  "godzina_min": "06:00"
}
```

Dostępne miasta: Warszawa, Kraków, Gdańsk (plik `miasta.json`). Nieznane miasto zwraca 404, a błąd serwisu pogodowego zwraca 502.