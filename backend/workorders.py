"""Repair work orders: assign -> start -> complete. Completing a work order records the repair.

One open work order per asset at a time. Each asset type has a target number of days to fix;
an open work order past its target date is overdue.
"""
from datetime import date, timedelta

from db import now, one, rows

# target days to fix, by asset type (simulated service levels for the demo)
TARGET_DAYS = {"drain": 3, "streetlight": 2, "toilet": 2, "road": 7, "footpath": 10}
OPEN = ("assigned", "in_progress")


class WorkOrderError(ValueError):
    pass


def default_due(asset_type: str, start=None) -> str:
    start = start or now().date()
    return (start + timedelta(days=TARGET_DAYS.get(asset_type, 7))).isoformat()


def decorate(wo):
    """Add plain-language status and overdue information."""
    if not wo:
        return None
    today = now().date()
    due = date.fromisoformat(wo["due_date"]) if wo.get("due_date") else None
    wo["overdue"] = bool(due and wo["status"] in OPEN and due < today)
    wo["days_overdue"] = (today - due).days if wo["overdue"] else 0
    wo["days_left"] = (due - today).days if due and wo["status"] in OPEN and not wo["overdue"] else None
    wo["status_label"] = {"assigned": "Repair assigned", "in_progress": "Work started",
                          "completed": "Fixed", "cancelled": "Cancelled"}.get(wo["status"], wo["status"])
    return wo


def open_for(conn, asset_id):
    return decorate(one(conn, "SELECT * FROM work_orders WHERE asset_id=? AND status IN ('assigned','in_progress') "
                              "ORDER BY created_at DESC LIMIT 1", (asset_id,)))


def history(conn, asset_id):
    return [decorate(w) for w in rows(conn, "SELECT * FROM work_orders WHERE asset_id=? ORDER BY created_at DESC", (asset_id,))]


def assign(conn, asset, contractor, repair_type, due_date, notes, by):
    if repair_type not in ("temporary", "permanent"):
        raise WorkOrderError("Repair type must be temporary or permanent.")
    if not (contractor or "").strip():
        raise WorkOrderError("Choose a contractor.")
    if open_for(conn, asset["asset_id"]):
        raise WorkOrderError("This asset already has an open work order. Complete it first.")
    due = due_date or default_due(asset["type"])
    try:
        if date.fromisoformat(due) < now().date():
            raise WorkOrderError("The target date cannot be in the past.")
    except ValueError as e:
        if isinstance(e, WorkOrderError):
            raise
        raise WorkOrderError("Target date must look like 2026-11-05.")
    cur = conn.execute(
        "INSERT INTO work_orders (asset_id,status,contractor,repair_type,due_date,notes,created_by,created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (asset["asset_id"], "assigned", contractor.strip(), repair_type, due, (notes or "").strip(), by, now().isoformat()),
    )
    conn.commit()
    return cur.lastrowid


def _get_open(conn, wo_id):
    wo = one(conn, "SELECT * FROM work_orders WHERE id=?", (wo_id,))
    if not wo:
        raise LookupError("work order not found")
    if wo["status"] not in OPEN:
        raise WorkOrderError(f"This work order is already {wo['status'].replace('_', ' ')}.")
    return wo


def start(conn, wo_id):
    wo = _get_open(conn, wo_id)
    if wo["status"] == "in_progress":
        raise WorkOrderError("Work has already started.")
    conn.execute("UPDATE work_orders SET status='in_progress', started_at=? WHERE id=?", (now().isoformat(), wo_id))
    conn.commit()


def complete(conn, wo_id, cost, notes, after_photo_url):
    wo = _get_open(conn, wo_id)
    if cost is None or cost < 0:
        raise WorkOrderError("Enter the actual cost (0 or more).")
    t = now().isoformat()
    cur = conn.execute(
        "INSERT INTO repairs (asset_id,repair_type,cost,completed_at,contractor,notes,after_photo_url,work_order_id) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (wo["asset_id"], wo["repair_type"], cost, t, wo["contractor"], (notes or wo["notes"] or "").strip(), after_photo_url, wo_id),
    )
    conn.execute("UPDATE work_orders SET status='completed', started_at=COALESCE(started_at, ?), completed_at=?, cost=?, "
                 "completion_notes=?, after_photo_url=?, repair_id=? WHERE id=?",
                 (t, t, cost, (notes or "").strip(), after_photo_url, cur.lastrowid, wo_id))
    conn.commit()
    return cur.lastrowid


def list_orders(conn, status="open"):
    sql = ("SELECT w.*, a.name AS asset_name, a.type AS asset_type FROM work_orders w JOIN assets a USING(asset_id) ")
    if status == "open":
        sql += "WHERE w.status IN ('assigned','in_progress') "
    elif status == "completed":
        sql += "WHERE w.status='completed' "
    sql += "ORDER BY w.due_date ASC, w.created_at DESC"
    out = [decorate(w) for w in rows(conn, sql)]
    out.sort(key=lambda w: (not w["overdue"], w["status"] not in OPEN, w["due_date"] or ""))
    return out
