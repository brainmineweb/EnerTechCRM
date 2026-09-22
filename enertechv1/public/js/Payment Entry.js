frappe.ui.form.on("Payment Entry", {
	paid_amount(frm) {
		validate_paid_amount_vs_outstanding(frm);
	},
	validate(frm) {
		validate_paid_amount_vs_outstanding(frm);
	}
});

function validate_paid_amount_vs_outstanding(frm) {
	const total_outstanding = (frm.doc.references || []).reduce(
		(sum, row) => sum + flt(row.outstanding_amount),
		0
	);

	if (!total_outstanding) return;

	if (flt(frm.doc.paid_amount) > total_outstanding) {
		frappe.msgprint(
			__("Paid Amount should be equal to or less than Outstanding Amount ({0})", [
				format_currency(total_outstanding, frm.doc.paid_to_account_currency)
			])
		);
		frm.set_value("paid_amount", total_outstanding);
	}
}