frappe.ui.form.on('Opportunity', {
    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button('Create Opportunity', function() {
                frm.copy_doc(function(new_doc) {
                    // this callback fires on the new doc, before routing
                    new_doc.status = 'Open';
                    new_doc.opportunity_owner = frappe.session.user;
                    new_doc.transaction_date = frappe.datetime.get_today();
                    new_doc.docstatus = 0;
                });
            });
        }
    }
});