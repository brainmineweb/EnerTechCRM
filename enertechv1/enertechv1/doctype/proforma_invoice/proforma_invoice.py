# Copyright (c) 2026, Brainmine AI and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt
from frappe.model.naming import getseries
import re
from frappe.utils import getdate, nowdate


class ProformaInvoice(Document):

	def before_insert(self):
		self.generate_series()

	def before_save(self):
		self.validate_rate()

	def before_submit(self):
		buyer = self.create_customer(self.buyer)
		customer = self.create_customer(self.customer)
		# Set the buyer as the customer for the invoice
		self.buyer = buyer
		self.set_customer_email(buyer)
		# self.send_proforma_email()


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

		customer = frappe.db.exists("Customer", {"customer_name": customer_name} , "name")

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
				print_format="proforma invoice 2",
				as_pdf=True,
				pdf_generator="chrome"
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
		today = getdate(nowdate())
		year = str(today.year)[2:]
		month = f"{today.month:02d}"

		series_key = f"PI-{year}"          # scoped to year -> resets automatically each year
		number = getseries(series_key, 3)  # returns zero-padded string, e.g. "00001"

		series = f"EUPL/{year}/{month}/{number}"
		self.proforma_invoice_no = series
		self.naming_series = series


@frappe.whitelist()
def ping_test():
	return "pong from proforma_invoice.py"

@frappe.whitelist()
def make_proforma_invoice(source_name, target_doc=None):
	opportunity = frappe.get_doc("Opportunity", frappe.get_value("Quotation", source_name, "custom_opportunity_reference"))
	customer = opportunity.contact_person
	customer_phone = opportunity.phone or opportunity.contact_mobile or opportunity.phone_ext
	customer_email = opportunity.contact_email
	quotation = frappe.get_doc("Quotation", source_name)
	proforma_invoice = frappe.new_doc("Proforma Invoice")

	proforma_invoice.quotation = quotation.name
	proforma_invoice.date = frappe.utils.today()
	proforma_invoice.buyer = quotation.customer_name or quotation.party_name
	proforma_invoice.buyer_name = customer
	proforma_invoice.buyers_email = customer_email
	proforma_invoice.buyers_phone_no = customer_phone
	proforma_invoice.buyer_gstin = quotation.get("billing_address_gstin")
	proforma_invoice.address = quotation.get("custom_address")
	proforma_invoice.total = quotation.total
	proforma_invoice.total_gst = quotation.custom_total_gst
	proforma_invoice.total_with_gst = quotation.custom_total_with_gst

	for item in quotation.items:
		proforma_invoice.append("items", {
			"item": item.item_code,
			"quantity": item.qty,
			"uom": item.uom,
			"rate": item.rate,
			"amount": item.amount,
			"custom_cgst_rate": item.custom_cgst_rate,
            "custom_cgst_amount": item.custom_cgst_amount,
	        "custom_sgst_rate": item.custom_sgst_rate,
             "custom_sgst_amount": item.custom_sgst_amount,
            "custom_igst_rate": item.custom_igst_rate,
            "custom_igst_amount": item.custom_igst_amount,
		})

	return proforma_invoice

@frappe.whitelist()
def make_sales_order(source_name, target_doc=None):
	source = frappe.get_doc("Proforma Invoice", source_name)

	customer = frappe.db.get_value(
		"Customer",
		{"customer_name": source.customer},
		"name"
	)
	buyer = frappe.db.get_value(
		"Customer",
		{"customer_name": source.buyer},
		"name"
	)
	if not customer:
		frappe.throw(f"Customer '{source.customer}' not found. Please submit the Proforma Invoice first so the Customer is created.")

	sales_order = frappe.new_doc("Sales Order")
	sales_order.ignore_pricing_rule = 1

	sales_order.custom_buyer = buyer
	sales_order.custom_buyers_name = source.buyer
	sales_order.custom_buyers_gstin = source.buyer_gstin
	sales_order.custom_buyers_address = source.address
	sales_order.custom_buyers_order_no = source.buyers_order_no
	sales_order.customer = customer
	sales_order.transaction_date = source.date
	sales_order.delivery_date = source.delivery_date or source.date
	sales_order.custom_order_date = source.buyers_order_date
	sales_order.custom_warrenty = source.warranty
	sales_order.custom_freight_terms = source.freight_terms
	sales_order.custom_dispatched_through = source.dispatched_through
	sales_order.custom_address = source.consignee_address
	sales_order.custom_modeterms_of_payment = source.modeterms_of_payment
	sales_order.custom_customers_address = source.consignee_address
	sales_order.customer = source.customer
	sales_order.custom_quotation = source.quotation
	sales_order.custom_proforma_invoice = source.name
	sales_order.custom_buyers_phone_no = source.buyers_phone_no
	sales_order.custom_customers_phone_no = source.customer_phone_no
	sales_order.custom_customer_gstin = source.consignee_gstin
	sales_order.custom_customers_phone_no = source.customer_phone_no

	if sales_order.meta.has_field("custom_proforma_invoice"):
		sales_order.custom_proforma_invoice = source.name

	# Copy Items
	for row in source.items:
		item = frappe.get_cached_doc("Item", row.item)

		so_item = sales_order.append("items", {
			"item_code": row.item,
			"item_name": item.item_name,
			"qty": row.quantity,
			"uom": row.uom,
			"rate": row.rate,
			"price_list_rate": row.rate,
			"delivery_date": source.delivery_date or source.date,
			"item_tax_template": None,
		})
		so_item.ignore_pricing_rule = 1

	# Keep taxes table empty
	sales_order.taxes_and_charges = None
	sales_order.taxes = []

	# -----------------------------------------------------------------
	# Insert directly on the server. Because there's no unsaved form
	# opened in the browser for this document, the client-side item-tax
	# auto-add logic never runs — it only fires on form load/refresh,
	# which we're skipping entirely.
	# -----------------------------------------------------------------
	sales_order.insert(ignore_permissions=True)

	# Server-side validate/calculate_taxes_and_totals also runs during
	# insert(), so re-assert an empty taxes table AFTER insert in case
	# anything repopulated it during save, then save again if needed.
	if sales_order.taxes:
		sales_order.taxes = []
		sales_order.save(ignore_permissions=True)

	frappe.msgprint(f"Sales Order {sales_order.name} created successfully.")

	return sales_order.name



def generate_sales_order_series(doc, method=None):
	if not doc.is_new():
		return

	today = getdate(nowdate())
	year = str(today.year)[2:]
	month = f"{today.month:02d}"

	series_key = f"SO-{year}"           # independent counter, resets each year
	number = getseries(series_key, 3)

	doc.custom_sales_order_no = f"EUPL/SO/{year}/{month}/{number}"


@frappe.whitelist()
def make_dish(source_name, target_doc=None):
	"""Map a Proforma Invoice into a new Dish, carrying over buyer/order/item data."""

	proforma_invoice = frappe.get_doc("Proforma Invoice", source_name)

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
	dish.date = frappe.utils.today()

	dish.customer = proforma_invoice.buyer
	dish.contact_no = proforma_invoice.buyers_phone_no
	dish.gst_no = proforma_invoice.buyer_gstin

	dish.expected_delivery = proforma_invoice.delivery_date
	dish.warranty = proforma_invoice.warranty
	dish.mode_terms_of_payment = proforma_invoice.modeterms_of_payment
	dish.mode_of_dispatch = proforma_invoice.dispatched_through
	dish.terms_of_delivery = proforma_invoice.freight_terms

	dish.dispatch_to_name = proforma_invoice.buyer
	dish.dispatch_to_address = proforma_invoice.consignee_address

	dish.sub_total = proforma_invoice.total
	dish.gst_amount = proforma_invoice.total_gst
	dish.total = proforma_invoice.total_with_gst

	for row in proforma_invoice.items:
		dish.append("items", {
			"item_code": row.item,
			"qty": row.quantity,
			"uom": row.uom,
			"rate": row.rate,
			"amount": row.amount,
		})

	return dish


