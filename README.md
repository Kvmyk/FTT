![Logo](https://github.com/user-attachments/assets/fd63b77b-7ad9-4fec-ab52-c3ca663bbdc5)


# Find My Throne 🚻

## Opis

[**Find My Throne**](https://findmythrone.net/) to nowoczesna aplikacja internetowa, która pomaga szybko zlokalizować najbliższą toaletę publiczną w dowolnym miejscu na świecie! 🚽 Dzięki zaawansowanej technologii routing'u i sztucznej inteligencji, nasza aplikacja oferuje bezpieczne i niezawodne rozwiązanie dla użytkowników na całym globie.

## Funkcje

- **Lokalizacja najbliższych toalet** 🗺️  
  Wykorzystuje Twoją bieżącą lokalizację, aby znaleźć najbliższe toalety publiczne.

- **Nawigacja w czasie rzeczywistym** 🧭  
  Oferuje precyzyjne wskazówki wykorzystując publiczne API OpenRouteService z fallback'iem do OSRM dla maksymalnej niezawodności.

- **Informacje o udogodnieniach** ℹ️  
  Pozwala sprawdzić, czy toaleta jest przystosowana dla osób niepełnosprawnych lub wyposażona w przewijak dla niemowląt.

- **Oceny i recenzje użytkowników** ⭐  
  Umożliwia przeglądanie opinii innych użytkowników oraz dodawanie własnych ocen po skorzystaniu z toalety.

- **Monitorowanie treści użytkowników** 🛡️  
  Dzięki integracji z Google Gemini AI, aplikacja automatycznie filtruje obraźliwe lub nieodpowiednie treści w recenzjach i komentarzach, zapewniając przyjazne środowisko dla wszystkich użytkowników.

- **Globalna dostępność** 🌍  
  Aplikacja działa na całym świecie bez ograniczeń geograficznych, umożliwiając znajdowanie toalet publicznych w dowolnej lokalizacji.

## 🔹 Integracja z Google Gemini AI

Aby zapewnić bezpieczne i przyjazne środowisko dla wszystkich użytkowników, **Find My Throne** wykorzystuje Google Gemini AI do analizy treści generowanych przez użytkowników. System automatycznie sprawdza recenzje i komentarze pod kątem mowy nienawiści, wulgaryzmów i nieodpowiednich treści.

### 🔍 Cechy systemu moderacji:

- **Analiza w języku polskim**: Specjalizuje się w wykrywaniu polskich wulgaryzmów i slangu internetowego.
- **Sztuczna inteligencja**: Wykorzystuje zaawansowane modele językowe Google Gemini do precyzyjnej analizy tekstu.
- **Automatyczna moderacja**: Treści zawierające mowę nienawiści są automatycznie blokowane.
- **Bezpieczeństwo użytkowników**: Chroni społeczność przed nieodpowiednimi treściami.

### 🔗 Przykład konfiguracji:
```bash
# Wymagany klucz API Google Gemini w pliku .env
GEMINI_API_KEY=your_api_key_here
```

Dzięki integracji z Google Gemini AI, **Find My Throne** automatycznie filtruje nieodpowiednie treści, zapewniając przyjazną atmosferę w społeczności użytkowników.


## Stos technologiczny

**Find My Throne** został zbudowany z wykorzystaniem następujących technologii:

- **Język programowania**:  
  ![Python](https://img.shields.io/badge/Python-3.8%2B-blue)

- **Framework webowy**:  
  ![Flask](https://img.shields.io/badge/Flask-2.x-lightgrey)

- **Frontend**:  
  ![HTML5](https://img.shields.io/badge/HTML5-E34F26?logo=html5&logoColor=white)
  ![CSS3](https://img.shields.io/badge/CSS3-1572B6?logo=css3&logoColor=white)
  ![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?logo=javascript&logoColor=black)

- **Baza danych**:  
  ![SQLite](https://img.shields.io/badge/SQLite-3.x-blue)

- **Geokodowanie i routing**:  
  ![Nominatim](https://img.shields.io/badge/Nominatim-OpenStreetMap-brightgreen)
  ![OpenRouteService](https://img.shields.io/badge/OpenRouteService-Free_API-green)

- **Sztuczna inteligencja**:  
  ![Google Gemini](https://img.shields.io/badge/Google_Gemini-AI_Moderation-blue)

- **Konteneryzacja**:  
  ![Docker](https://img.shields.io/badge/Docker-Multi--stage_builds-2496ED)

- **System operacyjny serwera**:  
  ![Ubuntu](https://img.shields.io/badge/Ubuntu-22.04%20LTS-orange)

- **Zarządzanie wersjami**:  
  ![Git](https://img.shields.io/badge/Git-2.x-red)

- **Hosting kodu źródłowego**:  
  ![GitHub](https://img.shields.io/badge/GitHub-Repo-lightgrey)

## 🚀 Ulepszenia techniczne

**Find My Throne** został znacząco ulepszony pod kątem wydajności, niezawodności i globalnej dostępności:

### 🌐 Routing i nawigacja
- **OpenRouteService API**: Zastąpiono lokalny OSRM publicznym API dla globalnej dostępności
- **Fallback do OSRM**: Automatyczne przełączanie na publiczne OSRM w przypadku problemów z głównym API
- **Dekodowanie polyline**: Wsparcie dla zakodowanych tras z OpenRouteService

### 🛡️ Bezpieczeństwo i moderacja
- **Google Gemini AI**: Zaawansowana detekcja mowy nienawiści w języku polskim
- **Automatyczna moderacja**: Filtrowanie nieodpowiednich treści w czasie rzeczywistym
- **Obsługa błędów**: Graceful degradation w przypadku problemów z API

### 📦 Deployment i konteneryzacja
- **Multi-stage Docker builds**: Zoptymalizowane obrazy kontenerów
- **Alpine Linux variant**: Minimalne obrazy dla produkcji
- **Distroless images**: Obrazy bez zbędnych zależności dla maksymalnego bezpieczeństwa
- **.dockerignore**: Optymalizacja czasu budowania

### 🗺️ Usunięte ograniczenia
- **Globalna dostępność**: Usunięto ograniczenia do województwa opolskiego
- **Uniwersalność**: Aplikacja działa w dowolnej lokalizacji na świecie

## 📋 Wymagania i konfiguracja

### Zmienne środowiskowe (.env)
```bash
# Geokodowanie (Nominatim)
USER_AGENT=YourAppName/1.0

# Routing (OpenRouteService)
OPENROUTESERVICE_API_KEY=your_openrouteservice_api_key

# Moderacja treści (Google Gemini)
GEMINI_API_KEY=your_gemini_api_key

# Administracja
ADMIN_KEY=your_admin_password
```

### Docker deployment
```bash
# Standardowy build
docker build -t find-my-throne .

# Alpine variant (mniejszy obraz)
docker build -f Dockerfile.alpine -t find-my-throne:alpine .

# Distroless variant (najbezpieczniejszy)
docker build -f Dockerfile.distroless -t find-my-throne:distroless .
```

## 📜 Licencja

Ten projekt jest objęty licencją **GNU General Public License v3 (GPL-3.0)**. Więcej informacji znajdziesz w pliku [LICENSE](LICENSE) lub na stronie oficjalnej licencji: [GNU GPL v3](https://www.gnu.org/licenses/gpl-3.0.html).
