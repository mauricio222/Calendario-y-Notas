![CodeRabbit Pull Request Reviews](https://img.shields.io/coderabbit/prs/github/mauricio222/Calendario-y-Notas?utm_source=oss&utm_medium=github&utm_campaign=mauricio222%2FCalendario-y-Notas&labelColor=171717&color=FF570A&link=https%3A%2F%2Fcoderabbit.ai&label=CodeRabbit+Reviews)

# Calendario y Notas

A simple web application to manage your calendar events and notes.

## Features
- Add, view, and manage calendar events
- Add, view, and manage personal notes
- Simple and intuitive web interface

## Setup

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd Calendario-y-Notas
   ```
2. **Create a virtual environment (recommended):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Initialize the database:**
   ```bash
   python init_db.py
   ```
5. **Run the app:**
   ```bash
   python app.py
   ```

## Project Structure
- `app.py`: Main application file
- `init_db.py`: Script to initialize the SQLite database
- `templates/`: HTML templates
- `requirements.txt`: Python dependencies
- `calendario_notas.db`: SQLite database (excluded from version control)

## Notes
- Do not commit `calendario_notas.db`, `venv/`, or `__pycache__/` to version control (see `.gitignore`).
- For any issues or feature requests, please open an issue on GitHub. 
