// Copyright (c) 2026, Brainmine Web Solutions Pvt Ltd

frappe.query_reports["DISH Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "customer",
			label: __("Customer Name"),
			fieldtype: "Data",
		},
		{
			fieldname: "inspection",
			label: __("Inspection"),
			fieldtype: "Select",
			options: ["", "Yes", "No"],
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "inspection" && data) {
			const color = data.inspection === "Yes" ? "green" : "red";
			value = `<span style="color:${color};font-weight:600">${value}</span>`;
		}
		return value;
	},
};