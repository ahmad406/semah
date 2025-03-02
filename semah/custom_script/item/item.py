
import frappe

def validate(doc, method):
    set_item_naming(doc, method)

def on_update(self,method):
    if self.has_batch_no and self.create_new_batch:
        batch_series=self.name+"-"
        sql='''update `tabItem` set batch_number_series="{0}" where name="{1}" '''.format(batch_series,self.name)
        update= frappe.db.sql(sql,as_dict=1)
@frappe.whitelist()
def subnaming(customer,sub):
    code=""
    sql="""select item_code from `tabSub Customer` where parent="{0}" and sub_customer_full_name="{1}" """.format(customer,sub)
    subc= frappe.db.sql(sql,as_dict=1)
    customer=frappe.db.sql("""select customer_code from `tabCustomer` where name="{0}" """.format(customer),as_dict=1)
    if customer and subc:
        code=customer[0].customer_code+"-"+subc[0].item_code
    else:
        code=customer[0].customer_code
    return code




@frappe.whitelist()
def set_item_naming(doc, method):
    if doc.customer_:
        # Fetch customer code
        customer_code = frappe.db.get_value("Customer", doc.customer_, "customer_code")
        
        if customer_code:
            doc.item_naming = customer_code.upper()

        # Handle sub_customer logic
        if doc.sub_customer:
            naming = subnaming(doc.customer_, doc.sub_customer)
            if naming:
                doc.item_naming = naming.upper()




@frappe.whitelist()
def get_stock(self,item):
    stk= frappe.db.sql("""select * from `tabitem bin location` where parent="{0}"  and stored_qty !=0 """.format(item),as_dict=1)
    return stk
@frappe.whitelist()
def onload(self,item=None):
    stk= frappe.db.sql("""select DISTINCT(sub_customer),parent from `tabitem bin location` """,as_dict=1)
    sub_customer=''
    for item in stk:
        target_doc=frappe.get_doc('Item',item.parent)
        if(item.parent==self.name):
            sub_customer=sub_customer+','+item.sub_customer
            self.sub_customer=sub_customer
            self.save()

@frappe.whitelist()
def update_all(item=None):
    items= frappe.db.sql("""select name from `tabItem` """.format(item),as_dict=1)
    for k in items:
        target_doc = frappe.get_doc("Item", k.name)
        target_doc.bin_display=[]
        stk= frappe.db.sql("""select * from `tabitem bin location` where parent="{0}"  and stored_qty !=0 """.format(k.name),as_dict=1)
        for i in stk:
            rw = target_doc.append('bin_display', {})
            rw.warehouse = i.warehouse
            rw.batch_no = i.batch_no
            rw.bin_location = i.bin_location
            rw.expiry = i.expiry
            rw.stored_qty = i.stored_qty
            rw.stored_in =i.stored_in
            rw.sub_customer=i.sub_customer
            rw.area_use=i.area_use
            rw.length=i.length
            rw.height=i.height
            rw.width=i.width
            rw.manufacturing_date=i.manufacturing_date
        target_doc.save()


      
   
      