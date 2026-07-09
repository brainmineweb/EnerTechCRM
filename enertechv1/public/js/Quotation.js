frappe.ui.form.on("Quotation", {
    refresh(frm) {
        add_proforma_invoice_button(frm);
    },
});

function add_proforma_invoice_button(frm) {
    const create_proforma_invoice = () => {
        if (frm.is_new()) {
            frappe.msgprint(__("Please save the Quotation before creating a Proforma Invoice."));
            return;
        }

        frappe.model.open_mapped_doc({
            method: "enertechv1.enertechv1.doctype.proforma_invoice.proforma_invoice.make_proforma_invoice",
            frm: frm,
        });
    };

    frm.remove_custom_button(__("Create Proforma Invoice"));
    frm.add_custom_button(__("Create Proforma Invoice"), create_proforma_invoice);
}
