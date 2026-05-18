from backend.config import get_settings

settings = get_settings()
print(f"DATABASE_URL: {settings.database_url}")
