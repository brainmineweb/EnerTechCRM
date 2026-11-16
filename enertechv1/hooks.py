app_name = "enertechv1"
app_title = "EnerTechv1"
app_publisher = "Brainmine AI"
app_description = "Custom App for the EnerTech UPS"
app_email = "nileshp01@brainmine.ai"
app_license = "mit"



# Fixtures to export and include with the app
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            ["dt", "in", [
                "Lead",
                "Quotation",
                "Quotation Item",
                "Opportunity",
                "Sales Order",
                "Sales Order Item",
                "Item",
                "Expense Claim",
                "Expense Claim Detail",
                "Employee",
                "Warehouse",
                "Customer Group",
                "Material Request",
                "Stock Entry",
                "Quality Inspection",
                "Delivery Note",
            ]],
        ]
    },
    {
        "dt": "Role",
        "filters": [["name", "in", ["Stores Person"]]],
    },
    "Property Setter",
    "Client Script",
    "Server Script",
    "Workspace",
    "Web Page",
    "Print Format",
    "Report",
    "Custom DocPerm",
    "Translation",
]


# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "enertechv1",
# 		"logo": "/assets/enertechv1/logo.png",
# 		"title": "EnerTechv1",
# 		"route": "/enertechv1",
# 		"has_permission": "enertechv1.api.permission.has_app_permission"
# 	}
# ]


permission_query_conditions = {
    "Lead": "enertechv1.permissions.lead_query"
}
# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/enertechv1/css/enertechv1.css"
# app_include_js = "/assets/enertechv1/js/enertechv1.js"

# include js, css files in header of web template
# web_include_css = "/assets/enertechv1/css/enertechv1.css"
# web_include_js = "/assets/enertechv1/js/enertechv1.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "enertechv1/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "enertechv1/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "enertechv1.utils.jinja_methods",
# 	"filters": "enertechv1.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "enertechv1.install.before_install"
# after_install = "enertechv1.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "enertechv1.uninstall.before_uninstall"
# after_uninstall = "enertechv1.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "enertechv1.utils.before_app_install"
# after_app_install = "enertechv1.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "enertechv1.utils.before_app_uninstall"
# after_app_uninstall = "enertechv1.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "enertechv1.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }
doc_events = {
    "Material Request": {
        "on_submit": [
            "enertechv1.enertechv1.api.stores.on_linked_doc_change",
            "enertechv1.enertechv1.api.notifications.notify_stores_on_request",
        ],
        "on_cancel": "enertechv1.enertechv1.api.stores.on_linked_doc_change",
        "on_update_after_submit": "enertechv1.enertechv1.api.stores.on_linked_doc_change",
    },
    "Stock Entry": {
        "validate": "enertechv1.enertechv1.api.stores.stock_entry_validate",
        "on_submit": "enertechv1.enertechv1.api.stores.stock_entry_on_submit",
        "on_cancel": "enertechv1.enertechv1.api.stores.stock_entry_on_cancel",
    },
    "Quality Inspection": {
        "validate": "enertechv1.enertechv1.api.stores.quality_inspection_validate",
        "before_submit": "enertechv1.enertechv1.api.stores.quality_inspection_before_submit",
        "on_submit": "enertechv1.enertechv1.api.stores.quality_inspection_on_submit",
        "before_cancel": "enertechv1.enertechv1.api.stores.quality_inspection_before_cancel",
        "on_cancel": "enertechv1.enertechv1.api.stores.quality_inspection_on_cancel",
    },
    "Delivery Note": {
        "validate": "enertechv1.enertechv1.api.stores.delivery_note_validate",
        "on_submit": [
            "enertechv1.enertechv1.api.stores.delivery_note_on_submit",
            "enertechv1.enertechv1.api.returns.on_return_submit",
        ],
        "before_cancel": "enertechv1.enertechv1.api.returns.on_return_before_cancel",
        "on_cancel": "enertechv1.enertechv1.api.stores.on_linked_doc_change",
    },
}
# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"enertechv1.tasks.all"
# 	],
# 	"daily": [
# 		"enertechv1.tasks.daily"
# 	],
# 	"hourly": [
# 		"enertechv1.tasks.hourly"
# 	],
# 	"weekly": [
# 		"enertechv1.tasks.weekly"
# 	],
# 	"monthly": [
# 		"enertechv1.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "enertechv1.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "enertechv1.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "enertechv1.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["enertechv1.utils.before_request"]
# after_request = ["enertechv1.utils.after_request"]

# Job Events
# ----------
# before_job = ["enertechv1.utils.before_job"]
# after_job = ["enertechv1.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"enertechv1.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logsa
# }
doctype_js = {
    "Quotation": "public/js/Quotation.js",
    "Opportunity": "public/js/Opportunity.js",
    "Sales Order": "public/js/Sales Order.js",
    "Payment Entry": "public/js/Payment Entry.js",
    "Lead": "public/js/Lead.js",
    "Material Request": "public/js/Material Request.js",
    "Quality Inspection": "public/js/quality_inspection.js",
}