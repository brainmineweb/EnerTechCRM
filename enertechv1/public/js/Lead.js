frappe.ui.form.on('Lead', {
    setup(frm) {
        set_lead_owner_query(frm);
    },
    onload(frm) {
        set_lead_owner_query(frm);
    },
    refresh(frm) {
        set_lead_owner_query(frm);
    }
});

function set_lead_owner_query(frm) {
    frm.set_query('lead_owner', function () {
        console.log("lead_owner query called");
        return {
            query: 'enertechv1.api.get_sales_users'
        };
    });
}