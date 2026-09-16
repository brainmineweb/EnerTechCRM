frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		if (frm.doc.__islocal) return;

		frappe.call({
			method: "enertechv1.custom.sales_order.get_so_payment_entries",
			args: { sales_order: frm.doc.name },
			callback: (r) => populate_payment_table(frm, r.message || []),
		});

		frm.add_custom_button("Create Dish", () => {
			frappe.call({
				method: "enertechv1.enertechv1.doctype.dish.dish.create_dishes_from_sales_order",
				args: { sales_order_name: frm.doc.name },
				freeze: true,
				freeze_message: "Creating Dish documents...",
				callback: () => frm.reload_doc(),
			});
		});
	},
});

function populate_payment_table(frm, rows) {
	frappe.model.clear_table(frm.doc, "custom_so_payment_details");

	let total_received = 0;

	rows.forEach((row) => {
		const child = frappe.model.add_child(
			frm.doc,
			"Sales Order Payment Details",
			"custom_so_payment_details"
		);

		child.payment_entry = row.payment_entry;
		child.date = row.posting_date;
		child.payment_type = row.payment_type;
		child.mode_of_payment = row.mode_of_payment;
		child.reference_no = row.reference_no;
		child.reference_date = row.reference_date;
		child.allocated_amount = row.allocated_amount;

		total_received += flt(row.allocated_amount);
	});

	frm.refresh_field("custom_so_payment_details");

	const balance_remaining = flt(frm.doc.grand_total) - total_received;

	frm.set_value("custom_total_received", total_received);
	frm.set_value("custom_balance_remaining", balance_remaining);

	frm.doc.__unsaved = 0;
	frm.dirty_flag_cleared = true;
	if (frm.page) frm.page.clear_indicator?.();
}