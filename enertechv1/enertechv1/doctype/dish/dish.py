import frappe
from frappe.model.document import Document
from frappe.model.naming import getseries
from frappe.utils import getdate, nowdate


class Dish(Document):

	def before_insert(self):
		self.generate_series()

	def on_submit(self):
		make_sales_order(self.name)

	@frappe.whitelist()
	def generate_series(self):
		"""
		Generate Dish number only on submit.
		Finds the MAX number in the sequence, ignores amended/cancelled docs.
		Next number = max + 1 (always increments, never reuses gaps).
		"""
		today = getdate(nowdate())
		year = str(today.year)[2:]
		month = f"{today.month:02d}"
		prefix = f"EUPL/{year}/{month}/"

		# Get ALL Dishes for this year/month (including amended ones)
		all_dishes = frappe.get_all(
			"Dish",
			filters=[
				["dish_no", "like", f"{prefix}%"]
			],
			fields=["dish_no", "docstatus"]
		)

		max_number = 0

		for dish in all_dishes:
			# Skip amended/cancelled docs (docstatus=2)
			if dish.docstatus == 2:
				continue

			# Extract the number from "EUPL/26/01/045"
			try:
				parts = dish.dish_no.split("/")
				if len(parts) == 4:
					num = int(parts[3])
					max_number = max(max_number, num)
			except (ValueError, IndexError):
				pass

		# Next number is always max + 1
		next_number = max_number + 1
		number = f"{next_number:03d}"  # zero-padded to 3 digits

		series = f"{prefix}{number}"
		self.dish_no = series
    

@frappe.whitelist()
def make_sales_order(source_name, target_doc=None):
    source = frappe.get_doc("Dish", source_name)

    customer = frappe.db.get_value(
        "Customer",
        {"customer_name": source.customer},
        "name"
    )

    if not customer:
        frappe.throw(
            f"Customer '{source.customer}' not found. "
            f"Please ensure the Customer exists (created via Proforma Invoice submission) before creating the Sales Order."
        )

    sales_order = frappe.new_doc("Sales Order")
    sales_order.ignore_pricing_rule = 1
    sales_order.customer = customer
    sales_order.transaction_date = source.date
    sales_order.delivery_date = source.expected_delivery or source.date
    sales_order.po_no = source.purchase_order_no
    sales_order.po_date = source.order_date

    for row in source.items:
        sales_order.append("items", {
            "item_code": row.item_code,
            "qty": row.qty,
            "uom": row.uom,
            "rate": row.rate,
            "delivery_date": source.expected_delivery or source.date,
        })

    # Pull GST rates from the first item row (cast to float — they arrive as strings)
    first_row = source.items[0] if source.items else None
    cgst_rate = float(first_row.cgst_rate or 0) if first_row else 0
    sgst_rate = float(first_row.sgst_rate or 0) if first_row else 0
    igst_rate = float(first_row.igst_rate or 0) if first_row else 0

    if igst_rate > 0:
        sales_order.append("taxes", {
            "charge_type": "On Net Total",
            "account_head": "Output Tax IGST - EUPL",
            "description": "IGST",
            "rate": igst_rate,
        })
    else:
        if cgst_rate > 0:
            sales_order.append("taxes", {
                "charge_type": "On Net Total",
                "account_head": "Output Tax CGST - EUPL",
                "description": "CGST",
                "rate": cgst_rate,
            })
        if sgst_rate > 0:
            sales_order.append("taxes", {
                "charge_type": "On Net Total",
                "account_head": "Output Tax SGST - EUPL",
                "description": "SGST",
                "rate": sgst_rate,
            })

    sales_order.custom_total_gst = source.gst_amount

    sales_order.insert(ignore_permissions=True)
    sales_order.add_comment("Info", f"Auto-created from Dish {source.name}")

    frappe.msgprint(f"Sales Order {sales_order.name} created successfully.")

    return sales_order.name