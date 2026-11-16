import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

# Warehouses used by the Dish stores flow
QC_HOLD = "QC Hold - EUPL"
DISPATCH = "Dispatch - EUPL"
REJECTED = "Rejected - EUPL"
FINISHED_GOODS = "Finished Goods - EUPL"
RETURNS = "Returns - EUPL"

REQUESTED = "Requested"
IN_QC = "In QC"
READY = "Ready for Dispatch"
PARTLY_REJECTED = "Partly Rejected"
PARTLY_DELIVERED = "Partly Delivered"
DELIVERED = "Delivered"
AT_EXHIBITION = "At Exhibition"
PARTLY_RETURNED = "Partly Returned"
RETURNED = "Returned"


# ============================================================
# Helpers
# ============================================================

def _q(value):
    """Quantity as short text: 9.0 -> '9', 2.5 -> '2.5'."""
    return "%g" % flt(value)


def _stock_uom(item_code):
    return frappe.get_cached_value("Item", item_code, "stock_uom")


def _dish_required(dish_doc):
    required = {}
    for row in dish_doc.items:
        if not row.item_code:
            continue
        entry = required.setdefault(row.item_code, {"qty": 0.0, "item_name": row.item_name})
        entry["qty"] += flt(row.qty)
    return required


def _net_qty(dish):
    """Net qty per (item_code, warehouse) moved by submitted Stock Entries of this Dish."""
    rows = frappe.db.sql(
        """
        select sed.item_code, sed.s_warehouse, sed.t_warehouse, sed.transfer_qty
        from `tabStock Entry Detail` sed
        join `tabStock Entry` se on se.name = sed.parent
        where se.custom_dish = %s and se.docstatus = 1
        """,
        dish,
        as_dict=True,
    )
    net = {}
    for r in rows:
        qty = flt(r.transfer_qty)
        if r.t_warehouse:
            net[(r.item_code, r.t_warehouse)] = net.get((r.item_code, r.t_warehouse), 0) + qty
        if r.s_warehouse:
            net[(r.item_code, r.s_warehouse)] = net.get((r.item_code, r.s_warehouse), 0) - qty
    return net


def _qc_inbound_qty(dish):
    """Total qty ever moved INTO QC Hold for this Dish."""
    return flt(frappe.db.sql(
        """
        select sum(sed.transfer_qty)
        from `tabStock Entry Detail` sed
        join `tabStock Entry` se on se.name = sed.parent
        where se.custom_dish = %s and se.docstatus = 1
            and sed.t_warehouse = %s and ifnull(sed.s_warehouse, '') != %s
        """,
        (dish, QC_HOLD, QC_HOLD),
    )[0][0])


def _pending_requested(dish):
    rows = frappe.db.sql(
        """
        select mri.item_code, sum(greatest(mri.stock_qty - ifnull(mri.ordered_qty, 0), 0)) as qty
        from `tabMaterial Request Item` mri
        join `tabMaterial Request` mr on mr.name = mri.parent
        where mr.custom_dish = %s
            and mr.docstatus < 2
            and ifnull(mr.status, '') not in ('Stopped', 'Cancelled')
        group by mri.item_code
        """,
        dish,
        as_dict=True,
    )
    return {r.item_code: flt(r.qty) for r in rows}


def _delivered_qty(dish):
    """Qty delivered per item by submitted OUTWARD Delivery Notes of this Dish."""
    rows = frappe.db.sql(
        """
        select dni.item_code, sum(dni.stock_qty) as qty
        from `tabDelivery Note Item` dni
        join `tabDelivery Note` dn on dn.name = dni.parent
        where dn.custom_dish = %s and dn.docstatus = 1 and dn.is_return = 0
        group by dni.item_code
        """,
        dish,
        as_dict=True,
    )
    return {r.item_code: flt(r.qty) for r in rows}


def _returned_qty(dish):
    """Qty returned per item by submitted Sales Returns of this Dish (positive numbers)."""
    rows = frappe.db.sql(
        """
        select dni.item_code, sum(-dni.stock_qty) as qty
        from `tabDelivery Note Item` dni
        join `tabDelivery Note` dn on dn.name = dni.parent
        where dn.custom_dish = %s and dn.docstatus = 1 and dn.is_return = 1
        group by dni.item_code
        """,
        dish,
        as_dict=True,
    )
    return {r.item_code: flt(r.qty) for r in rows}


def is_exhibition_dish(dish_doc):
    """True if the Dish's customer belongs to a Customer Group marked 'Is Exhibition'."""
    customer = dish_doc.get("customer")
    if not customer:
        return False
    group = frappe.db.get_value("Customer", customer, "customer_group")
    return bool(group and frappe.db.get_value("Customer Group", group, "custom_is_exhibition"))


def _linked_docs(dish):
    return {
        "material_requests": frappe.get_all(
            "Material Request",
            filters={"custom_dish": dish},
            fields=["name", "status", "docstatus"],
            order_by="creation asc",
        ),
        "stock_entries": frappe.get_all(
            "Stock Entry",
            filters={"custom_dish": dish},
            fields=["name", "docstatus", "from_warehouse", "to_warehouse", "posting_date"],
            order_by="creation asc",
        ),
        "quality_inspections": frappe.get_all(
            "Quality Inspection",
            filters={"custom_dish": dish},
            fields=["name", "status", "docstatus", "item_code", "reference_name",
                    "custom_accepted_qty", "custom_rejected_qty"],
            order_by="creation asc",
        ),
        "delivery_notes": frappe.get_all(
            "Delivery Note",
            filters={"custom_dish": dish},
            fields=["name", "status", "docstatus", "posting_date"],
            order_by="creation asc",
        ),
    }


def _compute_status(items, has_open_mr, is_exhibition=False):
    if not items:
        return ""
    if is_exhibition and any(i["delivered"] > 0 for i in items):
        if all(i["returned"] >= i["delivered"] for i in items):
            return RETURNED
        if any(i["returned"] > 0 for i in items):
            return PARTLY_RETURNED
        return AT_EXHIBITION
    if all(i["delivered"] >= i["required"] for i in items):
        return DELIVERED
    if any(i["delivered"] > 0 for i in items):
        return PARTLY_DELIVERED
    if all(i["in_dispatch"] + i["delivered"] >= i["required"] for i in items):
        return READY
    if any(i["in_qc"] > 0 for i in items):
        return IN_QC
    if any(i["rejected"] > 0 for i in items):
        return PARTLY_REJECTED
    if has_open_mr or any(i["requested"] > 0 for i in items):
        return REQUESTED
    return ""

def _stages(items, links, qc_in_qty):
    """The six steps shown in the Stores Progress tracker on the Dish."""
    required = sum(i["required"] for i in items)
    in_dispatch = sum(i["in_dispatch"] for i in items)
    delivered = sum(i["delivered"] for i in items)
    reached_dispatch = in_dispatch + delivered

    mrs = [m for m in links["material_requests"] if m.docstatus == 1]
    qis = [q for q in links["quality_inspections"] if q.docstatus < 2]
    qi_pending = [q for q in qis if q.docstatus == 0]
    qi_done = [q for q in qis if q.docstatus == 1]
    accepted = sum(flt(q.get("custom_accepted_qty")) for q in qi_done)
    rejected = sum(flt(q.get("custom_rejected_qty")) for q in qi_done)
    dns = [d for d in links["delivery_notes"] if d.docstatus == 1]

    def docs(rows, doctype):
        return [{"doctype": doctype, "name": r.name} for r in rows]

    stages = [
        {
            "key": "requested",
            "label": _("Request sent to Stores"),
            "done": bool(mrs),
            "partial": False,
            "detail": _("{0} request(s) sent").format(len(mrs)) if mrs else _("Not requested yet"),
            "next": _("Sales: click Request from Stores"),
            "docs": docs(mrs, "Material Request"),
        },
        {
            "key": "moved_qc",
            "label": _("Moved to Quality Control"),
            "done": qc_in_qty > 0,
            "partial": False,
            "detail": _("{0} unit(s) moved to QC Hold").format(_q(qc_in_qty)) if qc_in_qty else "",
            "next": _("Stores: click Move to Quality Control on the request"),
            "docs": [],
        },
        {
            "key": "inspection_created",
            "label": _("Sent for inspection"),
            "done": bool(qis),
            "partial": False,
            "detail": _("{0} inspection(s), {1} pending").format(len(qis), len(qi_pending)) if qis else "",
            "next": _("Created automatically when stock enters QC Hold"),
            "docs": docs(qi_pending, "Quality Inspection"),
        },
        {
            "key": "inspection_done",
            "label": _("Inspection done"),
            "done": bool(qi_done) and not qi_pending,
            "partial": bool(qi_done) and bool(qi_pending),
            "warning": rejected > 0,
            "detail": (
                _("Accepted {0} · Rejected {1}").format(_q(accepted), _q(rejected))
                + (" — " + _("request replacements from Stores") if rejected > 0 else "")
            ) if qi_done else "",
            "next": _("QC: enter Accepted / Rejected qty and submit the inspection"),
            "docs": docs(qi_done, "Quality Inspection"),
        },
        {
            "key": "dispatch",
            "label": _("Ready in Dispatch"),
            "done": required > 0 and reached_dispatch >= required,
            "partial": 0 < reached_dispatch < required,
            "detail": _("{0} of {1} unit(s)").format(_q(reached_dispatch), _q(required)) if reached_dispatch else "",
            "next": _("Happens automatically when QC accepts units"),
            "docs": [],
        },
        {
            "key": "delivered",
            "label": _("Delivered"),
            "done": required > 0 and delivered >= required,
            "partial": 0 < delivered < required,
            "detail": _("{0} of {1} unit(s) delivered").format(_q(delivered), _q(required)) if delivered else "",
            "next": _("Dispatch: click Create Delivery Note"),
            "docs": docs(dns, "Delivery Note"),
        },
    ]

    current_set = False
    for s in stages:
        if s["done"]:
            s["state"] = "done"
        elif s["partial"] or not current_set:
            s["state"] = "current"
            current_set = True
        else:
            s["state"] = "pending"
    return stages


def _build_summary(dish_doc):
    required = _dish_required(dish_doc)
    net = _net_qty(dish_doc.name)
    pending = _pending_requested(dish_doc.name)
    delivered = _delivered_qty(dish_doc.name)
    returned = _returned_qty(dish_doc.name)
    exhibition = is_exhibition_dish(dish_doc)

    items = []
    for item_code, info in required.items():
        done = max(flt(delivered.get(item_code)), 0)
        back = max(flt(returned.get(item_code)), 0)
        in_qc = max(flt(net.get((item_code, QC_HOLD))), 0)
        in_dispatch = max(flt(net.get((item_code, DISPATCH))) - done, 0)
        rejected = max(flt(net.get((item_code, REJECTED))), 0)
        requested = flt(pending.get(item_code))
        still_needed = max(info["qty"] - in_qc - in_dispatch - done - requested, 0)

        items.append({
            "item_code": item_code,
            "item_name": info["item_name"],
            "required": info["qty"],
            "requested": requested,
            "in_qc": in_qc,
            "in_dispatch": in_dispatch,
            "rejected": rejected,
            "delivered": done,
            "returned": back,
            "at_exhibition": max(done - back, 0) if exhibition else 0,
            "still_needed": still_needed,
        })

    links = _linked_docs(dish_doc.name)
    has_open_mr = any(
        m.docstatus < 2 and m.status not in ("Stopped", "Cancelled", "Transferred")
        for m in links["material_requests"]
    )

    return {
        "items": items,
        "links": links,
        "is_exhibition": exhibition,
        "status": _compute_status(items, has_open_mr, exhibition),
        "stages": _stages(items, links, _qc_inbound_qty(dish_doc.name)),
    }


def update_dish_stores_status(dish):
    if not dish or not frappe.db.exists("Dish", dish):
        return
    doc = frappe.get_doc("Dish", dish)
    status = _build_summary(doc)["status"]
    if (doc.get("stores_status") or "") != status:
        frappe.db.set_value("Dish", dish, "stores_status", status, update_modified=False)


def _free_warehouses(company):
    return frappe.get_all(
        "Warehouse",
        filters={"count_in_dish_availability": 1, "is_group": 0, "disabled": 0, "company": company},
        pluck="name",
    )


def _is_qc_inbound(se):
    """A Stock Entry of a Dish that moved stock INTO QC Hold."""
    return bool(se.get("custom_dish")) and any(
        row.t_warehouse == QC_HOLD and row.s_warehouse != QC_HOLD for row in se.items
    )


def _get_approved_dish(dish):
    doc = frappe.get_doc("Dish", dish)
    doc.check_permission("read")
    if doc.docstatus != 1:
        frappe.throw(_("Dish {0} must be Approved first.").format(dish))
    return doc


# ============================================================
# Dish form
# ============================================================

@frappe.whitelist()
def get_dish_stores_summary(dish):
    doc = frappe.get_doc("Dish", dish)
    doc.check_permission("read")
    summary = _build_summary(doc)
    if doc.docstatus == 1 and (doc.get("stores_status") or "") != summary["status"]:
        frappe.db.set_value("Dish", dish, "stores_status", summary["status"], update_modified=False)
    return summary


@frappe.whitelist()
def make_material_request(dish):
    frappe.only_for(["Sales User", "Sales Manager", "System Manager"])
    """Sales: Request from Stores → submitted Material Request (free warehouses → QC Hold)."""
    doc = _get_approved_dish(dish)
    frappe.has_permission("Material Request", "create", throw=True)

    summary = _build_summary(doc)
    free_whs = _free_warehouses(doc.company)
    if not free_whs:
        frappe.throw(_("No warehouse is marked 'Count in Dish Availability'."))

    schedule_date = max(getdate(doc.expected_delivery or nowdate()), getdate(nowdate()))

    mr = frappe.new_doc("Material Request")
    mr.material_request_type = "Material Transfer"
    mr.company = doc.company
    mr.transaction_date = nowdate()
    mr.schedule_date = schedule_date
    mr.set_warehouse = QC_HOLD
    mr.custom_dish = dish

    for it in summary["items"]:
        need = it["still_needed"]
        if need <= 0:
            continue

        bins = frappe.get_all(
            "Bin",
            filters={"item_code": it["item_code"], "warehouse": ["in", free_whs], "actual_qty": [">", 0]},
            fields=["warehouse", "actual_qty"],
            order_by="actual_qty desc",
        )
        uom = _stock_uom(it["item_code"])

        for b in bins:
            take = min(need, flt(b.actual_qty))
            if take <= 0:
                continue
            mr.append("items", {
                "item_code": it["item_code"],
                "qty": take,
                "uom": uom,
                "conversion_factor": 1,
                "from_warehouse": b.warehouse,
                "warehouse": QC_HOLD,
                "schedule_date": schedule_date,
            })
            need -= take
            if need <= 0:
                break

    if not mr.items:
        frappe.throw(_("Nothing to request: the items are already requested / pulled, or there is no free stock."))

    mr.insert()
    mr.submit()
    mr.add_comment("Info", _("Created from Dish {0}").format(dish))
    update_dish_stores_status(dish)
    return mr.name


@frappe.whitelist()
def make_delivery_note(dish):
    """Dispatch: draft Delivery Note from the Sales Order, only for units of this Dish in Dispatch."""
    from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note as so_to_dn

    doc = _get_approved_dish(dish)
    frappe.has_permission("Delivery Note", "create", throw=True)

    if not doc.sales_order:
        frappe.throw(_("Dish {0} is not linked to a Sales Order.").format(dish))
    
    so_status = frappe.db.get_value("Sales Order", doc.sales_order, ["docstatus", "status"], as_dict=True)
    if not so_status:
        frappe.throw(_("Sales Order {0} linked to Dish {1} does not exist.").format(doc.sales_order, dish))
    if so_status.docstatus == 0:
        frappe.throw(_("Sales Order {0} is still a Draft. Submit it before creating the Delivery Note.").format(doc.sales_order))
    if so_status.docstatus == 2:
        frappe.throw(_("Sales Order {0} is cancelled. Link this Dish to its amended Sales Order first.").format(doc.sales_order))
    if so_status.status in ("Closed", "On Hold"):
        frappe.throw(_("Sales Order {0} is {1}. Reopen or release it before creating the Delivery Note.").format(doc.sales_order, so_status.status))

    draft = frappe.db.get_value("Delivery Note", {"custom_dish": dish, "docstatus": 0}, "name")
    if draft:
        return draft

    summary = _build_summary(doc)
    ready = {i["item_code"]: i["in_dispatch"] for i in summary["items"] if i["in_dispatch"] > 0}
    if not ready:
        frappe.throw(_("No units of Dish {0} are in {1} yet.").format(dish, DISPATCH))

    dn = so_to_dn(doc.sales_order)

    kept = []
    for row in dn.items:
        left = flt(ready.get(row.item_code))
        if left <= 0:
            continue
        factor = flt(row.conversion_factor) or 1
        take = min(left, flt(row.stock_qty) or flt(row.qty) * factor)
        if take <= 0:
            continue
        row.qty = take / factor
        row.stock_qty = take
        row.warehouse = DISPATCH
        ready[row.item_code] = left - take
        kept.append(row)

    if not kept:
        frappe.throw(_("Sales Order {0} has nothing left to deliver for the items of this Dish.").format(doc.sales_order))

    dn.set("items", kept)
    for idx, row in enumerate(dn.items, 1):
        row.idx = idx

    dn.set_warehouse = DISPATCH
    dn.custom_dish = dish
    dn.run_method("calculate_taxes_and_totals")
    dn.insert()
    dn.add_comment("Info", _("Created from Dish {0}").format(dish))
    return dn.name


# ============================================================
# Material Request: Stores "Move to Quality Control"
# ============================================================

@frappe.whitelist()
def make_qc_transfer(material_request):
    """Stores: Material Request → submitted Stock Entry into QC Hold.
    Quality Inspections are created by the Stock Entry on_submit hook."""

    frappe.only_for(["Stores Person", "System Manager"])
    from erpnext.stock.doctype.material_request.material_request import make_stock_entry

    mr = frappe.get_doc("Material Request", material_request)
    mr.check_permission("read")
    # frappe.has_permission("Stock Entry", "create", throw=True)
    # frappe.has_permission("Stock Entry", "submit", throw=True)

    if mr.docstatus != 1:
        frappe.throw(_("Material Request {0} must be submitted first.").format(mr.name))
    if mr.material_request_type != "Material Transfer":
        frappe.throw(_("Only Material Transfer requests can be moved to Quality Control."))
    if not mr.get("custom_dish"):
        frappe.throw(_("This Material Request is not linked to a Dish."))
    if mr.status in ("Transferred", "Stopped", "Cancelled"):
        frappe.throw(_("Material Request {0} is already {1}.").format(mr.name, mr.status))

    se = make_stock_entry(mr.name)
    se.custom_dish = mr.custom_dish
    se.to_warehouse = QC_HOLD

    for row in se.items:
        row.t_warehouse = QC_HOLD
        if not row.s_warehouse:
            frappe.throw(_("Row {0}: no source warehouse on the Material Request for {1}.").format(row.idx, row.item_code))

    if not se.items:
        frappe.throw(_("Nothing pending to transfer on {0}.").format(mr.name))

    se.insert()
    se.submit()
    return se.name


def create_quality_inspections(se):
    """One draft Quality Inspection per row that moved into QC Hold."""
    qi_meta = frappe.get_meta("Quality Inspection")
    has_row_ref = qi_meta.has_field("child_row_reference")
    created = []

    for row in se.items:
        if row.t_warehouse != QC_HOLD or row.s_warehouse == QC_HOLD:
            continue

        filters = {
            "reference_type": "Stock Entry",
            "reference_name": se.name,
            "item_code": row.item_code,
            "docstatus": ["<", 2],
        }
        if has_row_ref:
            filters["child_row_reference"] = row.name
        if frappe.db.exists("Quality Inspection", filters):
            continue

        qty = flt(row.transfer_qty) or flt(row.qty)
        qi = frappe.new_doc("Quality Inspection")
        qi.inspection_type = "In Process"
        qi.reference_type = "Stock Entry"
        qi.reference_name = se.name
        qi.item_code = row.item_code
        qi.sample_size = qty
        qi.inspected_by = frappe.session.user
        qi.report_date = nowdate()
        qi.manual_inspection = 1
        qi.status = "Accepted"
        qi.custom_dish = se.custom_dish
        qi.custom_accepted_qty = qty
        qi.custom_rejected_qty = 0
        if has_row_ref:
            qi.child_row_reference = row.name

        qi.flags.ignore_permissions = True
        qi.insert()
        created.append(qi.name)

    return created


# ============================================================
# Quality Inspection result → stock moves
# ============================================================

def _make_qc_result_entry(qi, target_warehouse, qty):
    company = frappe.db.get_value("Stock Entry", qi.reference_name, "company")

    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Transfer"
    se.purpose = "Material Transfer"
    se.company = company
    se.custom_dish = qi.custom_dish
    se.custom_quality_inspection = qi.name
    se.from_warehouse = QC_HOLD
    se.to_warehouse = target_warehouse
    se.append("items", {
        "item_code": qi.item_code,
        "qty": qty,
        "uom": _stock_uom(qi.item_code),
        "conversion_factor": 1,
        "s_warehouse": QC_HOLD,
        "t_warehouse": target_warehouse,
    })

    se.flags.ignore_permissions = True
    se.insert()
    se.submit()
    se.add_comment("Info", _("Auto-created from Quality Inspection {0}").format(qi.name))
    return se.name


def _is_dish_qc(doc):
    return bool(doc.get("custom_dish")) and doc.reference_type == "Stock Entry" and bool(doc.reference_name)


# ============================================================
# Document event hooks (wired in hooks.py)
# ============================================================

def on_linked_doc_change(doc, method=None):
    update_dish_stores_status(doc.get("custom_dish"))


# ---- Stock Entry ----

def stock_entry_validate(doc, method=None):
    """Carry the Dish link from the Material Request (standard Create → Transfer)."""
    if doc.get("custom_dish"):
        return
    for row in doc.items:
        if row.get("material_request"):
            dish = frappe.db.get_value("Material Request", row.material_request, "custom_dish")
            if dish:
                doc.custom_dish = dish
                return


def stock_entry_on_submit(doc, method=None):
    if _is_qc_inbound(doc):
        create_quality_inspections(doc)
    update_dish_stores_status(doc.get("custom_dish"))


def stock_entry_on_cancel(doc, method=None):
    if _is_qc_inbound(doc):
        drafts = frappe.get_all(
            "Quality Inspection",
            filters={"reference_type": "Stock Entry", "reference_name": doc.name, "docstatus": 0},
            pluck="name",
        )
        for name in drafts:
            frappe.delete_doc("Quality Inspection", name, ignore_permissions=True)
    update_dish_stores_status(doc.get("custom_dish"))


# ---- Quality Inspection ----

def quality_inspection_validate(doc, method=None):
    if not doc.get("custom_dish") and doc.reference_type == "Stock Entry" and doc.reference_name:
        doc.custom_dish = frappe.db.get_value("Stock Entry", doc.reference_name, "custom_dish")

    if not _is_dish_qc(doc):
        return

    accepted = flt(doc.get("custom_accepted_qty"))
    rejected = flt(doc.get("custom_rejected_qty"))

    if accepted < 0 or rejected < 0:
        frappe.throw(_("Accepted Qty and Rejected Qty cannot be negative."))
    if flt(doc.sample_size) and accepted + rejected > flt(doc.sample_size) + 0.0001:
        frappe.throw(_("Accepted Qty + Rejected Qty cannot be more than the inspected qty {0}.").format(doc.sample_size))

    if accepted + rejected > 0:
        doc.status = "Accepted" if accepted > 0 else "Rejected"


def quality_inspection_before_submit(doc, method=None):
    if not _is_dish_qc(doc):
        return
    accepted = flt(doc.get("custom_accepted_qty"))
    rejected = flt(doc.get("custom_rejected_qty"))
    if accepted + rejected <= 0:
        return
    total = accepted + rejected
    if flt(doc.sample_size) and abs(total - flt(doc.sample_size)) > 0.0001:
        frappe.throw(
            _("Accepted Qty + Rejected Qty must equal the inspected qty {0} (currently {1}).").format(
                doc.sample_size, total
            )
        )


def quality_inspection_on_submit(doc, method=None):
    if not _is_dish_qc(doc):
        return

    source = frappe.get_doc("Stock Entry", doc.reference_name)
    if not _is_qc_inbound(source):
        return

    if frappe.db.exists("Stock Entry", {"custom_quality_inspection": doc.name, "docstatus": 1}):
        return

    accepted = flt(doc.get("custom_accepted_qty"))
    rejected = flt(doc.get("custom_rejected_qty"))

    # Inspection made by hand (no qty split entered): use the qty that went into QC Hold
    if accepted + rejected <= 0:
        qc_qty = sum(
            flt(r.transfer_qty) or flt(r.qty)
            for r in source.items
            if r.item_code == doc.item_code and r.t_warehouse == QC_HOLD
        )
        if doc.status == "Rejected":
            rejected = qc_qty
        else:
            accepted = qc_qty

        # Returned goods go back to free stock; outward goods go to Dispatch
    is_return = any(r.s_warehouse == RETURNS for r in source.items)
    if accepted > 0:
        _make_qc_result_entry(doc, FINISHED_GOODS if is_return else DISPATCH, accepted)
    if rejected > 0:
        _make_qc_result_entry(doc, REJECTED, rejected)

    update_dish_stores_status(doc.custom_dish)


def quality_inspection_before_cancel(doc, method=None):
    """Reverse the auto stock moves before the inspection itself is cancelled."""
    for name in frappe.get_all(
        "Stock Entry",
        filters={"custom_quality_inspection": doc.name, "docstatus": 1},
        pluck="name",
    ):
        se = frappe.get_doc("Stock Entry", name)
        se.flags.ignore_permissions = True
        se.cancel()


def quality_inspection_on_cancel(doc, method=None):
    update_dish_stores_status(doc.get("custom_dish"))


# ---- Delivery Note ----

def delivery_note_validate(doc, method=None):
    """A Delivery Note linked to a Dish ships only from Dispatch, for no more than is there."""
    dish = doc.get("custom_dish")
    if not dish or doc.get("is_return"):
        return

    net = _net_qty(dish)
    delivered = _delivered_qty(dish)

    wanted = {}
    for row in doc.items:
        if row.warehouse != DISPATCH:
            frappe.throw(_("Row {0}: Dish {1} can only be delivered from {2}.").format(row.idx, dish, DISPATCH))
        wanted[row.item_code] = wanted.get(row.item_code, 0) + (flt(row.stock_qty) or flt(row.qty))

    for item_code, qty in wanted.items():
        available = max(flt(net.get((item_code, DISPATCH))) - flt(delivered.get(item_code)), 0)
        if qty > available + 0.0001:
            frappe.throw(
                _("{0}: only {1} unit(s) of Dish {2} are in Dispatch, but this Delivery Note has {3}.").format(
                    item_code, _q(available), dish, _q(qty)
                )
            )

def delivery_note_on_submit(doc, method=None):
    """Refresh the Dish status when a Dish Delivery Note (or return) is submitted."""
    update_dish_stores_status(doc.get("custom_dish"))