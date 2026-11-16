import json

import frappe
from frappe import _
from frappe.utils import flt

from enertechv1.enertechv1.api.stores import (
    QC_HOLD,
    RETURNS,
    _q,
    _stock_uom,
    is_exhibition_dish,
    update_dish_stores_status,
)


# ============================================================
# Helpers
# ============================================================

def _returnable_rows(dish):
    """Outward Delivery Note rows of this Dish with the qty still out (oldest first)."""
    dns = frappe.get_all(
        "Delivery Note",
        filters={"custom_dish": dish, "docstatus": 1, "is_return": 0},
        pluck="name",
        order_by="posting_date asc, creation asc",
    )
    if not dns:
        return []

    rows = frappe.get_all(
        "Delivery Note Item",
        filters={"parent": ["in", dns]},
        fields=["name", "parent", "item_code", "qty", "returned_qty", "conversion_factor"],
    )
    order = {name: idx for idx, name in enumerate(dns)}
    rows.sort(key=lambda r: order[r.parent])

    for r in rows:
        factor = flt(r.conversion_factor) or 1
        r.returnable = max(flt(r.qty) - flt(r.returned_qty), 0) * factor
    return [r for r in rows if r.returnable > 0]


# ============================================================
# Dish: Mark Returned
# ============================================================

@frappe.whitelist()
def make_exhibition_return(dish, items, remarks=None):
    """Stores: create submitted Sales Return(s) for units back from an exhibition.
    Stock comes into the Returns warehouse; the on_submit hook moves it to QC Hold."""
    from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_return

    frappe.only_for(["Stores Person", "System Manager"])

    doc = frappe.get_doc("Dish", dish)
    doc.check_permission("read")
    if doc.docstatus != 1:
        frappe.throw(_("Dish {0} must be Approved.").format(dish))
    if not is_exhibition_dish(doc):
        frappe.throw(_("Dish {0} is not for an exhibition customer.").format(dish))

    if isinstance(items, str):
        items = json.loads(items)
    wanted = {}
    for i in items or []:
        qty = flt(i.get("qty"))
        if qty > 0:
            wanted[i["item_code"]] = wanted.get(i["item_code"], 0) + qty
    if not wanted:
        frappe.throw(_("Enter a returned quantity for at least one item."))

    rows = _returnable_rows(dish)
    for item_code, qty in wanted.items():
        out = sum(r.returnable for r in rows if r.item_code == item_code)
        if qty > out + 0.0001:
            frappe.throw(_("{0}: only {1} unit(s) are at the exhibition, but {2} were entered.").format(
                item_code, _q(out), _q(qty)))

    created = []
    for dn_name in dict.fromkeys(r.parent for r in rows):
        take_by_row = {}
        for r in rows:
            if r.parent != dn_name or wanted.get(r.item_code, 0) <= 0:
                continue
            take = min(wanted[r.item_code], r.returnable)
            if take > 0:
                take_by_row[r.name] = take
                wanted[r.item_code] -= take
        if not take_by_row:
            continue

        ret = make_sales_return(dn_name)
        kept = []
        for row in ret.items:
            take = take_by_row.get(row.dn_detail)
            if not take:
                continue
            factor = flt(row.conversion_factor) or 1
            row.qty = -(take / factor)
            row.stock_qty = -take
            row.warehouse = RETURNS
            kept.append(row)
        if not kept:
            continue

        ret.set("items", kept)
        for idx, row in enumerate(ret.items, 1):
            row.idx = idx
        ret.set_warehouse = RETURNS
        ret.custom_dish = dish
        ret.run_method("calculate_taxes_and_totals")

        ret.flags.ignore_permissions = True
        ret.insert()
        ret.submit()
        ret.add_comment("Info", _("Exhibition return for Dish {0}").format(dish))
        if remarks:
            ret.add_comment("Comment", remarks)
        created.append(ret.name)

    if not created:
        frappe.throw(_("Nothing could be returned. Check the Delivery Notes of this Dish."))

    update_dish_stores_status(dish)
    return created


# ============================================================
# Document event hooks (wired in hooks.py)
# ============================================================

def on_return_submit(doc, method=None):
    """A Dish Sales Return into Returns → move it to QC Hold (this creates the inspection)."""
    dish = doc.get("custom_dish")
    if not dish or not doc.get("is_return"):
        return

    rows = [r for r in doc.items if r.warehouse == RETURNS and flt(r.stock_qty) < 0]
    if not rows:
        return

    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Transfer"
    se.purpose = "Material Transfer"
    se.company = doc.company
    se.custom_dish = dish
    se.custom_return_delivery_note = doc.name
    se.from_warehouse = RETURNS
    se.to_warehouse = QC_HOLD

    for r in rows:
        se.append("items", {
            "item_code": r.item_code,
            "qty": abs(flt(r.stock_qty)),
            "uom": _stock_uom(r.item_code),
            "conversion_factor": 1,
            "s_warehouse": RETURNS,
            "t_warehouse": QC_HOLD,
        })

    se.flags.ignore_permissions = True
    se.insert()
    se.submit()
    se.add_comment("Info", _("Auto-created from exhibition return {0}").format(doc.name))


def on_return_before_cancel(doc, method=None):
    """Reverse the Returns → QC Hold move before the Sales Return is cancelled."""
    if not doc.get("is_return") or not doc.get("custom_dish"):
        return
    for name in frappe.get_all(
        "Stock Entry",
        filters={"custom_return_delivery_note": doc.name, "docstatus": 1},
        pluck="name",
    ):
        se = frappe.get_doc("Stock Entry", name)
        se.flags.ignore_permissions = True
        se.cancel()