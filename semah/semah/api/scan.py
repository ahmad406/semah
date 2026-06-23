# Copyright (c) 2026, Dconnex and contributors
# Mobile scan API — all SQL parameterized, all endpoints scoped to session user's roles.
# Drop this file in: semah/semah/api/scan.py

import frappe
from frappe import _
from frappe.utils import flt, nowdate, now_datetime


def _assert_stock_role():
    allowed = {'Stock User', 'Stock Manager', 'System Manager', 'Warehouse Manager'}
    if not allowed & set(frappe.get_roles()):
        frappe.throw(_("Access denied."), frappe.PermissionError)


# ─── 1. PON list for scanning ─────────────────────────────────────────────────

@frappe.whitelist()
def get_pons_for_scanning():
    """Return open Preparation Order Notes (excluding Completed/Cancelled).
    Includes a per-row item count and how many items are already scanned.
    """
    _assert_stock_role()

    pons = frappe.db.sql(
        """
        SELECT
            p.name,
            p.customer,
            p.sub_customer,
            p.order_status,
            p.required_date,
            p.allow_delivery,
            p.actual_qty,
            p.scanned_qty,
            p.total_quantity,
            c.customer_name,
            (SELECT COUNT(*) FROM `tabPreparation Storage Details` s
             WHERE s.parent = p.name) AS item_count
        FROM `tabPreparation Order Note` p
        LEFT JOIN `tabCustomer` c ON c.name = p.customer
        WHERE p.order_status NOT IN ('Completed', 'Cancelled') and p.docstatus=1
        ORDER BY p.modified DESC
        LIMIT 100
        """,
        as_dict=True,
    )
    return pons


# ─── 2. Full scan data for one PON ───────────────────────────────────────────

@frappe.whitelist()
def get_pon_scan_data(pon_name):
    """Return the PON header + storage_details to scan + already scanned items."""
    _assert_stock_role()
    if not pon_name:
        frappe.throw(_("pon_name is required."))

    pon = frappe.db.get_value(
        "Preparation Order Note",
        pon_name,
        [
            "name", "customer", "sub_customer", "order_status",
            "required_date", "allow_delivery", "actual_qty",
            "scanned_qty", "total_quantity", "note",
        ],
        as_dict=True,
    )
    if not pon:
        frappe.throw(_("Preparation Order Note {0} not found.").format(pon_name))

    # Customer name
    pon["customer_name"] = frappe.db.get_value("Customer", pon.customer, "customer_name") or pon.customer

    # Storage details (what needs to be scanned)
    storage = frappe.db.sql(
        """
        SELECT
            s.name,
            s.item,
            s.item_name,
            s.bin_location_name,
            s.pallet,
            s.batch_no,
            s.delivery_qty,
            s.expiry_date,
            s.warehouse,
            s.sub_customer,
            s.uom
        FROM `tabPreparation Storage Details` s
        WHERE s.parent = %s AND s.parenttype = 'Preparation Order Note'
        ORDER BY s.idx
        """,
        (pon_name,),
        as_dict=True,
    )

    # Already scanned rows (scanned_items child table)
    scanned = frappe.db.sql(
        """
        SELECT
            sc.name,
            sc.bin_location_name,
            sc.pallet,
            sc.batch_no,
            sc.delivery_qty,
            sc.source_row
        FROM `tabPreparation Storage Details barcode` sc
        WHERE sc.parent = %s AND sc.parenttype = 'Preparation Order Note'
        ORDER BY sc.idx
        """,
        (pon_name,),
        as_dict=True,
    )

    return {
        "pon": pon,
        "storage_details": storage,
        "scanned_items": scanned,
    }


# ─── 3. Record one scan ────────────────────────────────────────────────────────

@frappe.whitelist()
def submit_scan(pon_name=None, row_name=None, delivery_qty=None):
    """Add or update a scanned entry in scanned_items for the given storage row.
    Validates that row_name belongs to this PON.
    Reads from both kwargs and form_dict to handle Frappe JSON body parsing
    differences across versions.
    """
    _assert_stock_role()

    pon_name     = pon_name     or frappe.form_dict.get('pon_name')
    row_name     = row_name     or frappe.form_dict.get('row_name')
    delivery_qty = delivery_qty if delivery_qty is not None \
                   else frappe.form_dict.get('delivery_qty', 0)

    if not pon_name:
        frappe.throw(_("pon_name is required."))
    if not row_name:
        frappe.throw(_("row_name is required."))

    delivery_qty = flt(delivery_qty)
    if delivery_qty < 0:
        frappe.throw(_("Quantity cannot be negative."))

    # Validate the row belongs to this PON
    row = frappe.db.get_value(
        "Preparation Storage Details",
        {"name": row_name, "parent": pon_name, "parenttype": "Preparation Order Note"},
        [
            "name", "item", "item_name", "bin_location_name", "pallet",
            "batch_no", "delivery_qty", "expiry_date", "warehouse",
            "sub_customer", "uom", "qty_required", "stored_qty",
            "stored_in", "area_used", "height", "width", "length",
            "description", "required_date",
        ],
        as_dict=True,
    )
    if not row:
        frappe.throw(_("Storage row {0} not found on order {1}.").format(row_name, pon_name))

    pon_doc = frappe.get_doc("Preparation Order Note", pon_name)

    # Check if already scanned (by source_row reference)
    existing = next(
        (s for s in pon_doc.get("scanned_items") if s.get("source_row") == row_name),
        None,
    )

    if existing:
        existing.delivery_qty = delivery_qty
    else:
        pon_doc.append(
            "scanned_items",
            {
                "item":              row.item,
                "item_name":         row.item_name,
                "bin_location_name": row.bin_location_name,
                "pallet":            row.pallet,
                "batch_no":          row.batch_no,
                "delivery_qty":      delivery_qty,
                "expiry_date":       row.expiry_date,
                "warehouse":         row.warehouse,
                "sub_customer":      row.sub_customer,
                "uom":               row.uom,
                "qty_required":      row.qty_required,
                "stored_qty":        row.stored_qty,
                "stored_in":         row.stored_in,
                "area_used":         row.area_used,
                "height":            row.height,
                "width":             row.width,
                "length":            row.length,
                "description":       row.description,
                "required_date":     row.required_date,
                "source_row":        row_name,   # link back to storage row
            },
        )

    # Update aggregate scanned qty on the PON
    total_scanned = sum(
        flt(s.delivery_qty) for s in pon_doc.get("scanned_items")
    )
    pon_doc.scanned_qty = total_scanned
    pon_doc.flags.ignore_permissions = True
    pon_doc.save()
    frappe.db.commit()

    return {
        "scanned_row": row_name,
        "delivery_qty": delivery_qty,
        "total_scanned": total_scanned,
    }


# ─── 4. Finalize scan ─────────────────────────────────────────────────────────

@frappe.whitelist()
def finalize_scan(pon_name=None):
    """Validate all storage_details rows have a matching scan, then set allow_delivery = 1.
    Raises if any row is missing or has a mismatched qty.
    """
    _assert_stock_role()

    pon_name = pon_name or frappe.form_dict.get('pon_name')
    if not pon_name:
        frappe.throw(_("pon_name is required."))

    pon_doc = frappe.get_doc("Preparation Order Note", pon_name)

    storage_rows = {r.name: r for r in pon_doc.get("storage_details")}
    scanned_map  = {s.source_row: s for s in pon_doc.get("scanned_items") if s.get("source_row")}

    missing = []
    mismatches = []

    for row_name, row in storage_rows.items():
        if row_name not in scanned_map:
            missing.append(f"{row.bin_location_name} / {row.pallet} — {row.item_name}")
            continue
        scan = scanned_map[row_name]
        if flt(scan.delivery_qty) != flt(row.delivery_qty):
            mismatches.append(
                f"{row.bin_location_name} / {row.pallet}: "
                f"expected {row.delivery_qty}, scanned {scan.delivery_qty}"
            )

    if missing:
        frappe.throw(
            _("The following items have not been scanned:\n{0}").format("\n".join(missing))
        )

    if mismatches:
        frappe.throw(
            _("Quantity mismatches found (confirm overrides on the app):\n{0}").format(
                "\n".join(mismatches)
            )
        )

    pon_doc.allow_delivery = "1"
    pon_doc.order_status = "To make Delivery Note"
    pon_doc.flags.ignore_permissions = True
    pon_doc.save()
    frappe.db.commit()

    return {
        "success": True,
        "message": f"All {len(storage_rows)} items scanned. Delivery Note creation is now enabled on the desk.",
    }


# ADD THESE FUNCTIONS TO YOUR EXISTING scan.py
# Path: semah/semah/semah/api/scan.py
# Append everything below to the end of the file (keep the existing functions).
# ════════════════════════════════════════════════════════════════════════════

# ─── BIN TRANSFER ─────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_bin_contents(bin_name=None):
    """Return what's stored in a bin (for the transfer source preview)."""
    _assert_stock_role()
    bin_name = bin_name or frappe.form_dict.get('bin_name')
    if not bin_name:
        frappe.throw(_("bin_name is required."))

    if not frappe.db.exists("Bin Name", bin_name):
        frappe.throw(_("Bin {0} not found.").format(bin_name))

    status = frappe.db.get_value("Bin Name", bin_name, "status")

    rows = frappe.db.sql(
        """
        SELECT
            c.name,
            c.parent AS item_code,
            c.pallet,
            c.bin_location,
            c.stored_qty,
            c.batch_no,
            DATE_FORMAT(c.expiry, '%%d-%%m-%%Y') AS expiry,
            c.warehouse
        FROM `tabitem bin location` c
        WHERE c.bin_location = %s AND c.stored_qty > 0
        """,
        (bin_name,),
        as_dict=True,
    )

    for r in rows:
        r["item_name"] = frappe.db.get_value("Item", r.item_code, "item_name") or r.item_code

    return {
        "bin_name": bin_name,
        "status": status,
        "contents": rows,
        "is_empty": len(rows) == 0,
    }


@frappe.whitelist()
def do_bin_transfer(source_bin=None, target_bin=None):
    """Move stock from source_bin to target_bin by creating + submitting a
    Transfer Bin document. Uses the existing doctype so all its validation runs.
    """
    _assert_stock_role()
    source_bin = source_bin or frappe.form_dict.get('source_bin')
    target_bin = target_bin or frappe.form_dict.get('target_bin')

    if not source_bin or not target_bin:
        frappe.throw(_("Both source_bin and target_bin are required."))
    if source_bin == target_bin:
        frappe.throw(_("Source and target bin cannot be the same."))

    # Pre-checks (mirror the doctype so we fail fast with a clean message)
    source_status = frappe.db.get_value("Bin Name", source_bin, "status")
    if source_status == "Vacant":
        frappe.throw(_("Source bin {0} is vacant.").format(source_bin))

    target_status = frappe.db.get_value("Bin Name", target_bin, "status")
    if target_status == "Occupied":
        frappe.throw(_("Target bin {0} is already occupied.").format(target_bin))

    source_rows = frappe.db.sql(
        """SELECT name FROM `tabitem bin location`
           WHERE bin_location = %s AND stored_qty > 0""",
        (source_bin,),
    )
    if not source_rows:
        frappe.throw(_("Source bin {0} has no stock.").format(source_bin))
    if len(source_rows) > 1:
        frappe.throw(
            _("Bin {0} holds multiple stock records — transfer it on the desk.").format(source_bin)
        )

    # Create + submit the Transfer Bin document (runs its own on_submit logic)
    doc = frappe.new_doc("Transfer Bin")
    doc.source_bin = source_bin
    doc.target_bin = target_bin
    doc.flags.ignore_permissions = True
    doc.insert()
    doc.submit()
    frappe.db.commit()

    return {
        "success": True,
        "transfer": doc.name,
        "message": f"Moved stock from {source_bin} to {target_bin}.",
    }


# ════════════════════════════════════════════════════════════════════════════
# RECEIVING — BIN ASSIGNMENT (CORRECTED FLOW)
# ════════════════════════════════════════════════════════════════════════════
# Real flow:
#   1. User creates Material Receipt, enters item (qty 15)
#   2. Clicks "Update Storage" → system splits by pallet capacity into rows
#      (e.g. 3 rows of qty 5), each row already has stored_qty + pallet + batch,
#      but bin_location is EMPTY
#   3. Saved as draft
#   4. Worker scans ONE bin per storage row → bin_location gets filled
#
# The app does NOT enter qty or pick items — every row is pre-made.
# Worker just assigns a vacant bin to each row, one scan per row.
#
# Append/replace the receiving section in your scan.py with this.
# ════════════════════════════════════════════════════════════════════════════


@frappe.whitelist()


# ─── RECEIVING / PUT-AWAY (one bin per pre-split row) ───────────────────────

@frappe.whitelist()
def get_open_receipts():
    """Draft Material Receipt Stock Entries that have storage rows still
    missing a bin_location (i.e. still need put-away scanning).
    """
    _assert_stock_role()

    rows = frappe.db.sql(
        """
        SELECT
            se.name,
            se.posting_date,
            se.customer_nm AS customer,
            se.total_items as total_qty,
            (SELECT COUNT(*) FROM `tabStorage details` s
                WHERE s.parent = se.name) AS total_rows,
            (SELECT COUNT(*) FROM `tabStorage details` s
                WHERE s.parent = se.name
                AND (s.bin_location IS NULL OR s.bin_location = '')) AS pending_rows
        FROM `tabStock Entry` se
        WHERE se.stock_entry_type = 'Material Receipt'
        AND se.docstatus = 0
        HAVING total_rows > 0
        ORDER BY se.modified DESC
        LIMIT 50
        """,
        as_dict=True,
    )
    return rows


@frappe.whitelist()
def get_receipt_rows(se_name=None):
    """Return the pre-split storage rows of a draft receipt.
    Each row already has item, batch, qty, expiry — only bin_location may be empty.
    The worker scans one bin per row.
    """
    _assert_stock_role()
    se_name = se_name or frappe.form_dict.get('se_name')
    if not se_name:
        frappe.throw(_("se_name is required."))

    se = frappe.db.get_value(
        "Stock Entry", se_name,
        ["name", "stock_entry_type", "customer_nm", "posting_date", "docstatus"],
        as_dict=True,
    )
    if not se:
        frappe.throw(_("Stock Entry {0} not found.").format(se_name))
    if se.docstatus != 0:
        frappe.throw(_("This receipt is already submitted."))

    rows = frappe.db.sql(
        """
        SELECT
            s.name,
            s.item_code,
            s.item_name,
            s.stored_qty,
            s.pallet,
            s.bin_location,
            s.batch_no,
            DATE_FORMAT(s.expiry, '%%Y-%%m-%%d') AS expiry,
            s.t_ware_house AS warehouse,
            s.uom
        FROM `tabStorage details` s
        WHERE s.parent = %s AND s.parenttype = 'Stock Entry'
        ORDER BY s.idx
        """,
        (se_name,),
        as_dict=True,
    )

    pending = sum(1 for r in rows if not r.bin_location)

    return {
        "stock_entry": se,
        "rows": rows,
        "total_rows": len(rows),
        "pending_rows": pending,
    }


@frappe.whitelist()
def assign_bin_to_row(se_name=None, row_name=None, bin_location=None):
    """Assign a scanned empty bin to ONE pre-split storage row.
    Validates the bin is vacant and the row belongs to this receipt.
    Saves immediately so progress is never lost.
    """
    _assert_stock_role()

    se_name      = se_name      or frappe.form_dict.get('se_name')
    row_name     = row_name     or frappe.form_dict.get('row_name')
    bin_location = bin_location or frappe.form_dict.get('bin_location')

    if not se_name or not row_name or not bin_location:
        frappe.throw(_("se_name, row_name and bin_location are required."))

    # bin must exist + be vacant
    if not frappe.db.exists("Bin Name", bin_location):
        frappe.throw(_("Bin {0} does not exist.").format(bin_location))

    bin_status = frappe.db.get_value("Bin Name", bin_location, "status")

    # STRICT empty check: sum actual stored qty, not just existence
    stored_total = frappe.db.sql(
        """SELECT COALESCE(SUM(stored_qty), 0) FROM `tabitem bin location`
           WHERE bin_location = %s AND stored_qty > 0""",
        (bin_location,),
    )[0][0]

    if flt(stored_total) > 0:
        frappe.throw(_("Bin {0} is not empty — it holds {1} units.").format(bin_location, flt(stored_total)))
    if bin_status == "Occupied":
        frappe.throw(_("Bin {0} is marked Occupied.").format(bin_location))

    # bin must not already be used by another row on THIS receipt
    se = frappe.get_doc("Stock Entry", se_name)
    if se.docstatus != 0:
        frappe.throw(_("This receipt is already submitted."))

    for r in se.get("storage_details"):
        if r.name != row_name and (r.bin_location or "") == bin_location:
            frappe.throw(
                _("Bin {0} is already assigned to another row on this receipt.").format(bin_location)
            )

    # find + set the target row
    target = next((r for r in se.get("storage_details") if r.name == row_name), None)
    if not target:
        frappe.throw(_("Storage row not found on this receipt."))

    target.bin_location = bin_location
    se.flags.ignore_permissions = True
    se.save()

    # mark bin occupied so it can't be scanned for another row mid-session
    frappe.db.set_value("Bin Name", bin_location, "status", "Occupied")
    frappe.db.commit()

    # how many rows still pending?
    pending = sum(1 for r in se.get("storage_details") if not r.bin_location)

    return {
        "success": True,
        "row": row_name,
        "bin": bin_location,
        "item_code": target.item_code,
        "stored_qty": target.stored_qty,
        "pending_rows": pending,
    }


@frappe.whitelist()
def clear_bin_from_row(se_name=None, row_name=None):
    """Undo: remove the bin from a storage row (if worker scanned wrong bin).
    Frees the bin back to Vacant.
    """
    _assert_stock_role()
    se_name  = se_name  or frappe.form_dict.get('se_name')
    row_name = row_name or frappe.form_dict.get('row_name')

    se = frappe.get_doc("Stock Entry", se_name)
    if se.docstatus != 0:
        frappe.throw(_("This receipt is already submitted."))

    target = next((r for r in se.get("storage_details") if r.name == row_name), None)
    if not target:
        frappe.throw(_("Row not found."))

    old_bin = target.bin_location
    target.bin_location = None
    se.flags.ignore_permissions = True
    se.save()

    # free the bin only if no other stock/row uses it
    if old_bin:
        still_used = any(
            (r.bin_location or "") == old_bin for r in se.get("storage_details")
        )
        has_stock = frappe.db.exists(
            "item bin location", {"bin_location": old_bin, "stored_qty": (">", 0)}
        )
        if not still_used and not has_stock:
            frappe.db.set_value("Bin Name", old_bin, "status", "Vacant")

    frappe.db.commit()
    return {"success": True, "freed_bin": old_bin}
# ════════════════════════════════════════════════════════════════════════════
# ADD THESE TO scan.py (append at the bottom, after the other functions)
# ════════════════════════════════════════════════════════════════════════════

# ─── BIN / PALLET LOOKUP ──────────────────────────────────────────────────────

@frappe.whitelist()
def lookup_scan(scan_value=None):
    """Scan a bin OR pallet barcode and get full info on what's stored:
    item, batch, qty, reserved, expiry, manufacturing date, pallet, bin, etc.
    Tries bin_location first, then pallet.
    """
    _assert_stock_role()
    scan_value = scan_value or frappe.form_dict.get('scan_value')
    if not scan_value:
        frappe.throw(_("scan_value is required."))

    scan_value = scan_value.strip()

    # Try as BIN first
    rows = frappe.db.sql(
        """
        SELECT
            c.parent AS item_code,
            c.bin_location,
            c.pallet,
            c.warehouse,
            c.stored_qty,
            COALESCE(c.reserved_qty, 0) AS reserved_qty,
            (c.stored_qty - COALESCE(c.reserved_qty, 0)) AS available_qty,
            c.batch_no,
            DATE_FORMAT(c.expiry, '%%d-%%m-%%Y') AS expiry,
            DATE_FORMAT(c.manufacturing_date, '%%d-%%m-%%Y') AS manufacturing_date,
            c.sub_customer,
            c.area_use
        FROM `tabitem bin location` c
        WHERE c.bin_location = %s AND c.stored_qty > 0
        """,
        (scan_value,),
        as_dict=True,
    )
    matched_as = "bin"

    # If nothing, try as PALLET
    if not rows:
        rows = frappe.db.sql(
            """
            SELECT
                c.parent AS item_code,
                c.bin_location,
                c.pallet,
                c.warehouse,
                c.stored_qty,
                COALESCE(c.reserved_qty, 0) AS reserved_qty,
                (c.stored_qty - COALESCE(c.reserved_qty, 0)) AS available_qty,
                c.batch_no,
                DATE_FORMAT(c.expiry, '%%d-%%m-%%Y') AS expiry,
                DATE_FORMAT(c.manufacturing_date, '%%d-%%m-%%Y') AS manufacturing_date,
                c.sub_customer,
                c.area_use
            FROM `tabitem bin location` c
            WHERE c.pallet = %s AND c.stored_qty > 0
            """,
            (scan_value,),
            as_dict=True,
        )
        matched_as = "pallet"

    # Resolve bin status / type even if empty
    bin_status = None
    if frappe.db.exists("Bin Name", scan_value):
        bin_status = frappe.db.get_value("Bin Name", scan_value, "status")
        matched_as = matched_as if rows else "bin"

    if not rows:
        return {
            "found": False,
            "scan_value": scan_value,
            "matched_as": "bin" if bin_status else "unknown",
            "bin_status": bin_status,
            "message": _("Nothing stored under {0}.").format(scan_value)
                       + ((" Bin status: " + bin_status) if bin_status else ""),
        }

    # add item names + customer
    for r in rows:
        r["item_name"] = frappe.db.get_value("Item", r.item_code, "item_name") or r.item_code
        r["customer"] = frappe.db.get_value("Item", r.item_code, "customer_") or ""

    return {
        "found": True,
        "scan_value": scan_value,
        "matched_as": matched_as,
        "bin_status": bin_status,
        "records": rows,
    }


# ─── STRICT EMPTY-BIN VALIDATION (used by receiving) ─────────────────────────
# This is already enforced inside assign_bin_to_row, but exposed separately so
# the app can verify a bin is empty BEFORE the user even sees the confirm screen.

@frappe.whitelist()
def is_bin_empty(bin_name=None):
    """Return whether a bin is truly empty and safe to assign.
    Checks BOTH the Bin Name status AND actual stored stock.
    """
    _assert_stock_role()
    bin_name = bin_name or frappe.form_dict.get('bin_name')
    if not bin_name:
        frappe.throw(_("bin_name is required."))

    if not frappe.db.exists("Bin Name", bin_name):
        return {"empty": False, "reason": "not_found",
                "message": _("Bin {0} does not exist.").format(bin_name)}

    status = frappe.db.get_value("Bin Name", bin_name, "status")

    stored = frappe.db.sql(
        """SELECT COALESCE(SUM(stored_qty), 0) AS qty
           FROM `tabitem bin location`
           WHERE bin_location = %s AND stored_qty > 0""",
        (bin_name,),
        as_dict=True,
    )[0]

    if flt(stored.qty) > 0:
        return {"empty": False, "reason": "has_stock",
                "message": _("Bin {0} already holds {1} units.").format(bin_name, flt(stored.qty))}

    if status == "Occupied":
        return {"empty": False, "reason": "marked_occupied",
                "message": _("Bin {0} is marked Occupied.").format(bin_name)}

    return {"empty": True, "status": status,
            "message": _("Bin {0} is empty and available.").format(bin_name)}


# ─── SITE BRANDING (for in-app logo, not the OS launcher icon) ───────────────
# Android/iOS launcher icons are baked into the APK at build time and cannot
# be changed at runtime by any app — this is a platform restriction, not a
# limitation of this code. What we CAN do: fetch the client's logo from their
# Frappe site and display it inside the app (login screen, home header) right
# after they connect. allow_guest=True so it works before login too.

@frappe.whitelist(allow_guest=True)
def get_site_branding():
    """Return the site's logo URL + display name for in-app branding.
    Reads Website Settings.app_logo (same logo shown in the desk navbar).
    """
    logo_path = None
    try:
        logo_path = frappe.db.get_single_value("Website Settings", "app_logo")
    except Exception:
        logo_path = None

    if not logo_path:
        try:
            logo_path = frappe.db.get_single_value("Navbar Settings", "app_logo")
        except Exception:
            logo_path = None

    site_title = None
    try:
        site_title = frappe.db.get_single_value("Website Settings", "app_name")
    except Exception:
        site_title = None

    logo_url = None
    if logo_path:
        base = frappe.utils.get_url()
        logo_url = logo_path if logo_path.startswith("http") else f"{base}{logo_path}"

    return {
        "logo_url": logo_url,
        "site_title": site_title or frappe.local.site,
    }

# ─── BIN TRANSFER ─────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_bin_contents(bin_name=None):
    """Return what's stored in a bin (for the transfer source preview)."""
    _assert_stock_role()
    bin_name = bin_name or frappe.form_dict.get('bin_name')
    if not bin_name:
        frappe.throw(_("bin_name is required."))

    if not frappe.db.exists("Bin Name", bin_name):
        frappe.throw(_("Bin {0} not found.").format(bin_name))

    status = frappe.db.get_value("Bin Name", bin_name, "status")

    rows = frappe.db.sql(
        """
        SELECT
            c.name,
            c.parent AS item_code,
            c.pallet,
            c.bin_location,
            c.stored_qty,
            c.batch_no,
            DATE_FORMAT(c.expiry, '%%d-%%m-%%Y') AS expiry,
            c.warehouse
        FROM `tabitem bin location` c
        WHERE c.bin_location = %s AND c.stored_qty > 0
        """,
        (bin_name,),
        as_dict=True,
    )

    for r in rows:
        r["item_name"] = frappe.db.get_value("Item", r.item_code, "item_name") or r.item_code

    return {
        "bin_name": bin_name,
        "status": status,
        "contents": rows,
        "is_empty": len(rows) == 0,
    }


@frappe.whitelist()
def do_bin_transfer(source_bin=None, target_bin=None):
    """Move stock from source_bin to target_bin by creating + submitting a
    Transfer Bin document. Uses the existing doctype so all its validation runs.
    """
    _assert_stock_role()
    source_bin = source_bin or frappe.form_dict.get('source_bin')
    target_bin = target_bin or frappe.form_dict.get('target_bin')

    if not source_bin or not target_bin:
        frappe.throw(_("Both source_bin and target_bin are required."))
    if source_bin == target_bin:
        frappe.throw(_("Source and target bin cannot be the same."))

    # Pre-checks (mirror the doctype so we fail fast with a clean message)
    source_status = frappe.db.get_value("Bin Name", source_bin, "status")
    if source_status == "Vacant":
        frappe.throw(_("Source bin {0} is vacant.").format(source_bin))

    target_status = frappe.db.get_value("Bin Name", target_bin, "status")
    if target_status == "Occupied":
        frappe.throw(_("Target bin {0} is already occupied.").format(target_bin))

    source_rows = frappe.db.sql(
        """SELECT name FROM `tabitem bin location`
           WHERE bin_location = %s AND stored_qty > 0""",
        (source_bin,),
    )
    if not source_rows:
        frappe.throw(_("Source bin {0} has no stock.").format(source_bin))
    if len(source_rows) > 1:
        frappe.throw(
            _("Bin {0} holds multiple stock records — transfer it on the desk.").format(source_bin)
        )

    # Create + submit the Transfer Bin document (runs its own on_submit logic)
    doc = frappe.new_doc("Transfer Bin")
    doc.source_bin = source_bin
    doc.target_bin = target_bin
    doc.flags.ignore_permissions = True
    doc.insert()
    doc.submit()
    frappe.db.commit()

    return {
        "success": True,
        "transfer": doc.name,
        "message": f"Moved stock from {source_bin} to {target_bin}.",
    }


# ════════════════════════════════════════════════════════════════════════════
# RECEIVING — BIN ASSIGNMENT (CORRECTED FLOW)
# ════════════════════════════════════════════════════════════════════════════
# Real flow:
#   1. User creates Material Receipt, enters item (qty 15)
#   2. Clicks "Update Storage" → system splits by pallet capacity into rows
#      (e.g. 3 rows of qty 5), each row already has stored_qty + pallet + batch,
#      but bin_location is EMPTY
#   3. Saved as draft
#   4. Worker scans ONE bin per storage row → bin_location gets filled
#
# The app does NOT enter qty or pick items — every row is pre-made.
# Worker just assigns a vacant bin to each row, one scan per row.
#
# Append/replace the receiving section in your scan.py with this.
# ════════════════════════════════════════════════════════════════════════════


@frappe.whitelist()


# ─── RECEIVING / PUT-AWAY (one bin per pre-split row) ───────────────────────

@frappe.whitelist()
def get_open_receipts():
    """Draft Material Receipt Stock Entries that have storage rows still
    missing a bin_location (i.e. still need put-away scanning).
    """
    _assert_stock_role()

    rows = frappe.db.sql(
        """
        SELECT
            se.name,
            se.posting_date,
            se.customer_nm AS customer,
            se.total_items as total_qty,
            (SELECT COUNT(*) FROM `tabStorage details` s
                WHERE s.parent = se.name) AS total_rows,
            (SELECT COUNT(*) FROM `tabStorage details` s
                WHERE s.parent = se.name
                AND (s.bin_location IS NULL OR s.bin_location = '')) AS pending_rows
        FROM `tabStock Entry` se
        WHERE se.stock_entry_type = 'Material Receipt'
        AND se.docstatus = 0
        HAVING total_rows > 0
        ORDER BY se.modified DESC
        LIMIT 50
        """,
        as_dict=True,
    )
    return rows


@frappe.whitelist()
def get_receipt_rows(se_name=None):
    """Return the pre-split storage rows of a draft receipt.
    Each row already has item, batch, qty, expiry — only bin_location may be empty.
    The worker scans one bin per row.
    """
    _assert_stock_role()
    se_name = se_name or frappe.form_dict.get('se_name')
    if not se_name:
        frappe.throw(_("se_name is required."))

    se = frappe.db.get_value(
        "Stock Entry", se_name,
        ["name", "stock_entry_type", "customer_nm", "posting_date", "docstatus"],
        as_dict=True,
    )
    if not se:
        frappe.throw(_("Stock Entry {0} not found.").format(se_name))
    if se.docstatus != 0:
        frappe.throw(_("This receipt is already submitted."))

    rows = frappe.db.sql(
        """
        SELECT
            s.name,
            s.item_code,
            s.item_name,
            s.stored_qty,
            s.pallet,
            s.bin_location,
            s.batch_no,
            DATE_FORMAT(s.expiry, '%%Y-%%m-%%d') AS expiry,
            s.t_ware_house AS warehouse,
            s.uom
        FROM `tabStorage details` s
        WHERE s.parent = %s AND s.parenttype = 'Stock Entry'
        ORDER BY s.idx
        """,
        (se_name,),
        as_dict=True,
    )

    pending = sum(1 for r in rows if not r.bin_location)

    return {
        "stock_entry": se,
        "rows": rows,
        "total_rows": len(rows),
        "pending_rows": pending,
    }


@frappe.whitelist()
def assign_bin_to_row(se_name=None, row_name=None, bin_location=None):
    """Assign a scanned empty bin to ONE pre-split storage row.
    Validates the bin is vacant and the row belongs to this receipt.
    Saves immediately so progress is never lost.
    """
    _assert_stock_role()

    se_name      = se_name      or frappe.form_dict.get('se_name')
    row_name     = row_name     or frappe.form_dict.get('row_name')
    bin_location = bin_location or frappe.form_dict.get('bin_location')

    if not se_name or not row_name or not bin_location:
        frappe.throw(_("se_name, row_name and bin_location are required."))

    # bin must exist + be vacant
    if not frappe.db.exists("Bin Name", bin_location):
        frappe.throw(_("Bin {0} does not exist.").format(bin_location))

    bin_status = frappe.db.get_value("Bin Name", bin_location, "status")

    # STRICT empty check: sum actual stored qty, not just existence
    stored_total = frappe.db.sql(
        """SELECT COALESCE(SUM(stored_qty), 0) FROM `tabitem bin location`
           WHERE bin_location = %s AND stored_qty > 0""",
        (bin_location,),
    )[0][0]

    if flt(stored_total) > 0:
        frappe.throw(_("Bin {0} is not empty — it holds {1} units.").format(bin_location, flt(stored_total)))
    if bin_status == "Occupied":
        frappe.throw(_("Bin {0} is marked Occupied.").format(bin_location))

    # bin must not already be used by another row on THIS receipt
    se = frappe.get_doc("Stock Entry", se_name)
    if se.docstatus != 0:
        frappe.throw(_("This receipt is already submitted."))

    for r in se.get("storage_details"):
        if r.name != row_name and (r.bin_location or "") == bin_location:
            frappe.throw(
                _("Bin {0} is already assigned to another row on this receipt.").format(bin_location)
            )

    # find + set the target row
    target = next((r for r in se.get("storage_details") if r.name == row_name), None)
    if not target:
        frappe.throw(_("Storage row not found on this receipt."))

    target.bin_location = bin_location
    se.flags.ignore_permissions = True
    se.save()

    # mark bin occupied so it can't be scanned for another row mid-session
    frappe.db.set_value("Bin Name", bin_location, "status", "Occupied")
    frappe.db.commit()

    # how many rows still pending?
    pending = sum(1 for r in se.get("storage_details") if not r.bin_location)

    return {
        "success": True,
        "row": row_name,
        "bin": bin_location,
        "item_code": target.item_code,
        "stored_qty": target.stored_qty,
        "pending_rows": pending,
    }


@frappe.whitelist()
def clear_bin_from_row(se_name=None, row_name=None):
    """Undo: remove the bin from a storage row (if worker scanned wrong bin).
    Frees the bin back to Vacant.
    """
    _assert_stock_role()
    se_name  = se_name  or frappe.form_dict.get('se_name')
    row_name = row_name or frappe.form_dict.get('row_name')

    se = frappe.get_doc("Stock Entry", se_name)
    if se.docstatus != 0:
        frappe.throw(_("This receipt is already submitted."))

    target = next((r for r in se.get("storage_details") if r.name == row_name), None)
    if not target:
        frappe.throw(_("Row not found."))

    old_bin = target.bin_location
    target.bin_location = None
    se.flags.ignore_permissions = True
    se.save()

    # free the bin only if no other stock/row uses it
    if old_bin:
        still_used = any(
            (r.bin_location or "") == old_bin for r in se.get("storage_details")
        )
        has_stock = frappe.db.exists(
            "item bin location", {"bin_location": old_bin, "stored_qty": (">", 0)}
        )
        if not still_used and not has_stock:
            frappe.db.set_value("Bin Name", old_bin, "status", "Vacant")

    frappe.db.commit()
    return {"success": True, "freed_bin": old_bin}
# ════════════════════════════════════════════════════════════════════════════
# ADD THESE TO scan.py (append at the bottom, after the other functions)
# ════════════════════════════════════════════════════════════════════════════

# ─── BIN / PALLET LOOKUP ──────────────────────────────────────────────────────

@frappe.whitelist()
def lookup_scan(scan_value=None):
    """Scan a bin OR pallet barcode and get full info on what's stored:
    item, batch, qty, reserved, expiry, manufacturing date, pallet, bin, etc.
    Tries bin_location first, then pallet.
    """
    _assert_stock_role()
    scan_value = scan_value or frappe.form_dict.get('scan_value')
    if not scan_value:
        frappe.throw(_("scan_value is required."))

    scan_value = scan_value.strip()

    # Try as BIN first
    rows = frappe.db.sql(
        """
        SELECT
            c.parent AS item_code,
            c.bin_location,
            c.pallet,
            c.warehouse,
            c.stored_qty,
            COALESCE(c.reserved_qty, 0) AS reserved_qty,
            (c.stored_qty - COALESCE(c.reserved_qty, 0)) AS available_qty,
            c.batch_no,
            DATE_FORMAT(c.expiry, '%%d-%%m-%%Y') AS expiry,
            DATE_FORMAT(c.manufacturing_date, '%%d-%%m-%%Y') AS manufacturing_date,
            c.sub_customer,
            c.area_use
        FROM `tabitem bin location` c
        WHERE c.bin_location = %s AND c.stored_qty > 0
        """,
        (scan_value,),
        as_dict=True,
    )
    matched_as = "bin"

    # If nothing, try as PALLET
    if not rows:
        rows = frappe.db.sql(
            """
            SELECT
                c.parent AS item_code,
                c.bin_location,
                c.pallet,
                c.warehouse,
                c.stored_qty,
                COALESCE(c.reserved_qty, 0) AS reserved_qty,
                (c.stored_qty - COALESCE(c.reserved_qty, 0)) AS available_qty,
                c.batch_no,
                DATE_FORMAT(c.expiry, '%%d-%%m-%%Y') AS expiry,
                DATE_FORMAT(c.manufacturing_date, '%%d-%%m-%%Y') AS manufacturing_date,
                c.sub_customer,
                c.area_use
            FROM `tabitem bin location` c
            WHERE c.pallet = %s AND c.stored_qty > 0
            """,
            (scan_value,),
            as_dict=True,
        )
        matched_as = "pallet"

    # Resolve bin status / type even if empty
    bin_status = None
    if frappe.db.exists("Bin Name", scan_value):
        bin_status = frappe.db.get_value("Bin Name", scan_value, "status")
        matched_as = matched_as if rows else "bin"

    if not rows:
        return {
            "found": False,
            "scan_value": scan_value,
            "matched_as": "bin" if bin_status else "unknown",
            "bin_status": bin_status,
            "message": _("Nothing stored under {0}.").format(scan_value)
                       + ((" Bin status: " + bin_status) if bin_status else ""),
        }

    # add item names + customer
    for r in rows:
        r["item_name"] = frappe.db.get_value("Item", r.item_code, "item_name") or r.item_code
        r["customer"] = frappe.db.get_value("Item", r.item_code, "customer_") or ""

    return {
        "found": True,
        "scan_value": scan_value,
        "matched_as": matched_as,
        "bin_status": bin_status,
        "records": rows,
    }


# ─── STRICT EMPTY-BIN VALIDATION (used by receiving) ─────────────────────────
# This is already enforced inside assign_bin_to_row, but exposed separately so
# the app can verify a bin is empty BEFORE the user even sees the confirm screen.

@frappe.whitelist()
def is_bin_empty(bin_name=None):
    """Return whether a bin is truly empty and safe to assign.
    Checks BOTH the Bin Name status AND actual stored stock.
    """
    _assert_stock_role()
    bin_name = bin_name or frappe.form_dict.get('bin_name')
    if not bin_name:
        frappe.throw(_("bin_name is required."))

    if not frappe.db.exists("Bin Name", bin_name):
        return {"empty": False, "reason": "not_found",
                "message": _("Bin {0} does not exist.").format(bin_name)}

    status = frappe.db.get_value("Bin Name", bin_name, "status")

    stored = frappe.db.sql(
        """SELECT COALESCE(SUM(stored_qty), 0) AS qty
           FROM `tabitem bin location`
           WHERE bin_location = %s AND stored_qty > 0""",
        (bin_name,),
        as_dict=True,
    )[0]

    if flt(stored.qty) > 0:
        return {"empty": False, "reason": "has_stock",
                "message": _("Bin {0} already holds {1} units.").format(bin_name, flt(stored.qty))}

    if status == "Occupied":
        return {"empty": False, "reason": "marked_occupied",
                "message": _("Bin {0} is marked Occupied.").format(bin_name)}

    return {"empty": True, "status": status,
            "message": _("Bin {0} is empty and available.").format(bin_name)}
