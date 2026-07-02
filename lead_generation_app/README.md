# LeadGen Studio 🚀
### Effortless Lead Generation for the Modern Web

A premium, high-performance, and undetectable **Lead Generation App** built using the **Scrapling** framework. It features robust scrapers for **Google Maps** and **LinkedIn**, coupled with a beautiful, real-time dark-mode dashboard to control, monitor, and export your lead databases.

---

## Features

- **Google Maps Scraper**: Search by keyword/category and location. Utilizes headless Chromium automation to execute infinite scrolls, extract listings, ratings, phone numbers, websites, and physical addresses.
- **LinkedIn Scraper**: 
  - **Google X-Ray Dork Mode**: 100% safe, high-speed, no-login required scraping that scans public search engines to isolate profiles and company pages.
  - **Cookie Authentication Mode**: Authenticate via your browser's session cookie (`li_at`) to fetch direct, inside-network LinkedIn search cards.
- **Sleek Glassmorphic Dashboard**: A premium, responsive front-end dashboard that streams scraper terminal logs and active leads list in real-time.
- **Campaign Database**: Automatically saves scraped campaigns to local `data/` storage for quick reloading and management.
- **Dataset Exports**: Single-click downloads to CSV or JSON formats.
- **Dockerized VPS Ready**: Uses the official `pyd4vinci/scrapling` base image to deploy to any cloud VPS (Ubuntu, AWS, PetroSky, etc.) without manual browser installs.

---

## Local Installation & Setup

Ensure you have **Python 3.10+** installed on your system.

### 1. Set Up a Virtual Environment
From this directory:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r backend/requirements.txt
```

### 3. Install Browser Binaries (Required for Google Maps Scraper)
Run Scrapling's installer command to fetch the custom-patched Chromium binary and system dependencies:
```bash
scrapling install
```

---

## Running the Application

### 1. Launch the Server
Start the FastAPI server:
```bash
python backend/app.py
```

### 2. Access the Studio
Open your browser and navigate to:
```
http://localhost:8000
```
Use the sleek control center in the **Scraper Panel** to name your campaign, enter search keywords, locations, and hit **Launch Campaign**! Watch terminal feeds populate in real-time.

---

## 🐳 VPS & Docker Deployment (Recommended for Servers)

To run this on a headless VPS, Docker is highly recommended. It isolates the Playwright/Patchright browser instances and prevents dependency conflicts.

### 1. Build the Docker Image
```bash
docker build -t leadgen-studio .
```

### 2. Run the Container
Run the container and map port `8000`:
```bash
docker run -d -p 8000:8000 --name leadgen-app leadgen-studio
```

### 3. Access on VPS
Visit your server's IP:
```
http://<your-vps-ip>:8000
```

---

## Project Structure

```
lead_generation_app/
│
├── backend/
│   ├── __init__.py
│   ├── app.py             # FastAPI backend with SSE streaming
│   ├── google_maps.py     # Async Google Maps scraping engine
│   ├── linkedin.py        # safe X-Ray & auth LinkedIn engines
│   └── requirements.txt   # Python backend dependencies
│
├── frontend/
│   ├── index.html         # Glassmorphic user interface
│   ├── style.css          # Premium theme and styles
│   └── main.js            # Frontend controllers and SSE parsers
│
├── data/                  # Campaign data files (.json, .csv)
│
├── Dockerfile             # Custom container spec
└── README.md              # Documentation
```

---

*Powered by the [Scrapling Web Scraping Framework](https://github.com/D4Vinci/Scrapling).*
