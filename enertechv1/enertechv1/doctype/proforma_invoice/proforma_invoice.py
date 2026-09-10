# Copyright (c) 2026, Brainmine AI and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt
from frappe.model.naming import getseries
import re
from frappe.utils import getdate, nowdate
from frappe.utils import strip_html_tags

# Add to proforma_invoice.py
# (also add this import near the top of the file)
from enertechv1.enertechv1.doctype.dish.dish import guess_state_from_address_text, get_company_gst_state

def html_to_text_with_breaks(html):
	"""Convert HTML to plain text while preserving line breaks."""
	if not html:
		return ""

	# <br>, <br/>, <br /> -> newline
	text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)

	# closing block tags -> newline
	text = re.sub(r"</(p|div|li|tr|h[1-6])>", "\n", text, flags=re.IGNORECASE)

	# strip remaining tags
	text = strip_html_tags(text)

	# clean up: trim each line, collapse 3+ newlines into 2
	lines = [line.strip() for line in text.split("\n")]
	text = "\n".join(lines)
	text = re.sub(r"\n{3,}", "\n\n", text).strip()

	return text


class ProformaInvoice(Document):

	def before_insert(self):
		self.generate_series()

	def validate(self):
		self.validate_rate()

	def before_save(self):
		self.validate_rate()
		self.calculate_totals()

	def before_submit(self):
		buyer = self.create_customer(self.buyer)
		customer = self.create_customer(self.customer)
		# Set the buyer as the customer for the invoice
		self.buyer = buyer
		self.set_customer_email(buyer)
		self.send_proforma_email()


	def validate_rate(self):
		# Default status
		self.approval_status = "Approved"

		# Check every item
		for row in self.items:

			# Get the selling rate from Item Master
			selling_rate = frappe.db.get_value(
				"Item",
				row.item,
				"custom_selling_rate"
			) or 0

			# If any item's rate is less than the Item Master selling rate,
			# mark the document as needing approval.
			if flt(row.rate) < flt(selling_rate):
				self.approval_status = "Needs Approval"
				break


	def create_customer(self, customer_name=None):
		"""Create Customer if it does not already exist, return the customer name (str)."""

		customer = frappe.db.exists("Customer", {"customer_name": customer_name}, "name")

		# Customer already exists
		if customer:
			return customer

		# Create new Customer
		customer_doc = frappe.get_doc({
			"doctype": "Customer",
			"customer_name": customer_name,
			"customer_type": "Company",
			"customer_group": "Commercial",
			"territory": "All Territories"
		})

		customer_doc.insert(ignore_permissions=True)

		frappe.msgprint(f"Customer {customer_doc.name} created successfully.")

		return customer_doc.name

	def get_quotation_email(self):
		"""Resolve the client email from the linked Quotation (or its Lead/Opportunity)."""

		quotation = frappe.get_doc("Quotation", self.quotation)

		email = None

		if quotation.contact_email:
			email = quotation.contact_email

		if not email and quotation.party_name:
			email = frappe.db.get_value(
				"Lead",
				quotation.party_name,
				"email_id"
			)

		if not email:
			opportunity = frappe.db.get_value(
				"Opportunity",
				{"party_name": quotation.party_name},
				["contact_email"],
				as_dict=True
			)

			if opportunity:
				email = opportunity.contact_email

		return email


	def set_customer_email(self, customer):
		"""Attach the client email to the Customer directly if the Customer doctype
		has an email field. If not, fall back to creating/linking a Contact with
		the email instead.

		customer: the Customer name (str) returned by create_customer().
		"""

		email = self.get_quotation_email()

		if not email:
			return

		customer_doc = frappe.get_doc("Customer", self.buyer)

		# Try common direct-email field names on Customer first.
		for fieldname in ("email_id", "custom_email_id", "custom_email"):
			if customer_doc.meta.has_field(fieldname):
				customer_doc.db_set(fieldname, email)
				return

		# No direct email field on Customer -> fall back to Contact.
		self.create_contact(customer, email)


	def create_contact(self, customer, email=None):
		"""Create Contact and link it with Customer.

		customer: the Customer name (str) returned by create_customer().
		email: email to attach to the contact (already resolved by caller).
		"""

		quotation = frappe.get_doc("Quotation", self.quotation)

		if email is None:
			email = self.get_quotation_email()

		# -------------------------------
		# Get Phone
		# -------------------------------
		phone = None

		if quotation.party_name:
			phone = frappe.db.get_value(
				"Lead",
				quotation.party_name,
				"phone"
			)

		# -------------------------------
		# Check Existing Contact
		# -------------------------------
		if email:
			existing_contact = frappe.db.get_value(
				"Contact Email",
				{"email_id": email},
				"parent"
			)

			if existing_contact:
				return existing_contact

		# -------------------------------
		# Create Contact
		# -------------------------------
		contact = frappe.get_doc({
			"doctype": "Contact",
			"first_name": self.customer,
			"email_ids": [],
			"phone_nos": [],
			"links": [{
				"link_doctype": "Customer",
				"link_name": customer
			}]
		})

		if email:
			contact.append("email_ids", {
				"email_id": email,
				"is_primary": 1
			})

		if phone:
			contact.append("phone_nos", {
				"phone": phone,
				"is_primary_phone": 1
			})

		contact.insert(ignore_permissions=True)

		return contact.name


	def send_proforma_email(self):
		"""Send Proforma Invoice Email"""

		client_email = self.get_quotation_email()

		if not client_email:
			frappe.throw("No client email found.")

		# =====================================
		# SALESPERSON
		# =====================================
		salesperson_email = frappe.db.get_value(
			"User",
			self.owner,
			"email"
		)

		owner = frappe.get_doc("User", self.owner)

		owner_name = owner.full_name or self.owner
		owner_email = owner.email or ""
		owner_mobile = owner.mobile_no or ""

		owner_designation = frappe.db.get_value(
			"Employee",
			{"user_id": self.owner},
			"designation"
		) or ""

		# =====================================
		# SUBJECT
		# =====================================
		subject = "Proforma Invoice (PI) for EnerTech Solar & Power Products Solution"

		# =====================================
		# EMAIL BODY
		# =====================================
		message = f"""
		<p>Dear <b>{self.customer}</b>,</p>

		<p>Greetings from <b>EnerTech UPS Pvt. Ltd.</b></p>

		<p>
		Thank you for your valuable inquiry and for considering
		EnerTech as your trusted partner for advanced
		Solar & Power Products Solution.
		</p>

		<p>
		As per your requirement, we have prepared the
		<b>Proforma Invoice (PI)</b> for the proposed system.
		Please find the attached PI for your review and kind consideration.
		</p>

		<h4>Why Choose EnerTech?</h4>

		<p>
		EnerTech is one of India's leading manufacturers of
		Solar Hybrid Inverters,
		Solar Inverters,
		Battery Energy Storage Systems (BESS),
		Online UPS,
		Static Frequency Converter,
		Servo Voltage Stabilizer,
		Industrial Battery Charger and
		Industrial Power Backup Solutions,
		with over <b>35 years of experience</b>.
		</p>

		<p>
		We are confident that our solution will provide reliable,
		efficient and long-term energy savings for your application.
		</p>

		<p>
		Should you require any modifications to the quotation,
		technical clarification,
		or commercial discussion,
		please feel free to contact us.
		We would be pleased to assist you.
		</p>

		<p>
		We look forward to receiving your valuable order and
		establishing a long-term business relationship.
		</p>

		<br>

		<p>
		Best Regards,
		</p>

		<p>
		<b>{owner_name}</b><br>
		{owner_designation}<br><br>

		<b>EnerTech UPS Pvt. Ltd.</b><br>

		🌐 www.enertechups.com<br>

		📧 {owner_email}<br>

		📞 {owner_mobile}
		</p>
		"""

		# =====================================
		# PDF
		# =====================================
		pdf_data = frappe.get_print(
				self.doctype,
				self.name,
				print_format="Proforma Invoice Print 2",
				as_pdf=True
		)

		attachments = [{
			"fname": f"{self.name}.pdf",
			"fcontent": pdf_data
		}]

		# =====================================
		# Attach uploaded files
		# =====================================
		files = frappe.get_all(
			"File",
			filters={
				"attached_to_doctype": self.doctype,
				"attached_to_name": self.name
			},
			fields=[
				"file_name",
				"file_url"
			]
		)

		for file in files:
			try:
				file_doc = frappe.get_doc(
					"File",
					{"file_url": file.file_url}
				)

				attachments.append({
					"fname": file.file_name,
					"fcontent": file_doc.get_content()
				})

			except Exception:
				frappe.log_error(
					frappe.get_traceback(),
					f"Unable to attach {file.file_name}"
				)

		# =====================================
		# SEND EMAIL
		# =====================================
		frappe.sendmail(
			recipients=[client_email],
			sender=salesperson_email,
			cc=[
				"sales@enertechups.com",
				"marketing@enertechups.com"
			],
			subject=subject,
			message=message,
			attachments=attachments,
			expose_recipients="header",
			now=True,
			send_priority=0
		)




	@frappe.whitelist()
	def generate_series(self):
		"""Generate PI number. Numbers are never reused, even from cancelled docs."""
		today = getdate(nowdate())
		year = str(today.year)[2:]
		month = f"{today.month:02d}"
		prefix = f"EUPL/{year}/{month}/"

		rows = frappe.db.sql("""
			select name, proforma_invoice_no
			from `tabProforma Invoice`
			where name like %(p)s or proforma_invoice_no like %(p)s
		""", {"p": f"{prefix}%"}, as_dict=True)

		pattern = re.compile(r"^" + re.escape(prefix) + r"(\d+)")

		max_number = 0
		for row in rows:
			for value in (row.proforma_invoice_no, row.name):
				if not value:
					continue
				match = pattern.match(value)
				if match:
					max_number = max(max_number, int(match.group(1)))

		next_number = max_number + 1
		series = f"{prefix}{next_number:03d}"

		# safety net against any leftover row occupying the name
		while frappe.db.exists("Proforma Invoice", series):
			next_number += 1
			series = f"{prefix}{next_number:03d}"

		self.proforma_invoice_no = series
		self.naming_series = series


	def calculate_totals(self):
		"""
		Recalculate item amounts, GST and Proforma Invoice totals
		every time the document is saved.

		In-State:
			- CGST + SGST applicable
			- IGST forced to 0

		Out-State:
			- IGST applicable
			- CGST + SGST forced to 0

		Manually entered GST rates are respected and GST amounts
		are recalculated based on the entered rates.
		"""

		total = 0
		total_gst = 0

		# --------------------------------------------------
		# Get tax category
		# --------------------------------------------------
		tax_category = self.tax_category

		# --------------------------------------------------
		# Calculate every item
		# --------------------------------------------------
		for item in self.items:

			# ----------------------------------------------
			# Calculate item amount
			# ----------------------------------------------
			quantity = flt(item.quantity)
			rate = flt(item.rate)

			item.amount = quantity * rate

			base_amount = flt(item.amount)

			# Add to subtotal
			total += base_amount

			# ----------------------------------------------
			# Reset GST amounts
			# ----------------------------------------------
			item.custom_cgst_amount = 0
			item.custom_sgst_amount = 0
			item.custom_igst_amount = 0

			# ----------------------------------------------
			# IN-STATE
			# ----------------------------------------------
			if tax_category == "In-State":

				# IGST is not applicable for In-State
				item.custom_igst_rate = 0
				item.custom_igst_amount = 0

				# Default CGST rate if empty or zero
				if not flt(item.custom_cgst_rate):
					item.custom_cgst_rate = 9

				# Default SGST rate if empty or zero
				if not flt(item.custom_sgst_rate):
					item.custom_sgst_rate = 9

				# Calculate CGST
				item.custom_cgst_amount = (
					base_amount * flt(item.custom_cgst_rate)
				) / 100

				# Calculate SGST
				item.custom_sgst_amount = (
					base_amount * flt(item.custom_sgst_rate)
				) / 100

			# ----------------------------------------------
			# OUT-STATE
			# ----------------------------------------------
			elif tax_category == "Out-State":

				# CGST and SGST are not applicable for Out-State
				item.custom_cgst_rate = 0
				item.custom_sgst_rate = 0

				item.custom_cgst_amount = 0
				item.custom_sgst_amount = 0

				# Default IGST rate if empty
				if item.custom_igst_rate is None or item.custom_igst_rate == "":
					item.custom_igst_rate = 18

				# Calculate IGST
				item.custom_igst_amount = (
					base_amount * flt(item.custom_igst_rate)
				) / 100

			# ----------------------------------------------
			# No tax category
			# ----------------------------------------------
			else:
				item.custom_cgst_rate = 0
				item.custom_sgst_rate = 0
				item.custom_igst_rate = 0

				item.custom_cgst_amount = 0
				item.custom_sgst_amount = 0
				item.custom_igst_amount = 0

			# ----------------------------------------------
			# Add item GST to total GST
			# ----------------------------------------------
			total_gst += (
				flt(item.custom_cgst_amount)
				+ flt(item.custom_sgst_amount)
				+ flt(item.custom_igst_amount)
			)

		# --------------------------------------------------
		# Update Proforma Invoice totals
		# --------------------------------------------------
		self.total = total
		self.total_gst = total_gst
		self.total_with_gst = total + total_gst


@frappe.whitelist()
def ping_test():
	return "pong from proforma_invoice.py"

@frappe.whitelist()
def make_dish(source_name, target_doc=None):
	"""Map a Proforma Invoice into a new Dish, carrying over buyer/order/item data."""

	proforma_invoice = frappe.get_doc("Proforma Invoice", source_name)
	quotation = frappe.get_doc("Quotation", proforma_invoice.quotation , "name")
	lead = frappe.get_doc("Lead", quotation.party_name)

	dish = frappe.new_doc("Dish")
	dish.buyer = proforma_invoice.buyer
	dish.buyers_name = proforma_invoice.buyer_name
	dish.buyers_email = proforma_invoice.buyers_email
	dish.buyers_phone_no = proforma_invoice.buyers_phone_no
	dish.bueyer_gst_no = proforma_invoice.buyer_gstin
	dish.buyer_address = proforma_invoice.address
	dish.customer = proforma_invoice.customer
	dish.customer_name = proforma_invoice.customer_name
	dish.customer_phone_no = proforma_invoice.customer_phone_no
	dish.customer_gstin = proforma_invoice.consignee_gstin
	dish.customer_address = proforma_invoice.consignee_address
	dish.delivery_date = proforma_invoice.delivery_date
	dish.proforma_invoice = proforma_invoice.name
	dish.buyers_email = proforma_invoice.buyers_email
	dish.customers_email = proforma_invoice.customer_email
	dish.quotation = proforma_invoice.quotation
	dish.tax_category = proforma_invoice.tax_category
	dish.date = frappe.utils.today()
	dish.dispatch_state = lead.custom_state

	dish.customer = proforma_invoice.buyer
	dish.contact_no = proforma_invoice.buyers_phone_no
	dish.gst_no = proforma_invoice.buyer_gstin

	dish.expected_delivery = proforma_invoice.delivery_date
	dish.warranty = proforma_invoice.warranty
	dish.mode_terms_of_payment = proforma_invoice.modeterms_of_payment
	dish.mode_of_dispatch = proforma_invoice.dispatched_through
	dish.terms_of_delivery = proforma_invoice.freight_terms

	dish.invoice_to_name = proforma_invoice.buyer
	dish.invoice_to_address = proforma_invoice.address

	dish.dispatch_to_name = proforma_invoice.customer
	dish.dispatch_to_address = proforma_invoice.consignee_address

	dish.sub_total = proforma_invoice.total
	dish.gst_amount = proforma_invoice.total_gst
	dish.total = proforma_invoice.total_with_gst

	for row in proforma_invoice.items:
		dish.append("items", {
			"item_code": row.item,
			"item_name":row.item_name,
			"qty": row.quantity,
			"warrenty":row.warranty_years,
			"uom": row.uom,
			"rate": row.rate,
			"amount": row.amount,
			"description": row.description,
			"hsn_code": row.gst_hsn_code,
			"cgst_rate": row.custom_cgst_rate,
			"cgst_amt": row.custom_cgst_amount,
			"sgst_rate": row.custom_sgst_rate,
			"sgst_amount": row.custom_sgst_amount,
			"igst_rate": row.custom_igst_rate,
			"igst_amt": row.custom_igst_amount,
		})

	return dish

@frappe.whitelist()
def make_proforma_invoice(source_name, target_doc=None):
	quotation = frappe.get_doc("Quotation", source_name)

	# ---- Resolve Opportunity (guard: quotation may not have one linked) ----
	opportunity_name = quotation.get("custom_opportunity_reference")
	if not opportunity_name:
		frappe.throw("This Quotation has no linked Opportunity (custom_opportunity_reference is empty).")

	opportunity = frappe.get_doc("Opportunity", opportunity_name)

	# ---- Resolve Lead (guard: party may be a Customer, not a Lead) ----
	lead = None
	if opportunity.party_name and opportunity.opportunity_from == "Lead":
		lead = frappe.get_doc("Lead", opportunity.party_name)

	customer = opportunity.contact_person
	customer_phone = opportunity.phone or opportunity.contact_mobile or opportunity.phone_ext
	customer_email = opportunity.contact_email

	proforma_invoice = frappe.new_doc("Proforma Invoice")
	proforma_invoice.modeterms_of_payment = quotation.payment_terms_template
	proforma_invoice.buyer_gstin = lead.custom_gst_number if lead else None
	proforma_invoice.quotation = quotation.name
	proforma_invoice.date = frappe.utils.today()
	proforma_invoice.buyer = quotation.customer_name or quotation.party_name
	proforma_invoice.buyer_name = customer
	proforma_invoice.buyers_email = customer_email
	proforma_invoice.buyers_phone_no = customer_phone
	proforma_invoice.address = lead.custom_address
	proforma_invoice.total = quotation.total
	proforma_invoice.total_gst = quotation.custom_total_gst
	proforma_invoice.total_with_gst = quotation.custom_total_with_gst
	proforma_invoice.tax_category = quotation.custom_tax_category

	for item in quotation.items:
		proforma_invoice.append("items", {
			"item": item.item_code,
			"item_name": item.item_name,
			"description": html_to_text_with_breaks(item.description or item.description or ""),
			"quantity": item.qty,
			"warranty_years": item.custom_warrenty_years,
			"uom": item.uom,
			"gst_hsn_code": item.gst_hsn_code,
			"rate": item.rate,
			"amount": item.amount,
			"custom_cgst_rate": item.custom_cgst_rate,
			"custom_cgst_amount": item.custom_cgst_amount,
			"custom_igst_rate": item.custom_igst_rate,
			"custom_cgst_amount": item.custom_cgst_amount,
			"custom_sgst_rate": item.custom_sgst_rate,
			"custom_sgst_amount": item.custom_sgst_amount,
			"custom_igst_amount": item.custom_igst_amount,
		})

	return proforma_invoice


def generate_sales_order_series(doc, method=None):
	if not doc.is_new():
		return

	today = getdate(nowdate())
	year = str(today.year)[2:]
	month = f"{today.month:02d}"

	series_key = f"SO-{year}"
	number = getseries(series_key, 3)

	doc.custom_sales_order_no = f"EUPL/SO/{year}/{month}/{number}"



@frappe.whitelist()
def make_sales_order(source_name, target_doc=None):
	source = frappe.get_doc("Proforma Invoice", source_name)

	# ---------------------------------------------------------
	# 1. Resolve Customer
	#    (buyer becomes a real Customer link once PI is submitted;
	#     fall back to a name lookup just in case)
	# ---------------------------------------------------------
	customer = None

	if source.buyer and frappe.db.exists("Customer", source.buyer):
		customer = source.buyer
	else:
		customer = frappe.db.get_value(
			"Customer",
			{"customer_name": source.buyer or source.customer},
			"name"
		)

	if not customer:
		frappe.throw(
			f"Customer '{source.buyer or source.customer}' not found. "
			"Please submit the Proforma Invoice (which creates the Customer) "
			"before creating a Sales Order."
		)

	# ---------------------------------------------------------
	# 2. Prevent duplicate Sales Order from same PI
	# ---------------------------------------------------------
	# existing_so = frappe.db.exists(
	# 	"Sales Order",
	# 	{"custom_proforma_invoice": source.name}
	# )

	# if existing_so:
	# 	frappe.throw(
	# 		f"Sales Order {existing_so} already exists for Proforma Invoice {source.name}."
	# 	)

	# ---------------------------------------------------------
	# 3. Build Sales Order
	# ---------------------------------------------------------
	sales_order = frappe.new_doc("Sales Order")
	sales_order.company = source.company or frappe.defaults.get_user_default("Company")
	sales_order.ignore_pricing_rule = 1
	sales_order.customer = customer
	sales_order.custom_quotation = source.quotation
	sales_order.custom_proforma_invoice = source.name

	if source.date:
		sales_order.transaction_date = source.date

	sales_order.delivery_date = source.delivery_date

	if source.tax_category:
		sales_order.tax_category = source.tax_category

	# ---------------------------------------------------------
	# 4. Add Items
	# ---------------------------------------------------------
	if not source.items:
		frappe.throw(f"Proforma Invoice {source.name} does not contain any items.")

	for row in source.items:

		item = sales_order.append("items", {
			"item_code": row.item,
			"item_name": row.item_name,
			"qty": row.quantity,
			"uom": row.uom,
			"rate": row.rate,
			"delivery_date": source.date,
		})

		if hasattr(item, "cgst_rate") and row.custom_cgst_rate:
			item.cgst_rate = row.custom_cgst_rate

		if hasattr(item, "sgst_rate") and row.custom_sgst_rate:
			item.sgst_rate = row.custom_sgst_rate

		if hasattr(item, "igst_rate") and row.custom_igst_rate:
			item.igst_rate = row.custom_igst_rate

	# ---------------------------------------------------------
	# 5. Determine GST rates across all items (same validation as Dish)
	# ---------------------------------------------------------
	cgst_rates, sgst_rates, igst_rates = set(), set(), set()

	for row in source.items:
		cgst = float(row.custom_cgst_rate or 0)
		sgst = float(row.custom_sgst_rate or 0)
		igst = float(row.custom_igst_rate or 0)

		if cgst > 0:
			cgst_rates.add(cgst)
		if sgst > 0:
			sgst_rates.add(sgst)
		if igst > 0:
			igst_rates.add(igst)

	if len(cgst_rates) > 1:
		frappe.throw(
			f"Proforma Invoice {source.name} contains multiple CGST rates: "
			f"{', '.join(str(x) for x in sorted(cgst_rates))}%. "
			"Please use item-level tax configuration for different GST rates."
		)
	if len(sgst_rates) > 1:
		frappe.throw(
			f"Proforma Invoice {source.name} contains multiple SGST rates: "
			f"{', '.join(str(x) for x in sorted(sgst_rates))}%. "
			"Please use item-level tax configuration for different GST rates."
		)
	if len(igst_rates) > 1:
		frappe.throw(
			f"Proforma Invoice {source.name} contains multiple IGST rates: "
			f"{', '.join(str(x) for x in sorted(igst_rates))}%. "
			"Please use item-level tax configuration for different GST rates."
		)

	cgst_rate = next(iter(cgst_rates), 0)
	sgst_rate = next(iter(sgst_rates), 0)
	igst_rate = next(iter(igst_rates), 0)

	# ---------------------------------------------------------
	# 6. GST Transaction Type
	# ---------------------------------------------------------
	tax_category = (source.tax_category or "").strip().lower()

	is_out_state = tax_category in (
		"out-state", "out state", "out-stage", "out stage",
		"inter-state", "inter state",
	)
	is_in_state = tax_category in (
		"in-state", "in state", "in-stage", "in stage",
		"intra-state", "intra state",
	)

	if not is_out_state and not is_in_state:
		frappe.throw(
			f"Invalid Tax Category '{source.tax_category}' in Proforma Invoice {source.name}. "
			"Expected In-State or Out-State."
		)

	# ---------------------------------------------------------
	# 7. Resolve Place of Supply from address text, cross-check tax_category
	# ---------------------------------------------------------
	customer_place_of_supply = guess_state_from_address_text(source.address)

	if not customer_place_of_supply:
		frappe.throw(
			f"Could not detect a state name in Proforma Invoice {source.name}'s address text "
			f"('{source.address or ''}'). Please fix the address so GST place of supply "
			"can be determined before creating a Sales Order."
		)

	sales_order.place_of_supply = customer_place_of_supply
	actual_state_code = customer_place_of_supply.split("-")[0]
	company_state_code = get_company_gst_state(sales_order.company)

	actually_in_state = (actual_state_code == company_state_code)
	if actually_in_state != is_in_state:
		frappe.throw(
			f"Proforma Invoice {source.name}: tax_category says "
			f"{'In-State' if is_in_state else 'Out-State'}, but the address text "
			f"resolves to {customer_place_of_supply}, which is "
			f"{'in-state' if actually_in_state else 'out-state'}. "
			"Please fix the address or tax_category."
		)

	# ---------------------------------------------------------
	# 8. Add GST Taxes
	# ---------------------------------------------------------
	if is_out_state:
		if igst_rate <= 0:
			if cgst_rate > 0 and sgst_rate > 0:
				igst_rate = cgst_rate + sgst_rate
			else:
				frappe.throw(
					f"Proforma Invoice {source.name} is marked as Out-State "
					"but no valid IGST rate was found."
				)

		sales_order.append("taxes", {
			"charge_type": "On Net Total",
			"account_head": "Output Tax IGST - EUPL",
			"description": f"IGST {igst_rate}%",
			"rate": igst_rate,
		})

	elif is_in_state:
		if cgst_rate <= 0 or sgst_rate <= 0:
			if igst_rate > 0:
				cgst_rate = igst_rate / 2
				sgst_rate = igst_rate / 2
			else:
				frappe.throw(
					f"Proforma Invoice {source.name} is marked as In-State "
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
	# 9. Custom GST Total
	# ---------------------------------------------------------
	if hasattr(sales_order, "custom_total_gst"):
		sales_order.custom_total_gst = source.total_gst or 0

	# ---------------------------------------------------------
	# 10. Insert the Sales Order
	# ---------------------------------------------------------
	sales_order.insert(ignore_permissions=True)

	sales_order.add_comment(
		"Info",
		f"Auto-created from Proforma Invoice {source.name}"
	)

	frappe.msgprint(
		f"Sales Order {sales_order.name} created successfully."
	)

	return sales_order.name