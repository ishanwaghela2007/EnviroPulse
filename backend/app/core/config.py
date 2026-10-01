"""Central configuration. Every tunable value is read from environment variables
(see backend/.env.example). Nothing secret is hard-coded."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Infrastructure
    database_url: str = "postgresql+psycopg://enviro:enviro@localhost:5432/enviropulse"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173"
    log_level: str = "INFO"

    # External sources (keys optional; connectors report OFFLINE when unset)
    openaq_base_url: str = "https://api.openaq.org/v3"
    openaq_api_key: str = ""
    openaq_search_radius_m: int = 12000
    ogd_aqi_base_url: str = "https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
    ogd_api_key: str = ""
    http_timeout_seconds: float = 10.0

    # Scheduling / workers
    enable_scheduler: bool = True
    ingest_interval_seconds: int = 300
    pipeline_interval_seconds: int = 10
    demo_stream_auto: bool = False
    demo_tick_seconds: int = 5
    enable_demo_controls: bool = True

    # Analytics
    default_time_window_minutes: int = 15
    baseline_window_buckets: int = 96        # 24 h of 15-min windows
    min_baseline_buckets: int = 24           # 6 h minimum before an anomaly score is produced
    anomaly_zscore_threshold: float = 3.0
    detector_version: str = "rolling-zscore-v1"
    attribution_window_buckets: int = 96
    attribution_version: str = "lagged-assoc-v1"
    forecast_horizon: int = 8                # 8 x 15 min = next 2 h
    forecast_min_history_buckets: int = 288  # 3 days
    model_version: str = "forecast-v1"
    stale_after_minutes: int = 720
    active_anomaly_lookback_buckets: int = 4
    alert_clear_windows: int = 2             # consecutive clearly-normal windows needed to close an episode
    alert_clear_margin_pct: float = 5.0      # deadband: recovery needs the value this % inside the limit

    # Seed / demo
    history_days: int = 14
    history_lag_hours: int = 8
    random_seed: int = 13

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
