var pon;
frappe.ui.form.on("Delivery Note", {
    refresh: function (frm, doc, dt, dn) {
        frm.add_custom_button(__('Preparation Order Note'),
            function () {
                if (!cur_frm.doc.customer) {
                    frappe.throw({
                        title: __("Mandatory"),
                        message: __("Please Select a Customer")
                    });
                }
                else {
                    frm.trigger("add_Preparation_order_note");

                }
                // erpnext.utils.map_current_doc({
                //     method: "semah.semah.doctype.preparation_order_note.preparation_order_note.get_item",
                //     source_doctype: "Preparation Order Note",
                //     target: frm,
                //     setters: {
                //         customer: frm.doc.customer,
                //     },
                //     get_query_filters: {
                //         customer: frm.doc.customer,
                //     },

                // }) 

            }, __("Get Items From"));
            if (cur_frm.doc.docstatus!=1){
                frm.page.wrapper.find('use[href="#icon-printer"]').closest("button").hide();
    
            }

    },
    onload: function (frm) {
        frm.set_df_property('sub___customer_details', 'hidden', 1);
        cur_frm.set_df_property('address', 'read_only', 1);
        $('[data-fieldname="prepration"] ').css("display", "none")
        if (!frm.is_new()) {
            frm.trigger("options");
            cur_frm.set_df_property('storage_details', 'read_only', 1)
            cur_frm.set_df_property('items', 'read_only', 1)
        }
        if (cur_frm.doc.customer) {
            frm.trigger("options");
            frm.trigger("sub_customer");
            cur_frm.set_df_property('storage_details', 'read_only', 1)
            cur_frm.set_df_property('items', 'read_only', 1)
        }
    },
    options: function (frm) {
        if (cur_frm.doc.customer) {
            frappe.db.get_doc('Customer', cur_frm.doc.customer)
                .then(r => {
                    if (r) {
                        var sub = [" ",];
                        // while (sub.length > 0) {
                        //     sub.pop();
                        // }
                        var sub_customer = r.sub_customer
                        for (var i = 0; i < sub_customer.length; i++) {
                            sub.push(sub_customer[i].sub_customer_full_name)
                        }
                        frm.set_df_property("sub_customer", "options", sub);
                    }
                })

        }

    },

    customer: function (frm) {
        frm.trigger("options");

    },
    add_Preparation_order_note: function (frm) {

        var table_fields = []
        var data = []
        table_fields = [
            {
                "fieldtype": "Link", label: __('Name '), "options": "Preparation Order Note", fieldname: 'name', reqd: 1, read_only: true,
                in_list_view: 1,change: function () {

                    dialog.fields_dict.preparation_order_note.df.data.some(d => {
                        if (d.idx == this.doc.idx) {

                            d.name = d.name_1
                            dialog.fields_dict.preparation_order_note.grid.refresh();


                        }
                    })
                }
            },
            {
                "fieldtype": "Link", label: __('Name '), "options": "Preparation Order Note", fieldname: 'name_1', reqd: 1,change: function () {

                    dialog.fields_dict.preparation_order_note.df.data.some(d => {
                        if (d.idx == this.doc.idx) {

                            d.name_1 = d.name
                            dialog.fields_dict.preparation_order_note.grid.refresh();


                        }
                    })
                }
            },
            {
                fieldtype: 'Data', label: __('Customer'), fieldname: 'customer_1', change: function () {

                    dialog.fields_dict.preparation_order_note.df.data.some(d => {
                        if (d.idx == this.doc.idx) {

                            d.customer_1 = d.customer
                            dialog.fields_dict.preparation_order_note.grid.refresh();


                        }
                    })
                }
            }
        ];
        table_fields.push({
            fieldtype: 'Data', label: __('Customer'), fieldname: 'customer', read_only: 1,
            in_list_view: 1,change: function () {

                dialog.fields_dict.preparation_order_note.df.data.some(d => {
                    if (d.idx == this.doc.idx) {

                        d.customer = d.customer_1
                        dialog.fields_dict.preparation_order_note.grid.refresh();


                    }
                })
            }
        });

        const dialog = new frappe.ui.Dialog({
            title: __('Preparation order note'),

            fields: [
                {
                    fieldname: "preparation_order_note",
                    fieldtype: "Table",
                    label: "Preparation order note",
                    cannot_add_rows: true,
                    in_place_edit: true,
                    cannot_delete_rows: true,
                    reqd: 1,
                    // data: [],
                    fields: table_fields,
                    data: data,
                    get_data: () => {
                        return data;
                    }
                }
            ],
            primary_action: async function ({ preparation_order_note }) {
                if (preparation_order_note.length > 0) {
                    var _return = true
                    var items = $.grep(preparation_order_note, function (element, index) {
                        return element.__checked == 1;
                    });
                    if (items.length > 1) {
                        frappe.throw("You can select only one entry")
                        _return = false
                    }
                    if (_return == true) {
                        cur_frm.set_value("prepration", items[0]['name'])
                        frappe.db.get_doc('Preparation Order Note', items[0]['name'])
                            .then(doc => {
                                var storage = doc.storage_details
                                cur_frm.clear_table("items");
                                cur_frm.set_value("address_and_contact_details", doc.address_and_contact_details)
                                cur_frm.set_value("required_date", doc.required_date)
                                cur_frm.set_value("sub_customer", doc.sub_customer)
                                cur_frm.set_value("delivery_request", doc.delivery_request)

                                var itmg = doc.item_grid
                                Object.entries(storage).forEach(([key, value]) => {
                                    var rw = cur_frm.add_child("items");
                                    rw.item_code = value["item"]
                                    rw.warehouse = value["warehouse"]
                                    rw.batch_no = value["batch_no"]
                                    rw.qty = value["delivery_qty"]
                                    rw.quantity_required = value["qty_required"]
                                    rw.required_date = value["required_date"]
                                    rw.description = value["description"]
                                    rw.item_name = value["item_name"]
                                    rw.uom = value["uom"]
                                    rw.sub_customer = value["sub_customer"]
                                    frappe.db.get_value('Batch',  value["batch_no"], 'customer_batch_id')
                                    .then(r => {
                                      if(r.message.customer_batch_id) {
                                      row.customer_batch_id = r.message.customer_batch_id
                                      }
                                    })



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
                                cur_frm.refresh_field('items')
                                cur_frm.set_df_property('items', 'read_only', 1)
                                var storage = doc.storage_details
                                cur_frm.clear_table("storage_details");
                                Object.entries(storage).forEach(([key, value]) => {
                                    var row = cur_frm.add_child("storage_details");
                                    row.item_code = value["item"]
                                    row.bin_location_name = value["bin_location_name"]
                                    row.qty_required = value["qty_required"]
                                    row.delivery_qty = value["delivery_qty"]
                                    row.expiry_date = value["expiry_date"]
                                    row.stored_qty = value["stored_qty"]
                                    row.batch_no = value["batch_no"]
                                    row.warehouse = value["warehouse"]
                                    row.area_used = value["area_used"]
                                    row.manufacture_date = value["manufacture_date"]
                                    row.stored_in = value["stored_in"]
                                    row.height = value["height"]
                                    row.width = value["width"]
                                    row.length = value["length"]

                                });
                                cur_frm.refresh_field('storage_details')
                                cur_frm.set_df_property('storage_details', 'read_only', 1)
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
            method: "semah.custom_script.delivery_note.delivery_note.get_item",
            args: {
                'customer': frm.doc.customer
            }, callback: function (r) {
                data = r.message
            }
        })
        setTimeout(() => {
            dialog.fields_dict.preparation_order_note.df.data = data;
            dialog.fields_dict.preparation_order_note.grid.refresh();
        }, 300)
    },
    sub_customer: function (frm) {
        if (!cur_frm.doc.sub_customer == '' && !cur_frm.doc.docstatus>0) {
            frappe.db.get_doc('Customer', cur_frm.doc.customer)
                .then(re => {
                    var sub_details = re.sub_customer
                    if (sub_details) {
                        frm.set_df_property('sub___customer_details', 'hidden', 0);
                        Object.entries(sub_details).forEach(([key, value]) => {
                            if (cur_frm.doc.sub_customer == value["sub_customer_full_name"]) {
                                cur_frm.set_value("address", value["address"])
                                cur_frm.set_value("contact_persion_email", value["contact_person_email_id"])
                                cur_frm.set_value("contact_person_phone", value["contact_person_phone"])
                                cur_frm.set_value("contact_person_name", value["contact_person_name"])
                            }
                        })

                    }


                })


        }
    }


})

frappe.ui.form.on("Note Storage details",
    {
        stored_in: function (frm, cdt, cdn) {
            var storage = locals[cdt][cdn]
            if (storage.stored_in == "CBM") {
                var area = parseFloat(storage.length) * parseFloat(storage.width) * parseFloat(storage.height)
                frappe.model.set_value(cdt, cdn, "area_used", area)
            }
            if (storage.stored_in == "Pallet") {
                var area = parseFloat(storage.length) * parseFloat(storage.width)
                frappe.model.set_value(cdt, cdn, "area_used", area)
            }
        }
    })
