import frappe
from frappe import _
from frappe.utils import validate_email_address,format_time, global_date_format, now


from frappe.desk.query_report import build_xlsx_data
from frappe.email.email_body import get_formatted_html
from frappe.utils.xlsxutils import make_xlsx


@frappe.whitelist()
def validate(doc,method):
    validate_cc_emails(doc)
    subc_code=[]
    sql="""select name from `tabCustomer` where customer_code="{0}"  """.format(doc.customer_code)
    code= frappe.db.sql(sql,as_dict=1)
    if code and code[0].name !=doc.name :
        frappe.throw("Duplicate Customer code already exist in  {0} ".format(code[0].name))
    for j in doc.sub_customer:
        subc_code.append(j.item_code)

    subc_code = str(subc_code)[1:-1]
    if subc_code:
        sub="""select item_code,parent from `tabSub Customer` where item_code in ({0})  """.format(subc_code)
        sub_code= frappe.db.sql(sub,as_dict=1)
        for s in sub_code:
            if s.parent!=doc.name:
                frappe.throw("Duplicate Sub Customer  Item code {0} in {1} ".format(s.item_code,s.parent) )






def validate_cc_emails(doc):
    # If CC is provided, Email is mandatory
    if doc.email_cc and not doc.email:
        frappe.throw(
            _("Email is mandatory when CC Email Addresses are specified.")
        )

    if not doc.email_cc:
        return

    emails = [email.strip() for email in doc.email_cc.split(",") if email.strip()]

    invalid_emails = [
        email for email in emails
        if not validate_email_address(email, throw=False)
    ]

    if invalid_emails:
        frappe.throw(
            _("Invalid email address(es): {0}").format(", ".join(invalid_emails))
        )

    # Optional: normalize formatting
    doc.email_cc = ", ".join(emails)


# ──────────────────────────────────────────────
# CONFIG — adjust these to match your setup
# ──────────────────────────────────────────────
REPORT_NAME          = "Stock Report Semah"               # exact Report docname
REPORT_FORMAT        = "XLSX"              # HTML | XLSX | CSV | PDF
CUSTOMER_FILTER_KEY  = "customer"          # filter fieldname in the report
EMAIL_FIELD          = "email"   # custom field on Customer (TO)
CC_FIELD             = "email_cc"      # custom field on Customer (CC, comma-separated)
NO_OF_ROWS           = 5000
RUN_AS_USER          = "Administrator"
# ──────────────────────────────────────────────


def send_repo_to_all_customers():
    """
    Scheduled entry point.
    Enqueues one job per customer that has a report email set.
    """
    customers = frappe.get_all(
    "Customer",
    filters=[
        ["disabled", "=", 0],
        [EMAIL_FIELD, "!=", ""],
        [EMAIL_FIELD, "is", "set"],
    ],
    fields=["name", EMAIL_FIELD, CC_FIELD],
)


    for customer in customers:
        email_to = (customer.get(EMAIL_FIELD) or "").strip()
        if not email_to:
            continue  # skip customers with no report email

        frappe.enqueue(
            "semah.custom_script.customer.customer.process_customer_report",
            customer_name=customer.name,
            email_to=email_to,
            cc_raw=customer.get(CC_FIELD) or "",
            queue="long",
            timeout=600,
            now=False,
        )


def process_customer_report(customer_name, email_to, cc_raw=""):
    """
    Generate and send REPO report for a single customer.
    Called by the enqueue above (runs in worker).
    """
    try:
        report  = frappe.get_doc("Report", REPORT_NAME)
        filters = {CUSTOMER_FILTER_KEY: customer_name}

        columns, data = report.get_data(
            limit=NO_OF_ROWS,
            user=RUN_AS_USER,
            filters=filters,
            as_dict=True,
            ignore_prepared_report=True,
            are_default_filters=False,
        )

        if not data:
            return  # no data for this customer — skip silently

        # inject Sr. No.
        columns.insert(0, frappe._dict(fieldname="sr", label="Sr", fieldtype="Int", width="30px"))
        for i, row in enumerate(data):
            row["sr"] = i + 1

        # build file / message body
        file_content = _build_content(columns, data, filters)
        if file_content is None:
            return

        # CC: split comma-separated string into list
        cc_list = [e.strip() for e in cc_raw.split(",") if e.strip()]

        if REPORT_FORMAT == "HTML":
            # HTML: inline message, no attachment
            frappe.sendmail(
                recipients=[email_to],
                cc=cc_list,
                subject=f"Stock Report – {customer_name}",
                message=file_content,           # file_content IS the html here
                reference_doctype="Customer",
                reference_name=customer_name,
            )
        else:
            # XLSX / CSV / PDF: plain intro message + attachment
            frappe.sendmail(
                recipients=[email_to],
                cc=cc_list,
                subject=f"Stock Report – {customer_name}",
                message=_plain_body(customer_name),
                attachments=[{
                    "fname": _file_name(customer_name),
                    "fcontent": file_content,
                }],
                reference_doctype="Customer",
                reference_name=customer_name,
            )

    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"REPO Report failed for customer: {customer_name}",
        )




def _build_content(columns, data, filters):
    """Return report bytes/string in the configured format."""

    if REPORT_FORMAT == "HTML":
        return _html_table(columns, data)

    report_data = frappe._dict(
        report_name=REPORT_NAME,
        filters=filters,
        columns=columns,
        result=data,
    )

    if REPORT_FORMAT == "XLSX":
        xlsx_data, col_widths, styles = build_xlsx_data(
            report_data, [], 1, ignore_visible_idx=True
        )
        return make_xlsx(xlsx_data, REPORT_NAME, column_widths=col_widths, styles=styles).getvalue()
    elif REPORT_FORMAT == "CSV":
        from frappe.utils.csvutils import to_csv
        xlsx_data, _, _ = build_xlsx_data(
            report_data, [], 1, ignore_visible_idx=True, build_styles=False
        )
        return to_csv(xlsx_data)

    elif REPORT_FORMAT == "PDF":
        from frappe.utils.pdf import get_pdf
        html = get_formatted_html(
            subject=REPORT_NAME,
            message=_html_table(columns, data),
        )
        options = {"orientation": "landscape"} if len(columns) > 8 else {}
        return get_pdf(html, options)

    frappe.throw(_(f"Unsupported REPORT_FORMAT: {REPORT_FORMAT}"))


def _html_table(columns, data):
    """Render report HTML using Frappe's built-in email template."""
    date_time = global_date_format(now()) + " " + format_time(now())
    return frappe.render_template(
        "frappe/templates/emails/auto_email_report.html",
        {
            "title": REPORT_NAME,
            "description": "",
            "date_time": date_time,
            "columns": columns,
            "data": data,
            "report_url": "",
            "report_name": REPORT_NAME,
            "edit_report_settings": "",
        },
    )


def _plain_body(customer_name):
    return (
        f"<p>Dear {frappe.utils.escape_html(customer_name)},</p>"
        f"<p>Please find attached your stock report. Contact us for any queries.</p>"
    )


def _file_name(customer_name):
    safe = customer_name.replace(" ", "-").replace("/", "-")
    return f"REPO-{safe}.{REPORT_FORMAT.lower()}"