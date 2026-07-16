# Copyright (c) 2026, Brainmine AI and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt
from frappe.model.naming import getseries
import re
from frappe.utils import getdate, nowdate
from frappe.utils import strip_html_tags

class ProformaInvoice(Document):

	def before_insert(self):
		self.generate_series()

	def validate(self):
		self.validate_rate()

	def before_save(self):
		self.validate_rate()

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
		"""
		Generate PI number only on submit.
		Finds the MAX number in the sequence, ignores amended/cancelled docs.
		Next number = max + 1 (always increments, never reuses gaps).
		"""
		today = getdate(nowdate())
		year = str(today.year)[2:]
		month = f"{today.month:02d}"
		prefix = f"EUPL/{year}/{month}/"

		# Get ALL PIs for this year/month (including amended ones)
		all_pis = frappe.get_all(
			"Proforma Invoice",
			filters=[
				["proforma_invoice_no", "like", f"{prefix}%"]
			],
			fields=["proforma_invoice_no", "docstatus"]
		)

		max_number = 0

		for pi in all_pis:
			# Skip amended/cancelled docs (docstatus=2)
			if pi.docstatus == 2:
				continue

			# Extract the number from "EUPL/26/01/045"
			try:
				parts = pi.proforma_invoice_no.split("/")
				if len(parts) == 4:
					num = int(parts[3])
					max_number = max(max_number, num)
			except (ValueError, IndexError):
				pass

		# Next number is always max + 1
		next_number = max_number + 1
		number = f"{next_number:03d}"  # zero-padded to 3 digits

		series = f"{prefix}{number}"
		self.proforma_invoice_no = series
		self.naming_series = series

@frappe.whitelist()
def ping_test():
	return "pong from proforma_invoice.py"

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
	proforma_invoice.address = quotation.get("custom_address")
	proforma_invoice.total = quotation.total
	proforma_invoice.total_gst = quotation.custom_total_gst
	proforma_invoice.total_with_gst = quotation.custom_total_with_gst

	for item in quotation.items:
		proforma_invoice.append("items", {
			"item": item.item_code,
			"item_name": item.item_name,
			"description": strip_html_tags(item.technical_description or item.description or ""),
			"quantity": item.qty,
			"warranty_years": item.warranty_years,
			"uom": item.uom,
			"gst_hsn_code": item.gst_hsn_code,
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
			"qty": row.quantity,
			"uom": row.uom,
			"rate": row.rate,
			"amount": row.amount,
			"description": row.description,
			"hsn_code": row.gst_hsn_code,
			"cgst_rate": row.custom_cgst_rate,
			"cgst_amount": row.custom_cgst_amount,
			"sgst_rate": row.custom_sgst_rate,
			"sgst_amount": row.custom_sgst_amount,
			"igst_rate": row.custom_igst_rate,
			"igst_amount": row.custom_igst_amount,
		})

	return dish