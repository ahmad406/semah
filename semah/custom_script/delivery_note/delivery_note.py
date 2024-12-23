import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc

@frappe.whitelist()
def on_submit(doc,method):
        order = frappe.get_doc('Preparation Order Note', doc.prepration)
        order.order_status="Completed"
        order.save()
        request = frappe.get_doc('Delivery Request', doc.delivery_request)
        request.doc_status="Completed"
        request.save()
        # for itm in doc.get('storage_details'):
        #     target_doc = frappe.get_doc("Item", itm.item_code)
        #     target_doc.bin_display=[]
        #     # rv= frappe.db.sql("""delete from `tabitem bin display` where parent="{0}" """.format(itm.item_code),as_dict=1)
        #     stk= frappe.db.sql("""select * from `tabitem bin location` where parent="{0}"  and stored_qty !=0 order by expiry asc""".format(itm.item_code),as_dict=1)
        #     for i in stk:
        #         rw = target_doc.append('bin_display', {})
        #         rw.warehouse = i.warehouse
        #         rw.batch_no = i.batch_no
        #         rw.bin_location = i.bin_location
        #         rw.expiry = i.expiry
        #         rw.stored_qty = i.stored_qty
        #         rw.stored_in =i.stored_in
        #         rw.sub_customer=i.sub_customer
        #         rw.area_use=i.area_use
        #         rw.length=i.length
        #         rw.height=i.height
        #         rw.width=i.width
        #         rw.manufacturing_date=i.manufacturing_date
        #     target_doc.save()

@frappe.whitelist()
def get_item(customer):
    data=frappe.db.sql("""select name,customer,name as name_1,customer as customer_1  from `tabPreparation Order Note` where customer="{0}"  and docstatus=1  order by creation  desc """.format(customer),as_dict=True)
    return data



@frappe.whitelist()
def before_submit(doc,method):
    for s in doc.get('storage_details'):
        to_update=False
        items=frappe.get_doc("Item",s.item_code)
        for i in items.bin:
            if  s.batch_no:
                if s.expiry_date:
                    if i.batch_no== s.batch_no and i.bin_location==s.bin_location_name and s.warehouse==i.warehouse and convert_to_string(s.expiry_date)==convert_to_string(i.expiry):
                        i.stored_qty=i.stored_qty-s.delivery_qty
                        if not s.height:
                            i.area_use=s.length*s.width* i.stored_qty
                        if s.height:
                            i.area_use=s.length*s.width*s.height* i.stored_qty
                        to_update=True
                        break
                else:
                    if i.batch_no== s.batch_no and i.bin_location==s.bin_location_name and s.warehouse==i.warehouse :
                        i.stored_qty=i.stored_qty-s.delivery_qty
                        if not s.height:
                            i.area_use=s.length*s.width* i.stored_qty
                        if s.height:
                            i.area_use=s.length*s.width*s.height* i.stored_qty
                        to_update=True
                        break
            else:
                if  i.bin_location==s.bin_location_name and s.warehouse==i.warehouse :
                    i.stored_qty=i.stored_qty-s.delivery_qty
                    if not s.height:
                        i.area_use=s.length*s.width* i.stored_qty
                    if s.height:
                        i.area_use=s.length*s.width*s.height* i.stored_qty
                    to_update=True
                    break
        if to_update:
            items.save()
        else:
            frappe.throw("Nothing to update in item {0}".format(s.item_code))



@frappe.whitelist()
def before_cancel(doc,method):
    for s in doc.get('storage_details'):
        items=frappe.get_doc("Item",s.item_code)
        to_update=False
        for i in items.bin:
            if  s.batch_no:
                if s.expiry_date:
                    if i.batch_no== s.batch_no and i.bin_location==s.bin_location_name and s.warehouse==i.warehouse and convert_to_string(s.expiry_date)==convert_to_string(i.expiry):
                        i.stored_qty=i.stored_qty+s.delivery_qty
                        if not s.height:
                            i.area_use+=s.length*s.width* i.stored_qty
                        if s.height:
                            i.area_use+=s.length*s.width*s.height* i.stored_qty
                        to_update=True
                        break
                else:
                    if i.batch_no== s.batch_no and i.bin_location==s.bin_location_name and s.warehouse==i.warehouse :
                        i.stored_qty=i.stored_qty+s.delivery_qty
                        if not s.height:
                            i.area_use+=s.length*s.width* i.stored_qty
                        if s.height:
                            i.area_use+=s.length*s.width*s.height* i.stored_qty
                        to_update=True
                        break
            else:
                if  i.bin_location==s.bin_location_name and s.warehouse==i.warehouse :
                    i.stored_qty=i.stored_qty+s.delivery_qty
                    if not s.height:
                        i.area_use=s.length*s.width* i.stored_qty
                    if s.height:
                        i.area_use=s.length*s.width*s.height* i.stored_qty
                    to_update=True
                    break
        if to_update:
            items.save()
        else:
            frappe.throw("Nothing to update in item {0}".format(s.item_code))
@frappe.whitelist()
def on_cancel(doc,method):
    pass
    # for itm in doc.get('storage_details'):
    #     target_doc = frappe.get_doc("Item", itm.item_code)
    #     target_doc.bin_display=[]
    #     # rv= frappe.db.sql("""delete from `tabitem bin display` where parent="{0}" """.format(itm.item_code),as_dict=1)
    #     stk= frappe.db.sql("""select * from `tabitem bin location` where parent="{0}"  and stored_qty !=0 order by expiry asc""".format(itm.item_code),as_dict=1)
    #     for i in stk:
    #         rw = target_doc.append('bin_display', {})
    #         rw.warehouse = i.warehouse
    #         rw.batch_no = i.batch_no
    #         rw.bin_location = i.bin_location
    #         rw.expiry = i.expiry
    #         rw.stored_qty = i.stored_qty
    #         rw.stored_in =i.stored_in
    #         rw.sub_customer=i.sub_customer
    #         rw.area_use=i.area_use
    #         rw.length=i.length
    #         rw.height=i.height
    #         rw.width=i.width
    #         rw.manufacturing_date=i.manufacturing_date
    #     target_doc.save()


# @frappe.whitelist()
# def make_delivery_note(source_name, target_doc=None):
# 	def set_missing_values(source, target):
# 		delivery_note = frappe.get_doc(target)
# 	doclist = get_mapped_doc("Preparation Order Note", source_name, {
# 		"Preparation Order Note": {
# 			"doctype": "Delivery Note",
# 			"field_map": {
# 				"customer": "customer",
# 				# "warehouse":"set_warehouse",
# 				"sub_customer":"sub_customer",
# 				"required_date":"required_date",
# 				"address_and_contact_details":"address_display"
# 			}
# 		},
        # "Preparation Item Grid":{
        # 	"doctype": "Delivery Note Item",
        # 	"field_map": {
        # 		"item_code": "item",
        # 		"item_description": "description",
        # 		"required_date": "required_date",
        # 		"qty_required": "quantity_required"
        # 	}
        # },
        # "Preparation Storage Details":{
        # 	"doctype": "Note Storage details",
        # 	"field_map": {
        # 		"item": "item_code",
        # 		"warehouse": "warehouse",
        # 		"expiry_date": "expiry_date",
        # 		"bin_location_name": "bin_location_name",
        # 		"batch_no": "batch_no",
        # 		"expiry_date":"expiry_date",
        # 		"delivery_qty": "delivery_qty"
        # 	}
        # }
    # }, target_doc, set_missing_values)
    # return doclist


frappe.whitelist()
def delete_stock_ledger(name):
    sql="""select name from `tabStock Ledger Entry` where voucher_no="{0}" """.format(name)
    for d  in frappe.db.sql(sql,as_dict=True):
        stock=frappe.get_doc("Stock Ledger Entry",d.name)
        stock.cancel()
        stock.delete()

@frappe.whitelist()
def background_recreate_d():
    frappe.enqueue(recreating_all, timeout=4800, queue='long',
    job_name='recreating_all', now=False)
@frappe.whitelist()
def recreating_all():
		sql="""select name from `tabDelivery Note` where docstatus=1  order by posting_date"""
		for d in frappe.db.sql(sql,as_dict=1):
			delev=frappe.get_doc("Delivery Note",d.name)
			recreating(delev)


def recreating(delev):
    self=delev
    for s in self.get('storage_details'):
        items=frappe.get_doc("Item",s.item_code)
        to_update=False
        for i in items.bin:
            if  s.batch_no:
                if s.expiry_date:
                    if i.batch_no== s.batch_no and i.bin_location==s.bin_location_name and s.warehouse==i.warehouse and convert_to_string(s.expiry_date)==convert_to_string(i.expiry):
                        i.stored_qty=i.stored_qty-s.delivery_qty
                        if not s.height:
                            i.area_use=s.length*s.width* i.stored_qty
                        if s.height:
                            i.area_use=s.length*s.width*s.height* i.stored_qty
                        to_update=True
                        break
                else:
                    if i.batch_no== s.batch_no and i.bin_location==s.bin_location_name and s.warehouse==i.warehouse :
                        i.stored_qty=i.stored_qty-s.delivery_qty
                        if not s.height:
                            i.area_use=s.length*s.width* i.stored_qty
                        if s.height:
                            i.area_use=s.length*s.width*s.height* i.stored_qty
                    to_update=True
                    break
            else:
                if  i.bin_location==s.bin_location_name and s.warehouse==i.warehouse :
                    i.stored_qty=i.stored_qty-s.delivery_qty
                    if not s.height:
                        i.area_use=s.length*s.width* i.stored_qty
                    if s.height:
                        i.area_use=s.length*s.width*s.height* i.stored_qty
                to_update=True
                break
        if to_update:
            frappe.errprint(self.name)
            items.save()
        else:
            frappe.throw("Nothing to update in item {0} {1}".format(s.item_code,s.parent))


import datetime

def convert_to_string(date):
    if isinstance(date, datetime.date):
        return date.strftime('%Y-%m-%d')
    else:
        return date