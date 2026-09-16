import frappe


@frappe.whitelist()
def get_so_payment_entries(sales_order):
	rows = frappe.db.sql("""
		select
			pe.name as payment_entry,
			pe.posting_date,
			pe.payment_type,
			pe.mode_of_payment,
			pe.reference_no,
			pe.reference_date,
			per.allocated_amount
		from `tabPayment Entry Reference` per
		inner join `tabPayment Entry` pe on pe.name = per.parent
		where pe.docstatus = 1
			and (
				(per.reference_doctype = 'Sales Order' and per.reference_name = %(so)s)
				or (
					per.reference_doctype = 'Sales Invoice'
					and per.reference_name in (
						select distinct sii.parent
						from `tabSales Invoice Item` sii
						inner join `tabSales Invoice` si on si.name = sii.parent
						where sii.sales_order = %(so)s
							and si.docstatus = 1
					)
				)
			)
		order by pe.posting_date asc, pe.creation asc
	""", {"so": sales_order}, as_dict=True)

	return rows