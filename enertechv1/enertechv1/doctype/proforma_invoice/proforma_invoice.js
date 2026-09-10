frappe.ui.form.on("Proforma Invoice", {
	refresh(frm) {
		frm.add_custom_button("Sales Order", () => {
			frappe.call({
				method: "enertechv1.enertechv1.doctype.proforma_invoice.proforma_invoice.make_sales_order",
				args: { source_name: frm.doc.name },
				freeze: true,
				freeze_message: __("Creating Sales Order..."),
				callback: (r) => {
					if (r.message) {
						frappe.set_route("Form", "Sales Order", r.message);
					}
				}
			});
		}, __("Create"));
	},


	customer_same_as_consignee(frm) {
		if (frm.doc.customer_same_as_consignee) {
			frm.set_value("customer", frm.doc.buyer || "");
			frm.set_value("customer_name", frm.doc.buyer_name || "");
			frm.set_value("customer_phone_no", frm.doc.buyer_phone_no || "");
			frm.set_value("customer_email", frm.doc.buyers_email || "");
			frm.set_value("consignee_gstin", frm.doc.buyer_gstin || "");
			frm.set_value("consignee_address", frm.doc.address || "");
			frm.set_value("customer_phone_no", frm.doc.buyers_phone_no || "");
		} else {
			frm.set_value("customer", "");
			frm.set_value("consignee_gstin", "");
			frm.set_value("consignee_address", "");
		}
	}
});