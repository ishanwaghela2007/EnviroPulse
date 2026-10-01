"""Alignment worker: picks up newly created readings/factory outputs (watermark) and aligns the affected
zone windows. In this prototype it runs as the first stage of analytics_worker.run_pending()."""
from app.services.pipeline import pending_ranges  # noqa: F401  (re-exported for modular use)
