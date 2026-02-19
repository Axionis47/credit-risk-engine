"""Initialize database tables."""

from credit_scoring.config.settings import load_settings
from credit_scoring.utils.database import DatabaseManager


def main():
    settings = load_settings()
    db = DatabaseManager(settings.database.url)
    db.create_tables()
    print("Database tables created.")


if __name__ == "__main__":
    main()
