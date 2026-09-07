import frappe
from frappe.model.document import Document
from frappe.model.naming import getseries
from frappe.utils import getdate, nowdate, flt


INDIA_STATE_GST_CODE = {
	"andhra pradesh": "37-Andhra Pradesh", "arunachal pradesh": "12-Arunachal Pradesh",
	"assam": "18-Assam", "bihar": "10-Bihar", "chhattisgarh": "22-Chhattisgarh",
	"goa": "30-Goa", "gujarat": "24-Gujarat", "haryana": "06-Haryana",
	"himachal pradesh": "02-Himachal Pradesh", "jharkhand": "20-Jharkhand",
	"karnataka": "29-Karnataka", "kerala": "32-Kerala", "madhya pradesh": "23-Madhya Pradesh",
	"maharashtra": "27-Maharashtra", "manipur": "14-Manipur", "meghalaya": "17-Meghalaya",
	"mizoram": "15-Mizoram", "nagaland": "13-Nagaland", "odisha": "21-Odisha",
	"punjab": "03-Punjab", "rajasthan": "08-Rajasthan", "sikkim": "11-Sikkim",
	"tamil nadu": "33-Tamil Nadu", "telangana": "36-Telangana", "tripura": "16-Tripura",
	"uttar pradesh": "09-Uttar Pradesh", "uttarakhand": "05-Uttarakhand",
	"west bengal": "19-West Bengal", "delhi": "07-Delhi",
	"jammu and kashmir": "01-Jammu and Kashmir", "ladakh": "38-Ladakh",
	"chandigarh": "04-Chandigarh", "puducherry": "34-Puducherry",
	"andaman and nicobar islands": "35-Andaman and Nicobar Islands",
	"dadra and nagar haveli and daman and diu": "26-Dadra and Nagar Haveli and Daman and Diu",
	"lakshadweep": "31-Lakshadweep",
}


def guess_state_from_address_text(address_text):
	"""Match the longest state name found in free-text address, to avoid
	'Uttar Pradesh' matching inside 'Uttarakhand'-type substrings."""
	text = (address_text or "").lower()
	matches = [name for name in INDIA_STATE_GST_CODE if name in text]
	if not matches:
		return None
	best = max(matches, key=len)
	return INDIA_STATE_GST_CODE[best]


def get_company_gst_state(company):
	company_address = frappe.get_all(
		"Address",
		filters=[
			["Dynamic Link", "link_doctype", "=", "Company"],
			["Dynamic Link", "link_name", "=", company],
			["Address", "is_your_company_address", "=", 1],
		],
		pluck="name",
		limit=1,
	)

	if not company_address:
		frappe.throw(f"No company address with GST state found for {company}.")

	company_state_code = frappe.db.get_value(
		"Address", company_address[0], "gst_state_number"
	)

	if not company_state_code:
		frappe.throw(
			f"Company address {company_address[0]} has no GST state number set."
		)

	return company_state_code


class Dish(Document):

	def validate(self):
		self.calculate_totals()

	def before_save(self):
		self.calculate_totals()

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

	def calculate_totals(self):
		"""
		Recalculate item amounts and GST totals every time the Dish
		is saved, based on this Dish's own `tax_category` field.

		- In-State  -> CGST + SGST calculated, IGST rate forced to 0
		- Out-State -> IGST calculated, CGST/SGST rates forced to 0
		- Rates are editable per item; a default is only applied if
		  the item doesn't already have a rate set.
		"""

		total = 0
		total_gst = 0

		tax_category = (self.tax_category or "").strip().lower()

		is_out_state = tax_category in (
			"out-state", "out state", "out-stage", "out stage",
			"inter-state", "inter state",
		)
		is_in_state = tax_category in (
			"in-state", "in state", "in-stage", "in stage",
			"intra-state", "intra state",
		)

		for item in self.items:

			# --------------------------------------------
			# Item amount
			# --------------------------------------------
			qty = flt(item.qty)
			rate = flt(item.rate)

			item.amount = qty * rate
			base_amount = item.amount

			total += base_amount

			# --------------------------------------------
			# Reset GST amounts every recalculation
			# --------------------------------------------
			item.cgst_amt = 0
			item.sgst_amount = 0
			item.igst_amt = 0

			# --------------------------------------------
			# In-State: CGST + SGST, IGST forced to zero
			# --------------------------------------------
			if is_in_state:

				item.igst_rate = 0

				if not flt(item.cgst_rate):
					item.cgst_rate = 9

				if not flt(item.sgst_rate):
					item.sgst_rate = 9

				item.cgst_amt = (base_amount * flt(item.cgst_rate)) / 100
				item.sgst_amount = (base_amount * flt(item.sgst_rate)) / 100

			# --------------------------------------------
			# Out-State: IGST only, CGST/SGST forced to zero
			# --------------------------------------------
			elif is_out_state:

				item.cgst_rate = 0
				item.sgst_rate = 0

				if not flt(item.igst_rate):
					item.igst_rate = 18

				item.igst_amt = (base_amount * flt(item.igst_rate)) / 100

			total_gst += (
				flt(item.cgst_amt)
				+ flt(item.sgst_amount)
				+ flt(item.igst_amt)
			)

		self.sub_total = total
		self.gst_amount = total_gst
		self.total = total + total_gst


@frappe.whitelist()
def make_sales_order(source_name, target_doc=None):
	source = frappe.get_doc("Dish", source_name)

	# ---------------------------------------------------------
	# 1. Get Customer
	# ---------------------------------------------------------
	customer = frappe.db.get_value(
		"Customer",
		{"customer_name": source.customer},
		"name"
	)

	if not customer:
		frappe.throw(
			f"Customer '{source.customer}' not found. "
			"Please ensure the Customer exists before creating the Sales Order."
		)

	# ---------------------------------------------------------
	# 2. Prevent duplicate Sales Order from same Dish
	# ---------------------------------------------------------
	existing_so = frappe.db.exists(
		"Sales Order",
		{
			"custom_dish": source.name
		}
	)

	if existing_so:
		frappe.throw(
			f"Sales Order {existing_so} already exists for Dish {source.name}."
		)

	# ---------------------------------------------------------
	# 3. Create Sales Order
	# ---------------------------------------------------------
	sales_order = frappe.new_doc("Sales Order")

	sales_order.ignore_pricing_rule = 1
	sales_order.customer = customer
	sales_order.custom_quotation = source.quotation
	sales_order.custom_proforma_invoice = source.proforma_invoice
	sales_order.custom_dish = source.name

	if source.date:
		sales_order.transaction_date = source.date

	sales_order.delivery_date = (
		source.expected_delivery
		or source.date
	)

	if source.purchase_order_no:
		sales_order.po_no = source.purchase_order_no

	if source.order_date:
		sales_order.po_date = source.order_date

	# ---------------------------------------------------------
	# 4. Copy Tax Category
	# ---------------------------------------------------------
	if source.tax_category:
		sales_order.tax_category = source.tax_category

	# ---------------------------------------------------------
	# 5. Copy custom Dish reference
	# ---------------------------------------------------------
	if hasattr(sales_order, "custom_dish"):
		sales_order.custom_dish = source.name

	# ---------------------------------------------------------
	# 6. Add Items
	# ---------------------------------------------------------
	if not source.items:
		frappe.throw(
			f"Dish {source.name} does not contain any items."
		)

	for row in source.items:

		item = sales_order.append("items", {
			"item_code": row.item_code,
			"qty": row.qty,
			"uom": row.uom,
			"rate": row.rate,
			"delivery_date": (
				source.expected_delivery
				or source.date
			),
		})

		# Copy GST rates to SO item if these custom fields exist
		if hasattr(item, "cgst_rate") and row.cgst_rate:
			item.cgst_rate = row.cgst_rate

		if hasattr(item, "sgst_rate") and row.sgst_rate:
			item.sgst_rate = row.sgst_rate

		if hasattr(item, "igst_rate") and row.igst_rate:
			item.igst_rate = row.igst_rate

	# ---------------------------------------------------------
	# 7. Determine GST rates
	#
	# We collect rates from ALL Dish items instead of only
	# looking at the first item.
	# ---------------------------------------------------------
	cgst_rates = set()
	sgst_rates = set()
	igst_rates = set()

	for row in source.items:

		cgst = float(row.cgst_rate or 0)
		sgst = float(row.sgst_rate or 0)
		igst = float(row.igst_rate or 0)

		if cgst > 0:
			cgst_rates.add(cgst)

		if sgst > 0:
			sgst_rates.add(sgst)

		if igst > 0:
			igst_rates.add(igst)

	# ---------------------------------------------------------
	# 8. Validate GST rate consistency
	#
	# This code assumes one GST rate structure per Dish.
	# Example:
	#
	# In-State:
	#   CGST 9%
	#   SGST 9%
	#
	# Out-State:
	#   IGST 18%
	# ---------------------------------------------------------

	if len(cgst_rates) > 1:
		frappe.throw(
			f"Dish {source.name} contains multiple CGST rates: "
			f"{', '.join(str(x) for x in sorted(cgst_rates))}%. "
			"Please use item-level tax configuration for different GST rates."
		)

	if len(sgst_rates) > 1:
		frappe.throw(
			f"Dish {source.name} contains multiple SGST rates: "
			f"{', '.join(str(x) for x in sorted(sgst_rates))}%. "
			"Please use item-level tax configuration for different GST rates."
		)

	if len(igst_rates) > 1:
		frappe.throw(
			f"Dish {source.name} contains multiple IGST rates: "
			f"{', '.join(str(x) for x in sorted(igst_rates))}%. "
			"Please use item-level tax configuration for different GST rates."
		)

	cgst_rate = next(iter(cgst_rates), 0)
	sgst_rate = next(iter(sgst_rates), 0)
	igst_rate = next(iter(igst_rates), 0)

	# ---------------------------------------------------------
	# 9. GST Transaction Type
	# ---------------------------------------------------------
	tax_category = (source.tax_category or "").strip().lower()

	# Support both your current value "Out-Stage" and
	# the more natural "Out-State".
	is_out_state = tax_category in (
		"out-state",
		"out state",
		"out-stage",
		"out stage",
		"inter-state",
		"inter state",
	)

	is_in_state = tax_category in (
		"in-state",
		"in state",
		"in-stage",
		"in stage",
		"intra-state",
		"intra state",
	)

	if not is_out_state and not is_in_state:
		frappe.throw(
			f"Invalid Tax Category '{source.tax_category}' in Dish {source.name}. "
			"Expected In-State or Out-State."
		)

	# ---------------------------------------------------------
	# 9b. Resolve Place of Supply from free-text address and
	#     cross-check against the Dish's declared tax_category.
	#
	# Without this, place_of_supply has no address to derive
	# from and India Compliance falls back to treating every
	# transaction as intra-state, rejecting any IGST row.
	# ---------------------------------------------------------
	customer_place_of_supply = guess_state_from_address_text(source.customer_address)

	if customer_place_of_supply:
		sales_order.place_of_supply = customer_place_of_supply
		actual_state_code = customer_place_of_supply.split("-")[0]
		company_state_code = get_company_gst_state(sales_order.company)

		actually_in_state = (actual_state_code == company_state_code)
		if actually_in_state != is_in_state:
			frappe.throw(
				f"Dish {source.name}: tax_category says "
				f"{'In-State' if is_in_state else 'Out-State'}, but the address text "
				f"resolves to {customer_place_of_supply}, which is "
				f"{'in-state' if actually_in_state else 'out-state'} for company "
				f"{sales_order.company}. Please fix the address or tax_category."
			)
	else:
		frappe.msgprint(
			f"Could not detect a state name in Dish {source.name}'s address text. "
			"GST place of supply not set automatically — please verify manually.",
			alert=True,
		)

	# ---------------------------------------------------------
	# 10. Add GST Taxes
	# ---------------------------------------------------------
	if is_out_state:

		# -----------------------------------------------------
		# OUT-STATE
		# IGST only
		# -----------------------------------------------------

		if igst_rate <= 0:

			# If Dish does not have IGST but has CGST + SGST,
			# derive IGST from their total.
			if cgst_rate > 0 and sgst_rate > 0:
				igst_rate = cgst_rate + sgst_rate

			else:
				frappe.throw(
					f"Dish {source.name} is marked as Out-State "
					"but no valid IGST rate was found."
				)

		sales_order.append("taxes", {
			"charge_type": "On Net Total",
			"account_head": "Output Tax IGST - EUPL",
			"description": f"IGST {igst_rate}%",
			"rate": igst_rate,
		})

	elif is_in_state:

		# -----------------------------------------------------
		# IN-STATE
		# CGST + SGST
		# -----------------------------------------------------

		if cgst_rate <= 0 or sgst_rate <= 0:

			# If only IGST exists, split it into CGST + SGST.
			if igst_rate > 0:
				cgst_rate = igst_rate / 2
				sgst_rate = igst_rate / 2

			else:
				frappe.throw(
					f"Dish {source.name} is marked as In-State "
					"but valid CGST/SGST rates were not found."
				)

		sales_order.append("taxes", {
			"charge_type": "On Net Total",
			"account_head": "Output Tax CGST - EUPL",
			"description": f"CGST {cgst_rate}%",
			"rate": cgst_rate,
		})

		sales_order.append("taxes", {
			"charge_type": "On Net Total",
			"account_head": "Output Tax SGST - EUPL",
			"description": f"SGST {sgst_rate}%",
			"rate": sgst_rate,
		})

	# ---------------------------------------------------------
	# 11. Custom GST Total
	# ---------------------------------------------------------
	if hasattr(sales_order, "custom_total_gst"):
		sales_order.custom_total_gst = source.gst_amount or 0

	# ---------------------------------------------------------
	# 12. Insert Sales Order
	# ---------------------------------------------------------
	sales_order.insert(ignore_permissions=True)

	sales_order.add_comment(
		"Info",
		f"Auto-created from Dish {source.name}"
	)

	frappe.msgprint(
		f"Sales Order {sales_order.name} created successfully."
	)

	return sales_order.name