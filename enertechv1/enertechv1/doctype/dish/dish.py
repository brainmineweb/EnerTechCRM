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
		today = getdate(nowdate())
		year = str(today.year)[2:]
		month = f"{today.month:02d}"

		series_key = f"DISH-{year}"        # independent counter, scoped to year -> resets automatically
		number = getseries(series_key, 3)  # zero-padded string, e.g. "00001"

		series = f"EUPL/{year}/{month}/{number}"
		self.dish_no = series


@frappe.whitelist()
def make_sales_order(source_name, target_doc=None):
	"""Create a clean, standard-fields-only Sales Order from a submitted Dish.
	No custom fields are set here on purpose — all customization lives on Dish.
	"""

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

	sales_order.insert(ignore_permissions=True)
	sales_order.add_comment("Info", f"Auto-created from Dish {source.name}")

	frappe.msgprint(f"Sales Order {sales_order.name} created successfully.")

	return sales_order.name