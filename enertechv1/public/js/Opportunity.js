frappe.ui.form.on('Opportunity', {
    refresh: function(frm) {
        set_contact_default(frm);
    }
});

function set_contact_default(frm) {
    if (frm.doc.opportunity_from !== 'Lead' || !frm.doc.party_name) return;

    frappe.db.get_list('Contact', {
        filters: [
            ['Dynamic Link', 'link_doctype', '=', 'Lead'],
            ['Dynamic Link', 'link_name', '=', frm.doc.party_name]
        ],
        fields: ['name'],
        order_by: '`tabContact`.creation asc',
        limit: 1
    }).then(contacts => {
        if (!contacts.length) return;

        let meta = frappe.get_meta('Follow Up Activities');
        let field = meta.fields.find(f => f.fieldname === 'contact_with');
        if (field) {
            field.default = contacts[0].name;
        }
    }).catch(err => {
        console.error('Contact fetch failed:', err);
    });
}