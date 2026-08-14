frappe.query_reports["Cold Funnel Quotation Report"] = {
    filters: [
        {
            fieldname: "from_date",
            label: "From Date",
            fieldtype: "Date"
        },
        {
            fieldname: "to_date",
            label: "To Date",
            fieldtype: "Date"
        },
        {
            fieldname: "sales_person",
            label: "Sales Person",
            fieldtype: "Link",
            options: "User"
        },
        {
            fieldname: "item",
            label: "Item",
            fieldtype: "Link",
            options: "Item"
        }
    ]
};