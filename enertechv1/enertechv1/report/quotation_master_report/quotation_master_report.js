
frappe.query_reports["Quotation Master Report"] = {
    filters: [
        {
            fieldname: "from_date",
            label: "From Date",
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            reqd: 0
        },
        {
            fieldname: "to_date",
            label: "To Date",
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 0
        },
        {
            fieldname: "sales_person",
            label: "Sales Person",
            fieldtype: "Link",
            options: "User",
            reqd: 0
        },
        {
            fieldname: "opportunity_status",
            label: "Opportunity Status",
            fieldtype: "Select",
            options: "\nOpen\nQuotation\nConverted\nClosed\nLost",
            reqd: 0
        },
        {
            fieldname: "quotation_created",
            label: "Quotation Created",
            fieldtype: "Select",
            options: "\nYes\nNo",
            reqd: 0
        },
        {
            fieldname: "source",
            label: "Source",
            fieldtype: "Data",
            reqd: 0
        },
        {
            fieldname: "latest_inquiry_status",
            label: "Latest Inquiry Status",
            fieldtype: "Select",
            options: "\nCold\nHot\nWarm\nLost",
            reqd: 0
        }
    ]
};