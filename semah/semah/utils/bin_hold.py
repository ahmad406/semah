# Helpers for the bin hold feature (Stock Hold and Release Note).
# A bin is held when Bin Name.on_hold = 1.

import frappe
from frappe import _
from frappe.utils import flt


def get_hold_info(bin_name):
	"""Return {reason, held_by, held_on, hold_ref} if the bin is held, else None."""
	if not bin_name:
		return None
	row = frappe.db.get_value(
		"Bin Name", bin_name,
		["on_hold", "hold_reason", "held_by", "held_on", "hold_ref"],
		as_dict=True,
	)
	if row and row.on_hold:
		return row
	return None


def is_bin_held(bin_name):
	return bool(get_hold_info(bin_name))


def assert_bin_not_held(bin_name, context=None):
	"""Throw a clear error if the bin is on hold."""
	info = get_hold_info(bin_name)
	if not info:
		return
	msg = _("Bin <b>{0}</b> is on hold").format(bin_name)
	if info.hold_ref:
		msg += _(" ({0})").format(info.hold_ref)
	if info.hold_reason:
		msg += _(". Reason: {0}").format(frappe.bold(info.hold_reason))
	if context:
		msg += ". " + context
	frappe.throw(msg, title=_("Bin On Hold"))


def get_held_free_qty(item_code):
	"""Free (unreserved) qty of an item that sits in held bins. Used for shortage hints."""
	res = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(c.stored_qty - COALESCE(c.reserved_qty, 0)), 0)
		FROM `tabitem bin location` c
		INNER JOIN `tabBin Name` bn ON bn.name = c.bin_location
		WHERE c.parent = %s AND bn.on_hold = 1 AND c.stored_qty - COALESCE(c.reserved_qty, 0) > 0
		""",
		(item_code,),
	)
	return flt(res[0][0]) if res else 0
