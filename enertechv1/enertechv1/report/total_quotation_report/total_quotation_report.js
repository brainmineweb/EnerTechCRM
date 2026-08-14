
frappe.query_reports["Total Quotation Report"] = {
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
            fieldname: "status",
            label: "Status",
            fieldtype: "Select",
            options: "\nHot\nWarm\nCold\nLost"
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