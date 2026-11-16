frappe.ui.form.on("Material Request", {
	refresh(frm) {
		const doc = frm.doc;

		if (
			doc.docstatus !== 1 ||
			!doc.custom_dish ||
			doc.material_request_type !== "Material Transfer" ||
			["Transferred", "Stopped", "Cancelled"].includes(doc.status)
		) {
			return;
		}

		const btn = frm.add_custom_button(__("Move to Quality Control"), () => {
			const esc = frappe.utils.escape_html;
			const rows = (doc.items || [])
				.map((r) => {
					const pending = flt(r.stock_qty) - flt(r.ordered_qty);
					return `<tr>
						<td>${esc(r.item_code)}</td>
						<td>${esc(r.from_warehouse || "")}</td>
						<td class="text-right">${format_number(pending)}</td>
					</tr>`;
				})
				.join("");

			frappe.confirm(
				`<p>${__("Move these items to <b>QC Hold</b> for Dish {0}?", [esc(doc.custom_dish)])}</p>
				<table class="table table-bordered table-sm">
					<thead><tr><th>${__("Item")}</th><th>${__("From")}</th><th class="text-right">${__("Qty")}</th></tr></thead>
					<tbody>${rows}</tbody>
				</table>`,
				() => {
					frappe.call({
						method: "enertechv1.enertechv1.api.stores.make_qc_transfer",
						args: { material_request: doc.name },
						freeze: true,
						freeze_message: __("Moving stock to Quality Control…"),
						callback(r) {
							if (!r.message) return;
							frappe.show_alert({
								message: __("Moved to QC Hold: {0}", [r.message]),
								indicator: "green",
							});
							frappe.set_route("Form", "Stock Entry", r.message);
						},
					});
				}
			);
		});

		btn.removeClass("btn-default").addClass("btn-primary");
	},
});