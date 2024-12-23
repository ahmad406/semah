import frappe

@frappe.whitelist()
def validate(doc,method):
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