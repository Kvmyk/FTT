# Find My Throne (Refactored) 🚻

Nowoczesna wersja aplikacji do znajdowania toalet publicznych.

## 🚀 Uruchomienie

1. Zainstaluj zależności:
   ```bash
   pip install -r app/requirements.txt
   ```

2. Uruchom serwer:
   ```bash
   python run.py
   ```

3. Otwórz w przeglądarce: [http://localhost:5000](http://localhost:5000)

## 🛠 Zmiany (Refaktoryzacja)

- **Architektura**: Przejście na Flask Application Factory + Blueprints.
- **Frontend**: Leaflet.js (mapa po stronie klienta) + Tailwind CSS (nowoczesny wygląd).
- **API**: Nowe endpointy JSON w `app/routes/api.py`.
- **Czystość**: Stary kod przeniesiony do katalogu `legacy/`.

## 📂 Struktura

- `run.py` - Punkt wejścia aplikacji.
- `app/`
  - `routes/` - Endpointy API i widoki.
  - `models/` - Obsługa bazy danych (SQLite).
  - `templates/` - Szablony HTML (Jinja2 + Tailwind).
  - `static/` - Ikony i zasoby.
  - `utils.py` - Funkcje pomocnicze (OSRM, AI).

## ⚠️ Uwagi

- Aplikacja oczekuje lokalnych usług OSRM (nawigacja) i MOP (analiza tekstu) pod adresami zdefiniowanymi w `app/utils.py`. Jeśli ich nie masz, funkcje trasowania i analizy komentarzy mogą zwracać błędy, ale mapa i toalety będą działać.
