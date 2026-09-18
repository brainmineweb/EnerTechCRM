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
// Lists every Sales Order item with a checkbox (checked by default).
// Child items (Item.custom_is_child_item) whose parent item isn't also
// on this Sales Order get an extra Link field so the user can point
// them at an existing, still-open parent Dish. That Dish's name/number
// is then used to number the new child Dish (see Dish.generate_series).
// ---------------------------------------------------------------------
function show_create_dish_dialog(frm, items) {
	const fields = [
		{
			fieldtype: "HTML",
			fieldname: "info",
			options:
				"<p>Select the items you want to create Dish documents for. " +
				"Child items whose parent item isn't on this Sales Order need " +
				"to be linked to an existing parent Dish below.</p>",
		},
	];

	items.forEach((item) => {
		const row_key = item.row_name;
		const needs_manual_parent = item.is_child_item && !item.parent_present_in_so;

		fields.push({
			fieldtype: "Check",
			fieldname: `select_${row_key}`,
			label: `${item.item_code} — ${item.item_name} (Qty: ${item.qty})` +
				(item.is_child_item ? " [Child Item]" : ""),
			default: 1,
		});

		if (needs_manual_parent) {
			fields.push({
				fieldtype: "Link",
				fieldname: `parent_dish_${row_key}`,
				label: `Link "${item.item_code}" to existing parent Dish`,
				options: "Dish",
				depends_on: `eval:doc.select_${row_key}`,
				get_query: () => ({
					filters: {
						parent_dish: ["in", ["", null]],
						docstatus: ["!=", 2],
					},
				}),
			});
		}
	});

	const dialog = new frappe.ui.Dialog({
		title: "Create Dish from Sales Order Items",
		size: "large",
		fields: fields,
		primary_action_label: "Create Dish(es)",
		primary_action(values) {
			const selected_items = [];
			const manual_parent_links = {};

			for (const item of items) {
				const row_key = item.row_name;
				if (!values[`select_${row_key}`]) continue;

				selected_items.push(row_key);

				if (item.is_child_item && !item.parent_present_in_so) {
					const linked_parent = values[`parent_dish_${row_key}`];
					if (!linked_parent) {
						frappe.msgprint(
							`Please link a parent Dish for child item "${item.item_code}", or unselect it.`
						);
						return;
					}
					manual_parent_links[row_key] = linked_parent;
				}
			}

			if (!selected_items.length) {
				frappe.msgprint("Please select at least one item.");
				return;
			}

			frappe.call({
				method: "enertechv1.enertechv1.doctype.dish.dish.create_dishes_from_sales_order",
				args: {
					sales_order_name: frm.doc.name,
					selected_items: selected_items,
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