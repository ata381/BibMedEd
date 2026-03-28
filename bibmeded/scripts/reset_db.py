"""Drop all tables and recreate from current SQLAlchemy models.

Usage (from bibmeded/ directory):
    python scripts/reset_db.py

Or inside Docker:
    docker compose exec api python scripts/reset_db.py

WARNING: This destroys all data. Only use in development.
"""
import sys
from pathlib import Path

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base, get_engine
import app.models  # noqa: F401 — register all models

def main():
    engine = get_engine()
    print(f"Connecting to: {engine.url}")
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    print("Creating all tables from current models...")
    Base.metadata.create_all(bind=engine)
    print("Done. Database schema is now in sync with models.")

if __name__ == "__main__":
    main()
