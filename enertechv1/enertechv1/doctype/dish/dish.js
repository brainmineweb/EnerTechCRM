// Copyright (c) 2026, Brainmine AI and contributors
// For license information, please see license.txt

// ============================================================
// Config
// ============================================================

const ENERTECH_STOCK = {
	colors: {
		"Available": "green",
		"Partial": "orange",
		"Not Available": "red",
	},
	methods: {
		live: "enertechv1.enertechv1.api.stock.get_stock_for_items",
		saved: "enertechv1.enertechv1.api.stock.refresh_dish_stock",
	},
};

const ENERTECH_STORES = {
	api: "enertechv1.enertechv1.api.stores",
	colors: {
		"Requested": "blue",
		"In QC": "orange",
		"Ready for Dispatch": "green",
		"Partly Rejected": "red",
		"Partly Delivered": "orange",
		"Delivered": "green",
		"At Exhibition": "purple",
		"Partly Returned": "orange",
		"Returned": "green",
	},
};

// ============================================================
// Dish
// ============================================================

frappe.ui.form.on("Dish", {
	refresh(frm) {
		// Replacement (existing)
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Replacement"), () => {
				frappe.model.open_mapped_doc({
					method: "enertechv1.enertechv1.doctype.dish.dish.make_replacement",
					frm: frm,
				});
			}, __("Create"));
		}

		// Stock availability
		enertech_load_dish_stock(frm);
		frm.add_custom_button(__("Refresh Stock"), () => {
			enertech_load_dish_stock(frm, true);
			enertech_load_dish_stores(frm);
		});

		// Stores flow (Approved Dishes only)
		enertech_load_dish_stores(frm);
	},

	customer_same_as_buyer(frm) {
		if (frm.doc.customer_same_as_buyer) {
			frm.set_value("customer", frm.doc.buyer || "");
			frm.set_value("customer_name", frm.doc.buyers_name || "");
			frm.set_value("contact_no", frm.doc.buyer_contact_no || "");
			frm.set_value("customers_email", frm.doc.buyers_email || "");
			frm.set_value("gst_no", frm.doc.bueyer_gst_no || "");
			frm.set_value("customer_address", frm.doc.buyer_address || "");
		} else {
			frm.set_value("customer", "");
			frm.set_value("customer_name", "");
			frm.set_value("contact_no", "");
			frm.set_value("customers_email", "");
			frm.set_value("gst_no", "");
			frm.set_value("customer_address", "");
		}
	},
});

// ============================================================
// Dish Item
// ============================================================

frappe.ui.form.on("Dish Item", {
	item_code(frm) {
		enertech_load_dish_stock(frm);
	},
	qty(frm) {
		enertech_load_dish_stock(frm);
	},
	items_remove(frm) {
		enertech_load_dish_stock(frm);
	},
});

// ============================================================
// Stock availability helpers
// ============================================================

function enertech_load_dish_stock(frm, show_alert = false) {
	const items = (frm.doc.items || []).filter((r) => r.item_code);

	if (!items.length) {
		enertech_render_dish_stock(frm, { items: [], status: "" });
		return;
	}

	// Unsaved or edited form → live check (no DB write).
	// Saved form → server recalculates and stores silently.
	const live = frm.is_new() || frm.is_dirty();

	enertech_render_loading(frm);

	frappe.call({
		method: live ? ENERTECH_STOCK.methods.live : ENERTECH_STOCK.methods.saved,
		args: live
			? {
				items: items.map((r) => ({ name: r.name, item_code: r.item_code, qty: r.qty })),
				company: frm.doc.company,
			}
			: { dish: frm.doc.name },
		callback(r) {
			if (!r.message) return;
			enertech_apply_dish_stock(frm, r.message);
			enertech_render_dish_stock(frm, r.message);
			if (show_alert) {
				frappe.show_alert({ message: __("Stock refreshed"), indicator: "green" });
			}
		},
		error() {
			enertech_render_error(frm);
		},
	});
}

function enertech_apply_dish_stock(frm, data) {
	// Direct assignment so the form is NOT marked dirty
	// (important for Approved / submitted Dishes).
	const by_name = {};
	(data.items || []).forEach((it) => {
		by_name[it.name] = it;
	});

	(frm.doc.items || []).forEach((row) => {
		const it = by_name[row.name];
		row.available_qty = it ? it.available_qty : 0;
		row.stock_status = it ? it.stock_status : "";
	});

	frm.doc.stock_status = data.status || "";
	frm.refresh_field("items");
	frm.refresh_field("stock_status");
}

function enertech_render_loading(frm) {
	const field = frm.fields_dict.stock_details;
	if (!field) return;
	field.$wrapper.html(`<div class="text-muted small">${__("Checking stock…")}</div>`);
}

function enertech_render_error(frm) {
	const field = frm.fields_dict.stock_details;
	if (!field) return;
	field.$wrapper.html(
		`<div class="text-danger small">${__("Could not load stock. Click Refresh Stock to try again.")}</div>`
	);
}

function enertech_render_dish_stock(frm, data) {
	const field = frm.fields_dict.stock_details;
	if (!field) return;

	const items = data.items || [];
	if (!items.length) {
		field.$wrapper.html(
			`<div class="text-muted small">${__("Add an item to see stock availability.")}</div>`
		);
		return;
	}

	const esc = frappe.utils.escape_html;
	const overall_color = ENERTECH_STOCK.colors[data.status] || "gray";

	const summary = `
		<div style="display:flex; align-items:center; gap:8px; margin-bottom:12px;">
			<span class="text-muted">${__("Overall")}:</span>
			<span class="indicator-pill ${overall_color}">${esc(data.status || __("Unknown"))}</span>
		</div>`;

	const blocks = items
		.map((it) => {
			const color = ENERTECH_STOCK.colors[it.stock_status] || "gray";
			const short = Math.max(flt(it.qty) - flt(it.available_qty), 0);

			const rows = (it.warehouses || []).length
				? it.warehouses
					.map(
						(w) => `
						<tr ${w.counts ? "" : 'class="text-muted"'}>
							<td>${esc(w.warehouse)}</td>
							<td class="text-right">${format_number(w.actual_qty)}</td>
							<td class="text-right">${format_number(w.reserved_qty)}</td>
							<td class="text-right">${format_number(w.projected_qty)}</td>
							<td class="text-center">${w.counts ? "✔" : "—"}</td>
						</tr>`
					)
					.join("")
				: `<tr><td colspan="5" class="text-muted text-center">${__("No stock in any warehouse")}</td></tr>`;

			return `
				<div style="border:1px solid var(--border-color); border-radius:8px; padding:10px 12px; margin-bottom:12px;">
					<div style="display:flex; flex-wrap:wrap; align-items:center; gap:8px; margin-bottom:8px;">
						<b>${esc(it.item_code)}</b>
						<span class="text-muted">·</span>
						<span>${__("Required")}: <b>${format_number(it.qty)}</b></span>
						<span class="text-muted">·</span>
						<span>${__("Free")}: <b>${format_number(it.available_qty)}</b></span>
						${short > 0
							? `<span class="text-muted">·</span><span>${__("Short")}: <b>${format_number(short)}</b></span>`
							: ""}
						<span class="indicator-pill ${color}" style="margin-left:auto;">${esc(it.stock_status)}</span>
					</div>
					<div style="overflow-x:auto;">
						<table class="table table-bordered table-sm" style="margin:0;">
							<thead>
								<tr>
									<th>${__("Warehouse")}</th>
									<th class="text-right">${__("Actual")}</th>
									<th class="text-right">${__("Reserved (SO)")}</th>
									<th class="text-right">${__("Projected")}</th>
									<th class="text-center">${__("Counts as Free")}</th>
								</tr>
							</thead>
							<tbody>${rows}</tbody>
						</table>
					</div>
				</div>`;
		})
		.join("");

	field.$wrapper.html(summary + blocks);
}

// ============================================================
// Stores flow helpers
// ============================================================

function enertech_load_dish_stores(frm) {
	const progress = frm.fields_dict.stores_progress_html;
	const details = frm.fields_dict.stores_html;

	if (frm.doc.docstatus !== 1) {
		const msg = `<div class="text-muted small">${__("Stores progress starts once the Dish is Approved.")}</div>`;
		if (progress) progress.$wrapper.html(msg);
		if (details) details.$wrapper.html("");
		return;
	}

	frappe.call({
		method: `${ENERTECH_STORES.api}.get_dish_stores_summary`,
		args: { dish: frm.doc.name },
		callback(r) {
			if (!r.message) return;
			const data = r.message;
			frm.doc.stores_status = data.status || "";
			frm.refresh_field("stores_status");
			enertech_add_stores_buttons(frm, data);
			enertech_render_stores_progress(frm, data);
			enertech_render_dish_stores(frm, data);
		},
	});
}

function enertech_add_stores_buttons(frm, data) {
	const items = data.items || [];
	const needs_more = items.some((i) => i.still_needed > 0);
	const has_stock = ["Available", "Partial"].includes(frm.doc.stock_status);
	const in_dispatch = items.some((i) => i.in_dispatch > 0);
	const draft_dn = ((data.links || {}).delivery_notes || []).find((d) => d.docstatus === 0);

	// Sales: request stock from Stores
	if (needs_more && has_stock && frappe.model.can_create("Material Request")) {
		frm.add_custom_button(__("Request from Stores"), () => {
			frappe.call({
				method: `${ENERTECH_STORES.api}.make_material_request`,
				args: { dish: frm.doc.name },
				freeze: true,
				freeze_message: __("Sending request to Stores…"),
				callback(r) {
					if (!r.message) return;
					frappe.show_alert({
						message: __("Request {0} sent to Stores", [r.message]),
						indicator: "green",
					});
					frm.reload_doc();
				},
			});
		}, __("Stores"));
	}

	// Dispatch: deliver units that passed inspection
	if (draft_dn) {
		frm.add_custom_button(__("Open Delivery Note"), () => {
			frappe.set_route("Form", "Delivery Note", draft_dn.name);
		});
	} else if (in_dispatch && frappe.model.can_create("Delivery Note")) {
		const btn = frm.add_custom_button(__("Create Delivery Note"), () => {
			frappe.call({
				method: `${ENERTECH_STORES.api}.make_delivery_note`,
				args: { dish: frm.doc.name },
				freeze: true,
				freeze_message: __("Creating Delivery Note…"),
				callback(r) {
					if (r.message) frappe.set_route("Form", "Delivery Note", r.message);
				},
			});
		});
		btn.removeClass("btn-default").addClass("btn-primary");
	}

		// Exhibition: Stores marks units back from the exhibition
	const at_exhibition = items.some((i) => flt(i.at_exhibition) > 0);
	if (data.is_exhibition && at_exhibition && frappe.user.has_role(["Stores Person", "System Manager"])) {
		frm.add_custom_button(__("Mark Returned"), () => enertech_mark_returned(frm, data), __("Exhibition"));
	}
}

function enertech_render_stores_progress(frm, data) {
	const field = frm.fields_dict.stores_progress_html;
	if (!field) return;

	const esc = frappe.utils.escape_html;
	const link = (dt, name) => frappe.utils.get_form_link(dt, name, true);
	const look = {
		done: { bg: "var(--green-500, #2e9d5a)", fg: "#fff" },
		current: { bg: "var(--orange-500, #e8862a)", fg: "#fff" },
		pending: { bg: "var(--gray-300, #d1d8dd)", fg: "var(--text-muted)" },
	};

	const stages = data.stages || [];
	const rows = stages
		.map((s, idx) => {
			const l = look[s.state] || look.pending;
			const last = idx === stages.length - 1;
			const mark = s.state === "done" ? "✓" : idx + 1;
			const docs = (s.docs || []).map((d) => link(d.doctype, d.name)).join(", ");
			const warn = s.warning
				? `<span class="indicator-pill red" style="margin-left:6px;">${__("Rejected units")}</span>`
				: "";
			const next =
				s.state === "current" && s.next
					? `<div class="small" style="color:var(--text-muted); margin-top:2px;">${__("Next")}: ${esc(s.next)}</div>`
					: "";
			const line = last
				? ""
				: `<div style="width:2px; flex:1; min-height:18px; background:${s.state === "done" ? look.done.bg : "var(--border-color)"};"></div>`;

			return `
				<div style="display:flex; gap:12px;">
					<div style="display:flex; flex-direction:column; align-items:center;">
						<div style="width:24px; height:24px; border-radius:50%; background:${l.bg}; color:${l.fg};
							display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:600; flex:none;">${mark}</div>
						${line}
					</div>
					<div style="padding-bottom:${last ? 0 : 14}px; min-width:0;">
						<div style="font-weight:600; ${s.state === "pending" ? "color:var(--text-muted);" : ""}">${esc(s.label)}${warn}</div>
						${s.detail ? `<div class="small">${esc(s.detail)}</div>` : ""}
						${docs ? `<div class="small" style="margin-top:2px;">${docs}</div>` : ""}
						${next}
					</div>
				</div>`;
		})
		.join("");

	const color = ENERTECH_STORES.colors[data.status] || "gray";
	const exhibition = data.is_exhibition
		? `<span class="indicator-pill purple">${__("Exhibition")}</span>`
		: "";
	field.$wrapper.html(`
		<div style="display:flex; align-items:center; gap:8px; margin-bottom:14px; flex-wrap:wrap;">
			<span class="text-muted">${__("Stores Status")}:</span>
			<span class="indicator-pill ${color}">${esc(data.status || __("Not Requested"))}</span>
			${exhibition}
		</div>
		${rows}
	`);
}

function enertech_render_dish_stores(frm, data) {
	const field = frm.fields_dict.stores_html;
	if (!field) return;

	const esc = frappe.utils.escape_html;
	const link = (dt, name) => frappe.utils.get_form_link(dt, name, true);
	const doc_state = (d) =>
		d.docstatus === 2 ? __("Cancelled") : d.docstatus === 1 ? __("Submitted") : __("Draft");

	const item_rows = (data.items || [])
		.map(
			(i) => `
			<tr>
				<td><b>${esc(i.item_code)}</b></td>
				<td class="text-right">${format_number(i.required)}</td>
				<td class="text-right">${format_number(i.requested)}</td>
				<td class="text-right">${format_number(i.in_qc)}</td>
				<td class="text-right">${format_number(i.in_dispatch)}</td>
				<td class="text-right">${format_number(i.rejected)}</td>
				<td class="text-right">${format_number(i.delivered)}</td>
				<td class="text-right">${format_number(i.returned)}</td>
				<td class="text-right"><b>${format_number(i.still_needed)}</b></td>
			</tr>`
		)
		.join("");

	const links = data.links || {};
	const doc_list = (title, dt, rows, extra) =>
		rows && rows.length
			? `<div style="margin-top:8px;"><span class="text-muted">${title}:</span> ${rows
				.map((d) => `${link(dt, d.name)} <span class="text-muted small">(${extra ? extra(d) : doc_state(d)})</span>`)
				.join(", ")}</div>`
			: "";

	field.$wrapper.html(`
		<div style="overflow-x:auto;">
			<table class="table table-bordered table-sm" style="margin:0;">
				<thead>
					<tr>
						<th>${__("Item")}</th>
						<th class="text-right">${__("Required")}</th>
						<th class="text-right">${__("Requested")}</th>
						<th class="text-right">${__("In QC")}</th>
						<th class="text-right">${__("In Dispatch")}</th>
						<th class="text-right">${__("Rejected")}</th>
						<th class="text-right">${__("Delivered")}</th>
						<th class="text-right">${__("Returned")}</th>
						<th class="text-right">${__("Still Needed")}</th>
					</tr>
				</thead>
				<tbody>${item_rows}</tbody>
			</table>
		</div>
		${doc_list(__("Material Requests"), "Material Request", links.material_requests, (d) => `${doc_state(d)}${d.status ? " · " + esc(d.status) : ""}`)}
		${doc_list(__("Stock Entries"), "Stock Entry", links.stock_entries, (d) => `${doc_state(d)} · ${esc(d.from_warehouse || "")} → ${esc(d.to_warehouse || "")}`)}
		${doc_list(__("Quality Inspections"), "Quality Inspection", links.quality_inspections, (d) => `${doc_state(d)} · ${esc(d.status || "")}`)}
		${doc_list(__("Delivery Notes"), "Delivery Note", links.delivery_notes, (d) => `${doc_state(d)}${d.status ? " · " + esc(d.status) : ""}`)}
	`);
}

function enertech_mark_returned(frm, data) {
	const rows = (data.items || [])
		.filter((i) => flt(i.at_exhibition) > 0)
		.map((i) => ({
			item_code: i.item_code,
			out_qty: flt(i.at_exhibition),
			return_qty: flt(i.at_exhibition),
		}));

	const d = new frappe.ui.Dialog({
		title: __("Mark Returned from Exhibition"),
		size: "large",
		fields: [
			{
				fieldtype: "HTML",
				options: `<p class="text-muted small">${__(
					"Enter the quantity that has come back. Returned units go to QC for re-inspection before they become free stock again."
				)}</p>`,
			},
			{
				fieldname: "items",
				fieldtype: "Table",
				label: __("Items"),
				cannot_add_rows: true,
				cannot_delete_rows: true,
				in_place_edit: true,
				data: rows,
				fields: [
					{ fieldname: "item_code", fieldtype: "Link", options: "Item", label: __("Item"), in_list_view: 1, read_only: 1, columns: 4 },
					{ fieldname: "out_qty", fieldtype: "Float", label: __("At Exhibition"), in_list_view: 1, read_only: 1, columns: 3 },
					{ fieldname: "return_qty", fieldtype: "Float", label: __("Returned Now"), in_list_view: 1, columns: 3 },
				],
			},
			{ fieldname: "remarks", fieldtype: "Small Text", label: __("Remarks") },
		],
		primary_action_label: __("Create Return"),
		primary_action(values) {
			const table = values.items || [];
			const over = table.find((r) => flt(r.return_qty) > flt(r.out_qty));
			if (over) {
				frappe.msgprint(__("{0}: returned qty cannot be more than {1}.", [over.item_code, over.out_qty]));
				return;
			}
			const items = table
				.filter((r) => flt(r.return_qty) > 0)
				.map((r) => ({ item_code: r.item_code, qty: flt(r.return_qty) }));
			if (!items.length) {
				frappe.msgprint(__("Enter a returned quantity for at least one item."));
				return;
			}

			frappe.call({
				method: "enertechv1.enertechv1.api.returns.make_exhibition_return",
				args: { dish: frm.doc.name, items: items, remarks: values.remarks || "" },
				freeze: true,
				freeze_message: __("Creating return…"),
				callback(r) {
					if (!r.message) return;
					d.hide();
					frappe.show_alert({
						message: __("Return {0} created. Units are in QC for re-inspection.", [r.message.join(", ")]),
						indicator: "green",
					});
					frm.reload_doc();
				},
			});
		},
	});

	d.show();
}