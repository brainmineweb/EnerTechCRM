import frappe


def execute(filters=None):
    filters = filters or {}

    columns = [
        {
            "label": "Customer Name",
            "fieldname": "customer_name",
            "fieldtype": "Data",
            "width": 180
        },
        {
            "label": "Email",
            "fieldname": "email_id",
            "fieldtype": "Data",
            "width": 220
        },
        {
            "label": "Phone",
            "fieldname": "phone",
            "fieldtype": "Data",
            "width": 140
        },
        {
            "label": "State",
            "fieldname": "state",
            "fieldtype": "Data",
            "width": 140
        },
        {
            "label": "Country",
            "fieldname": "country",
            "fieldtype": "Data",
            "width": 140
        },
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
            "label": "Amount",
            "fieldname": "amount",
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "label": "Total",
            "fieldname": "total",
            "fieldtype": "Currency",
            "width": 150
        }
    ]

    conditions = [
        "opp.custom_latest_inquiry_status = 'Cold'",
        "q.docstatus != 2"
    ]

    values = {}

    # --------------------------------
    # DATE FILTER
    # --------------------------------

    if filters.get("from_date"):
        conditions.append("""
            DATE(q.quotation_sent_date) >= %(from_date)s
        """)
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("""
            DATE(q.quotation_sent_date) <= %(to_date)s
        """)
        values["to_date"] = filters["to_date"]

    # --------------------------------
    # SALES PERSON FILTER
    # --------------------------------

    if filters.get("sales_person"):
        conditions.append("""
            opp.opportunity_owner = %(sales_person)s
        """)
        values["sales_person"] = filters["sales_person"]

    # --------------------------------
    # ITEM FILTER
    # --------------------------------

    if filters.get("item"):
        conditions.append("""
            qi.item_code = %(item)s
        """)
        values["item"] = filters["item"]

    where_condition = " AND ".join(conditions)

    data = frappe.db.sql(
        f"""
        SELECT
            q.customer_name AS customer_name,

            lead.email_id AS email_id,
            lead.phone AS phone,
            lead.custom_state AS state,
            lead.custom_country_link AS country,

            qi.item_code AS item_code,
            qi.item_name AS item_name,

            q.name AS quotation,
            q.quotation_sent_date AS quotation_sent_date,

            opp.opportunity_owner AS sales_person,

            opp.custom_latest_inquiry_status AS status,

            qi.amount AS amount,

            CASE
                WHEN ROW_NUMBER() OVER (
                    PARTITION BY q.name
                    ORDER BY qi.idx
                ) = 1
                THEN q.custom_total_with_gst
                ELSE NULL
            END AS total

        FROM `tabQuotation` q

        INNER JOIN `tabQuotation Item` qi
            ON qi.parent = q.name
            AND qi.parenttype = 'Quotation'

        INNER JOIN `tabOpportunity` opp
            ON opp.name = q.custom_opportunity_reference

        LEFT JOIN `tabLead` lead
            ON lead.name = q.party_name

        LEFT JOIN `tabUser` u
            ON u.name = opp.opportunity_owner

        WHERE {where_condition}

        ORDER BY
            q.quotation_sent_date DESC,
            q.name DESC,
            qi.idx ASC
        """,
        values,
        as_dict=True
    )

    return columns, data