"""A learner's consent, profile, own data and account deletion."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.auth.principal import Principal
from app.config import settings
from app.errors import ApiError
from app.repo import auth as auth_repo
from app.repo import consent as consent_repo
from app.repo import learners as learner_repo


# ---- consent ---------------------------------------------------------------------------------

def consent_text() -> dict:
    cfg = settings()["consent"]
    return {"version": cfg["version"], "service_text_vi": cfg["service_text_vi"],
            "research_text_vi": cfg["research_text_vi"]}


def consent_status(conn, learner_id: int) -> dict:
    service = consent_repo.active(conn, learner_id, "service")
    research = consent_repo.active(conn, learner_id, "research")
    return {"version": service["version"] if service else None,
            "service_given_at": service["given_at"] if service else None,
            "research_given_at": research["given_at"] if research else None}


def give_consent(conn, learner_id: int, version: str, service: bool, research: bool, now: datetime) -> dict:
    """Record the service consent (required) and set the research consent (optional) as asked."""
    current = settings()["consent"]["version"]
    if version != current:
        raise ApiError(409, "consent_version_outdated", "Nội dung đồng ý đã thay đổi. Vui lòng đọc lại.")
    if not service:
        raise ApiError(422, "service_consent_required", "Cần đồng ý với điều khoản dịch vụ để sử dụng ứng dụng.")
    if not consent_repo.has_current_service_consent(conn, learner_id, current):
        consent_repo.withdraw(conn, learner_id, "service", now)   # an older version, if any, is superseded
        consent_repo.give(conn, learner_id, "service", current, now)
    # Research consent follows the version too: consent to an older text is not consent to this one.
    active_research = consent_repo.active(conn, learner_id, "research")
    if active_research and (not research or active_research["version"] != current):
        consent_repo.withdraw(conn, learner_id, "research", now)
        active_research = None
    if research and active_research is None:
        consent_repo.give(conn, learner_id, "research", current, now)
    return consent_status(conn, learner_id)


def withdraw_consent(conn, learner_id: int, kind: str, now: datetime) -> dict:
    consent_repo.withdraw(conn, learner_id, kind, now)
    return consent_status(conn, learner_id)


# ---- profile ---------------------------------------------------------------------------------

def local_date(now: datetime) -> date:
    """The learner's calendar day at that instant (config local_timezone)."""
    return now.astimezone(ZoneInfo(settings()["local_timezone"])).date()


def get_me(conn, learner_id: int) -> dict:
    row = learner_repo.profile(conn, learner_id)
    return {
        "pseudonym_id": row["pseudonym_id"], "display_name": row["display_name"], "audience": row["audience"],
        "organisation": row["organisation"], "focus_module_ids": row["focus_module_ids"],
        "exam_date": row["exam_date"], "target_retention": row["target_retention"],
        "new_cards_per_day": row["new_cards_per_day"], "max_reviews_per_day": row["max_reviews_per_day"],
        "diagnostic_prompt_dismissed": row["diagnostic_prompt_dismissed"],
        "consent": consent_status(conn, learner_id),
    }


def patch_me(conn, learner_id: int, changes: dict, today: date) -> dict:
    """Apply the fields the learner sent. Everything is checked before anything is written; a field
    sent as null is left as it is."""
    changes = {k: v for k, v in changes.items() if v is not None}
    if "focus_module_ids" in changes:
        ids = changes["focus_module_ids"]
        unknown = learner_repo.unknown_modules(conn, ids)
        if not ids or unknown:
            raise ApiError(422, "unknown_module", "Học phần không tồn tại.", {"unknown": unknown})
    if "exam_date" in changes and changes["exam_date"] < today:
        raise ApiError(422, "invalid_exam_date", "Ngày thi không thể ở quá khứ.")
    if "display_name" in changes:
        changes["display_name"] = changes["display_name"].strip()
        if not changes["display_name"]:
            raise ApiError(422, "invalid_request", "Tên hiển thị không được để trống.")
        learner_repo.set_display_name(conn, learner_id, changes["display_name"])
    learner_repo.update_settings(conn, learner_id, changes)
    return get_me(conn, learner_id)


def export_data(conn, learner_id: int, now: datetime) -> dict:
    profile = get_me(conn, learner_id)
    return {"exported_at": now, "profile": profile,
            **learner_repo.export_rows(conn, learner_id, profile["pseudonym_id"])}


# ---- deletion --------------------------------------------------------------------------------

DELETION_MODES = ("erase", "keep_pseudonymous")


def delete_account(conn, principal: Principal, now: datetime) -> dict:
    """Close the learner's account, at once and in one transaction.

    The tokens go first, so nothing signed in survives. Then, by config: `erase` removes the learner
    and all their records; `keep_pseudonymous` removes the identity and keeps the records under the
    pseudonym. The activity log is kept in both, as pseudonymous records.
    """
    mode = settings()["account_deletion"]["learning_records"]
    if mode not in DELETION_MODES:
        raise RuntimeError(f"account_deletion.learning_records must be one of {', '.join(DELETION_MODES)}; got {mode!r}")
    request_id = learner_repo.record_deletion_request(conn, principal.pseudonym_id, now)
    auth_repo.delete_subject_tokens(conn, "learner", principal.subject_id)
    if mode == "erase":
        learner_repo.erase(conn, principal.subject_id, principal.pseudonym_id)
    else:
        learner_repo.close_keeping_records(conn, principal.subject_id)
    learner_repo.complete_deletion_request(conn, request_id, now)
    return {"requested_at": now}
