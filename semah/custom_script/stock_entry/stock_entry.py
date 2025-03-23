from __future__ import unicode_literals
import frappe

from frappe import _
from frappe.utils import  flt, getdate,get_link_to_form
from erpnext.stock.doctype.batch.batch import  set_batch_nos
from frappe.desk.reportview import get_filters_cond, get_match_cond
from erpnext.stock.doctype.serial_no.serial_no import update_serial_nos_after_submit
import collections

from erpnext.stock.doctype.stock_entry.stock_entry import  StockEntry
from erpnext.stock.doctype.stock_entry.stock_entry import *

class CustomStockEntry(StockEntry):
    def validate(self):
        self.pro_doc = frappe._dict()
        if self.work_order:
            self.pro_doc = frappe.get_doc('Work Order', self.work_order)

        self.validate_posting_time()
        self.validate_purpose()
        self.validate_item()
        self.validate_customer_provided_item()
        self.validate_qty()
        self.set_transfer_qty()
        self.validate_uom_is_integer("uom", "qty")
        self.validate_uom_is_integer("stock_uom", "transfer_qty")
        self.validate_warehouse()
        self.validate_work_order()
        self.validate_bom()
        self.mark_finished_and_scrap_items()
        self.validate_finished_goods()
        self.validate_with_material_request()
        self.validate_batch()
        self.validate_inspection()
        self.validate_fg_completed_qty()
        self.validate_difference_account()
        self.set_job_card_data()
        self.set_purpose_for_stock_entry()
        self.validate_duplicate_serial_no()

        if not self.from_bom:
            self.fg_completed_qty = 0.0
        if self._action == 'submit':
            # self.make_batches('t_warehouse')
            self.custommake_batches('t_warehouse')      
        else:
            set_batch_nos(self, 's_warehouse')

        self.customvalidate_serialized_batch()
        self.setdetails()
        self.set_actual_qty()
        self.calculate_rate_and_amount()
        self.validate_putaway_capacity()
        self.calculate_total_qty()
    @frappe.whitelist()
    def get_warehouse_of_customer(self):
        sql = """select name, parent_Warehouse from `tabWarehouse` where customer="{0}" and is_stock=1""".format(self.customer_nm)
        data = frappe.db.sql(sql, as_dict=True)
        
        if len(data) > 1:
            sql_p = """select for_value from `tabUser Permission` where allow="Warehouse" and user="{0}" and is_stock_warehouse=1""".format(frappe.session.user)
            pdata = frappe.db.sql(sql_p, as_dict=True)
            
            if not pdata:
                return None
            
            for d in data:
                if d.parent_Warehouse == pdata[0].for_value:
                    return {"customer_warehouse":  d.name}
        
                    
        elif data:
            return  {"customer_warehouse":  data[0].name}
        
        return None


    @frappe.whitelist()
    def calculate_total_qty(self):
        ttl_qty=0
        t_stored_qty=0
        for d in self.items:
            ttl_qty+=d.qty
        for s in self.storage_details:
            t_stored_qty+=s.stored_qty


    def custommake_batches(self, warehouse_field):
        '''Create batches if required. Called before submit'''
        for d in self.items:
            if d.get(warehouse_field) and not d.batch_no:
                has_batch_no, create_new_batch = frappe.db.get_value('Item', d.item_code, ['has_batch_no', 'create_new_batch'])
                if has_batch_no and create_new_batch:
                    batch_no = frappe.get_doc(dict(
                        doctype='Batch',
                        item=d.item_code,
                        manufacturing_date=d.manufacturing_date,
                        expiry_date=d.expiry,
                        customer_batch_id="-",
                        supplier=getattr(self, 'supplier', None),
                        reference_doctype=self.doctype,
                        reference_name=self.name)).insert().name
                    d.batch_no=batch_no
                for s in self.storage_details:
                    if s.item_code==d.item_code and  s.stored_qty ==d.qty and s.idx ==d.idx:
                        s.batch_no=d.batch_no
                        s.expiry=d.expiry
                        s.manufacture=d.manufacturing_date
        
        self.checkbatch()
    def setdetails(self):
        for b in self.items:
            if b.batch_no:
                expiry_date, manufacturing_date = frappe.db.get_value('Batch',b.batch_no, ['expiry_date', 'manufacturing_date'])
            if b.expiry is None:
                b.expiry=expiry_date  if b.batch_no else ""
                b.manufacturing_date=manufacturing_date  if b.batch_no else ""

    
    @frappe.whitelist()
    def recreate(self):
        if self.stock_entry_type == 'Material Receipt':
            for itm in self.get('storage_details'):
                target_doc = frappe.get_doc("Item", itm.item_code)
                exist=False
                for t in target_doc.bin:
                    exist=False
                    if itm.batch_no:
                        if itm.expiry:
                            if itm.batch_no==t.batch_no and t.bin_location==itm.bin_location and t.warehouse==itm.t_ware_house and convert_to_string(itm.expiry)==convert_to_string(t.expiry):
                                t.stored_qty=t.stored_qty+itm.stored_qty
                                t.area_use=t.area_use+itm.area_used
                                exist=True
                                break
                        else:
                            if itm.batch_no==t.batch_no and t.bin_location==itm.bin_location and t.warehouse==itm.t_ware_house :
                                t.stored_qty=t.stored_qty+itm.stored_qty
                                t.area_use=t.area_use+itm.area_used
                                exist=True
                                break
                    else:
                        if  t.bin_location==itm.bin_location and t.warehouse==itm.t_ware_house :
                            t.stored_qty=t.stored_qty+itm.stored_qty
                            t.area_use=t.area_use+itm.area_used
                            exist=True
                            break

                if exist==False:
                    fill_bin=target_doc.append("bin",{})
                    fill_bin.warehouse=itm.t_ware_house
                    fill_bin.bin_location=itm.bin_location
                    fill_bin.batch_no=itm.batch_no
                    fill_bin.expiry=itm.expiry
                    fill_bin.stored_qty=itm.stored_qty
                    fill_bin.stored_in=itm.display_stored_in
                    fill_bin.length=itm.length
                    fill_bin.width=itm.width
                    fill_bin.area_use=itm.area_used
                    fill_bin.manufacturing_date=itm.manufacture
                    fill_bin.sub_customer=itm.sub_customer
                    if itm.height:
                        fill_bin.height=itm.height
                target_doc.save()
                  
        elif self.stock_entry_type == 'Transfer to Quarantine'  :
            for ex in self.get('storage_details'):
                target_doc = frappe.get_doc("Item", ex.item_code)
                to_update=False
                for d in target_doc.bin:

                    if d.batch_no==ex.batch_no:

                        d.t_bin=d.bin_location
                        d.t_warehouse=d.warehouse
                        d.bin_location=ex.bin_location
                        d.warehouse=ex.t_ware_house
                        to_update=True
                        break
                if to_update:

                    target_doc.save()
                else:
                   frappe.throw("Item Not Found {}".format(ex.item_code))


                


                # transfer=frappe.db.sql(''' update `tabitem bin location` set t_bin=bin_location,t_warehouse=warehouse,bin_location="{1}",warehouse="{0}" where batch_no="{2}" and parent ="{3}" '''.format(ex.t_ware_house,ex.bin_location,ex.batch_no,ex.item_code),as_dict=True)
        elif self.stock_entry_type == 'Quarantine Item Issue to Customer':
            for ex in self.get('storage_details'):
                target_doc = frappe.get_doc("Item", ex.item_code)
                to_update=False
                for d in target_doc.bin:
                    if d.batch_no==ex.batch_no and d.bin_location==ex.bin_location and d.warehouse==ex.t_ware_house:
                        d.stored_qty=d.stored_qty-ex.stored_qty
                        to_update=True
                        break
                if to_update:
                    target_doc.save()
                else:
                    frappe.throw("Item Not Found {}".format(ex.item_code))
    def on_submit(self):
        self.update_stock_ledger()
        # self.custumonsubmit()
        update_serial_nos_after_submit(self, "items")
        self.update_work_order()
        self.validate_purchase_order()
        if self.purchase_order and self.purpose == "Send to Subcontractor":
            self.update_purchase_order_supplied_items()

        self.make_gl_entries()

        self.repost_future_sle_and_gle()
        self.update_cost_in_project()
        self.validate_reserved_serial_no_consumption()
        self.update_transferred_qty()
        self.update_quality_inspection()

        if self.work_order and self.purpose == "Manufacture":
            self.update_so_in_serial_number()

        if self.purpose == 'Material Transfer' and self.add_to_transit:
            self.set_material_request_transfer_status('In Transit')
        if self.purpose == 'Material Transfer' and self.outgoing_stock_entry:
            self.set_material_request_transfer_status('Completed')

    def on_cancel(self):
        if self.purchase_order and self.purpose == "Send to Subcontractor":
            self.update_purchase_order_supplied_items()

        if self.work_order and self.purpose == "Material Consumption for Manufacture":
            self.validate_work_order_status()

        self.update_work_order()
        self.update_stock_ledger()

        self.ignore_linked_doctypes = ('GL Entry', 'Stock Ledger Entry', 'Repost Item Valuation')

        self.make_gl_entries_on_cancel()
        self.repost_future_sle_and_gle()
        self.update_cost_in_project()
        self.update_transferred_qty()
        self.update_quality_inspection()
        self.custom_delete_auto_created_batches()
        self.delete_linked_stock_entry()

        if self.purpose == 'Material Transfer' and self.add_to_transit:
            self.set_material_request_transfer_status('Not Started')
        if self.purpose == 'Material Transfer' and self.outgoing_stock_entry:
            self.set_material_request_transfer_status('In Transit')


    def custom_delete_auto_created_batches(self):
        for d in self.items:
            for i in self.storage_details:
                if not d.batch_no: continue

                serial_nos = [sr.name for sr in frappe.get_all("Serial No",
                    {'batch_no': d.batch_no, 'status': 'Inactive'})]

                if serial_nos:
                    frappe.db.set_value("Serial No", { 'name': ['in', serial_nos] }, "batch_no", None)

                d.batch_no = None
                d.db_set("batch_no", None)
                i.batch_no = None
                i.db_set("batch_no", None)
            

        for data in frappe.get_all("Batch",
            {'reference_name': self.name, 'reference_doctype': self.doctype}):
            frappe.db.set_value('Batch',data.name, 'reference_name', None)
            frappe.delete_doc("Batch", data.name,force=1)

    @frappe.whitelist()
    def before_cancel(self):
        def revert_bin_location(target_doc, bin_details):
            """
            Reverts bin location and warehouse back to original values stored in t_bin and t_warehouse.
            """
            for bin_entry in target_doc.bin:
                if (
                    bin_entry.batch_no == bin_details.batch
                    and bin_entry.bin_location == bin_details.bin_location
                    and bin_entry.warehouse == bin_details.t_ware_house
                ):  
                    # Check if previous values exist before restoring
                    if not bin_entry.t_bin or not bin_entry.t_warehouse:
                        frappe.throw(f"Cannot revert: Original bin/warehouse not stored for {bin_details.item_code}.")

                    frappe.errprint([bin_entry.bin_location,bin_entry.warehouse,bin_entry.t_bin,bin_entry.t_warehouse])
                    bin_entry.bin_location = bin_entry.t_bin
                    bin_entry.warehouse = bin_entry.t_warehouse
                
                    # Clear temporary fields after restoring
                    bin_entry.t_bin = None
                    bin_entry.t_warehouse = None
                    frappe.errprint([bin_entry.bin_location,bin_entry.warehouse,bin_entry.t_bin,bin_entry.t_warehouse])
                    
                    return True
        
            # If no match is found, throw an error
            frappe.throw(f"Item not found for reverting: {bin_details.item_code} with batch {bin_details.batch}")


        def handle_bin(target_doc, bin_details, reduce=False):
            """
            Update existing bin or create a new one if it doesn't exist.
            The 'reduce' parameter determines whether to subtract stored_qty.
            """
            for bin in target_doc.bin:
                if bin.batch_no == bin_details.batch and bin.bin_location == bin_details.bin_location and bin.warehouse == bin_details.t_ware_house:
                    # Update stored_qty and area use
                    if reduce:
                        bin.stored_qty -= bin_details.stored_qty
                    else:
                        bin.stored_qty += bin_details.stored_qty

                    # Recalculate area use based on new stored_qty
                    bin.area_use = bin_details.length * bin_details.width * (bin_details.height or 1) * bin.stored_qty

                    # Prevent negative stored_qty
                    if bin.stored_qty < 0:
                        frappe.throw(f"Invalid operation: stored_qty cannot be negative for bin {bin.bin_location} in warehouse {bin.warehouse}.")
                    
                    return True

            # If reducing and no match found, raise error
            if reduce:
                frappe.throw(f"Item Not Found: {bin_details.item_code} with batch {bin_details.batch} at location {bin_details.bin_location}.")

            # Append a new bin if no match is found and reducing is not intended
            new_bin = target_doc.append("bin", {})
            new_bin.update({
                "warehouse": bin_details.t_ware_house,
                "bin_location": bin_details.bin_location,
                "batch_no": bin_details.batch,
                "expiry": bin_details.expiry,
                "stored_qty": bin_details.stored_qty,
                "area_use": bin_details.length * bin_details.width * (bin_details.height or 1),
            })
            return True

        # Main logic for different stock entry types
        if self.stock_entry_type == 'Material Receipt':
            for itm in self.get('storage_details'):
                target_doc = frappe.get_doc("Item", itm.item_code)
                if not handle_bin(target_doc, itm, reduce=True):  # Reduce stored_qty
                    frappe.throw(f"Failed to handle bin for item {itm.item_code}")
                target_doc.save()

        elif self.stock_entry_type == 'Transfer to Quarantine':
            for itm in self.get('storage_details'):
                target_doc = frappe.get_doc("Item", itm.item_code)
                if not revert_bin_location(target_doc, itm):
                    frappe.throw(f"Failed to revert bin for item {itm.item_code}")
                # frappe.throw("no")
                
                target_doc.save()


        elif self.stock_entry_type == 'Quarantine Item Issue to Customer':
            for itm in self.get('storage_details'):
                target_doc = frappe.get_doc("Item", itm.item_code)
                if not handle_bin(target_doc, itm, reduce=False):  # Add stored_qty
                    frappe.throw(f"Failed to handle bin for item {itm.item_code}")
                target_doc.save()

                        

    

   
    @frappe.whitelist()
    def before_submit(self):
        def update_or_create_bin(target_doc, bin_details, action):
            """
            Updates or creates a bin in the target_doc based on action.
            Action: 'add', 'transfer', or 'reduce'
            """
            for bin_entry in target_doc.bin:
                # Material Receipt: Add Quantity
                if action == 'add':
                    if (
                        bin_details.batch == bin_entry.batch_no
                        and bin_entry.bin_location == bin_details.bin_location
                        and bin_entry.warehouse == bin_details.t_ware_house
                        and (
                            not bin_details.expiry
                            or convert_to_string(bin_details.expiry) == convert_to_string(bin_entry.expiry)
                        )
                    ):
                        bin_entry.stored_qty += bin_details.stored_qty
                        bin_entry.area_use += bin_details.area_used
                        return True

                # Transfer to Quarantine: Update Location
                elif action == 'transfer':
                    if bin_entry.batch_no == bin_details.batch:
                        bin_entry.t_bin = bin_entry.bin_location
                        bin_entry.t_warehouse = bin_entry.warehouse
                        bin_entry.bin_location = bin_details.bin_location
                        bin_entry.warehouse = bin_details.t_ware_house
                        bin_entry.reciept = self.name
                        return True

                # Quarantine Item Issue to Customer: Reduce Quantity
                elif action == 'reduce':
                    if (
                        bin_entry.batch_no == bin_details.batch
                        and bin_entry.bin_location == bin_details.bin_location
                        and bin_entry.warehouse == bin_details.t_ware_house
                    ):
                        bin_entry.stored_qty -= bin_details.stored_qty
                        if bin_entry.stored_qty < 0:
                            frappe.throw(
                                f"Invalid operation: Negative stored_qty for bin {bin_entry.bin_location} in warehouse {bin_entry.warehouse}."
                            )
                        return True

            # If no match found
            if action == 'add':
                new_bin = target_doc.append("bin", {})
                new_bin.update(
                    {
                        "warehouse": bin_details.t_ware_house,
                        "bin_location": bin_details.bin_location,
                        "batch_no": bin_details.batch,
                        "expiry": bin_details.expiry,
                        "stored_qty": bin_details.stored_qty,
                        "stored_in": bin_details.display_stored_in,
                        "length": bin_details.length,
                        "width": bin_details.width,
                        "area_use": bin_details.area_used,
                        "manufacturing_date": bin_details.manufacture,
                        "sub_customer": bin_details.sub_customer,
                        "height": bin_details.height or 0,
                    }
                )
                return True
            return False

        for item in self.get('storage_details'):
            target_doc = frappe.get_doc("Item", item.item_code)

            if self.stock_entry_type == 'Material Receipt':
                # Add stored_qty
                if not update_or_create_bin(target_doc, item, action='add'):
                    frappe.throw(f"Failed to add bin details for item {item.item_code}")

            elif self.stock_entry_type == 'Transfer to Quarantine':
                # Transfer bin location
                if not update_or_create_bin(target_doc, item, action='transfer'):
                    frappe.throw(f"Item not found: {item.item_code} with batch {item.batch}")

            elif self.stock_entry_type == 'Quarantine Item Issue to Customer':
                # Reduce stored_qty
                if not update_or_create_bin(target_doc, item, action='reduce'):
                    frappe.throw(f"Item not found: {item.item_code} with batch {item.batch}")

            # Save changes to the target document
            target_doc.save()

    @frappe.whitelist()
    def updatestorage(self,bin):
        self.storage_details=[]
        for itm in self.items:
            if itm.batch_no:
                expiry_date, manufacturing_date = frappe.db.get_value('Batch',itm.batch_no, ['expiry_date', 'manufacturing_date'])
            row=self.append("storage_details",{})
            row.item_code = itm.item_code
            row.sub_customer = self.sub_customer
            if self.stock_entry_type=="Quarantine Item Issue to Customer":
                 row.t_ware_house = itm.s_warehouse
            else:
                row.t_ware_house = itm.t_warehouse
            row.batch_no=itm.batch_no
            row.batch=itm.batch_no
            row.expiry = expiry_date if itm.batch_no else ""
            row.manufacture = manufacturing_date  if itm.batch_no else ""
            row.stored_qty = itm.qty
            if len(bin) ==1:
                row.bin_location=bin[0]
        self.calculate_total_qty()
    @frappe.whitelist()
    def checkbatch(self):
        storage = self.storage_details
        item = self.items
        all_list = []

        raw =self.items
        for i in raw:
            if not i.batch_no:
                all_list.append(i.item_code)
        duplicate = ([item for item, count in collections.Counter(all_list).items() if count > 1])
        if len(duplicate) != 0:
            frappe.throw("Item " + duplicate + " is already in list with out batch no")
        

        for im in item:
            ttl = 0
            for j in storage:
                if (im.item_code == j.item_code and im.batch_no == j.batch_no):
                    ttl = ttl + j.stored_qty
            if (im.qty != ttl):
                frappe.throw(im.item_code + " Qty should not be greater or lesser than Stored qty! or check batch No again!")

   




    def customvalidate_serialized_batch(self):
        from erpnext.stock.doctype.serial_no.serial_no import get_serial_nos
        for d in self.get("items"):
            if hasattr(d, 'serial_no') and hasattr(d, 'batch_no') and d.serial_no and d.batch_no:
                serial_nos = get_serial_nos(d.serial_no)
                for serial_no_data in frappe.get_all("Serial No",
                    filters={"name": ("in", serial_nos)}, fields=["batch_no", "name"]):
                    if serial_no_data.batch_no != d.batch_no:
                        frappe.throw(_("Row #{0}: Serial No {1} does not belong to Batch {2}")
                            .format(d.idx, serial_no_data.name, d.batch_no))

            if flt(d.qty) > 0.0 and d.get("batch_no") and self.get("posting_date") and self.docstatus < 2:
                expiry_date = frappe.get_cached_value("Batch", d.get("batch_no"), "expiry_date")
                if expiry_date and getdate(expiry_date) < getdate(self.posting_date) and self.stock_entry_type != 'Transfer to Quarantine':
                    if  self.stock_entry_type != 'Quarantine Item Issue to Customer':
                        frappe.throw(_("Row #{0}: The batch {1} has already expired.")
                            .format(d.idx, get_link_to_form("Batch", d.get("batch_no"))))





@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_batch_no(doctype, txt, searchfield, start, page_len, filters):
	cond = ""
	if filters.get("posting_date"):
		cond = "and (batch.expiry_date is null or batch.expiry_date >= %(posting_date)s)"

	batch_nos = None
	args = {
		'item_code': filters.get("item_code"),
		'warehouse': filters.get("warehouse"),
		'posting_date': filters.get('posting_date'),
		'txt': "%{0}%".format(txt),
		"start": start,
		"page_len": page_len
	}

	having_clause = "having sum(sle.actual_qty) > 0"
	if filters.get("is_return"):
		having_clause = ""

	meta = frappe.get_meta("Batch", cached=True)
	searchfields = meta.get_search_fields()

	search_columns = ''
	search_cond = ''

	if searchfields:
		search_columns = ", " + ", ".join(searchfields)
		search_cond = " or " + " or ".join([field + " like %(txt)s" for field in searchfields])

	if args.get('warehouse'):
		searchfields = ['batch.' + field for field in searchfields]
		if searchfields:
			search_columns = ", " + ", ".join(searchfields)
			search_cond = " or " + " or ".join([field + " like %(txt)s" for field in searchfields])

		batch_nos = frappe.db.sql("""select sle.batch_no, round(sum(sle.actual_qty),2), sle.stock_uom,
				concat('MFG-',batch.manufacturing_date), concat('EXP-',batch.expiry_date)
				{search_columns}
			from `tabStock Ledger Entry` sle
				INNER JOIN `tabBatch` batch on sle.batch_no = batch.name
			where
				batch.disabled = 0
				and sle.item_code = %(item_code)s
				and sle.warehouse = %(warehouse)s
				and (sle.batch_no like %(txt)s
				or batch.expiry_date like %(txt)s
				or batch.manufacturing_date like %(txt)s
				{search_cond})
				and batch.docstatus < 2
				{cond}
				{match_conditions}
			group by batch_no {having_clause}
			order by batch.expiry_date, sle.batch_no desc
			limit %(start)s, %(page_len)s""".format(
				search_columns = search_columns,
				cond=cond,
				match_conditions=get_match_cond(doctype),
				having_clause = having_clause,
				search_cond = search_cond
			), args)

		return batch_nos
	else:
		return frappe.db.sql("""select name, concat('MFG-', manufacturing_date), concat('EXP-',expiry_date)
			{search_columns}
			from `tabBatch` batch
			where batch.disabled = 0
			and item = %(item_code)s
			and (name like %(txt)s
			or expiry_date like %(txt)s
			or manufacturing_date like %(txt)s
			{search_cond})
			and docstatus < 2
			{0}
			{match_conditions}

			order by expiry_date, name desc
			limit %(start)s, %(page_len)s""".format(cond, search_columns = search_columns,
			search_cond = search_cond, match_conditions=get_match_cond(doctype)), args)




# @frappe.whitelist()
# @frappe.validate_and_sanitize_search_inputs
# def get_batch_no(doctype, txt, searchfield, start, page_len, filters):
# 	cond = ""
# 	if filters.get("posting_date"):
# 		cond = "and (batch.expiry_date is null or batch.expiry_date >= %(posting_date)s)"

# 	batch_nos = None
# 	args = {
# 		"item_code": filters.get("item_code"),
# 		"warehouse": filters.get("warehouse"),
# 		"posting_date": filters.get("posting_date"),
# 		"txt": "%{0}%".format(txt),
# 		"start": start,
# 		"page_len": page_len,
# 	}

# 	having_clause = "having sum(sle.actual_qty) > 0"
# 	if filters.get("is_return"):
# 		having_clause = ""

# 	meta = frappe.get_meta("Batch", cached=True)
# 	searchfields = meta.get_search_fields()

# 	search_columns = ""
# 	search_cond = ""

# 	if searchfields:
# 		search_columns = ", " + ", ".join(searchfields)
# 		search_cond = " or " + " or ".join([field + " like %(txt)s" for field in searchfields])

# 	if args.get("warehouse"):
# 		searchfields = ["batch." + field for field in searchfields]
# 		if searchfields:
# 			search_columns = ", " + ", ".join(searchfields)
# 			search_cond = " or " + " or ".join([field + " like %(txt)s" for field in searchfields])
       
# 		batch_nos = frappe.db.sql(
# 			"""select sle.batch_no, round(sum(sle.actual_qty),2), sle.stock_uom,
# 				concat('MFG-',batch.manufacturing_date), concat('EXP-',batch.expiry_date)
# 				{search_columns}
# 			from `tabStock Ledger Entry` sle
# 				INNER JOIN `tabBatch` batch on sle.batch_no = batch.name
# 			where
#                 batch.expiry_date < CURDATE() and
# 				batch.disabled = 0
# 				and sle.is_cancelled = 0
# 				and sle.item_code = %(item_code)s
# 				and sle.warehouse = %(warehouse)s
# 				and (sle.batch_no like %(txt)s
# 				or batch.expiry_date like %(txt)s
# 				or batch.manufacturing_date like %(txt)s
# 				{search_cond})
# 				and batch.docstatus < 2
# 				{cond}
# 				{match_conditions}
# 			group by batch_no {having_clause}
# 			order by batch.expiry_date, sle.batch_no desc
# 			limit %(page_len)s offset %(start)s""".format(
# 				search_columns=search_columns,
# 				cond=cond,
# 				match_conditions=get_match_cond(doctype),
# 				having_clause=having_clause,
# 				search_cond=search_cond,
# 			),
# 			args,
# 		)

# 		return batch_nos
# 	else:
# 		return frappe.db.sql(
# 			"""select name, concat('MFG-', manufacturing_date), concat('EXP-',expiry_date)
# 			{search_columns}
# 			from `tabBatch` batch
# 			where batch.disabled = 0
#             and batch.expiry_date < CURDATE() 
# 			and item = %(item_code)s
# 			and (name like %(txt)s
# 			or expiry_date like %(txt)s
# 			or manufacturing_date like %(txt)s
# 			{search_cond})
# 			and docstatus < 2
# 			{0}
# 			{match_conditions}
# 			order by expiry_date, name desc
# 			limit %(page_len)s offset %(start)s""".format(
# 				cond,
# 				search_columns=search_columns,
# 				search_cond=search_cond,
# 				match_conditions=get_match_cond(doctype),
# 			),
# 			args,
# 		)



@frappe.whitelist()
def get_item_uom(item_code):
    uomlist=[]
    raw= frappe.db.sql(""" select uom from `tabUOM Conversion Detail` where parent="{0}" """.format(item_code),as_dict=1)
    for i in raw:
        uomlist.append(i.uom)
    return uomlist 


import datetime

def convert_to_string(date):
    if isinstance(date, datetime.date):
        return date.strftime('%Y-%m-%d')
    else:
        return date
    



@frappe.whitelist()
def background_recreate():
    frappe.enqueue(recreate_all, timeout=4800, queue='long',
    job_name='recreate_all', now=False)
@frappe.whitelist()
def recreate_all():
    sql="""select name from `tabStock Entry` where docstatus=1  and stock_entry_type != 'Material Receipt' order by posting_date """
    for d in frappe.db.sql(sql,as_dict=True):
        stk=frappe.get_doc("Stock Entry",d.name)
        stk.recreate()