// Copyright (c) 2026, Brainmine AI and contributors
// For license information, please see license.txt


frappe.ui.form.on("Proforma Invoice", {
    refresh(frm) {
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__('Dish'), function () {
				frappe.model.open_mapped_doc({
					// full dotted path to the whitelisted function in proforma_invoice.py
					// TODO: confirm this matches your actual app name / folder structure
					method: "enertechv1.enertechv1.doctype.proforma_invoice.proforma_invoice.make_dish",
					frm: frm,
				});
			}, __('Create'));
		}
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