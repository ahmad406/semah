import frappe
from frappe import _
from frappe.utils import validate_email_address

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