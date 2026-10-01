"""Operator actions: acknowledge, dismiss, confirm, tag a factory/event, report a sensor issue or note.
Feedback is persisted (future recalibration input). Acknowledge/dismiss change alert state but never
delete history; every action is written to the alert log."""
import logging

from sqlalchemy.orm import Session

from app.core import redis as rcache
from app.core.logging import log
from app.core.timeutil import utcnow
from app.repositories import alerts as alert_repo
from app.repositories import analytics as arepo
from app.repositories import factories as factory_repo
from app.repositories import feedback as feedback_repo
from app.repositories import zones as zone_repo

logger = logging.getLogger("enviropulse.feedback")
FEEDBACK_TYPES = {"confirm", "dismiss", "false_positive", "tag_factory", "tag_event", "sensor_issue", "note"}


class FeedbackError(ValueError):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def acknowledge_alert(db: Session, alert_id: int, operator: str, note: str | None) -> dict:
    alert = alert_repo.get_alert(db, alert_id)
    if alert is None:
        raise FeedbackError(f"Alert {alert_id} not found.", 404)
    if alert["status"] != "active":
        raise FeedbackError(f"Alert {alert_id} is '{alert['status']}'; only active alerts can be acknowledged.", 409)
    alert_repo.acknowledge(db, alert_id, operator, utcnow())
    alert_repo.log_event(db, alert_id, "acknowledged", f"Acknowledged by {operator}." + (f" Note: {note}" if note else ""))
    if note:
        feedback_repo.insert_feedback(db, {"zone_id": alert["zone_id"], "alert_id": alert_id, "anomaly_id": None,
                                           "feedback_type": "note", "feedback_text": note, "contributor_type": None,
                                           "contributor_id": None, "operator": operator})
    rcache.bump_data_version({"type": "alert_acknowledged", "alert_id": alert_id})
    log(logger, logging.INFO, "alert acknowledged", alert_id=alert_id, operator=operator)
    return alert_repo.get_alert(db, alert_id)


def submit_feedback(db: Session, f: dict) -> dict:
    if f["feedback_type"] not in FEEDBACK_TYPES:
        raise FeedbackError(f"Unknown feedback_type '{f['feedback_type']}'.")
    if not zone_repo.zone_exists(db, f["zone_id"]):
        raise FeedbackError(f"Zone '{f['zone_id']}' not found.", 404)
    alert = None
    if f.get("alert_id") is not None:
        alert = alert_repo.get_alert(db, f["alert_id"])
        if alert is None or alert["zone_id"] != f["zone_id"]:
            raise FeedbackError("alert_id does not exist in this zone.", 404)
    if f.get("anomaly_id") is not None:
        anomaly = arepo.get_anomaly(db, f["anomaly_id"])
        if anomaly is None or anomaly["zone_id"] != f["zone_id"]:
            raise FeedbackError("anomaly_id does not exist in this zone.", 404)
    if f["feedback_type"] in ("dismiss", "false_positive") and alert is None and f.get("anomaly_id") is None:
        raise FeedbackError(f"'{f['feedback_type']}' requires an alert_id or anomaly_id.")
    if f["feedback_type"] == "tag_factory":
        if not f.get("contributor_id") or f["contributor_id"] not in {x["id"] for x in
                                                                      factory_repo.zone_factories(db, f["zone_id"])}:
            raise FeedbackError("tag_factory requires contributor_id of a factory in this zone.")
        f["contributor_type"] = "factory"
    if f["feedback_type"] == "tag_event":
        if not f.get("contributor_id"):
            raise FeedbackError("tag_event requires contributor_id (event id).")
        f["contributor_type"] = "event"
    record = feedback_repo.insert_feedback(db, {
        "zone_id": f["zone_id"], "alert_id": f.get("alert_id"), "anomaly_id": f.get("anomaly_id"),
        "feedback_type": f["feedback_type"], "feedback_text": f.get("feedback_text"),
        "contributor_type": f.get("contributor_type"), "contributor_id": f.get("contributor_id"),
        "operator": f.get("operator") or "operator"})
    if alert is not None:
        if f["feedback_type"] in ("dismiss", "false_positive") and alert_repo.dismiss(db, alert["id"]):
            alert_repo.log_event(db, alert["id"], "dismissed",
                                 f"Dismissed by {record['operator']} ({f['feedback_type']}). The episode stays tracked "
                                 "so no duplicate alert opens until values return to normal.")
        else:
            alert_repo.log_event(db, alert["id"], f"feedback_{f['feedback_type']}",
                                 f"Operator feedback ({f['feedback_type']}): {f.get('feedback_text') or '—'}")
    rcache.bump_data_version({"type": "feedback", "feedback_id": record["id"]})
    log(logger, logging.INFO, "feedback stored", feedback_id=record["id"], type=f["feedback_type"], zone=f["zone_id"])
    return record
