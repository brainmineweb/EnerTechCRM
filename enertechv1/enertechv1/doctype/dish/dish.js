// Copyright (c) 2026, Brainmine AI and contributors
// For license information, please see license.txt

frappe.ui.form.on("Dish", {
	refresh(frm) {

	},

    customer_same_as_buyer(frm) {
		if (frm.doc.customer_same_as_buyer) {
			frm.set_value("customer", frm.doc.buyer || "");
			frm.set_value("customer_name", frm.doc.buyers_name || "");
			frm.set_value("contact_no", frm.doc.buyer_contact_no || "");
			frm.set_value("customers_email", frm.doc.buyers_email || "");
			frm.set_value("gst_no", frm.doc.bueyer_gst_no || "");
			frm.set_value("customer_address", frm.doc.buyer_address || "");
			frm.set_value("contact_no", frm.doc.buyer_contact_no || "");
		} else {
			frm.set_value("customer", "");
			frm.set_value("gst_no", "");
			frm.set_value("customer_address", "");
            frm.set_value("contact_no", "");
            frm.set_value("customers_email", "");
            frm.set_value("customer_name", "");
            
		}
	}
});


