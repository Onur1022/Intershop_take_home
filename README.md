# Intershop Kundenreferenz Matcher

Eine detaillierte Beschreibung des Projekts findet sich in der **Dokumentation.pdf** im übergeordneten Ordner. Eine Demonstration der Funktionalität ist in **Funktionalitaet.mp4** zu sehen.

---

## Lokale Ausführung

### 1. Virtuelle Umgebung erstellen und Abhängigkeiten installieren

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Daten scrapen

```bash
python scrape_references.py     # Kundenreferenzen von intershop.com
python scraper_products.py      # Produktinformationen von intershop.com
```

Die Referenzen werden als einzelne JSON-Dateien im Ordner `references/` gespeichert. Die Produktinformationen landen in `products.txt`.

### 3. Server starten

```bash
uvicorn server:app --reload --port 8000
```

Der Server ist danach unter `http://localhost:8000` erreichbar. Die interaktive API-Dokumentation findet sich unter `http://localhost:8000/docs`.

Alle Endpunkte sind sofort nutzbar – das verwendete Embedding-Modell (`all-MiniLM-L6-v2`) wurde bewusst klein gewählt und läuft vollständig lokal ohne weitere Konfiguration.

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
