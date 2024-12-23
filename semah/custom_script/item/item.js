frappe.ui.form.on("Item", {
    onload: function (frm) {
        cur_frm.set_df_property('sub', 'label', 'Sub Customer');
        if (cur_frm.doc.customer_ && (!frm.is_new())) {
            frm.trigger("options")

        }
        $('[data-fieldname="bin"]').css("display", "none");
        $('[data-fieldname="update_bin"]').css("display", "none");
        $('[data-fieldname="update_all"]').css("display", "none");
        $('[data-fieldname="sub_customer"]').css("display", "none");


        cur_frm.refresh_fields();
    },
    refresh: function (frm) {
        cur_frm.set_df_property('sub', 'label', 'Sub Customer');
        $('[data-fieldname="sub_customer"]').css("display", "none");

    },
    customer_: function (frm) {
        if (cur_frm.doc.customer_) {
            frm.trigger("options")
            frappe.db.get_value('Customer', cur_frm.doc.customer_, 'customer_code')
                .then(r => {
                    var name = r.message.customer_code.toUpperCase()
                    cur_frm.set_value("item_naming", name)
                })

        }

    },
    options: function (frm) {
        frappe.db.get_doc('Customer', cur_frm.doc.customer_)
            .then(r => {
                if (r) {
                    var sub = [" ",];
                    var sub_customer = r.sub_customer
                    for (var i = 0; i < sub_customer.length; i++) {
                        sub.push(sub_customer[i].sub_customer_full_name)
                    }
                    frm.set_df_property("sub", "options", sub);
                }
            })
    },

    sub: function (frm) {
        cur_frm.set_value("sub_customer", cur_frm.doc.sub)
        if (cur_frm.doc.customer_ && cur_frm.doc.sub_customer) {
            console.log("in")
            frappe.call({
                method: "semah.custom_script.item.item.subnaming",
                async: false,
                args: {
                    customer: cur_frm.doc.customer_,
                    sub: cur_frm.doc.sub_customer
                },
                callback: function (r) {
                    if (r.message) {
                        console.log(r.message)
                        let name = r.message.toUpperCase()
                        console.log(name, r.message)
                        if (name) {
                            cur_frm.set_value("item_naming", name)
                        }
                        
                    }
                }
            })
        }
        else {
            frappe.db.get_value('Customer', cur_frm.doc.customer_, 'customer_code')
                .then(r => {
                    var name = r.message.customer_code.toUpperCase()
                    cur_frm.set_value("item_naming", name)
                })
        }

    },

    update_bin: function (frm) {
        frappe.call({
            method: "semah.custom_script.item.item.get_stock",
            async: false,
            args: {
                item: cur_frm.doc.name,
                self: cur_frm.doc
            },
            callback: function (r) {
                cur_frm.clear_table("bin_display");
                if (r) {
                    var itm = r.message
                    console.log(itm)
                    for (var i = 0; i < itm.length; i++) {
                        var rw = cur_frm.add_child("bin_display");
                        rw.warehouse = itm[i].warehouse
                        rw.batch_no = itm[i].batch_no
                        rw.bin_location = itm[i].bin_location
                        rw.expiry = itm[i].expiry
                        rw.stored_qty = itm[i].stored_qty
                        rw.stored_in = itm[i].stored_in
                        rw.length = itm[i].length
                        rw.height = itm[i].height
                        rw.width = itm[i].width
                        rw.area_use = itm[i].area_use
                        rw.sub_customer = itm[i].sub_customer
                    }

                }


                cur_frm.refresh_fields();
                frm.save()

            }
        })
    },
    update_all: function (frm) {
        frappe.call({
            method: "semah.custom_script.item.item.update_all",
            async: false,

        })
    }
})