# 📊 Codeforces Progress Monitor

<div align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite" />
  <img src="https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white" alt="HTML5" />
  <img src="https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white" alt="CSS3" />
  <img src="https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black" alt="JavaScript" />
</div>

> **A sleek, full-stack dashboard to track daily Codeforces progress, log mistakes, and monitor upsolving habits.**

---

## ✨ Features

- **Real-Time Daily Dashboard**: Fetches data from the Codeforces API to display your current rating, daily accepted (AC) count, and wrong answer (WA) count.
- **Historical Progress Tracking**: Caches daily performance metrics in a local SQLite database, allowing you to review specific problem logs and statistics from any previous day.
- **Mistake & Reflection Logger**: A structured diary to categorize failed attempts (e.g., "Bailed Early", "Missed Greedy Property") and record key insights to prevent recurring errors.
- **Contest Upsolve Tracker**: Automatically analyzes your recent contests to verify if critical problems (like Problem C) have been successfully upsolved.
- **Persistent Multi-User Login**: Supports logging in with any Codeforces handle, caching the session locally, and separating historical data by user.

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python) for high-performance RESTful API endpoints and seamless asynchronous integration with the Codeforces API.
- **Database**: SQLite managed via SQLAlchemy ORM for lightweight, configuration-free local data persistence.
- **Frontend**: Vanilla HTML5, CSS3, and ES6 JavaScript featuring a responsive, premium dark-mode UI with custom glassmorphism effects and flexbox layouts.

## 🚀 Getting Started

Follow these steps to run the monitor on your local machine.

### Prerequisites
- Python 3.8+ installed

### Installation

1. Clone the repository and navigate to the project folder:
```bash
git clone <your-repo-url>
cd cf_monitor
```

2. Install dependencies using `uv` (the fast Python package installer and resolver):
```bash
uv sync
```

3. Launch the FastAPI development server using `uv`:
```bash
uv run uvicorn main:app --reload
```

4. Open your web browser and navigate to:
`http://127.0.0.1:8000`

## 🧠 What I Learned

- **API Integration & Caching**: Designed efficient backend logic to fetch, parse, and locally cache bulk data from the public Codeforces API without hitting rate limits.
- **Full-Stack Data Flow**: Implemented a complete flow from a vanilla JavaScript frontend using `fetch` to a FastAPI backend routing requests to an SQLite database.
- **Database Design**: Structured a relational schema using SQLAlchemy to handle multi-user scenarios and daily time-series data aggregation.
- **Advanced CSS Layouts**: Built a responsive, modern UI from scratch utilizing CSS Grid, Flexbox, custom properties, and micro-animations without relying on external UI libraries.

## 👤 Author

**Gavy0037**
- Codeforces: [Gavy0037](https://codeforces.com/profile/Gavy0037)
