import json

import frappe
from frappe.utils import flt

AVAILABLE = "Available"
PARTIAL = "Partial"
NOT_AVAILABLE = "Not Available"


def _get_stock_map(item_codes, company=None):
    """Return {item_code: {"available": qty, "warehouses": [...]}} from Bin."""
    item_codes = list({code for code in item_codes if code})
    if not item_codes:
        return {}

    bins = frappe.get_all(
        "Bin",
        filters={"item_code": ["in", item_codes]},
        fields=["item_code", "warehouse", "actual_qty", "reserved_qty", "projected_qty"],
    )

    warehouse_names = list({b.warehouse for b in bins})
    warehouses = {}
    if warehouse_names:
        warehouses = {
            w.name: w
            for w in frappe.get_all(
                "Warehouse",
                filters={"name": ["in", warehouse_names]},
                fields=["name", "company", "disabled", "count_in_dish_availability"],
            )
        }

    stock = {code: {"available": 0.0, "warehouses": []} for code in item_codes}

    for b in bins:
        wh = warehouses.get(b.warehouse)
        if not wh or (company and wh.company != company):
            continue
        if flt(b.actual_qty) == 0 and flt(b.reserved_qty) == 0:
            continue

        counts = bool(wh.count_in_dish_availability) and not wh.disabled
        stock[b.item_code]["warehouses"].append({
            "warehouse": b.warehouse,
            "actual_qty": flt(b.actual_qty),
            "reserved_qty": flt(b.reserved_qty),
            "projected_qty": flt(b.projected_qty),
            "counts": counts,
        })
        if counts:
            stock[b.item_code]["available"] += flt(b.actual_qty)

    for data in stock.values():
        data["available"] = max(data["available"], 0)

    return stock


def _row_status(available_for_row, required):
    if available_for_row <= 0:
        return NOT_AVAILABLE
    if required <= 0 or available_for_row >= required:
        return AVAILABLE
    return PARTIAL


def _overall_status(statuses):
    statuses = [s for s in statuses if s]
    if not statuses:
        return ""
    if all(s == AVAILABLE for s in statuses):
        return AVAILABLE
    if all(s == NOT_AVAILABLE for s in statuses):
        return NOT_AVAILABLE
    return PARTIAL


def _calculate(items, company=None):
    """items: list of objects/dicts with name, item_code, qty."""
    items = [frappe._dict(i) for i in items if i.get("item_code")]
    stock = _get_stock_map([i.item_code for i in items], company)

    remaining = {code: data["available"] for code, data in stock.items()}
    results = []

    for row in items:
        data = stock.get(row.item_code, {"available": 0.0, "warehouses": []})
        required = flt(row.qty)
        free_for_row = max(remaining.get(row.item_code, 0), 0)
        status = _row_status(free_for_row, required)
        remaining[row.item_code] = free_for_row - required

        results.append({
            "name": row.name,
            "item_code": row.item_code,
            "qty": required,
            "available_qty": data["available"],
            "stock_status": status,
            "warehouses": data["warehouses"],
        })

    return {
        "items": results,
        "status": _overall_status([r["stock_status"] for r in results]),
    }


def set_stock_fields(doc, method=None):
    """Called from Dish.validate, so drafts store current stock on save."""
    result = _calculate([r.as_dict() for r in doc.items], doc.company)
    by_name = {r["name"]: r for r in result["items"]}

    for row in doc.items:
        res = by_name.get(row.name)
        row.available_qty = res["available_qty"] if res else 0
        row.stock_status = res["stock_status"] if res else ""
    doc.stock_status = result["status"]


@frappe.whitelist()
def get_stock_for_items(items, company=None):
    """Live check for unsaved or edited Dishes. Reads only, writes nothing."""
    frappe.has_permission("Dish", "read", throw=True)
    if isinstance(items, str):
        items = json.loads(items)
    return _calculate(items, company)


@frappe.whitelist()
def refresh_dish_stock(dish):
    """Recalculate for a saved/submitted Dish and store it silently."""
    doc = frappe.get_doc("Dish", dish)
    doc.check_permission("read")

    result = _calculate([r.as_dict() for r in doc.items], doc.company)
    by_name = {r["name"]: r for r in result["items"]}

    for row in doc.items:
        res = by_name.get(row.name)
        if not res:
            continue
        if (flt(row.available_qty) != res["available_qty"]
                or (row.stock_status or "") != res["stock_status"]):
            frappe.db.set_value(
                "Dish Item", row.name,
                {"available_qty": res["available_qty"], "stock_status": res["stock_status"]},
                update_modified=False,
            )

    if (doc.stock_status or "") != result["status"]:
        frappe.db.set_value("Dish", doc.name, "stock_status", result["status"], update_modified=False)

    return result