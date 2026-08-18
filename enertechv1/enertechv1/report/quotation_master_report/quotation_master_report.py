import frappe


def execute(filters=None):
    filters = frappe._dict(filters or {})

    conditions = []
    values = {}

    # -----------------------------------------
    # DATE FILTER
    # -----------------------------------------

    if filters.get("from_date"):
        conditions.append("o.creation >= %(from_date)s")
        values["from_date"] = filters.get("from_date") + " 00:00:00"

    if filters.get("to_date"):
        conditions.append("o.creation <= %(to_date)s")
        values["to_date"] = filters.get("to_date") + " 23:59:59"

    # -----------------------------------------
    # SALES PERSON
    # -----------------------------------------

    if filters.get("sales_person"):
        conditions.append("o.opportunity_owner = %(sales_person)s")
        values["sales_person"] = filters.get("sales_person")

    # -----------------------------------------
    # LATEST INQUIRY STATUS
    # -----------------------------------------
    
    if filters.get("latest_inquiry_status"):
        conditions.append("o.custom_latest_inquiry_status = %(latest_inquiry_status)s")
        values["latest_inquiry_status"] = filters.get("latest_inquiry_status")

    # -----------------------------------------
    # OPPORTUNITY STATUS
    # -----------------------------------------

    if filters.get("opportunity_status"):
        conditions.append("o.status = %(opportunity_status)s")
        values["opportunity_status"] = filters.get("opportunity_status")

    # -----------------------------------------
    # SOURCE
    # -----------------------------------------

    if filters.get("source"):
        conditions.append("o.source = %(source)s")
        values["source"] = filters.get("source")

    # -----------------------------------------
    # QUOTATION CREATED
    # -----------------------------------------

    if filters.get("quotation_created") == "Yes":
        conditions.append("q.name IS NOT NULL")

    elif filters.get("quotation_created") == "No":
        conditions.append("q.name IS NULL")

    # -----------------------------------------
    # WHERE
    # -----------------------------------------

    where_clause = ""

    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # -----------------------------------------
    # COLUMNS
    # -----------------------------------------

    columns = [
        {
            "label": "Opportunity",
            "fieldname": "opportunity",
            "fieldtype": "Link",
            "options": "Opportunity",
            "width": 150
        },
        {
            "label": "Opportunity Created",
            "fieldname": "opportunity_created",
            "fieldtype": "Datetime",
            "width": 150
        },
        {
            "label": "Sales Person",
            "fieldname": "sales_person",
            "fieldtype": "Data",
            "width": 140
        },
        {
            "label": "Opportunity Items",
            "fieldname": "opportunity_items",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": "Quotation Created",
            "fieldname": "quotation_created",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": "Title",
            "fieldname": "title",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": "Item",
            "fieldname": "item",
            "fieldtype": "Data",
            "width": 180
        },
        {
            "label": "Quotation Date",
            "fieldname": "quotation_date",
            "fieldtype": "Date",
            "width": 120
        },
        {
            "label": "Quotation Sent Date",
            "fieldname": "quotation_sent_date",
            "fieldtype": "Date",
            "width": 130
        },
        {
            "label": "Mobile",
            "fieldname": "mobile",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": "Email",
            "fieldname": "email",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": "City",
            "fieldname": "city",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": "State",
            "fieldname": "state",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": "Country",
            "fieldname": "country",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": "Qty",
            "fieldname": "qty",
            "fieldtype": "Float",
            "width": 60
        },
        {
            "label": "Rate",
            "fieldname": "rate",
            "fieldtype": "Currency",
            "width": 100
        },
        {
            "label": "Amount",
            "fieldname": "amount",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": "Total",
            "fieldname": "total",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": "Total GST",
            "fieldname": "total_gst",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": "Total With GST",
            "fieldname": "total_with_gst",
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "label": "Expected Closing Date",
            "fieldname": "expected_closing_date",
            "fieldtype": "Date",
            "width": 140
        },
        {
            "label": "Opportunity Status",
            "fieldname": "opportunity_status",
            "fieldtype": "Data",
            "width": 130
        },
        {
            "label": "Source",
            "fieldname": "source",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": "Latest Inquiry Status",
            "fieldname": "latest_inquiry_status",
            "fieldtype": "Data",
            "width": 150
        }
    ]

    # -----------------------------------------
    # QUERY
    # -----------------------------------------

    data = frappe.db.sql(
        f"""
        SELECT

            CASE
                WHEN qi.idx = 1 OR qi.idx IS NULL
                THEN o.name
                ELSE ''
            END AS opportunity,

            CASE
                WHEN qi.idx = 1 OR qi.idx IS NULL
                THEN o.creation
                ELSE NULL
            END AS opportunity_created,

            CASE
                WHEN qi.idx = 1 OR qi.idx IS NULL
                THEN COALESCE(u.full_name, o.opportunity_owner)
                ELSE ''
            END AS sales_person,

            CASE
                WHEN qi.idx = 1 OR qi.idx IS NULL
                THEN (
                    SELECT GROUP_CONCAT(
                        COALESCE(oi.item_name, oi.item_code)
                        ORDER BY oi.idx
                        SEPARATOR ', '
                    )
                    FROM `tabOpportunity Item` oi
                    WHERE oi.parent = o.name
                )
                ELSE ''
            END AS opportunity_items,

            CASE
                WHEN qi.idx = 1 OR qi.idx IS NULL
                THEN
                    CASE
                        WHEN q.name IS NULL THEN 'No'
                        ELSE 'Yes'
                    END
                ELSE ''
            END AS quotation_created,

            CASE
                WHEN qi.idx = 1 OR qi.idx IS NULL
                THEN l.company_name
                ELSE ''
            END AS title,

            CASE
                WHEN q.name IS NULL THEN ''
                ELSE qi.item_name
            END AS item,

            CASE
                WHEN qi.idx = 1 OR qi.idx IS NULL
                THEN q.transaction_date
                ELSE NULL
            END AS quotation_date,

            CASE
                WHEN qi.idx = 1 OR qi.idx IS NULL
                THEN q.quotation_sent_date
                ELSE NULL
            END AS quotation_sent_date,

            CASE
                WHEN qi.idx = 1 OR qi.idx IS NULL
                THEN o.contact_mobile
                ELSE ''
            END AS mobile,

            CASE
                WHEN qi.idx = 1 OR qi.idx IS NULL
                THEN o.contact_email
                ELSE ''
            END AS email,

            CASE
                WHEN qi.idx = 1 OR qi.idx IS NULL
                THEN o.city
                ELSE ''
            END AS city,

            CASE
                WHEN qi.idx = 1 OR qi.idx IS NULL
                THEN o.custom_state
                ELSE ''
            END AS state,

            CASE
                WHEN qi.idx = 1 OR qi.idx IS NULL
                THEN o.custom_country_link
                ELSE ''
            END AS country,

            qi.qty AS qty,

            qi.rate AS rate,

            qi.amount AS amount,

            CASE
                WHEN qi.idx = 1 OR qi.idx IS NULL
                THEN q.total
                ELSE NULL
            END AS total,

            CASE
                WHEN qi.idx = 1 OR qi.idx IS NULL
                THEN q.custom_total_gst
                ELSE NULL
            END AS total_gst,

            CASE
                WHEN qi.idx = 1 OR qi.idx IS NULL
                THEN q.custom_total_with_gst
                ELSE NULL
            END AS total_with_gst,

            CASE
                WHEN qi.idx = 1 OR qi.idx IS NULL
                THEN o.expected_closing
                ELSE NULL
            END AS expected_closing_date,

            CASE
                WHEN qi.idx = 1 OR qi.idx IS NULL
                THEN o.status
                ELSE ''
            END AS opportunity_status,

            CASE
                WHEN qi.idx = 1 OR qi.idx IS NULL
                THEN o.source
                ELSE ''
            END AS source,

            CASE
                WHEN qi.idx = 1 OR qi.idx IS NULL
                THEN o.custom_latest_inquiry_status
                ELSE ''
            END AS latest_inquiry_status

        FROM `tabOpportunity` o

        LEFT JOIN `tabLead` l
            ON l.name = o.party_name

        LEFT JOIN `tabQuotation` q
            ON q.opportunity = o.name
            AND q.docstatus < 2

        LEFT JOIN `tabQuotation Item` qi
            ON qi.parent = q.name

        LEFT JOIN `tabUser` u
            ON u.name = o.opportunity_owner

        {where_clause}

        ORDER BY
            o.creation DESC,
            q.name,
            qi.idx
        """,
        values,
        as_dict=True
    )

    return columns, data