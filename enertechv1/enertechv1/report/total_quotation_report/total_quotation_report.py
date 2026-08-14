import frappe


def execute(filters=None):
    filters = filters or {}

    columns = [
        {
            "label": "Item",
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 150
        },
        {
            "label": "Item Name",
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": "Quotation",
            "fieldname": "quotation",
            "fieldtype": "Link",
            "options": "Quotation",
            "width": 150
        },
        {
            "label": "Quotation Sent Date",
            "fieldname": "quotation_sent_date",
            "fieldtype": "Date",
            "width": 130
        },
        {
            "label": "Sales Person",
            "fieldname": "sales_person",
            "fieldtype": "Data",
            "width": 180
        },
        {
            "label": "Status",
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": "Total With GST",
            "fieldname": "total_with_gst",
            "fieldtype": "Currency",
            "width": 150
        }
    ]

    conditions = []

    values = {}

    # --------------------------------
    # STATUS FILTER
    # --------------------------------

    if filters.get("status"):
        conditions.append(
            "opp.custom_latest_inquiry_status = %(status)s"
        )
        values["status"] = filters["status"]

    # --------------------------------
    # DATE FILTER
    # --------------------------------

    if filters.get("from_date"):
        conditions.append(
            "DATE(q.quotation_sent_date) >= %(from_date)s"
        )
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append(
            "DATE(q.quotation_sent_date) <= %(to_date)s"
        )
        values["to_date"] = filters["to_date"]

    # --------------------------------
    # SALES PERSON FILTER
    # --------------------------------

    if filters.get("sales_person"):
        conditions.append(
            "opp.opportunity_owner = %(sales_person)s"
        )
        values["sales_person"] = filters["sales_person"]

    # --------------------------------
    # ITEM FILTER
    # --------------------------------

    if filters.get("item"):
        conditions.append(
            "qi.item_code = %(item)s"
        )
        values["item"] = filters["item"]

    # --------------------------------
    # BUILD WHERE CONDITION
    # --------------------------------

    where_condition = ""

    if conditions:
        where_condition = "WHERE " + " AND ".join(conditions)

    # --------------------------------
    # QUERY
    # --------------------------------

    data = frappe.db.sql(
        f"""
        SELECT
            qi.item_code AS item_code,
            qi.item_name AS item_name,
            q.name AS quotation,
            q.quotation_sent_date AS quotation_sent_date,

            opp.opportunity_owner AS sales_person,

            opp.custom_latest_inquiry_status AS status,

            q.custom_total_with_gst AS total_with_gst

        FROM `tabQuotation` q

        INNER JOIN `tabQuotation Item` qi
            ON qi.parent = q.name
            AND qi.parenttype = 'Quotation'

        INNER JOIN `tabOpportunity` opp
            ON opp.name = q.custom_opportunity_reference

        {where_condition}

        ORDER BY
            q.quotation_sent_date DESC,
            q.name DESC
        """,
        values,
        as_dict=True
    )

    return columns, data