# Copyright (c) 2026, Brainmine Web Solutions Pvt Ltd
# Script Report: Dish Report

import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Dish No"), "fieldname": "name", "fieldtype": "Link", "options": "Dish", "width": 150},
		{"label": _("Dish Date"), "fieldname": "date", "fieldtype": "Date", "width": 110},
		{"label": _("Customer Name"), "fieldname": "customer", "fieldtype": "Data", "width": 180},
		{"label": _("Basic Amount"), "fieldname": "sub_total", "fieldtype": "Currency", "width": 130},
		{"label": _("Advance Payment"), "fieldname": "advance_payment", "fieldtype": "Currency", "width": 140},
		{"label": _("Rating"), "fieldname": "product_rating", "fieldtype": "Data", "width": 200},
		{"label": _("Expected Date of Delivery"), "fieldname": "expected_delivery", "fieldtype": "Date", "width": 160},
		{"label": _("Inspection"), "fieldname": "inspection", "fieldtype": "Data", "width": 100},
		{"label": _("Address"), "fieldname": "buyer_address", "fieldtype": "Small Text", "width": 600},
	]



def get_data(filters):
    conditions = ["d.docstatus < 2"]

    if filters.get("from_date"):
        conditions.append("d.`date` >= %(from_date)s")

    if filters.get("to_date"):
        conditions.append("d.`date` <= %(to_date)s")

    if filters.get("customer"):
        filters["customer"] = f"%{filters.get('customer')}%"
        conditions.append("d.customer like %(customer)s")

    if filters.get("inspection"):
        filters["inspection_val"] = 1 if filters.get("inspection") == "Yes" else 0
        conditions.append("ifnull(d.inspection, 0) = %(inspection_val)s")

    return frappe.db.sql(
        f"""
        SELECT
            d.name,
            d.`date`,
            d.customer,
            d.sub_total,
            IFNULL(so.custom_total_received, 0) AS advance_payment,
            di.item_name AS product_rating,
            d.expected_delivery,
            IF(IFNULL(d.inspection, 0) = 1, 'Yes', 'No') AS inspection,
            d.buyer_address
        FROM `tabDish` d
        LEFT JOIN `tabDish Item` di
            ON di.parent = d.name
            AND di.parenttype = 'Dish'
            AND di.parentfield = 'items'
        LEFT JOIN `tabSales Order` so
            ON so.name = d.sales_order
        WHERE {" AND ".join(conditions)}
        ORDER BY d.`date` DESC, d.name DESC
        """,
        filters,
        as_dict=True,
    )
