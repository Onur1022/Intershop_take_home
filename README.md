# Intershop Kundenreferenz Matcher
 
In diesem Ordner befinden sich folgende Begleitdokumente:
 
**Dokumentation.pdf** – Erklärt was das Programm macht, welche Technologien ich verwendet habe und warum ich mich für diese entschieden habe.
 
**Praesentation.pptx** – Die Präsentation, die ich beim Vorstellungsgespräch bei Intershop verwendet habe. Visualisiert die Systemarchitektur, den Technologie-Stack und die Funktionsweise des Systems.
 
**Testaufgabe.pdf** – Die originale Aufgabenstellung, auf deren Basis dieses Projekt entstanden ist.
 
**Funktionalitaet.mp4** – Eine Demo der Anwendung. Leider ohne Audio, da ich die Aufnahme in der Bibliothek gemacht habe. Im Video zeige ich der Reihe nach:
 
1. Server starten
2. Ab hier wird alles über das CLI-Script (`user.py`) ausgeführt:
   - Endpunkte abrufen
   - Versuch eine ähnliche Herausforderung hinzuzufügen, wird vom System abgelehnt
   - Eine neue Herausforderung hinzufügen, löst automatisch eine Referenzsuche aus
   - Produktempfehlung für eine Herausforderung abrufen
   - Visualisierung der gespeicherten Herausforderungen
---

## Lokale Ausführung

### 1. Virtuelle Umgebung erstellen und Abhängigkeiten installieren

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Daten scrapen

```bash
python scraper.py               # Kundenreferenzen von intershop.com
python scraper_products.py      # Produktinformationen von intershop.com
```

Die Referenzen werden als einzelne JSON-Dateien im Ordner `references/` gespeichert. Die Produktinformationen landen in `products.txt`.

### 3. Server starten

```bash
uvicorn server:app --reload --port 8000
```

Der Server ist danach unter `http://localhost:8000` erreichbar. Die interaktive API-Dokumentation findet sich unter `http://localhost:8000/docs`.

Das verwendete Embedding-Modell (`all-MiniLM-L6-v2`) läuft vollständig lokal ohne weitere Konfiguration. Der `/product-recommendation` Endpunkt benötigt zusätzlich eine Azure OpenAI Konfiguration – siehe Abschnitt unten.

### 4. CLI-Client verwenden

```bash
python user.py endpoints                                        # alle Endpunkte anzeigen
python user.py new "Wir möchten in 20 Länder verkaufen"        # neue Herausforderung
python user.py search "Wir möchten in 20 Länder verkaufen"     # Referenzen suchen
python user.py challenges                                       # gespeicherte Herausforderungen
python user.py visualize                                        # Übersicht im Terminal
python user.py recommend "Wir möchten in 20 Länder verkaufen"  # Produktempfehlung
```

---

## Produktempfehlung (Azure AI Foundry)

Für den `/product-recommendation` Endpunkt wird ein Azure OpenAI Modell benötigt. Lege dafür eine `.env` Datei im Projektordner an:

```
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-02-01
```

Alle anderen Endpunkte funktionieren ohne diese Konfiguration.
