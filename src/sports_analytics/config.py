from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
MARTS_DIR = DATA_DIR / "marts"
PARQUET_DIR = PROCESSED_DIR / "parquet"

API_FOOTBALL_RAW_DIR = RAW_DIR / "api_football"
API_FOOTBALL_FIXTURES_RAW_DIR = API_FOOTBALL_RAW_DIR / "fixtures"
API_FOOTBALL_EVENTS_RAW_DIR = API_FOOTBALL_RAW_DIR / "events"
API_FOOTBALL_PARQUET_DIR = PARQUET_DIR / "api_football_fixtures"
API_FOOTBALL_EVENTS_PARQUET_DIR = PARQUET_DIR / "api_football_events"
QUALITY_REPORTS_DIR = INTERIM_DIR / "quality_reports"
REQUEST_LOG_DIR = INTERIM_DIR / "request_logs"
