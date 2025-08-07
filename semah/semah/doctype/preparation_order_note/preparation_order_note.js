// Copyright (c) 2022, Dconnex and contributors
// For license information, please see license.txt
var total = 0
frappe.ui.form.on('Preparation Order Note', {

    customer: function (frm) {

        var customer = [];
        if (frm.doc.customer) {

            frappe.model.with_doc("Customer", frm.doc.customer, function () {
                var d = frappe.model.get_doc("Customer", frm.doc.customer)

                if (cur_frm.doc.customer == d.name) {
                    console.log(d.name, "jj")
                    $.each(d.sub_customer, function (index, row) {
                        customer.push(row.sub_customer_full_name)
                    });

                    frm.set_df_property('sub_customer', 'options', customer);
                    frm.refresh_field('sub_customer');
                    frm.refresh_fields();
                    // $(".grid-add-row").css("display", "none");


                }
            })

        }

    },
    onload: function (frm) {
        calculateItemGridQuanitty();
        calculateDeliveryqty();
        cur_frm.set_value("naming_series", "MAT-PON-.YYYY.-")
    },
    before_submit: function (frm) {
        cur_frm.doc.order_status = "To make Delivery Note"
    },
    barcode: function (frm) {
        frappe.call({
            method: "add_item_in_storage",
            doc: cur_frm.doc,
            callback: function (r) {
                if (r.message) {
                    cur_frm.refresh()

                }
            }
        });

    },
    insert: function (frm) {
        frappe.call({
            method: "add_item_in_storage",
            doc: cur_frm.doc,
            args: { "insert": true },
            callback: function (r) {
                if (r.message) {
                    cur_frm.refresh()

                }
            }
        });

    },

    refresh: function (frm) {
        $('[data-fieldname="tem"]').css("display", "none");
        if (!frm.is_new()) {
            frm.trigger("batch_no")
            frm.trigger("customer")

        }
        // if (cur_frm.doc.docstatus != 1) {
        //   frm.page.wrapper.find('use[href="#icon-printer"]').closest("button").hide();

        //}
        cur_frm.get_field("item_grid").grid.cannot_add_rows = true
        cur_frm.fields_dict["item_grid"].grid.remove_rows_button.hide()
        cur_frm.fields_dict["item_grid"].grid.refresh();
        cur_frm.get_field("scanned_items").grid.cannot_add_rows = true
        // if (frappe.user.has_role("Labour")) {
        //     cur_frm.fields_dict['scanned_items'].grid.wrapper.find('.grid-remove-all-rows').hide();
        //     cur_frm.fields_dict['scanned_items'].grid.wrapper.find('.grid-remove-rows').hide();
        //     frm.fields_dict['scanned_items'].grid.wrapper.find('.grid-delete-row').hide();
        //     frm.fields_dict['scanned_items'].grid.wrapper.find('.edit-grid-row').hide();

        // }

        frm.trigger("customer")
        if (cur_frm.doc.docstatus == 1) {

            frm.add_custom_button(__('Delivery Note'),
                function () {
                    frm.trigger("delivery_note")
                }, __('Create'));
        }

        frm.add_custom_button(__('Delivery Request'),
            function () {
                if (!cur_frm.doc.customer) {
                    frappe.throw({
                        title: __("Mandatory"),
                        message: __("Please Select a Customer")
                    });
                } else {
                    frm.trigger("add_delivery_request");

                }
                // erpnext.utils.map_current_doc({
                //   method: "semah.semah.doctype.delivery_request.delivery_request.get_item",
                //   source_doctype: "Delivery Request",
                //   target: frm,
                //   setters: {
                //     customer: frm.doc.customer,
                //   },
                //   get_query_filters: {
                //     customer: frm.doc.customer,
                //     // name: frm.doc.delivery_request
                //   }
                // })

            }, __("Get Items From"));
        //   if(cur_frm.doc.docstatus==1){
        //     cur_frm.doc.order_status="To make Delivery Note"
        //   }
        if (cur_frm.doc.docstatus == 0) {
            cur_frm.doc.order_status = "Draft"
        }

    },
    add_delivery_request: function (frm) {

        var table_fields = []
        var data = []
        table_fields = [{
            "fieldtype": "Link",
            label: __('Name '),
            "options": "Delivery Request",
            fieldname: 'name',
            reqd: 1,
            read_only: 1,
            in_list_view: 1
        }];
        table_fields.push({
            fieldtype: 'Data',
            label: __('Customer'),
            fieldname: 'customer',
            read_only: 1,
            in_list_view: 1
        });

        const dialog = new frappe.ui.Dialog({
            title: __('Delivery Request'),

            fields: [{
                fieldname: "delivery_request",
                fieldtype: "Table",
                label: "Delivery Request",
                cannot_add_rows: true,
                in_place_edit: false,
                cannot_delete_rows: true,
                reqd: 1,
                // data: [],
                fields: table_fields,
                data: data,
                get_data: () => {
                    return data;
                }
            }],
            primary_action: async function ({ delivery_request }) {
                if (delivery_request.length > 0) {
                    var _return = true
                    var items = $.grep(delivery_request, function (element, index) {
                        return element.__checked == 1;
                    });
                    if (items.length > 1) {
                        frappe.throw("You can select only one entry")
                        _return = false
                    }
                    if (_return == true) {
                        frappe.db.get_doc('Delivery Request', items[0]['name'])
                            .then(doc => {
                                console.log(doc)
                                var item = doc.item_grid
                                cur_frm.clear_table("item_grid");
                                cur_frm.set_value("sub_customer", doc.sub_customer)
                                cur_frm.set_value("delivery_request", doc.name)
                                cur_frm.set_value("warehouse", doc.sub_customer)
                                cur_frm.set_value("requested_date", doc.requested_date)
                                cur_frm.set_value("required_date", doc.required_date)
                                cur_frm.set_value("customer_primary_address", doc.address_html)
                                cur_frm.set_value("primary_address", doc.primary_address)
                                cur_frm.set_value("contact_person", doc.contact_person)
                                cur_frm.set_value("mobile_no", doc.mobile_no)
                                cur_frm.set_value("email_id", doc.email_id)
                                cur_frm.set_value("address_and_contact_details", doc.address_and_contact_details)
                                cur_frm.set_value("contact_person_email_id", doc.contact_person_email_id)
                                cur_frm.set_value("contact_person_phone", doc.contact_person_phone)


                                //var itmg = doc.item_grid
                                Object.entries(item).forEach(([key, value]) => {
                                    var rw = cur_frm.add_child("item_grid");
                                    rw.item_code = value["item_code"]
                                    rw.item_name = value["item_name"]
                                    rw.item_description = value["item_description"]
                                    rw.required_date = value["required_date"]
                                    rw.qty_required = value["qty_required"]
                                    rw.uom = value["uom"]


                                    // for (var i = 0; i < itmg.length; i++) {
                                    //     console.log(itmg[i].required_date, itmg[i].item_description,itmg[i].uom,itmg[i].item_name,"nm")

                                    //     if (itmg[i].item_code == value["item"]) {
                                    //         rw.quantity_required = itmg[i].qty_required
                                    //         rw.required_date = itmg[i].required_date
                                    //         rw.description = itmg[i].item_description
                                    //         rw.item_name = itmg[i].item_name
                                    //         rw.uom = itmg[i].uom
                                    //     }

                                    // }



                                });
                                cur_frm.refresh_field('item_grid')
                                //_property('storage_details', 'read_only', 1)
                                dialog.hide();

                            })
                    }
                }
            },
            primary_action_label: __('Add Item')
        });

        dialog.show();
        dialog.$wrapper.find('.modal-dialog').css("width", "700px");
        dialog.$wrapper.find('.modal-dialog').css("max-width", "800px");
        frappe.call({
            method: "semah.semah.doctype.preparation_order_note.preparation_order_note.get_delivery_request",
            args: {
                'customer': frm.doc.customer
            },
            callback: function (r) {
                data = r.message
            }
        })

        setTimeout(() => {
            dialog.fields_dict.delivery_request.df.data = data;
            dialog.fields_dict.delivery_request.grid.refresh();
        }, 300)
    },


    before_save: function (frm) {
        var storage = cur_frm.doc.storage_details
        var row = cur_frm.add_child("storage_details");
        cur_frm.clear_table("tem");
        Object.entries(storage).forEach(([key, value]) => {
            var row = cur_frm.add_child("tem");
            row.item = value["item"]
            row.warehouse = value["warehouse"]
            // row.bin_location_name = value["bin_location_name"]
            row.batch_no = value["batch_no"]
            row.delivery_qty = value["delivery_qty"]
            row.expiry_date = value["expiry_date"]
            row.qty_required = value["qty_required"]
            row.required_date = value["required_date"]
            row.uom = value["uom"]
            row.item_name = value["item_name"]
            row.description = value["description"]
            frappe.db.get_value('Batch', value["batch_no"], 'customer_batch_id')
                .then(r => {
                    if (r.message.customer_batch_id) {
                        row.customer_batch_id = r.message.customer_batch_id
                    }
                })
        })
    },


    update_storage: function (frm, cdt, cdn) {
        frappe.call({
            doc: cur_frm.doc,
            method: 'update_storage_details',
            freeze: true,
            callback: function (r, rt) {
               
        cur_frm.refresh_field("storage_details")
        calculateDeliveryqty();

            }
        });
        // var d = locals[cdt][cdn];
        // var itm = frm.doc.item_grid

        // for (var i = 0; i < itm.length; i++) {
        //     frappe.call({
        //         method: "get_stock",
        //         doc:cur_frm.doc,
        //         async: false,
        //         args: {
        //             item: itm[i].item_code
        //         },
        //         callback: function (r) {
        //             console.log(r)
        //             if (i == 0) {
        //                 cur_frm.clear_table("storage_details");
        //             }
        //             var list = r.message
        //             var qty_required = itm[i].qty_required
        //             var bal;
        //             if (qty_required < 0 || qty_required == 0) {
        //                 frappe.throw("Delivery qty can't be " + qty_required + " of item " + itm[i].item_code)
        //                 cur_frm.clear_table("storage_details");
        //             }

        //             for (var j = 0; j < list.length; j++) {
        //                 console.log(list[j].stored_qty)

        //                 if (qty_required > 0 && list[j].stored_qty > 0) {
        //                     var rw = cur_frm.add_child("storage_details");
        //                     // frappe.model.set_value(rw.doctype, rw.name, "batch_no", list[j].batch_no)
        //                     rw.batch_no = list[j].batch_no
        //                     rw.item = itm[i].item_code
        //                     rw.item_name = itm[i].item_name
        //                     rw.uom = itm[i].uom
        //                     rw.description = itm[i].item_description
        //                     rw.required_date = itm[i].required_date
        //                     rw.qty_required = itm[i].qty_required
        //                     rw.warehouse = list[j].warehouse
        //                     rw.expiry_date = list[j].expiry
        //                     rw.bin_location_name = list[j].bin_location
        //                     rw.pallet = list[j].pallet
        //                     // rw.batch_no = list[j].batch_no
        //                     rw.stored_qty = list[j].stored_qty
        //                     rw.area_used = list[j].area_use
        //                     rw.stored_in = list[j].stored_in
        //                     rw.sub_customer = list[j].sub_customer
        //                     if (list[j].height != 0) {
        //                         rw.height = list[j].height
        //                     }
        //                     rw.width = list[j].width
        //                     rw.length = list[j].length
        //                     rw.manufacture_date = list[j].manufacturing_date



        //                     // frappe.model.set_value(rw.doctype, rw.name, "batch_no",list[j].batch_no)

        //                     // rw.batch_no = list[j].batch_no
        //                     if (qty_required > list[j].stored_qty) {
        //                         rw.delivery_qty = list[j].stored_qty
        //                     } else {
        //                         rw.delivery_qty = qty_required

        //                     }
        //                     bal = qty_required - list[j].stored_qty
        //                     qty_required = qty_required - list[j].stored_qty
        //                 }
        //             }
        //             console.log(bal)
        //             if (qty_required > 0) {
        //                 console.log(bal)
        //                 frappe.throw("insufficient stock of " + itm[i].item_code)

        //             }

        cur_frm.refresh_field("storage_details")
        calculateDeliveryqty();




        //     }

        // });

        // }


    },
    delivery_note: function (frm) {


        frappe.model.open_mapped_doc({
            method: "semah.semah.doctype.preparation_order_note.preparation_order_note.make_delivery_note",
            frm: cur_frm
        })

    },
    setup: function (frm) {
        // if (!frm.is_new()) {
        // $(frm.wrapper).on('grid-row-render', function(e, grid_row) {
        //     if (in_list(['Preparation Storage Details'], grid_row.doc.doctype)) {
        //         console.log(grid_row.doc.idx);
        //         if (grid_row && grid_row.doc.item && grid_row.doc.batch_no && grid_row.doc.warehouse) {
        //             // grid_row.columns_list[4].df.options =[""]
        //             frappe.call({
        //                 method: "semah.semah.doctype.preparation_order_note.preparation_order_note.get_bin",
        //                 args: {
        //                     item: grid_row.doc.item,
        //                     batch: grid_row.doc.batch_no,
        //                     warehouse: grid_row.doc.warehouse,
        //                 },
        //                 callback: function(r) {
        //                     grid_row.columns_list[4].df.options = r.message

        //                 }
        //             })


        //         }
        //     }
        // });
        // }
        cur_frm.set_query("bin_location_name", "storage_details", function (frm, cdt, cdn) {
            const item_code_list = (cur_frm.doc.item_grid || []).map(row => row.item_code).filter(Boolean);

            return {
                query: 'semah.semah.doctype.preparation_order_note.preparation_order_note.bin_filter',
                filters: {
                    "item_code_list": item_code_list
                }
            };
        });

        frm.set_query("item", "storage_details", function (frm, cdt, cdn) {
            var item_list = [];
            for (var i = 0; i < cur_frm.doc.item_grid.length; i++) {
                item_list.push(cur_frm.doc.item_grid[i].item_code)
            }
            if (item_list.length > 0)
                return {
                    "filters": {
                        "name": ["in", item_list]
                    }
                };
            else return {}
        });
        frm.set_query("warehouse", "storage_details", function (frm, cdt, cdn) {
            var item_list = [];
            return {
                "filters": {
                    "name": cur_frm.doc.warehouse
                }
            }
        });
        frm.set_query("batch_no", "storage_details", function (frm, cdt, cdn) {
            var value = locals[cdt][cdn]
            var batch = [];
            frappe.model.with_doc("Item", value.item, function () {
                var tabletransfer = frappe.model.get_doc("Item", value.item)
                $.each(tabletransfer.bin, function (index, row) {
                    if (value.warehouse == row.warehouse && value.item == tabletransfer.name) {
                        batch.push(row.batch_no)

                        //frm.fields_dict.storage_details.grid.update_docfield_property('bin_location_name','options',row.bin_location);
                        //value.set_df_property('bin_location_name', 'options', row.bin_location);
                    }

                })

            })
            return {
                "filters": {
                    "name": ["in", batch]
                }
            }
        });
    },
    validate: function (frm) {
        var storage = frm.doc.storage_details
        var item = frm.doc.item_grid
        var qty = 0
        for (var i = 0; i < item.length; i++) {
            qty = 0;
            var items = $.grep(storage, function (element, index) {
                return element.item == item[i].item_code;
            });
            if (items.length > 0) {
                for (var j = 0; j < items.length; j++) {
                    qty = qty + items[j].delivery_qty
                }
            }
            if (qty == 0) {
                frappe.throw("Delivery Qty should not be greater or lesser than Required Qty!!");

            }
            if (qty > 0 && (qty < item[i].qty_required || qty > item[i].qty_required)) {
                frappe.msgprint("Delivery Qty should not be greater or lesser than Required Qty!!");
                //frappe.throw("");

                validated = false;
                return false;
            }

            // for (var j = 0; j < storage.length; j++) {
            //   if (storage[j].item == item[i].item_code && storage[j].stored_qty > item[i].qty_required) {
            //     storage[j].stored_qty = ''
            //     frappe.msgprint("Stored Qty should not be greater than Qty Required!!");
            //     //frappe.throw("");
            //     validated = false;
            //     return false;

            //   }
            // }
            if (item[i].qty_required == undefined) {
                frappe.msgprint("Delivery Quantity should not be greater than Required Qty!!")
                //value.delivery_qty=''
                validated = false;
                return false;
            }
        }
        var storage = frm.doc.storage_details
        for (var i = 0; i < storage.length; i++) {
            if (storage[i].delivery_qty > storage[i].stored_qty) {
                frappe.msgprint("Delivery Quantity should not be greater than Stored Qty!!")
                //value.delivery_qty=''
                validated = false;
                return false;
            }
        }


    }
});
frappe.ui.form.on('Preparation Storage Details', {

    //  


    delivery_qty: function (frm, cdt, cdn) {

        //var total=0
        var row = locals[cdt][cdn];
        var items = frm.doc.storage_details
        var value = frm.doc.item_grid
        if (row.stored_qty == undefined) {
            frappe.msgprint("Delivery Quantity should not be greater than Stored Qty!!")
            //value.delivery_qty=''
            validated = false;
            return false;
        }
        total = 0
        for (var i = 0; i < items.length; i++) {
            if (row.item == items[i].item) {
                //console.log(items[i].item)
                total = total + items[i].delivery_qty
                //console.log(items[i].delivery_qty)
                //console.log(total,'total')
            }
        }
        //total=total+row.delivery_qty;
        for (var j = 0; j < value.length; j++) {

            if (row.item == value[j].item_code && total > value[j].qty_required) {
                frappe.model.set_value(cdt, cdn, "delivery_qty", '');
                frappe.msgprint("Delivery Qty should not be greater than Required Qty!!");
                //frappe.throw("");

                validated = false;
                return false;
            }
        }
        frappe.model.set_value(cdt, cdn, "total", total);

    },

    expiry_date: function (frm, cdt, cdn) {
        cur_frm.refresh_fields("storage_details")
        cur_frm.refresh_fields("storage_details")
    },
    batch_no: function (frm, cdt, cdn) {
        var child = locals[cdt][cdn];
        if (child.batch_no != '') {

            frappe.call({
                method: "fetch_item_details",
                doc: cur_frm.doc,
                args: { "row": child, "value_type": "Batch" },
                callback: function (r) {
                    if (r.message) {
                        cur_frm.refresh()

                    }
                }
            });

        } else {
            frappe.model.set_value(cdt, cdn, "stored_qty", undefined)
            frappe.model.set_value(cdt, cdn, "stored_in", undefined)

            frappe.model.set_value(cdt, cdn, "height", undefined)
            frappe.model.set_value(cdt, cdn, "width", undefined)
            frappe.model.set_value(cdt, cdn, "length", undefined)
            frappe.model.set_value(cdt, cdn, "area_used", undefined)

        }


    },
    bin_location_name: function (frm, cdt, cdn) {
        var child = locals[cdt][cdn];
        if (child.bin_location_name != '') {

            frappe.call({
                method: "fetch_item_details",
                doc: cur_frm.doc,
                args: { "row": child, "value_type": "BIN" },
                callback: function (r) {
                    if (r.message) {
                        cur_frm.refresh()

                    }
                }
            });
            // if (child.item && child.batch_no && child.warehouse && child.bin_location_name) {
            //     frappe.call({
            //         method: "semah.semah.doctype.preparation_order_note.preparation_order_note.update_row",
            //         args: {
            //             item: child.item,
            //             batch: child.batch_no,
            //             warehouse: child.warehouse,
            //             bin_location_name: child.bin_location_name
            //         },
            //         callback: function (r) {
            //             if (r) {
            //                 console.log(r)
            //                 var result = r.message[0]
            //                 // if (r.message[0].stored_qty || r.message[0].stored_qty > 0) {
            //                 //   frappe.throw("insufficient  Quantity")
            //                 // }
            //                 // else {
            //                 frappe.model.set_value(cdt, cdn, "stored_qty", result.stored_qty)
            //                 frappe.model.set_value(cdt, cdn, "stored_in", result.stored_in)
            //                 frappe.model.set_value(cdt, cdn, "sub_customer", result.sub_customer)


            //                 frappe.model.set_value(cdt, cdn, "height", result.height)
            //                 frappe.model.set_value(cdt, cdn, "width", result.width)
            //                 frappe.model.set_value(cdt, cdn, "length", result.length)
            //                 frappe.model.set_value(cdt, cdn, "area_used", result.area_use)

            //                 // }
            //             }

            //         }
            //     })
            // }
        } else {
            frappe.model.set_value(cdt, cdn, "stored_qty", undefined)
            frappe.model.set_value(cdt, cdn, "stored_in", undefined)

            frappe.model.set_value(cdt, cdn, "height", undefined)
            frappe.model.set_value(cdt, cdn, "width", undefined)
            frappe.model.set_value(cdt, cdn, "length", undefined)
            frappe.model.set_value(cdt, cdn, "area_used", undefined)

        }


    }

})
frappe.ui.form.on('Preparation Item Grid', {
    item_code: function (frm, cdt, cdn) {
        var row = locals[cdt][cdn]
        if (row.item_code) {
            var item = frm.doc.item_grid
            for (var i = 0; i < item.length; i++) {
                if (row.item_code == item[i].item_code && row.idx != item[i].idx) {
                    row.item_code = ''
                    frappe.msgprint("Duplicate Item found!!");
                    //frappe.throw("");
                    validated = false;
                    return false;
                }

            }
        }
    },
    item_grid_add: function (frm, cdt, cdn) {
        var row = locals[cdt][cdn]
        cur_frm.get_field("item_grid").grid.grid_rows[row.idx - 1].remove();

        console.log(row)

    }

});
frappe.ui.form.on("Preparation Item Grid", "form_render", function (frm, cdt, cdn) {
    $(".row-actions").css("display", "none")

});


frappe.ui.form.on('Preparation Item Grid', {

    qty_required: function (frm, cdt, cdn) {
        calculateItemGridQuanitty();
    },
    item_grid_remove: function (frm, cdt, cdn) {

        calculateItemGridQuanitty();
    },
});

frappe.ui.form.on('Preparation Storage Details', {

    delivery_qty: function (frm, cdt, cdn) {
        calculateDeliveryqty();
    },
    storage_details_remove: function (frm, cdt, cdn) {

        calculateDeliveryqty();
    },
});

// function calculateItemGridQuanitty(frm) {
//     var total_stored_qty = 0;
//     $.each(frm.doc.item_grid || [], function(i, d) {
//         total_stored_qty += flt(d.qty_required);
//     });
//     console.log(total_stored_qty)
//     frm.set_value('total_quantity', total_stored_qty);
// }

function calculateItemGridQuanitty() {
    var total_stored_qty = 0;
    $.each(cur_frm.doc.item_grid || [], function (i, d) {
        total_stored_qty += flt(d.qty_required);
    });
    cur_frm.set_value('total_quantity', total_stored_qty);
}

function calculateDeliveryqty() {
    var total_stored_qty = 0;
    $.each(cur_frm.doc.storage_details || [], function (i, d) {
        total_stored_qty += flt(d.delivery_qty);
    });
    cur_frm.set_value('total_delivery_quantity', total_stored_qty);
}
