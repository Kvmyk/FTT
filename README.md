![Logo](https://github.com/user-attachments/assets/604e4c8e-2d5d-4ead-986a-d236d58f6d2b)
# Find My Throne 🚻

## Opis

[**Find My Throne**](https://findmythrone.net/) to strona internetowa, która pomaga szybko zlokalizować najbliższą toaletę publiczną! 🚽 Bez względu na Twoje położenie, nasza aplikacja wskaże Ci najszybszą drogę do najbliższego miejsca, gdzie możesz skorzystać z toalety.

## Funkcje

- **Lokalizacja najbliższych toalet** 🗺️  
  Wykorzystuje Twoją bieżącą lokalizację, aby znaleźć najbliższe toalety publiczne.

- **Nawigacja w czasie rzeczywistym** 🧭  
  Oferuje wskazówki krok po kroku, umożliwiając szybkie dotarcie do wybranego miejsca.

- **Informacje o udogodnieniach** ℹ️  
  Pozwala sprawdzić, czy toaleta jest przystosowana dla osób niepełnosprawnych lub wyposażona w przewijak dla niemowląt.

- **Oceny i recenzje użytkowników** ⭐  
  Umożliwia przeglądanie opinii innych użytkowników oraz dodawanie własnych ocen po skorzystaniu z toalety.

- **Monitorowanie treści użytkowników** 🛡️  
  Dzięki integracji z modelem [**MOP**](https://github.com/Kvmyk/MOP) (Monitorowanie Obraźliwych Przekazów), aplikacja automatycznie filtruje obraźliwe lub nieodpowiednie treści w recenzjach i komentarzach, zapewniając przyjazne środowisko dla wszystkich użytkowników.

## 🔹 Integracja z [MOP](https://github.com/Kvmyk/MOP)

Aby zapewnić bezpieczne i przyjazne środowisko dla wszystkich użytkowników, **Find My Throne** integruje model [**MOP**](https://github.com/Kvmyk/MOP) (Monitorowanie Obraźliwych Przekazów). Model ten analizuje treści generowane przez użytkowników, takie jak recenzje i komentarze, w celu wykrycia i filtrowania obraźliwych lub nieodpowiednich treści.

### 🔍 Cechy modelu MOP:

- **Czyszczenie tekstu**: Usuwa niepotrzebne znaki i formatowania, aby zapewnić spójność danych wejściowych.
- **Preprocessing**: Konwertuje tekst na małe litery i usuwa znaki specjalne, przygotowując dane do analizy.
- **Kodowanie tekstu**: Przekształca słowa na indeksy za pomocą słownika słów, umożliwiając modelowi przetwarzanie danych tekstowych.
- **Architektura modelu**: Wykorzystuje sieć LSTM do analizy sekwencji słów i klasyfikacji treści jako "hate" lub "neutral".
- **Trening i walidacja**: Model jest trenowany z użyciem funkcji straty BCELoss i optymalizatora Adam, z zastosowaniem technik takich jak early stopping i regularyzacja L2, aby zapewnić wysoką precyzję i generalizację.
- **API Flask**: Udostępnia interfejs API do analizy tekstu w czasie rzeczywistym, umożliwiając integrację z aplikacją **Find My Throne**.

### 🔗 Przykład użycia API MOP:
```bash
curl -X POST http://localhost:5001/analyze -H "Content-Type: application/json" -d '{"text": "Twój tekst do analizy"}'
```

### 📩 Przykładowa odpowiedź:
```json
{
  "text": "Twój tekst do analizy",
  "label": "neutral",
  "score": 0.3,
  "confidence": 0.4
}
```

Dzięki integracji modelu **MOP** z aplikacją **Find My Throne**, wszystkie treści generowane przez użytkowników są monitorowane i filtrowane pod kątem obraźliwych lub nieodpowiednich wypowiedzi, co przyczynia się do utrzymania przyjaznej atmosfery w społeczności użytkowników.


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

- **Geokodowanie i geolokalizacja**:  
  ![Nominatim](https://img.shields.io/badge/Nominatim-OpenStreetMap-brightgreen)

- **System operacyjny serwera**:  
  ![Ubuntu](https://img.shields.io/badge/Ubuntu-22.04%20LTS-orange)

- **Zarządzanie wersjami**:  
  ![Git](https://img.shields.io/badge/Git-2.x-red)

- **Hosting kodu źródłowego**:  
  ![GitHub](https://img.shields.io/badge/GitHub-Repo-lightgrey)

## 📜 Licencja

Ten projekt jest objęty licencją **GNU General Public License v3 (GPL-3.0)**. Więcej informacji znajdziesz w pliku [LICENSE](LICENSE) lub na stronie oficjalnej licencji: [GNU GPL v3](https://www.gnu.org/licenses/gpl-3.0.html). 
