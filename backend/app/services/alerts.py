"""Threshold + alert engine (independent of anomaly detection).

For each applicable rule, windows are evaluated strictly in time order from a persisted watermark:
  1. load rule   2. compare zone value   3. direction   4. persistence (consecutive windows)
  5. confidence (valid sensors / active sensors >= min_confidence)
  6. create or update alert (one open episode per zone+parameter+rule; enforced by a DB unique index)
  7. write alert log   8. dispatch in-app notification (alert log + Redis publish)
Recovery hysteresis: an episode closes only after ALERT_CLEAR_WINDOWS (default 2) consecutive windows that
are clearly normal — at least ALERT_CLEAR_MARGIN_PCT (default 5 %) inside the limit. Values hovering just
under the threshold hold the episode open, so one episode is never split into several alerts. A later breach after closure opens a
NEW episode. Missing or low-confidence data holds the current state (neither breach nor recovery)."""
import logging
import math
from datetime import datetime

from sqlalchemy.orm import Session

from app.core import redis as rcache
from app.core.config import get_settings
from app.core.logging import log
from app.core.parameters import PARAMETERS
from app.core.timeutil import bucket_delta, floor_bucket
from app.repositories import alerts as alert_repo
from app.repositories import analytics as arepo
from app.services.features import grid_frame

logger = logging.getLogger("enviropulse.alerts")


def _breached(value: float, rule: dict) -> bool:
    return value > rule["threshold_value"] if rule["direction"] == "above" else value < rule["threshold_value"]


def _clearly_normal(value: float, rule: dict, margin_pct: float) -> bool:
    """Recovery deadband (ISA-18.2 style): a window counts toward closing an episode only when the value is
    at least `margin_pct` % inside the limit. Values in the band between hold the episode open."""
    m = abs(rule["threshold_value"]) * margin_pct / 100.0
    return value <= rule["threshold_value"] - m if rule["direction"] == "above" else value >= rule["threshold_value"] + m


def _reason(rule: dict, value: float, n: int, conf: float) -> str:
    sp = PARAMETERS[rule["parameter"]]
    word = "exceeded" if rule["direction"] == "above" else "fell below"
    return (f"{sp.label} zone mean {value:.2f} {sp.unit} {word} the configured threshold {rule['threshold_value']:g} "
            f"{sp.unit} for {n} consecutive {int(bucket_delta().total_seconds() // 60)}-min windows "
            f"(required: {rule['persistence_windows']}); data confidence {conf:.2f} ≥ {rule['min_confidence']:.2f}.")


def _context(db: Session, zone_id: str, param: str, ts: datetime) -> str:
    anomalies = arepo.list_anomalies(db, zone_id, param, ts - 3 * bucket_delta(), ts, limit=1)
    if not anomalies:
        return "No statistical anomaly in the last hour: the value is high but consistent with its recent baseline."
    a = anomalies[0]
    parts = [f"Anomaly detected at {a['timestamp']:%H:%M} UTC (score {a['score']:.1f}σ)."]
    contributors = arepo.attributions_for(db, a["id"])[:2]
    if contributors:
        names = ", ".join(f"{c['contributor_name']} ({c['score']:.2f})" for c in contributors)
        parts.append(f"Likely contributors (estimate, not proof of cause): {names}.")
    return " ".join(parts)


def evaluate_zone(db: Session, zone_id: str, until: datetime, since: datetime | None = None) -> dict:
    d = bucket_delta()
    until = floor_bucket(until)
    stats = {"created": 0, "updated": 0, "resolved": 0}
    for rule in alert_repo.thresholds_for_zone(db, zone_id):
        p, key = rule["parameter"], f"alerts:{zone_id}:{rule['id']}"
        state = arepo.get_state(db, key) or {}
        last = datetime.fromisoformat(state["last_evaluated"]) if state.get("last_evaluated") else None
        first = (last + d) if last else floor_bucket(since or until)
        if first > until:
            continue
        consecutive = int(state.get("consecutive", 0))
        normal_streak = int(state.get("normal_streak", 0))
        clear_after = get_settings().alert_clear_windows
        margin = get_settings().alert_clear_margin_pct
        unit = PARAMETERS[p].unit
        frame = grid_frame(db, zone_id, [f"{p}_mean", f"{p}_confidence"], first, until)
        for ts, row in frame.iterrows():
            value, conf = row[f"{p}_mean"], row[f"{p}_confidence"]
            conf = 0.0 if conf is None or math.isnan(conf) else float(conf)
            if value is None or math.isnan(value) or conf < rule["min_confidence"]:
                continue  # missing / low-confidence data: hold state
            value = float(value)
            episode = alert_repo.open_episode(db, zone_id, p, rule["id"])
            if _breached(value, rule):
                consecutive += 1
                normal_streak = 0
                if episode is not None:
                    windows = episode["breach_windows"] + 1
                    reason = (f"{PARAMETERS[p].label} zone mean {value:.2f} {unit} is still beyond the "
                              f"{rule['threshold_value']:g} {unit} threshold ({rule['direction']}). Episode open since "
                              f"{episode['first_breach_at']:%Y-%m-%d %H:%M} UTC with {windows} breach windows; the "
                              f"persistence rule ({rule['persistence_windows']} consecutive windows) was met when the "
                              f"alert opened.")
                    alert_repo.update_alert(db, episode["id"], value, reason, _context(db, zone_id, p, ts), windows, ts,
                                            rule["direction"])
                    alert_repo.log_event(db, episode["id"], "updated",
                                         f"Breach continues: {value:.2f} {unit} ({windows} breach windows in episode).",
                                         value, ts)
                    stats["updated"] += 1
                    continue
                if consecutive < rule["persistence_windows"]:
                    continue  # transient breach: persistence not met yet
                reason = _reason(rule, value, consecutive, conf)
                alert_id = alert_repo.create_alert(db, {
                    "zone_id": zone_id, "parameter": p, "threshold_id": rule["id"], "value": value,
                    "threshold": rule["threshold_value"], "unit": unit, "direction": rule["direction"],
                    "reason": reason, "source_context": _context(db, zone_id, p, ts), "severity": rule["severity"],
                    "action_text": rule["action_text"], "breach_windows": consecutive,
                    "first_breach_at": ts - (consecutive - 1) * d, "last_breach_at": ts})
                alert_repo.log_event(db, alert_id, "created", reason, value, ts)
                alert_repo.log_event(db, alert_id, "notification_dispatched",
                                     "In-app notification dispatched to the dashboard alert channel.", value, ts)
                rcache.bump_data_version({"type": "alert_created", "alert_id": alert_id, "zone_id": zone_id})
                log(logger, logging.WARNING, "alert created", alert_id=alert_id, zone=zone_id, parameter=p,
                    value=round(value, 2), threshold=rule["threshold_value"])
                stats["created"] += 1
            else:
                consecutive = 0
                if episode is None:
                    normal_streak = 0
                    continue
                if not _clearly_normal(value, rule, margin):
                    normal_streak = 0  # inside the deadband: hold the episode open
                    alert_repo.log_event(db, episode["id"], "recovery_pending",
                                         f"{value:.2f} {unit} is within limits but inside the {margin:g}% recovery "
                                         f"deadband; episode held open.", value, ts)
                    continue
                normal_streak += 1
                if normal_streak < clear_after:
                    alert_repo.log_event(db, episode["id"], "recovery_pending",
                                         f"Within limits ({value:.2f} {unit}); {normal_streak}/{clear_after} normal "
                                         f"windows needed to close the episode.", value, ts)
                    continue
                status = alert_repo.close_episode(db, episode["id"], ts)
                alert_repo.log_event(db, episode["id"], "resolved",
                                     f"Within limits for {normal_streak} consecutive windows ({value:.2f} {unit}); "
                                     f"episode closed with status '{status}'.", value, ts)
                log(logger, logging.INFO, "alert episode closed", alert_id=episode["id"], status=status)
                stats["resolved"] += 1
                normal_streak = 0
        arepo.set_state(db, key, {"last_evaluated": until.isoformat(), "consecutive": consecutive,
                                  "normal_streak": normal_streak})
    return stats


def threshold_status(db: Session, zone_id: str) -> list[dict]:
    """Current 'threshold decision' per rule — what the engine sees right now, for the UI."""
    out = []
    for rule in alert_repo.thresholds_for_zone(db, zone_id):
        p = rule["parameter"]
        sp = PARAMETERS[p]
        latest = arepo.latest_feature_time(db, zone_id, f"{p}_mean")
        state = arepo.get_state(db, f"alerts:{zone_id}:{rule['id']}") or {}
        episode = alert_repo.open_episode(db, zone_id, p, rule["id"])
        vals = arepo.latest_features(db, zone_id, [f"{p}_mean", f"{p}_confidence"], latest) if latest else {}
        value = vals.get(f"{p}_mean", {}).get("value")
        conf = vals.get(f"{p}_confidence", {}).get("value")
        consecutive = int(state.get("consecutive", 0))
        if value is None:
            decision = "insufficient_data"
        elif episode:
            decision = "alert_open"
        elif consecutive > 0:
            decision = "pending_persistence"
        else:
            decision = "within_limits"
        out.append({"threshold_id": rule["id"], "parameter": p, "label": sp.label, "unit": sp.unit,
                    "threshold": rule["threshold_value"], "direction": rule["direction"],
                    "persistence_windows": rule["persistence_windows"], "min_confidence": rule["min_confidence"],
                    "severity": rule["severity"], "basis": rule["basis"], "current_value": value,
                    "confidence": conf, "consecutive_breach_windows": consecutive, "evaluated_at": latest,
                    "decision": decision, "open_alert_id": episode["id"] if episode else None})
    return out
