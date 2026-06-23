import frappe
from semah.semah.api.portal import get_customer_for_user, get_portal_context

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/wh-request"
		raise frappe.Redirect

	get_customer_for_user()

	context.portal = get_portal_context()
	context.show_sidebar = False
	context.title = "Delivery Requests"
	return context
