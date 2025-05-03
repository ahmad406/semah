from . import __version__ as app_version

app_name = "semah"
app_title = "Semah"
app_publisher = "Dconnex"
app_description = "App for semah v13 erpnext"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "cloud@avu.net.in"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/semah/css/semah.css"
app_include_js = "/assets/semah/js/comman.js"

# include js, css files in header of web template
# web_include_css = "/assets/semah/css/semah.css"
# web_include_js = "/assets/semah/js/semah.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "semah/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js =  {
	"Stock Entry":["custom_script/stock_entry/stock_entry.js"],
    "Sales Invoice":["custom_script/sales_invoice/sales_invoice.js"],
	"Delivery Note":["custom_script/delivery_note/delivery_note.js"],
	"Batch":["custom_script/batch/batch.js"],
	"Item" : "custom_script/item/item.js",
}
doctype_list_js = {
	"Item" : "custom_script/item/item_list.js",
	"Stock Entry" : "custom_script/stock_entry/stock_entry_list.js"
	}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "semah.install.before_install"
# after_install = "semah.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "semah.notifications.get_notification_config"

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

override_doctype_class = {
    
	"Stock Entry": "semah.custom_script.stock_entry.stock_entry.CustomStockEntry"
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	# "Stock Entry": {
	# 	# "onload": "semah.custom_script.stock_entry.stock_entry.onload",
	# 	# "validate": "semah.custom_script.stock_entry.stock_entry.validate",
	# 	"before_submit" : "semah.custom_script.stock_entry.stock_entry.before_submit",
	# 	"on_submit" : "semah.custom_script.stock_entry.stock_entry.on_submit",
	# 	"before_cancel" : "semah.custom_script.stock_entry.stock_entry.before_cancel",
	# 	"on_cancel" : "semah.custom_script.stock_entry.stock_entry.on_cancel",
		
	# },
	"Delivery Note": {
		"before_submit" : "semah.custom_script.delivery_note.delivery_note.before_submit",
		"before_cancel" : "semah.custom_script.delivery_note.delivery_note.before_cancel",
        "on_submit" : "semah.custom_script.delivery_note.delivery_note.on_submit",
		 "on_cancel" : "semah.custom_script.delivery_note.delivery_note.on_cancel"
	},
    "Customer": {
		"validate" : "semah.custom_script.customer.customer.validate",
	},
	"Item": {
		"on_update" : "semah.custom_script.item.item.on_update",
        "before_validate" : "semah.custom_script.item.item.validate",
	},
	
	
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"semah.tasks.all"
# 	],
# 	"daily": [
# 		"semah.tasks.daily"
# 	],
# 	"hourly": [
# 		"semah.tasks.hourly"
# 	],
# 	"weekly": [
# 		"semah.tasks.weekly"
# 	]
# 	"monthly": [
# 		"semah.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "semah.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "semah.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "semah.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]


# User Data Protection
# --------------------

user_data_fields = [
	{
		"doctype": "{doctype_1}",
		"filter_by": "{filter_by}",
		"redact_fields": ["{field_1}", "{field_2}"],
		"partial": 1,
	},
	{
		"doctype": "{doctype_2}",
		"filter_by": "{filter_by}",
		"partial": 1,
	},
	{
		"doctype": "{doctype_3}",
		"strict": False,
	},
	{
		"doctype": "{doctype_4}"
	}
]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"semah.auth.validate"
# ]
fixtures = ['Property Setter','Custom Field', 'Print Format']
