import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    filters = frappe._dict(filters or {})

    warehouses = get_warehouses(filters)
    if not warehouses:
        return get_columns([]), []

    items = get_items(filters)
    if not items:
        return get_columns(warehouses), []

    bins = frappe.get_all(
        "Bin",
        filters={
            "item_code": ["in", [i.name for i in items]],
            "warehouse": ["in", [w.name for w in warehouses]],
        },
        fields=["item_code", "warehouse", "actual_qty", "stock_value"],
    )

    columns = get_columns(warehouses)
    data = build_rows(items, warehouses, bins, filters)
    return columns, data


def get_warehouses(filters):
    wh_filters = {"is_group": 0, "disabled": 0}
    if filters.company:
        wh_filters["company"] = filters.company
    if filters.free_only:
        wh_filters["count_in_dish_availability"] = 1

    selected = filters.get("warehouse")
    if isinstance(selected, str):
        selected = frappe.parse_json(selected) if selected.startswith("[") else [selected]
    if selected:
        wh_filters["name"] = ["in", selected]

    return frappe.get_all(
        "Warehouse",
        filters=wh_filters,
        fields=["name", "warehouse_name", "count_in_dish_availability"],
        order_by="count_in_dish_availability desc, name asc",
    )


def get_items(filters):
    item_filters = {"is_stock_item": 1, "disabled": 0}
    if filters.item_code:
        item_filters["name"] = filters.item_code
    if filters.item_group:
        item_filters["item_group"] = ["descendants of (inclusive)", filters.item_group]

    return frappe.get_all(
        "Item",
        filters=item_filters,
        fields=["name", "item_name", "item_group", "stock_uom"],
        order_by="item_group asc, name asc",
    )


def get_columns(warehouses):
    columns = [
        {"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 130},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 220},
        {"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 130},
        {"label": _("UOM"), "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 70},
    ]

    for idx, wh in enumerate(warehouses):
        columns.append({
            "label": wh.warehouse_name or wh.name,
            "fieldname": f"wh_{idx}",
            "fieldtype": "Float",
            "width": 120,
        })

    columns += [
        {"label": _("Free Qty"), "fieldname": "free_qty", "fieldtype": "Float", "width": 100},
        {"label": _("Total Qty"), "fieldname": "total_qty", "fieldtype": "Float", "width": 100},
        {"label": _("Stock Value"), "fieldname": "stock_value", "fieldtype": "Currency", "width": 130},
    ]
    return columns


def build_rows(items, warehouses, bins, filters):
    wh_index = {wh.name: idx for idx, wh in enumerate(warehouses)}
    free_whs = {wh.name for wh in warehouses if wh.count_in_dish_availability}

    stock = {}
    for b in bins:
        stock.setdefault(b.item_code, []).append(b)

    data = []
    for item in items:
        row = {
            "item_code": item.name,
            "item_name": item.item_name,
            "item_group": item.item_group,
            "stock_uom": item.stock_uom,
            "free_qty": 0.0,
            "total_qty": 0.0,
            "stock_value": 0.0,
        }
        for idx in range(len(warehouses)):
            row[f"wh_{idx}"] = 0.0

        for b in stock.get(item.name, []):
            qty = flt(b.actual_qty)
            row[f"wh_{wh_index[b.warehouse]}"] = qty
            row["total_qty"] += qty
            row["stock_value"] += flt(b.stock_value)
            if b.warehouse in free_whs:
                row["free_qty"] += qty

        if not filters.show_zero and not any(flt(row[f"wh_{i}"]) for i in range(len(warehouses))):
            continue

        data.append(row)

    return data