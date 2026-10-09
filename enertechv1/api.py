
import frappe

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_sales_users(doctype, txt, searchfield, start, page_len, filters):
    sales_roles = [
        "Sales Person",
        "Sales Manager",
        "Sales User",
    ]

    return frappe.db.sql("""
        SELECT DISTINCT u.name, u.full_name
        FROM `tabUser` u
        INNER JOIN `tabHas Role` r ON r.parent = u.name
        WHERE u.enabled = 1
          AND u.name NOT IN ('Guest', 'Administrator')
          AND r.role IN %(roles)s
          AND (
              u.name LIKE %(txt)s
              OR u.full_name LIKE %(txt)s
          )
        ORDER BY u.full_name
        LIMIT %(start)s, %(page_len)s
    """, {
        "roles": tuple(sales_roles),
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len
    })
