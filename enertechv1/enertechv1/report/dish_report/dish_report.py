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
		{"label": _("Rating"), "fieldname": "product_rating", "fieldtype": "Data", "width": 90},
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
		select
			d.name,
			d.`date`,
			d.customer,
			d.sub_total,
			ifnull(so.custom_total_received, 0) as advance_payment,
			d.product_rating,
			d.expected_delivery,
			if(ifnull(d.inspection, 0) = 1, 'Yes', 'No') as inspection,
			d.buyer_address
		from `tabDish` d
		left join `tabSales Order` so on so.name = d.sales_order
		where {" and ".join(conditions)}
		order by d.`date` desc, d.name desc
		""",
		filters,
		as_dict=True,
	)