// Copyright (c) 2026, Brainmine AI and contributors
// For license information, please see license.txt

frappe.query_reports["Current Stock Balance"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "MultiSelectList",
			options: "Warehouse",
			get_data: (txt) =>
				frappe.db.get_link_options("Warehouse", txt, {
					company: frappe.query_report.get_filter_value("company"),
					is_group: 0,
				}),
		},
		{
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item",
		},
		{
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "Link",
			options: "Item Group",
		},
		{
			fieldname: "free_only",
			label: __("Free Stock Warehouses Only"),
			fieldtype: "Check",
		},
		{
			fieldname: "show_zero",
			label: __("Show Items With Zero Stock"),
			fieldtype: "Check",
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;

		if (column.fieldtype === "Float" && flt(data[column.fieldname]) < 0) {
			value = `<span style="color: var(--red-500);">${value}</span>`;
		}
		if (column.fieldname === "free_qty") {
			value = `<b>${value}</b>`;
		}
		return value;
	},
};