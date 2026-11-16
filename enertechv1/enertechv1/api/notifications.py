import frappe
from frappe import _
from frappe.utils import escape_html, formatdate, get_fullname, get_url_to_form

STORES_ROLE = "Stores Person"
FALLBACK_SENDER = "sales@enertechups.com"
IGNORED_EMAILS = ("admin@example.com",)


# ============================================================
# Helpers
# ============================================================

def get_role_emails(role):
    """Email addresses of enabled desk users who have the given role."""
    users = frappe.get_all(
        "Has Role",
        filters={"role": role, "parenttype": "User"},
        pluck="parent",
    )
    if not users:
        return []

    emails = frappe.get_all(
        "User",
        filters={"name": ["in", users], "enabled": 1, "user_type": "System User"},
        pluck="email",
    )
    return sorted({e for e in emails if e and e not in IGNORED_EMAILS})


def get_user_email(user):
    """A user's real email address, or '' for Administrator / placeholder addresses."""
    if not user or user in ("Administrator", "Guest"):
        return ""
    email = frappe.db.get_value("User", user, "email") or ""
    return "" if email in IGNORED_EMAILS else email


def has_outgoing_account(email):
    return bool(email) and bool(
        frappe.db.get_value("Email Account", {"email_id": email, "enable_outgoing": 1}, "name")
    )


def get_sender(user):
    """The user's own address if it has an outgoing Email Account, else the fallback.
    Returns None if neither can send; ERPNext then uses the default outgoing account."""
    user_email = get_user_email(user)
    if has_outgoing_account(user_email):
        return user_email
    if has_outgoing_account(FALLBACK_SENDER):
        return FALLBACK_SENDER
    return None


def _link(doctype, name):
    return f'<a href="{get_url_to_form(doctype, name)}">{escape_html(name)}</a>'


def _log(title, message):
    try:
        frappe.log_error(title=title[:140], message=message)
    except Exception:
        pass


# ============================================================
# Material Request → Stores
# ============================================================

def notify_stores_on_request(doc, method=None):
    """Email everyone with the Stores role when a Dish request is submitted.
    Never blocks the submit: problems go to the Error Log."""
    if not doc.get("custom_dish") or doc.material_request_type != "Material Transfer":
        return

    recipients = get_role_emails(STORES_ROLE)
    if not recipients:
        _log(
            "Stores email not sent: " + doc.name,
            f"No enabled users with role '{STORES_ROLE}' and an email address. Material Request: {doc.name}",
        )
        return

    # ---------- Sender, reply-to, cc ----------
    owner_email = get_user_email(doc.owner)
    sender = get_sender(doc.owner)

    if not sender:
        _log(
            "Stores email: no sender account",
            f"Neither {owner_email or doc.owner} nor {FALLBACK_SENDER} has an enabled outgoing "
            f"Email Account. Sending with the default outgoing account. Material Request: {doc.name}",
        )

    reply_to = owner_email or sender or None
    cc = [owner_email] if owner_email and sender != owner_email and owner_email not in recipients else []

    # ---------- Message ----------
    dish = doc.custom_dish
    customer = frappe.db.get_value("Dish", dish, "customer") or ""

    rows = "".join(
        "<tr>"
        f"<td>{escape_html(r.item_code)}</td>"
        f"<td>{escape_html(r.item_name or '')}</td>"
        f"<td style='text-align:right;'>{frappe.format(r.qty, {'fieldtype': 'Float'})}</td>"
        f"<td>{escape_html(r.from_warehouse or '')}</td>"
        "</tr>"
        for r in doc.items
    )

    message = f"""
        <p>Hello,</p>
        <p>A new stock request has been sent to Stores.</p>
        <p>
            <b>Material Request:</b> {_link(doc.doctype, doc.name)}<br>
            <b>Dish:</b> {_link("Dish", dish)}<br>
            <b>Customer:</b> {escape_html(customer)}<br>
            <b>Requested by:</b> {escape_html(get_fullname(doc.owner))}<br>
            <b>Required by:</b> {formatdate(doc.schedule_date)}
        </p>
        <table border="1" cellpadding="6" style="border-collapse:collapse;">
            <tr><th>Item</th><th>Item Name</th><th>Qty</th><th>From Warehouse</th></tr>
            {rows}
        </table>
        <p>Please open the request and click <b>Move to Quality Control</b>.</p>
    """

    # ---------- Send ----------
    try:
        frappe.sendmail(
            recipients=recipients,
            cc=cc,
            sender=sender,
            reply_to=reply_to,
            subject=_("New stock request {0} for Dish {1}").format(doc.name, dish),
            message=message,
            reference_doctype=doc.doctype,
            reference_name=doc.name,
        )
        doc.add_comment(
            "Info",
            _("Stores notified ({0}) from {1}").format(", ".join(recipients), sender or _("default account")),
        )
    except Exception as e:
        _log("Stores email failed: " + doc.name, frappe.get_traceback() or str(e))
        frappe.msgprint(
            _("Request submitted, but the email to Stores could not be sent. Check the Error Log."),
            indicator="orange",
            alert=True,
        )