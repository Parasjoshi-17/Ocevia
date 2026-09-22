# 🌊 Ocevia

### Turning Ocean Data into Intelligent Decisions

**Ocevia** is an AI-powered marine decision-support system built for **Smart India Hackathon 2026 — Problem Statement PS-26176: Ocean Data Translator**.

It translates complex ocean, weather, and marine data into simple, understandable information for fishermen and coastal communities.

Instead of requiring users to interpret technical oceanographic data, Ocevia answers questions such as:

> **“Can I go fishing tomorrow morning near Mumbai?”**

The system retrieves scientific weather and ocean data, evaluates marine conditions using deterministic safety rules, checks available Potential Fishing Zone (PFZ) information, and generates a simple explanation.

---

## 🎯 Problem Statement

Ocean and weather information is often available in technical formats that are difficult for fishermen to interpret.

Important parameters such as:

* Wave height
* Wave direction
* Wind speed
* Wind gusts
* Sea-surface temperature
* Potential Fishing Zones (PFZ)

can be difficult to understand without technical knowledge.

This creates a gap between **available scientific data** and **usable decision-making information**.

### Ocevia's objective

Convert complex marine datasets into:

* Simple natural-language answers
* Marine safety advisories
* Fishing opportunity information
* Interactive map visualizations
* Location-specific information

---

# 🧠 Core Principle

> **DATA PROVIDES EVIDENCE. RULES DECIDE SAFETY. AI EXPLAINS.**

Ocevia deliberately separates AI-generated explanations from safety decisions.

The LLM does **not** determine whether conditions are safe.

Instead:

```text
Scientific Data
      ↓
Deterministic Safety Engine
      ↓
Safety Verdict
      ↓
AI Explanation
```

This reduces the risk of an LLM inventing or changing critical safety information.

---

# 🚀 Key Features

## 1. Natural Language Marine Queries

Users can ask questions using natural language.

Example:

```text
Can I go fishing tomorrow morning near Mumbai?
```

The system extracts relevant information such as:

* Location
* Date
* Time window
* User intent

and retrieves the required data.

---

## 2. Marine Safety Assessment

Ocevia evaluates marine conditions using deterministic rules based on:

* Wave height
* Wind speed
* Wind gusts

The system produces one of three states:

| Verdict           | Meaning                                                  |
| ----------------- | -------------------------------------------------------- |
| 🟢 SAFE           | Conditions are within the prototype's defined safe range |
| 🟡 CAUTION        | Conditions require additional caution                    |
| 🔴 DO NOT VENTURE | Conditions exceed the defined prototype thresholds       |

### Current prototype thresholds

**DO NOT VENTURE**

```text
Wave height > 2.5 m
OR
Wind speed > 45 km/h
OR
Wind gust > 60 km/h
```

**CAUTION**

```text
Wave height > 1.5 m
OR
Wind speed > 25 km/h
OR
Wind gust > 40 km/h
```

Otherwise:

```text
SAFE
```

> These are prototype decision-support thresholds and are not intended to replace official marine navigation or government safety advisories.

---

# 🎣 Fishing Opportunity

Marine safety and fishing opportunity are treated as **separate concepts**.

A location may have potential fishing activity while simultaneously having unsafe marine conditions.

Ocevia therefore does not convert safety conditions into a fake "fishing score."

The fishing opportunity engine uses available **PFZ advisory information** as evidence.

Example:

```text
PFZ Available
        +
SAFE conditions
        ↓
Fishing opportunity indicated
```

If PFZ information is unavailable, the system explicitly reports:

```text
No current PFZ advisory available for this region/date.
```

It does not fabricate fishing zones, fish species, or coordinates.

---

# 🗺️ Interactive Marine Map

Ocevia provides an interactive map for visualizing marine conditions.

Current map layers include:

* 🌬️ Wind
* 🌊 Wave height
* 🧭 Wave direction
* 🌡️ Sea-surface temperature
* 🎣 Potential Fishing Zones

The map uses Leaflet and OpenStreetMap for geographic visualization.

### Wind visualization

Wind speed and direction are converted into vector data and displayed using animated particles.

### Wave visualization

Wave height is represented as a continuous field, with directional information shown separately.

### Sea-surface temperature

Sea-surface temperature is retrieved from marine forecast data and visualized as a continuous spatial field.

> Intermediate pixels in the visual layers are generated through interpolation for visualization. They should not be interpreted as additional physical observations.

---

# 🏗️ System Architecture

```text
                    USER
                      │
                      ▼
              Natural Language Query
                      │
                      ▼
              Intent / Context Parser
                      │
          ┌───────────┴───────────┐
          │                       │
          ▼                       ▼
   Weather Data              Ocean Data
   Open-Meteo                 Open-Meteo
          │                       │
          └───────────┬───────────┘
                      ▼
              Scientific Data
                      │
          ┌───────────┴───────────┐
          │                       │
          ▼                       ▼
   Marine Safety            PFZ / Fishing
       Engine                 Analysis
          │                       │
          └───────────┬───────────┘
                      ▼
               Structured Result
                      │
                      ▼
                Claude API
                      │
                      ▼
             Human-Friendly
               Explanation
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
      Dashboard                 Map
```

---

# 🤖 Agentic Architecture

The backend is organized around specialized agents.

```text
                    Orchestrator
                         │
       ┌─────────────────┼─────────────────┐
       │                 │                 │
       ▼                 ▼                 ▼
 Weather Agent      Ocean Agent       Safety Agent
       │                 │                 │
       ▼                 ▼                 ▼
 Weather API        Marine API       Safety Rules
       
       ┌─────────────────┼─────────────────┐
       │                 │                 │
       ▼                 ▼                 ▼
    PFZ Agent       Fishing Agent    Explanation Agent
       │                 │                 │
       ▼                 ▼                 ▼
   PFZ Data        Fishing Rules     Claude API
```

The **Orchestrator** coordinates these components and combines their results into a structured response.

---

# 🛠️ Technology Stack

## Frontend

* React
* Vite
* JavaScript
* Leaflet
* React-Leaflet
* Leaflet Velocity
* HTML/CSS

## Backend

* Python
* Flask
* SQLite

## AI

* Anthropic Claude API
* Claude Sonnet

## Data Sources

* Open-Meteo Forecast API
* Open-Meteo Marine API
* PFZ advisory data where available
* OpenStreetMap

---

# 📁 Project Structure

```text
BlueMindAI/
│
├── app.py
├── database.py
├── weather.py
├── marine.py
├── map_data.py
├── pfz.py
├── rules.py
├── fishing_suitability.py
├── intent_parser.py
├── ai_explain.py
│
├── agents/
│   ├── orchestrator.py
│   ├── weather_agent.py
│   ├── ocean_agent.py
│   ├── safety_agent.py
│   ├── explanation_agent.py
│   ├── pfz_agent.py
│   └── fishing_agent.py
│
├── tools/
│   └── live_check.py
│
├── tests/
│   └── test_ocevia_flow.py
│
└── frontend/
    ├── package.json
    ├── vite.config.js
    │
    └── src/
        ├── App.jsx
        ├── App.css
        ├── index.css
        ├── main.jsx
        │
        ├── components/
        │   ├── Navbar.jsx
        │   ├── VelocityWindLayer.jsx
        │   ├── WaveLayer.jsx
        │   ├── SSTLayer.jsx
        │   ├── PFZLayer.jsx
        │   └── FieldOverlay.jsx
        │
        ├── pages/
        │   ├── Home.jsx
        │   ├── Dashboard.jsx
        │   ├── About.jsx
        │   ├── History.jsx
        │   └── MarineMap.jsx
        │
        └── fieldRaster.js
```

---

# ⚙️ Installation

## Prerequisites

Make sure the following are installed:

* Python 3.x
* Node.js
* npm
* Git

---

## 1. Clone the repository

```bash
git clone https://github.com/KashafnajTandel/BlueMindAI.git
cd BlueMindAI
```

---

# 🐍 Backend Setup

Create a virtual environment:

### Windows

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install required Python packages:

```powershell
pip install flask requests pandas openmeteo-requests requests-cache retry-requests
```

If your project contains a `requirements.txt`, install dependencies with:

```powershell
pip install -r requirements.txt
```

---

# 🔐 Environment Variables

Create a `.env` file in the backend project directory.

Example:

```env
ANTHROPIC_API_KEY=your_api_key_here
```

Do not commit API keys or other secrets to GitHub.

Add `.env` to `.gitignore`:

```gitignore
.env
.venv/
__pycache__/
node_modules/
```

---

# ▶️ Running the Backend

From the project root:

```powershell
python app.py
```

The Flask backend should start on:

```text
http://127.0.0.1:5000
```

---

# ⚛️ Running the Frontend

Open another terminal.

Navigate to the frontend:

```powershell
cd frontend
```

Install dependencies:

```powershell
npm install
```

Start Vite:

```powershell
npm run dev
```

The frontend will normally be available at:

```text
http://localhost:5173
```

---

# 🔄 Example User Flow

### User

```text
Can I go fishing tomorrow morning near Mumbai?
```

### System

```text
1. Identify location → Mumbai
2. Identify date → Tomorrow
3. Identify time → Morning
4. Retrieve weather data
5. Retrieve marine data
6. Evaluate safety conditions
7. Retrieve/check PFZ information
8. Evaluate fishing opportunity
9. Generate explanation
10. Display result and map
```

---

# 📡 Data Processing

## Weather

The system retrieves weather information such as:

* Wind speed
* Wind direction
* Wind gusts
* Temperature
* Precipitation

from Open-Meteo.

## Marine

Marine data includes:

* Wave height
* Wave direction
* Sea-surface temperature

from Open-Meteo Marine.

## Spatial Visualization

The map backend generates geographic grid points across the selected coastal region.

Data is retrieved in batches to avoid making an excessive number of API requests.

The frontend then interpolates the available model data for smooth visualization.

---

# 🔒 Safety Design

Ocevia follows a strict separation between **data retrieval**, **decision logic**, and **language generation**.

### The LLM cannot:

* Change the safety verdict
* Invent weather values
* Invent wave heights
* Invent PFZ coordinates
* Invent fish species
* Override deterministic safety rules

### Instead:

```text
APIs
 ↓
Scientific Measurements
 ↓
Deterministic Rules
 ↓
Safety Verdict
 ↓
LLM Explanation
```

This architecture is designed to make the system more transparent and auditable.

---

# 🧪 Testing

Offline tests are available in:

```text
tests/test_ocevia_flow.py
```

Run:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

The live validation tool is:

```text
tools/live_check.py
```

Run:

```powershell
python tools/live_check.py
```

or specify a backend URL:

```powershell
python tools/live_check.py http://127.0.0.1:5000
```

The tests cover areas such as:

* City resolution
* Regional map selection
* Safety thresholds
* PFZ normalization
* Fishing suitability logic
* Map API contracts
* API routing
* Data handling

---

# 🌐 API Endpoints

The backend provides API endpoints for interacting with the application.

### Ask

```http
POST /api/ask
```

Example:

```json
{
  "city": "Mumbai",
  "target_day": "tomorrow",
  "time_window": "morning"
}
```

### Map Data

```http
GET /api/map-data
```

The map endpoint provides geographic data used by the frontend map layers.

---

# 📊 Design Decisions

### Deterministic safety instead of LLM-based safety

Safety decisions require predictable and reproducible logic.

### No artificial fishing score

Without reliable training data, generating an ML-based fishing score would create false precision.

### PFZ as evidence

PFZ information is treated as an external scientific advisory rather than something generated by the language model.

### Separate safety and fishing opportunity

Good fishing conditions do not automatically mean safe marine conditions.

### Interpolation only for visualization

Interpolation is used to create visually continuous map fields. It does not create new physical observations.

---

# 🚧 Current Limitations

Ocevia is a prototype developed for the Smart India Hackathon.

Current limitations include:

* Open-Meteo is currently the primary operational weather/marine data source.
* Government datasets such as INCOIS/MOSDAC and IMD require deeper production integration.
* PFZ availability depends on the accessible advisory source.
* Map interpolation is for visualization and does not increase the underlying model resolution.
* The prototype safety thresholds are not official navigation standards.
* Internet/API availability can affect live results.
* Fishing opportunity analysis is intentionally conservative where supporting data is unavailable.
* The system should not replace official warnings or professional marine navigation guidance.

---

# 🔮 Future Scope

Future versions can integrate:

* Direct INCOIS PFZ APIs
* MOSDAC satellite data
* IMD marine weather information
* More detailed fisheries datasets
* Fish-species intelligence
* Satellite-derived ocean parameters
* Improved coastal/ocean masking
* Higher-resolution marine datasets
* Voice interaction
* WhatsApp integration
* SMS support
* Regional Indian-language support
* Offline/low-connectivity workflows
* Historical marine condition analysis
* More advanced fisheries decision-support models

---

# 🎯 Impact

Ocevia aims to reduce the gap between **scientific ocean information** and **practical understanding**.

Instead of requiring users to interpret:

```text
Wave Height: 1.8 m
Wind Speed: 31 km/h
Wave Direction: 247°
SST: 28.4°C
```

the system can communicate the result in a simpler form:

```text
⚠️ CAUTION

Sea conditions are moderately rough.
Wind and wave conditions require caution
during the selected time period.

Fishing activity may be indicated by
available PFZ information, but marine
safety should be considered first.
```

---

# ⚠️ Disclaimer

Ocevia is a **prototype decision-support system developed for Smart India Hackathon 2026**.

It should not be used as a replacement for:

* Official government marine warnings
* INCOIS advisories
* IMD warnings
* Coast Guard instructions
* Professional maritime navigation systems
* Local expert knowledge

Users should always follow official safety advisories before going to sea.

---

# 👥 Team

**Smart India Hackathon 2026**

**Problem Statement:** PS-26176 — Ocean Data Translator

**Project:** Ocevia

---

## 🌊 Ocevia

> **Turning Ocean Data into Intelligent Decisions.**
