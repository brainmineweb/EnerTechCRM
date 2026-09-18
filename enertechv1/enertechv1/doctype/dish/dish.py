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
		self.generate_series()

	def on_submit(self):
		make_sales_order(self.name)

	@frappe.whitelist()
	def generate_series(self):
		"""

		Parent Dish (no parent_dish): EUPL/YY/MM/### global running
		counter, same as before — max existing +1, ignoring cancelled docs.

		Child Dish (parent_dish set): <parent's dish_no>-<letter>,
		letter increments per parent (a, b, c...) based on how many
		non-cancelled children that parent already has.

		This works identically whether parent_dish was set because the
		parent Dish was created in the same batch, or because the child
		was manually linked to a pre-existing parent Dish — either way
		we just count that parent's current active children.
		"""
		if self.parent_dish:
			parent_dish_no = frappe.db.get_value("Dish", self.parent_dish, "dish_no")

			if not parent_dish_no:
				frappe.throw(f"Parent Dish {self.parent_dish} has no dish_no set yet.")

			existing_children = frappe.get_all(
				"Dish",
				filters={"parent_dish": self.parent_dish},
				fields=["docstatus"],
			)
			active_count = len([d for d in existing_children if d.docstatus != 2])

			self.dish_no = f"{parent_dish_no}-{chr(ord('a') + active_count)}"
			return

		today = getdate(nowdate())
		year = str(today.year)[2:]
		month = f"{today.month:02d}"
		prefix = f"EUPL/{year}/{month}/"

		all_dishes = frappe.get_all(
			"Dish",
			filters=[["dish_no", "like", f"{prefix}%"]],
			fields=["dish_no", "docstatus"]
		)

		max_number = 0
		for dish in all_dishes:
			if dish.docstatus == 2:
				continue
			try:
				parts = dish.dish_no.split("/")
				if len(parts) == 4:
					max_number = max(max_number, int(parts[3]))
			except (ValueError, IndexError):
				pass

		next_number = max_number + 1
		self.dish_no = f"{prefix}{next_number:03d}"

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
	"""Return the Sales Order's items for the "Create Dish" dialog.

	No Item-master flags are consulted here — Product vs. Sub Product,
	and which item is whose parent, is decided by the user in the
	dialog itself, per Dish-creation run, not baked into the Item.
	"""
	so = frappe.get_doc("Sales Order", sales_order_name)

	if not so.items:
		frappe.throw(f"Sales Order {so.name} has no items.")

	return [
		{
			"row_name": row.name,
			"item_code": row.item_code,
			"item_name": row.item_name,
			"qty": row.qty,
		}
		for row in so.items
	]


@frappe.whitelist()
def create_dishes_from_sales_order(
	sales_order_name,
	selected_items=None,
	parent_row_links=None,
	manual_parent_links=None,
):
	"""Create one Dish per selected "Product" item on the Sales Order,
	plus one child Dish per selected "Sub Product" item, numbered under
	its parent as <parent_dish_no>-a/-b/...

	There's no Item-master concept of child/parent items here — every
	row is a Product by default; the caller (the "Create Dish" dialog)
	decides per Dish-creation run which rows are Sub Products and what
	each one's parent is.

	selected_items: list of Sales Order Item row `name`s to create Dish
		documents for. If omitted, every item on the Sales Order is used,
		all as top-level Products (no hierarchy).

	parent_row_links: dict of {child_row_name: parent_row_name}, both
		row `name`s from this same Sales Order. Used when the Sub
		Product's real parent item is also present (and selected) on
		this Sales Order — the two Dishes are created together in this
		same run, with the child numbered off the freshly-created parent.

	manual_parent_links: dict of {child_row_name: parent_dish_name}.
		Used when the Sub Product's parent item is NOT on this Sales
		Order (e.g. it belongs to a different Dish entirely) — this
		supplies an existing, already-created Dish to link the child to
		instead. The child is numbered off that Dish exactly as if it
		had been created in this same batch.

	A row may appear in at most one of the two link dicts. Only one
	level of nesting is supported: a row used as someone's parent via
	parent_row_links must itself be a plain Product (not itself listed
	as a child in either dict).
	"""

	selected_items = frappe.parse_json(selected_items) if selected_items else None
	parent_row_links = frappe.parse_json(parent_row_links) if parent_row_links else {}
	manual_parent_links = frappe.parse_json(manual_parent_links) if manual_parent_links else {}

	so = frappe.get_doc("Sales Order", sales_order_name)

	if not so.items:
		frappe.throw(f"Sales Order {so.name} has no items.")

	if selected_items:
		selected_set = set(selected_items)
		so_rows = [row for row in so.items if row.name in selected_set]
	else:
		so_rows = list(so.items)

	if not so_rows:
		frappe.throw("No items selected to create Dish documents for.")

	so_row_names = {row.name for row in so_rows}
	so_rows_by_name = {row.name: row for row in so_rows}

	# A row can't be linked both ways at once.
	overlap = set(parent_row_links) & set(manual_parent_links)
	if overlap:
		codes = ", ".join(so_rows_by_name[r].item_code for r in overlap if r in so_rows_by_name)
		frappe.throw(
			f"Item(s) {codes} were given both an in-Sales-Order parent and a "
			"linked Dish — pick only one for each."
		)

	child_row_names = set(parent_row_links) | set(manual_parent_links)

	# ---- Validate parent_row_links: parent must be selected, distinct,
	# and itself a plain Product (only one level of nesting) ----
	for child_row, parent_row in parent_row_links.items():
		child_code = so_rows_by_name.get(child_row).item_code if child_row in so_rows_by_name else child_row

		if child_row not in so_row_names:
			frappe.throw(f"'{child_code}' is marked as a Sub Product but isn't among the selected items.")

		if parent_row == child_row:
			frappe.throw(f"'{child_code}' can't be marked as a Sub Product of itself.")

		if parent_row not in so_row_names:
			frappe.throw(
				f"'{child_code}' was marked as a Sub Product of an item that isn't "
				"selected to create a Dish for. Please select that item too, or "
				"link to an existing Dish instead."
			)

		if parent_row in child_row_names:
			parent_code = so_rows_by_name[parent_row].item_code
			frappe.throw(
				f"'{child_code}' was marked as a Sub Product of '{parent_code}', but "
				f"'{parent_code}' is itself marked as a Sub Product. Only one level "
				"of nesting is supported."
			)

	# ---- Validate manual_parent_links reference real Dishes ----
	for child_row, parent_dish in manual_parent_links.items():
		child_code = so_rows_by_name.get(child_row).item_code if child_row in so_rows_by_name else child_row

		if child_row not in so_row_names:
			frappe.throw(f"'{child_code}' is marked as a Sub Product but isn't among the selected items.")

		if not frappe.db.exists("Dish", parent_dish):
			frappe.throw(f"Linked parent Dish '{parent_dish}' does not exist.")

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

	def build_dish_header(dish):
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
			# --- already being pulled from PI (unchanged) ---
			dish.customer_name = pi.customer_name
			dish.customer_address = pi.consignee_address
			dish.buyer_address = pi.address
			dish.bueyer_gst_no = pi.buyer_gstin
			dish.customer_gstin = pi.consignee_gstin
			dish.buyers_email = pi.buyers_email
			dish.customers_email = pi.customer_email

			# --- restored: these came from the old PI -> Dish make_dish,
			# but were dropped when Dish creation moved to the Sales Order ---
			dish.buyer = pi.buyer
			dish.buyers_name = pi.buyer_name
			dish.buyers_phone_no = pi.buyers_phone_no
			dish.customer_phone_no = pi.customer_phone_no
			dish.contact_no = pi.buyers_phone_no
			dish.gst_no = pi.buyer_gstin
			dish.warranty = pi.warranty
			dish.mode_terms_of_payment = pi.modeterms_of_payment
			dish.mode_of_dispatch = pi.dispatched_through
			dish.terms_of_delivery = pi.freight_terms
			dish.invoice_to_name = pi.buyer
			dish.invoice_to_address = pi.address
			dish.dispatch_to_name = pi.customer
			dish.dispatch_to_address = pi.consignee_address
			dish.dispatch_state = get_dispatch_state_from_pi(pi)

	def build_item_row(dish, so_row):
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

	# Group Sub Product rows by their in-Sales-Order parent row name,
	# preserving SO order. Rows not appearing in either link dict are
	# plain, top-level Products.
	children_by_parent_row = {}
	for child_row, parent_row in parent_row_links.items():
		children_by_parent_row.setdefault(parent_row, []).append(child_row)

	created_parents = []
	created_children = []

	for so_row in so_rows:
		if so_row.name in child_row_names:
			continue  # created alongside its parent below, or as a manually-linked child

		parent_dish = frappe.new_doc("Dish")
		build_dish_header(parent_dish)
		build_item_row(parent_dish, so_row)
		parent_dish.insert(ignore_permissions=True)
		created_parents.append(parent_dish.name)

		for child_row_name in children_by_parent_row.get(so_row.name, []):
			child_dish = frappe.new_doc("Dish")
			build_dish_header(child_dish)
			child_dish.parent_dish = parent_dish.name
			build_item_row(child_dish, so_rows_by_name[child_row_name])
			child_dish.insert(ignore_permissions=True)
			created_children.append(child_dish.name)

	# ---- Manually-linked children (parent item not on this Sales Order) ----
	for child_row_name, parent_dish_name in manual_parent_links.items():
		child_dish = frappe.new_doc("Dish")
		build_dish_header(child_dish)
		child_dish.parent_dish = parent_dish_name
		build_item_row(child_dish, so_rows_by_name[child_row_name])
		child_dish.insert(ignore_permissions=True)
		created_children.append(child_dish.name)

	frappe.msgprint(
		f"Created {len(created_parents)} Dish document(s) and "
		f"{len(created_children)} child Dish document(s): "
		+ ", ".join(created_parents + created_children)
	)

	return {"parents": created_parents, "children": created_children}