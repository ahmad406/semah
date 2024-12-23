// Copyright (c) 2022, Dconnex and contributors
// For license information, please see license.txt

var item_list = []
frappe.ui.form.on('Delivery Request', {
    customer: function (frm) {
        var customer = [" ",];
        if (frm.doc.customer) {
            frappe.model.with_doc("Customer", frm.doc.customer, function () {
                var d = frappe.model.get_doc("Customer", frm.doc.customer)
                console.log(d.name)

                if (cur_frm.doc.customer == d.name) {
                    $.each(d.sub_customer, function (index, row) {
                        customer.push(row.sub_customer_full_name)
                    });
                    frm.set_df_property('sub_customer', 'options', customer);
                    frm.refresh_field('sub_customer');
                    frm.refresh_fields();

                }
            })
        }

    },
    get_indicator: function (frm) {
        if (cur_frm.doc_status == "Draft") {
            console.log("orange")
            return [__("Draft"), "orange", "status,=,Draft"];
        } //else if (doc.status === "On Hold") {
        // 	return [__("On Hold"), "orange", "status,=,On Hold"];
        // } else if (doc.status === "Delivered") {
        // 	return [__("Delivered"), "green", "status,=,Closed"];
        // } 
    },
    validate: function (frm) {
        if (frm.doc.required_date < frm.doc.requested_date) {
            frappe.msgprint("Required Date should be greater than Requested Date!!");
            //frappe.throw("");
            validated = false;
            return false;
        }
        if (frm.doc.requested_date == undefined) {
            frappe.msgprint("Required Date should be greater than Requested Date!!");
            //frappe.throw("");
            validated = false;
            return false;
        }
        // frappe.db.get_list('Preparation Order Note', {
        //     fields: ['delivery_request'],
        //     limit:2000
        // }).then(records => {
        //     console.log(records);
        //     for (var i=0;i<records.length;i++){
        //         if(cur_frm.doc.name==records[i].delivery_request){
        //             frappe.msgprint("Preparatioin Order Note Already created for this Delivery Request");
        //     //frappe.throw("");
        //     validated = false;
        //     return false;
        //         }
        //     }
        // })
    },
    sub_customer: function (frm) {
        frappe.call({
            method: "semah.semah.doctype.delivery_request.delivery_request.item_query",
            async: false,
            args: {
                customer_: cur_frm.doc.customer,
                sub_customer: cur_frm.doc.sub_customer
            },
            callback: function (r) {
                //cur_frm.clear_table("bin_display");
                if (r) {
                    item_list = []
                    var item = r.message
                    $.each(item, function (index, row) {
                        item_list.push(row.name)
                    })
                    console.log(item_list, item)
                }
            }
        })
        var customer = [" ",];
        //var address=[]
        if (frm.doc.sub_customer) {
            frappe.model.with_doc("Customer", frm.doc.customer, function () {
                var d = frappe.model.get_doc("Customer", frm.doc.customer)
                console.log(d.name)

                if (cur_frm.doc.customer == d.name) {
                    $.each(d.sub_customer, function (index, row) {
                        customer.push(row.sub_customer_full_name)
                        var sub = row.sub_customer_full_name
                        if (sub == frm.doc.sub_customer && row.address != undefined) {
                            var address = row.address
                            var phone = row.contact_person_phone
                            var email = row.contact_person_email_id
                            frm.doc.contact_person_email_id = email
                            frm.doc.address_and_contact_details = address
                            frm.doc.contact_person_phone = phone
                            console.log(row.address, "address")
                        }
                    });
                    frm.refresh_field("address_and_contact_details")
                    frm.refresh_fields();

                }
            })
        }
        if (frm.doc.sub_customer == '') {
            frm.doc.address_and_contact_details = ''
            frm.doc.contact_person_phone = ''
            frm.doc.contact_person_email_id = ''
        }
        frm.refresh_field("address_and_contact_details")
        frm.refresh_fields();

    },
    address_html: function (frm) {
        if (frm.doc.address_html) {
            return frm.call({
                method: "frappe.contacts.doctype.address.address.get_address_display",
                args: {
                    "address_dict": frm.doc.address_html
                },
                callback: function (r) {
                    if (r.message)
                        frm.set_value("primary_address", r.message);

                }
            });
        }
        else {
            frm.set_value("primary_address", "");
        }
    },

    refresh: function (frm) {
        frm.trigger("customer")
        if (cur_frm.doc.docstatus == 1) {
            //cur_frm.doc.doc_status="To make Preparation Order"
            frm.add_custom_button(__('Preparation Order Note'),
                function () {
                    frm.trigger("preparation_order_note")
                });
        }
        if (cur_frm.doc.docstatus == 0) {
            cur_frm.doc.doc_status = "Draft"
        }
        // if(cur_frm.doc.docstatus==2)
        // {
        //     cur_frm.doc.doc_status="Cancelled"
        // }
        // if(cur_frm.doc.docstatus==1)
        // {
        //     cur_frm.doc.doc_status="To make Preparation Order"
        // }

    },
    before_submit: function (frm) {
        cur_frm.doc.doc_status = "To make Preparation Order"
    },
    // before_cancel: function (frm) {
    //     console.log("cancel")
    //     cur_frm.doc.doc_status="Cancelled"
    // },
    // after_cancel: function (frm) {
    //     cur_frm.doc.doc_status="Cancelled"
    // },
    setup: function (frm) {
        frm.set_query("item_code", "item_grid", function (frm, cdt, cdn) {
            // var item_list = [];
            var d = locals[cdt][cdn];
            if (cur_frm.doc.sub_customer == '' || cur_frm.doc.sub_customer == undefined) {


                return {
                    "filters": {
                        "customer_": cur_frm.doc.customer
                    }
                };
            }
            else {
                return {
                    filters: [
                        ['Item', 'item_code', 'in', item_list],
                        // ["name", "not in", item_not]
                    ]
                }


            }


        });
        // if(cur_frm.doc.docstatus==0)
        // {
        //     cur_frm.doc.doc_status="Draft"
        // }
        // if(cur_frm.doc.docstatus==1)
        // {
        //     cur_frm.doc.doc_status="To make Preparation Order"
        // }


        //cur_frm.set_df_property("preparation_order_note","hidden",1);

        //frappe.throw("");
        // validated = false;
        // return false;
        frm.set_query("customer", function (frm) {
            return {
                filters: [
                    ['Customer', 'disabled', '=', 0],
                ]
            }
        });


    },
    preparation_order_note: function () {
        frappe.db.get_list('Preparation Order Note', {
            fields: ['delivery_request'],
            limit: 2000
        }).then(records => {
            console.log(records);
            for (var i = 0; i < records.length; i++) {
                if (cur_frm.doc.name == records[i].delivery_request) {
                    frappe.throw("Preparation Order Note Already created for this Delivery Request");
                    //frappe.throw("");
                    // validated = false;
                    // return false;
                }
            }
            frappe.model.open_mapped_doc({
                method: "semah.semah.doctype.delivery_request.delivery_request.make_preparation_order_note",
                frm: cur_frm
            })

        })



    },
    required_date: function (frm, cdt, cdn) {
        var d = frm.doc.item_grid

        if (frm.doc.required_date) {
            for (var i = 0; i < d.length; i++) {
                d[i].required_date = frm.doc.required_date

            }
            frm.refresh_field('item_grid');
        }

    },

});
frappe.ui.form.on('Item Grid', {
    item_grid_add: function (frm, cdt, cdn) {
        var d = locals[cdt][cdn];

        frappe.model.set_value(cdt, cdn, "required_date", frm.doc.required_date);
    },
    item_code: function (frm, cdt, cdn) {
        var row = locals[cdt][cdn]
        if (row.item_code) {
            var item = frm.doc.item_grid
            for (var i = 0; i < item.length; i++) {
                if (row.item_code == item[i].item_code && row.idx != item[i].idx) {
                    row.item_code = ''
                    row.item_name = ''
                    row.item_description = ''
                    row.uom = ''
                    row.required_date = ''
                    frappe.msgprint("Duplicate Item found!!");
                    //frappe.throw("");
                    validated = false;
                    return false;
                }

            }
        }
    },
    qty_required: function (frm, cdt, cdn) {
        console.log("yesyes")
        var row = locals[cdt][cdn]
        if (row.qty_required) {
            frappe.call({
                method: "calculate_total",
                doc: frm.doc,
                callback: function (r) {
                    cur_frm.dirty()
                    cur_frm.refresh_fields()
                }
            })
        }
    }
})

