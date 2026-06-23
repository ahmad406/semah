import frappe
from semah.semah.api.portal import get_customer_for_user, get_portal_context

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/wh-stock"
		raise frappe.Redirect

	# raises a friendly error if user isn't linked to a customer
	get_customer_for_user()

	context.portal = get_portal_context()
	context.show_sidebar = False
	context.title = "My Stock"
	return context
