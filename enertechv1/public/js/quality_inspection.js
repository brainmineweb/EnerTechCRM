frappe.ui.form.on("Quality Inspection", {
	refresh(frm) {
		if (!frm.doc.custom_dish) return;

		if (frm.doc.docstatus === 0) {
			frm.set_intro(
				__("Dish {0}: on Submit, the Accepted Qty moves to Dispatch and the Rejected Qty moves to Rejected.", [
					frappe.utils.escape_html(frm.doc.custom_dish),
				]),
				"blue"
			);
		}

		frm.add_custom_button(__("Open Dish"), () => {
			frappe.set_route("Form", "Dish", frm.doc.custom_dish);
		});
	},

	custom_accepted_qty(frm) {
		if (!frm.doc.custom_dish || frm.doc.docstatus !== 0) return;
		const rejected = flt(frm.doc.sample_size) - flt(frm.doc.custom_accepted_qty);
		frm.set_value("custom_rejected_qty", rejected > 0 ? rejected : 0);
	},
});