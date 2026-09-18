frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		if (frm.doc.__islocal) return;

		frappe.call({
			method: "enertechv1.custom.sales_order.get_so_payment_entries",
			args: { sales_order: frm.doc.name },
			callback: (r) => populate_payment_table(frm, r.message || []),
		});

		frm.add_custom_button("Create Dish", () => {
			frappe.call({
				method: "enertechv1.enertechv1.doctype.dish.dish.get_sales_order_dish_items",
				args: { sales_order_name: frm.doc.name },
				callback: (r) => {
					const items = r.message || [];
					if (!items.length) {
						frappe.msgprint("No items found on this Sales Order.");
						return;
					}
					show_create_dish_dialog(frm, items);
				},
			});
		});
	},
});

function populate_payment_table(frm, rows) {
	frappe.model.clear_table(frm.doc, "custom_so_payment_details");

	let total_received = 0;

	rows.forEach((row) => {
		const child = frappe.model.add_child(
			frm.doc,
			"Sales Order Payment Details",
			"custom_so_payment_details"
		);

		child.payment_entry = row.payment_entry;
		child.date = row.posting_date;
		child.payment_type = row.payment_type;
		child.mode_of_payment = row.mode_of_payment;
		child.reference_no = row.reference_no;
		child.reference_date = row.reference_date;
		child.allocated_amount = row.allocated_amount;

		total_received += flt(row.allocated_amount);
	});

	frm.refresh_field("custom_so_payment_details");

	const balance_remaining = flt(frm.doc.grand_total) - total_received;

	frm.set_value("custom_total_received", total_received);
	frm.set_value("custom_balance_remaining", balance_remaining);

	frm.doc.__unsaved = 0;
	frm.dirty_flag_cleared = true;
	if (frm.page) frm.page.clear_indicator?.();
}

// ---------------------------------------------------------------------
// "Create Dish" selection dialog
//
// For every item on the Sales Order, the user picks:
//   1. Whether to create a Dish for it at all.
//   2. Whether it's a Product (top-level) or a Sub Product.
//   3. If Sub Product: its parent, chosen from among the OTHER items on
//      this same Sales Order — or, if the real parent item isn't on
//      this Sales Order at all, a link to an existing parent Dish.
//
// None of this comes from the Item master — it's decided fresh each
// time this dialog runs, since the same item can be a standalone
// Product on one Sales Order and a Sub Product of something else on
// another.
// ---------------------------------------------------------------------
function show_create_dish_dialog(frm, items) {
	// Sanitize a child-table row name into something usable as a Frappe
	// dialog fieldname (row names are hash-like but let's not assume).
	const field_key = (row_name) => "r_" + row_name.replace(/[^a-zA-Z0-9]/g, "_");

	const LINK_DISH_VALUE = "__link_existing_dish__";

	const fields = [
		{
			fieldtype: "HTML",
			fieldname: "info",
			options:
				"<p>Select the items to create Dish documents for. For each " +
				"Sub Product, pick its parent from the other items on this " +
				"Sales Order — or, if the parent item isn't on this Sales " +
				"Order, link it to an existing Dish.</p>",
		},
	];

	items.forEach((item) => {
		const row_key = field_key(item.row_name);

		fields.push({
			fieldtype: "Check",
			fieldname: `select_${row_key}`,
			label: `${item.item_code} — ${item.item_name} (Qty: ${item.qty})`,
			default: 1,
		});

		fields.push({
			fieldtype: "Select",
			fieldname: `role_${row_key}`,
			label: "Type",
			options: ["Product", "Sub Product"],
			default: "Product",
			depends_on: `eval:doc.select_${row_key}`,
		});

		const other_item_options = items
			.filter((other) => other.row_name !== item.row_name)
			.map((other) => ({
				value: other.row_name,
				label: `${other.item_code} — ${other.item_name} (Qty: ${other.qty})`,
			}));

		fields.push({
			fieldtype: "Autocomplete",
			fieldname: `parent_choice_${row_key}`,
			label: "Parent item",
			options: [
				...other_item_options,
				{ value: LINK_DISH_VALUE, label: "🔗 Not on this Sales Order — link an existing Dish" },
			],
			depends_on: `eval:doc.select_${row_key} && doc.role_${row_key}=="Sub Product"`,
		});

		fields.push({
			fieldtype: "Link",
			fieldname: `parent_dish_${row_key}`,
			label: `Link "${item.item_code}" to existing parent Dish`,
			options: "Dish",
			depends_on:
				`eval:doc.select_${row_key} && doc.role_${row_key}=="Sub Product" ` +
				`&& doc.parent_choice_${row_key}=="${LINK_DISH_VALUE}"`,
			get_query: () => ({
				filters: {
					parent_dish: ["in", ["", null]],
					docstatus: ["!=", 2],
				},
			}),
		});
	});

	const dialog = new frappe.ui.Dialog({
		title: "Create Dish from Sales Order Items",
		size: "large",
		fields: fields,
		primary_action_label: "Create Dish(es)",
		primary_action(values) {
			const selected_items = [];
			const parent_row_links = {};
			const manual_parent_links = {};

			for (const item of items) {
				const row_key = field_key(item.row_name);
				if (!values[`select_${row_key}`]) continue;

				selected_items.push(item.row_name);

				if (values[`role_${row_key}`] !== "Sub Product") continue;

				const choice = values[`parent_choice_${row_key}`];
				if (!choice) {
					frappe.msgprint(`Please choose a parent for "${item.item_code}", or set it back to Product.`);
					return;
				}

				if (choice === LINK_DISH_VALUE) {
					const parent_dish = values[`parent_dish_${row_key}`];
					if (!parent_dish) {
						frappe.msgprint(`Please select the parent Dish to link "${item.item_code}" to.`);
						return;
					}
					manual_parent_links[item.row_name] = parent_dish;
				} else {
					parent_row_links[item.row_name] = choice;
				}
			}

			if (!selected_items.length) {
				frappe.msgprint("Please select at least one item.");
				return;
			}

			// Client-side sanity check: an in-SO parent must also be
			// selected, and can't itself be a Sub Product.
			for (const [child_row, parent_row] of Object.entries(parent_row_links)) {
				const child_item = items.find((i) => i.row_name === child_row);
				const parent_item = items.find((i) => i.row_name === parent_row);

				if (!selected_items.includes(parent_row)) {
					frappe.msgprint(
						`"${child_item.item_code}" is marked as a Sub Product of "${parent_item.item_code}", ` +
							"but that item isn't selected. Please select it, or link to an existing Dish instead."
					);
					return;
				}

				if (parent_row_links[parent_row] || manual_parent_links[parent_row]) {
					frappe.msgprint(
						`"${parent_item.item_code}" is itself marked as a Sub Product — only one level of ` +
							`nesting is supported, so it can't also be the parent of "${child_item.item_code}".`
					);
					return;
				}
			}

			frappe.call({
				method: "enertechv1.enertechv1.doctype.dish.dish.create_dishes_from_sales_order",
				args: {
					sales_order_name: frm.doc.name,
					selected_items: selected_items,
					parent_row_links: parent_row_links,
					manual_parent_links: manual_parent_links,
				},
				freeze: true,
				freeze_message: "Creating Dish documents...",
				callback: () => {
					dialog.hide();
					frm.reload_doc();
				},
			});
		},
	});

	dialog.show();
}