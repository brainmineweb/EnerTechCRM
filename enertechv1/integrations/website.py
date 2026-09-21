import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import strip_html, validate_email_address, escape_html, add_to_date, now_datetime

ALLOWED_ORIGINS = {"https://brainminetech.com", "https://www.brainminetech.com"}
MAX_WEBSITE_LEADS_PER_HOUR = 30   # global cap across all IPs
MIN_FILL_SECONDS = 3              # humans need more than 3 seconds to fill the form


def clean(value, max_len):
    return strip_html(str(value or "")).strip()[:max_len]


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=5, seconds=60 * 60)  # 5 submissions per IP per hour
def create_lead(full_name, email, phone=None, company=None, services=None,
                message=None, website_url=None, elapsed_ms=0):

    # 1. Honeypot: bots fill this hidden field, so return fake success
    if website_url:
        return {"ok": True}

    # 2. Only accept browser calls made from your own website
    if (frappe.get_request_header("Origin") or "") not in ALLOWED_ORIGINS:
        frappe.throw("Not allowed", frappe.PermissionError)

    # 3. Too-fast submission means a bot: fake success
    try:
        if int(elapsed_ms) < MIN_FILL_SECONDS * 1000:
            return {"ok": True}
    except (TypeError, ValueError):
        return {"ok": True}

    # 4. Global cap: stops spam spread across many IPs
    recent = frappe.db.count("Lead", {
        "source": "Website",
        "creation": (">", add_to_date(now_datetime(), hours=-1)),
    })
    if recent >= MAX_WEBSITE_LEADS_PER_HOUR:
        frappe.throw("Please try again later", frappe.TooManyRequestsError)

    # 5. Clean and validate
    full_name = clean(full_name, 140)
    email = validate_email_address((email or "").strip().lower(), throw=False)
    phone = clean(phone, 20)
    company = clean(company, 140)
    if isinstance(services, (list, tuple)):
        services = ", ".join(str(s) for s in services)
    services = clean(services, 300)
    message = clean(message, 2000)

    if not full_name or not email:
        frappe.throw("Invalid input")

    # 6. Spam text usually contains links: fake success
    if message.lower().count("http") > 2:
        return {"ok": True}

    # Split "Rahul Sharma" into first and last name
    parts = full_name.split(None, 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else None

    # Note that goes on the lead
    note_lines = []
    if services:
        note_lines.append(f"<b>Services:</b> {escape_html(services)}")
    if message:
        note_lines.append(f"<b>Business needs:</b> {escape_html(message)}")
    note = "<br>".join(note_lines)

    # Duplicate: add the note to the existing lead instead of creating another
    existing = frappe.db.get_value("Lead", {"email_id": email}, "name")
    if existing:
        if note:
            frappe.get_doc("Lead", existing).add_comment(
                "Comment", "<b>Website form submitted again</b><br>" + note
            )
        return {"ok": True}

    # Only fields you decide are set here
    lead = frappe.get_doc({
        "doctype": "Lead",
        "first_name": first_name,
        "last_name": last_name,
        "email_id": email,
        "mobile_no": phone,
        "company_name": company,
        "source": "Website",
        "status": "Lead",
    })
    if services and frappe.get_meta("Lead").has_field("custom_services_interested"):
        lead.custom_services_interested = services

    lead.flags.ignore_permissions = True
    lead.insert()
    if note:
        lead.add_comment("Comment", note)

    return {"ok": True}