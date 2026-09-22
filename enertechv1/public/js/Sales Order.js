// frappe.ui.form.on("Sales Order", {
// 	refresh(frm) {
// 		if (frm.doc.__islocal) return;

// 		frappe.call({
// 			method: "enertechv1.custom.sales_order.get_so_payment_entries",
// 			args: { sales_order: frm.doc.name },
// 			callback: (r) => populate_payment_table(frm, r.message || []),
// 		});

// 		frm.add_custom_button("Create Dish", () => {
// 			frappe.call({
// 				method: "enertechv1.enertechv1.doctype.dish.dish.get_sales_order_dish_items",
// 				args: { sales_order_name: frm.doc.name },
// 				callback: (r) => {
// 					const items = r.message || [];
// 					if (!items.length) {
// 						frappe.msgprint("No items found on this Sales Order.");
// 						return;
// 					}
// 					show_create_dish_dialog(frm, items);
// 				},
// 			});
// 		});
// 	},
// });

// function populate_payment_table(frm, rows) {
// 	frappe.model.clear_table(frm.doc, "custom_so_payment_details");

// 	let total_received = 0;

// 	rows.forEach((row) => {
// 		const child = frappe.model.add_child(
// 			frm.doc,
// 			"Sales Order Payment Details",
// 			"custom_so_payment_details"
// 		);

// 		child.payment_entry = row.payment_entry;
// 		child.date = row.posting_date;
// 		child.payment_type = row.payment_type;
// 		child.mode_of_payment = row.mode_of_payment;
// 		child.reference_no = row.reference_no;
// 		child.reference_date = row.reference_date;
// 		child.allocated_amount = row.allocated_amount;

// 		total_received += flt(row.allocated_amount);
// 	});

// 	frm.refresh_field("custom_so_payment_details");

// 	const balance_remaining = flt(frm.doc.grand_total) - total_received;

// 	frm.set_value("custom_total_received", total_received);
// 	frm.set_value("custom_balance_remaining", balance_remaining);

// 	frm.doc.__unsaved = 0;
// 	frm.dirty_flag_cleared = true;
// 	if (frm.page) frm.page.clear_indicator?.();
// }

// // ---------------------------------------------------------------------
// // "Create Dish" dialog — creates ONE Dish at a time.
// //
// // For the item the user picks, they choose:
// //   1. Whether it's a Product (top-level) or a Sub Product.
// //   2. If Sub Product: an existing, already-created parent Dish to
// //      link it to (since only one Dish is created per run, the parent
// //      must already exist — create the parent first, then come back
// //      and create the Sub Product linking to it).
// //
// // The dialog also shows, per item, how many Dishes already exist for
// // it and their names, so it's obvious at a glance what's been done
// // already before creating another one.
// // ---------------------------------------------------------------------
// function show_create_dish_dialog(frm, items) {
// 	const field_key = (row_name) => "r_" + row_name.replace(/[^a-zA-Z0-9]/g, "_");

// 	const item_by_row = {};
// 	items.forEach((item) => (item_by_row[item.row_name] = item));

// 	const existing_dishes_summary_html = () => {
// 		const rows = items
// 			.map((item) => {
// 				const existing = item.existing_dishes || [];
// 				const status = existing.length
// 					? `<span style="color:var(--green-600,#2ba24c);">${existing.length} dish(es) created:</span> ` +
// 					  existing
// 							.map(
// 								(name) =>
// 									`<a href="/app/dish/${encodeURIComponent(name)}" target="_blank">${frappe.utils.escape_html(name)}</a>`
// 							)
// 							.join(", ")
// 					: `<span style="color:var(--text-muted,#8d99a6);">No dish created yet</span>`;

// 				return `
// 					<tr>
// 						<td>${frappe.utils.escape_html(item.item_code)} — ${frappe.utils.escape_html(item.item_name)}</td>
// 						<td>${item.qty}</td>
// 						<td>${status}</td>
// 					</tr>
// 				`;
// 			})
// 			.join("");

// 		return `
// 			<table class="table table-bordered" style="margin-bottom: 10px;">
// 				<thead>
// 					<tr>
// 						<th>Item</th>
// 						<th>Qty</th>
// 						<th>Dishes already created</th>
// 					</tr>
// 				</thead>
// 				<tbody>${rows}</tbody>
// 			</table>
// 		`;
// 	};

// 	const item_select_options = items.map((item) => {
// 		const existing = item.existing_dishes || [];
// 		const existing_label = existing.length
// 			? ` — ${existing.length} dish(es) already: ${existing.join(", ")}`
// 			: " — none created yet";

// 		return {
// 			value: item.row_name,
// 			label: `${item.item_code} — ${item.item_name} (Qty: ${item.qty})${existing_label}`,
// 		};
// 	});

// 	const dialog = new frappe.ui.Dialog({
// 		title: "Create Dish from Sales Order Item",
// 		size: "large",
// 		fields: [
// 			{
// 				fieldtype: "HTML",
// 				fieldname: "existing_summary",
// 				options: existing_dishes_summary_html(),
// 			},
// 			{
// 				fieldtype: "Section Break",
// 			},
// 			{
// 				fieldtype: "Autocomplete",
// 				fieldname: "select_item",
// 				label: "Item to create Dish for",
// 				reqd: 1,
// 				options: item_select_options,
// 			},
// 			{
// 				fieldtype: "Select",
// 				fieldname: "role",
// 				label: "Type",
// 				options: ["Product", "Sub Product"],
// 				default: "Product",
// 				depends_on: "eval:doc.select_item",
// 			},
// 			{
// 				fieldtype: "Link",
// 				fieldname: "parent_dish",
// 				label: "Parent Dish",
// 				options: "Dish",
// 				depends_on: 'eval:doc.select_item && doc.role=="Sub Product"',
// 				description: "Only already-created, top-level Dishes can be picked as a parent.",
// 				get_query: () => ({
// 					filters: {
// 						parent_dish: ["in", ["", null]],
// 						docstatus: ["!=", 2],
// 					},
// 				}),
// 			},
// 		],
// 		primary_action_label: "Create Dish",
// 		primary_action(values) {
// 			if (!values.select_item) {
// 				frappe.msgprint("Please select an item to create a Dish for.");
// 				return;
// 			}

// 			const is_sub_product = values.role === "Sub Product";

// 			if (is_sub_product && !values.parent_dish) {
// 				frappe.msgprint("Please select the parent Dish to link this Sub Product to.");
// 				return;
// 			}

// 			frappe.call({
// 				method: "enertechv1.enertechv1.doctype.dish.dish.create_dish_from_sales_order_item",
// 				args: {
// 					sales_order_name: frm.doc.name,
// 					row_name: values.select_item,
// 					is_sub_product: is_sub_product ? 1 : 0,
// 					parent_dish: is_sub_product ? values.parent_dish : null,
// 				},
// 				freeze: true,
// 				freeze_message: "Creating Dish...",
// 				callback: (r) => {
// 					if (!r.message) return;
// 					dialog.hide();
// 					// Go straight to the newly created Dish instead of
// 					// staying on the Sales Order.
// 					frappe.set_route("Form", "Dish", r.message);
// 				},
// 			});
// 		},
// 	});

// 	dialog.show();
// }



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

		// Hide "Payment" from the Create dropdown once fully paid
		remove_payment_button_if_fully_paid(frm);
	},
});

function remove_payment_button_if_fully_paid(frm) {
	const balance = flt(frm.doc.custom_balance_remaining);

	if (balance <= 0) {
		// Small delay so Frappe's core sales_order.js has already added
		// the "Payment" button (under "Create") before we try to remove it.
		setTimeout(() => {
			frm.page.remove_inner_button(__("Payment"), __("Create"));
		}, 300);
	}
}

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

	// Balance may have just changed to 0 after this refresh — re-check
	// whether the "Payment" button should be removed.
	remove_payment_button_if_fully_paid(frm);
}

// ---------------------------------------------------------------------
// "Create Dish" dialog — creates ONE Dish at a time.
//
// For the item the user picks, they choose:
//   1. Whether it's a Product (top-level) or a Sub Product.
//   2. If Sub Product: an existing, already-created parent Dish to
//      link it to (since only one Dish is created per run, the parent
//      must already exist — create the parent first, then come back
//      and create the Sub Product linking to it).
//
// The dialog also shows, per item, how many Dishes already exist for
// it and their names, so it's obvious at a glance what's been done
// already before creating another one.
// ---------------------------------------------------------------------
function show_create_dish_dialog(frm, items) {
	const field_key = (row_name) => "r_" + row_name.replace(/[^a-zA-Z0-9]/g, "_");

	const item_by_row = {};
	items.forEach((item) => (item_by_row[item.row_name] = item));

	const existing_dishes_summary_html = () => {
		const rows = items
			.map((item) => {
				const existing = item.existing_dishes || [];
				const status = existing.length
					? `<span style="color:var(--green-600,#2ba24c);">${existing.length} dish(es) created:</span> ` +
					  existing
							.map(
								(name) =>
									`<a href="/app/dish/${encodeURIComponent(name)}" target="_blank">${frappe.utils.escape_html(name)}</a>`
							)
							.join(", ")
					: `<span style="color:var(--text-muted,#8d99a6);">No dish created yet</span>`;

				return `
					<tr>
						<td>${frappe.utils.escape_html(item.item_code)} — ${frappe.utils.escape_html(item.item_name)}</td>
						<td>${item.qty}</td>
						<td>${status}</td>
					</tr>
				`;
			})
			.join("");

		return `
			<table class="table table-bordered" style="margin-bottom: 10px;">
				<thead>
					<tr>
						<th>Item</th>
						<th>Qty</th>
						<th>Dishes already created</th>
					</tr>
				</thead>
				<tbody>${rows}</tbody>
			</table>
		`;
	};

	const item_select_options = items.map((item) => {
		const existing = item.existing_dishes || [];
		const existing_label = existing.length
			? ` — ${existing.length} dish(es) already: ${existing.join(", ")}`
			: " — none created yet";

		return {
			value: item.row_name,
			label: `${item.item_code} — ${item.item_name} (Qty: ${item.qty})${existing_label}`,
		};
	});

	const dialog = new frappe.ui.Dialog({
		title: "Create Dish from Sales Order Item",
		size: "large",
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "existing_summary",
				options: existing_dishes_summary_html(),
			},
			{
				fieldtype: "Section Break",
			},
			{
				fieldtype: "Autocomplete",
				fieldname: "select_item",
				label: "Item to create Dish for",
				reqd: 1,
				options: item_select_options,
			},
			{
				fieldtype: "Select",
				fieldname: "role",
				label: "Type",
				options: ["Product", "Sub Product"],
				default: "Product",
				depends_on: "eval:doc.select_item",
			},
			{
				fieldtype: "Link",
				fieldname: "parent_dish",
				label: "Parent Dish",
				options: "Dish",
				depends_on: 'eval:doc.select_item && doc.role=="Sub Product"',
				description: "Only already-created, top-level Dishes can be picked as a parent.",
				get_query: () => ({
					filters: {
						parent_dish: ["in", ["", null]],
						docstatus: ["!=", 2],
					},
				}),
			},
		],
		primary_action_label: "Create Dish",
		primary_action(values) {
			if (!values.select_item) {
				frappe.msgprint("Please select an item to create a Dish for.");
				return;
			}

			const is_sub_product = values.role === "Sub Product";

			if (is_sub_product && !values.parent_dish) {
				frappe.msgprint("Please select the parent Dish to link this Sub Product to.");
				return;
			}

			frappe.call({
				method: "enertechv1.enertechv1.doctype.dish.dish.create_dish_from_sales_order_item",
				args: {
					sales_order_name: frm.doc.name,
					row_name: values.select_item,
					is_sub_product: is_sub_product ? 1 : 0,
					parent_dish: is_sub_product ? values.parent_dish : null,
				},
				freeze: true,
				freeze_message: "Creating Dish...",
				callback: (r) => {
					if (!r.message) return;
					dialog.hide();
					// Go straight to the newly created Dish instead of
					// staying on the Sales Order.
					frappe.set_route("Form", "Dish", r.message);
				},
			});
		},
	});

	dialog.show();
}