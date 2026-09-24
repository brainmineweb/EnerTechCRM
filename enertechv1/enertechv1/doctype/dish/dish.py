import re

import frappe
from frappe.model.document import Document
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

# Frappe appends "-1", "-2" ... to the name of an amended document.
AMEND_SUFFIX_RE = re.compile(r"-\d+$")


def _strip_amend_suffix(value):
	"""'EUPL/26/09/007-1'   -> 'EUPL/26/09/007'
	'EUPL/26/09/007-a-2' -> 'EUPL/26/09/007-a'"""
	return AMEND_SUFFIX_RE.sub("", value or "")


def _existing_names_and_numbers(prefix):
	"""Return every Dish name and dish_no starting with `prefix`,
	INCLUDING cancelled ones — a cancelled Dish still exists in the
	database and still occupies its name, so its number can't be reused."""
	rows = frappe.db.sql(
		"""
		select name, dish_no
		from `tabDish`
		where name like %(p)s or dish_no like %(p)s
		""",
		{"p": prefix + "%"},
		as_dict=True,
	)

	values = []
	for r in rows:
		values.append(r.name or "")
		values.append(r.dish_no or "")
	return values


def guess_state_from_address_text(address_text):
	"""Normalize a state name (as stored on Lead.custom_state) into the
	'NN-StateName' GST format, e.g. 'Maharashtra' -> '27-Maharashtra'."""
	text = (address_text or "").strip().lower()
	return INDIA_STATE_GST_CODE.get(text)


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
		# -------------------------------------------------------------
		# Amended Dish (e.g. EUPL/26/09/007 cancelled -> EUPL/26/09/007-1)
		# Keep the ORIGINAL number instead of generating a new one.
		# Frappe itself names the document <original>-1.
		# -------------------------------------------------------------
		if self.amended_from:
			original = frappe.db.get_value(
				"Dish",
				self.amended_from,
				["dish_no", "sales_order", "parent_dish"],
				as_dict=True,
			) or {}

			self.dish_no = _strip_amend_suffix(
				original.get("dish_no") or self.amended_from
			)

			if not self.sales_order and original.get("sales_order"):
				self.sales_order = original.get("sales_order")

			if not self.parent_dish and original.get("parent_dish"):
				self.parent_dish = original.get("parent_dish")

			return

		self.generate_series()

	@frappe.whitelist()
	def generate_series(self):
		"""
		Parent Dish (no parent_dish): EUPL/YY/MM/### — highest existing
		number + 1.

		Child Dish (parent_dish set): <parent's base dish_no>-a / -b / -c ...
		— next letter after the highest letter already used for that parent.

		Cancelled and amended Dishes ARE counted, because their names
		still exist in the database. Amendment suffixes (-1, -2 ...) are
		ignored when reading numbers, so 007, 007-1, 007-a, 007-a-1 all
		count as number 007.
		"""
		# ---------------------------------------------------------
		# Child Dish
		# ---------------------------------------------------------
		if self.parent_dish:
			parent_dish_no = frappe.db.get_value("Dish", self.parent_dish, "dish_no")

			if not parent_dish_no:
				frappe.throw(f"Parent Dish {self.parent_dish} has no dish_no set yet.")

			base = _strip_amend_suffix(parent_dish_no)
			child_prefix = f"{base}-"
			pattern = re.compile(
				r"^" + re.escape(child_prefix) + r"([a-z])(?:-\d+)?$"
			)

			max_idx = -1
			for value in _existing_names_and_numbers(child_prefix):
				m = pattern.match(value)
				if m:
					max_idx = max(max_idx, ord(m.group(1)) - ord("a"))

			next_idx = max_idx + 1
			if next_idx > 25:
				frappe.throw(
					f"Parent Dish {self.parent_dish} already has 26 sub products (a–z)."
				)

			self.dish_no = f"{child_prefix}{chr(ord('a') + next_idx)}"
			return

		# ---------------------------------------------------------
		# Parent Dish
		# ---------------------------------------------------------
		today = getdate(nowdate())
		year = str(today.year)[2:]
		month = f"{today.month:02d}"
		prefix = f"EUPL/{year}/{month}/"
		pattern = re.compile(r"^" + re.escape(prefix) + r"(\d+)")

		max_number = 0
		for value in _existing_names_and_numbers(prefix):
			m = pattern.match(value)
			if m:
				max_number = max(max_number, int(m.group(1)))

		self.dish_no = f"{prefix}{max_number + 1:03d}"

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


@frappe.whitelist()
def get_sales_order_dish_items(sales_order_name):
	"""Return the Sales Order's items for the "Create Dish" dialog,
	together with the Dish(es) already created against this Sales
	Order for each item.

	NOTE on matching: a Dish's item row does not store a reference
	back to the originating Sales Order item row, only the item_code.
	So "already created for this item" is worked out by matching
	item_code within Dishes linked to this Sales Order — if the same
	item_code appears on more than one row of the same Sales Order,
	those rows will show the same list of existing Dishes. If you
	need exact per-row tracking (e.g. duplicate item_codes with
	different rates), a custom field storing the source SO item row
	name on the Dish Item child table would be needed.
	"""
	so = frappe.get_doc("Sales Order", sales_order_name)

	if not so.items:
		frappe.throw(f"Sales Order {so.name} has no items.")

	existing_dishes = frappe.get_all(
		"Dish",
		filters={"sales_order": so.name, "docstatus": ["!=", 2]},
		fields=["name"],
		order_by="creation asc",
	)

	dishes_by_item_code = {}
	for d in existing_dishes:
		dish_doc = frappe.get_doc("Dish", d.name)
		for dish_item in dish_doc.items:
			dishes_by_item_code.setdefault(dish_item.item_code, []).append(dish_doc.name)

	return [
		{
			"row_name": row.name,
			"item_code": row.item_code,
			"item_name": row.item_name,
			"qty": row.qty,
			"existing_dishes": dishes_by_item_code.get(row.item_code, []),
		}
		for row in so.items
	]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def parent_dish_query(doctype, txt, searchfield, start, page_len, filters):
	"""Link-field query for the "Parent Dish" picker in the Create Dish dialog.

	Shows only top-level (non Sub Product), non-cancelled Dishes —
	including amended ones like EUPL/26/09/007-1. Dishes belonging to
	the current Sales Order are listed first.
	"""
	filters = filters or {}
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)

	return frappe.db.sql(
		"""
		select name, dish_no, customer
		from `tabDish`
		where docstatus < 2
			and ifnull(parent_dish, '') = ''
			and (
				name like %(txt)s
				or ifnull(dish_no, '') like %(txt)s
				or ifnull(customer, '') like %(txt)s
			)
		order by
			(ifnull(sales_order, '') = %(so)s) desc,
			creation desc
		limit %(start)s, %(page_len)s
		""",
		{
			"txt": f"%{txt}%",
			"so": filters.get("sales_order") or "",
			"start": int(start),
			"page_len": int(page_len),
		},
	)


@frappe.whitelist()
def create_dish_from_sales_order_item(
	sales_order_name,
	row_name,
	is_sub_product=0,
	parent_dish=None,
):
	"""Create a single Dish for one Sales Order item.

	is_sub_product: truthy if this Dish should be a child (Sub Product)
		Dish, numbered under `parent_dish` as <parent_dish_no>-a/-b/...

	parent_dish: name of an existing, already-created Dish to link as
		the parent when is_sub_product is truthy. Since only one Dish
		is created per call, the parent must already exist — create
		the parent Dish first (in an earlier call), then create the
		Sub Product Dish linking to it.
	"""
	if isinstance(is_sub_product, str):
		is_sub_product = frappe.parse_json(is_sub_product)
	is_sub_product = bool(is_sub_product)

	so = frappe.get_doc("Sales Order", sales_order_name)

	so_row = next((r for r in so.items if r.name == row_name), None)
	if not so_row:
		frappe.throw(f"Item row {row_name} not found on Sales Order {sales_order_name}.")

	if is_sub_product:
		if not parent_dish:
			frappe.throw("Please select a parent Dish for this Sub Product.")

		parent_info = frappe.db.get_value(
			"Dish", parent_dish, ["docstatus", "parent_dish"], as_dict=True
		)

		if not parent_info:
			frappe.throw(f"Parent Dish '{parent_dish}' does not exist.")

		if parent_info.docstatus == 2:
			frappe.throw(
				f"Parent Dish '{parent_dish}' is cancelled. "
				"Please use its amended version instead."
			)

		if parent_info.parent_dish:
			frappe.throw(
				f"'{parent_dish}' is itself a Sub Product — only one level of "
				"nesting is supported, so it can't be used as a parent."
			)

	pi = frappe.get_doc("Proforma Invoice", so.custom_proforma_invoice) if so.custom_proforma_invoice else None
	pi_items_by_code = {}
	if pi:
		for pi_row in pi.items:
			pi_items_by_code.setdefault(pi_row.item, []).append(pi_row)

	def get_dispatch_state_from_pi(pi):
		"""Old make_dish resolved dispatch_state from the Lead behind the PI's
		Quotation. Re-derive it the same way, but don't blow up if the
		Quotation's party isn't a Lead (e.g. it's a Customer)."""
		if not pi.quotation:
			return None

		quotation = frappe.db.get_value("Quotation", pi.quotation, "party_name")
		if not quotation:
			return None

		if not frappe.db.exists("Lead", quotation):
			return None

		return frappe.db.get_value("Lead", quotation, "custom_state")

	dish = frappe.new_doc("Dish")

	dish.customer = so.customer
	dish.quotation = so.custom_quotation
	dish.proforma_invoice = so.custom_proforma_invoice
	dish.tax_category = so.tax_category
	dish.date = frappe.utils.today()
	dish.expected_delivery = so.delivery_date
	dish.purchase_order_no = so.po_no
	dish.order_date = so.po_date
	dish.sales_order = so.name

	if pi:
		dish.customer_name = pi.customer_name
		dish.buyer_address = pi.address
		dish.bueyer_gst_no = pi.buyer_gstin
		dish.customer_gstin = pi.consignee_gstin
		dish.buyers_email = pi.buyers_email
		dish.buyer_contact_no = pi.buyers_phone_no

		dish.buyer = pi.buyer
		dish.buyers_name = pi.buyer_name
		dish.buyers_phone_no = pi.buyers_phone_no
		dish.warranty = pi.warranty
		dish.mode_terms_of_payment = pi.modeterms_of_payment
		dish.mode_of_dispatch = pi.dispatched_through
		dish.terms_of_delivery = pi.freight_terms
		dish.invoice_to_name = pi.buyer
		dish.invoice_to_address = pi.address
		dish.dispatch_to_name = pi.customer
		dish.dispatch_to_address = pi.consignee_address
		dish.dispatch_state = get_dispatch_state_from_pi(pi)

	if is_sub_product:
		dish.parent_dish = parent_dish

	pi_row = None
	queue = pi_items_by_code.get(so_row.item_code)
	if queue:
		pi_row = queue.pop(0)

	dish.append("items", {
		"item_code": so_row.item_code,
		"item_name": so_row.item_name,
		"qty": so_row.qty,
		"uom": so_row.uom,
		"rate": so_row.rate,
		"amount": so_row.amount,
		"description": pi_row.description if pi_row else so_row.description,
		"hsn_code": pi_row.gst_hsn_code if pi_row else None,
		"warrenty": pi_row.warranty_years if pi_row else None,
		"cgst_rate": getattr(so_row, "cgst_rate", None),
		"sgst_rate": getattr(so_row, "sgst_rate", None),
		"igst_rate": getattr(so_row, "igst_rate", None),
	})

	dish.insert(ignore_permissions=True)

	dish.add_comment(
		"Info",
		f"Auto-created from Sales Order {so.name}, item {so_row.item_code}"
	)

	return dish.name