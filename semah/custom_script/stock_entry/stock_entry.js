var item_list = []
var bin_location = []
var batch;

var uomlist;

frappe.ui.form.on("Stock Entry", {

    refresh: function (frm) {
        calculateTotalStoredQuantity(frm);
        $('[data-fieldname="sub"]').css("display", "none");
        cur_frm.set_df_property('sub_customer', 'label', 'Sub Customer');

        if (cur_frm.doc.customer_nm) {
            frm.trigger("customer_nm");
            frm.trigger("purpose");
            frm.trigger("to_warehouse");
            frm.trigger("update_item");
            cur_frm.set_df_property("total_incoming_value", "hidden", 1);
            cur_frm.set_df_property("total_outgoing_value", "hidden", 1);
            cur_frm.set_df_property("value_difference", "hidden", 1);

        }
        if (cur_frm.doc.docstatus != 1) {
            frm.page.wrapper.find('use[href="#icon-printer"]').closest("button").hide();

        }



    },

    sub_customer: function (frm) {
        // if (cur_frm.doc.sub_customer) {
        cur_frm.set_value("sub", cur_frm.doc.sub_customer)

        var itm = cur_frm.doc.storage_details
        for (var i = 0; i < itm.length; i++) {

            if (cur_frm.doc.sub_customer.length == 0) {
                cur_frm.doc.storage_details[i].sub_customer = ""
            }
            cur_frm.doc.storage_details[i].sub_customer = cur_frm.doc.sub_customer
        }


        // }


        cur_frm.refresh_fields("storage_details")
    },

    onload: function (frm) {
        $('[data-fieldname="sub"]').css("display", "none");
        cur_frm.set_df_property('sub_customer', 'label', 'Sub Customer');
        if (frm.is_new()) {
            cur_frm.clear_table("storage_details");
            cur_frm.set_value("total_area_used", undefined)
        }

    },
    update_item: function (frm) {
        if (cur_frm.doc.stock_entry_type == 'Material Receipt') {
            var itms = cur_frm.doc.items
            cur_frm.set_df_property("additional_costs_section", "hidden", 1);

            while (item_list.length > 0) {
                item_list.pop();
            }

            for (var i = 0; i < itms.length; i++) {
                item_list.push(itms[i].item_code)
            }
        }
    },

    setup: function (frm) {

        cur_frm.set_query("item_code", "storage_details", function (frm, cdt, cdn) {
            // var item_not = [];
            // for (var i = 0; i < cur_frm.doc.storage_details.length; i++) {
            //     item_not.push(cur_frm.doc.storage_details[i].item_code)
            // }
            // if (item_not.length > 0) {
            return {
                filters: [
                    ['Item', 'item_code', 'in', item_list],
                    // ["name", "not in", item_not]
                ]
            }
            // }
            // else{
            //     return {
            //         filters: [
            //             ['Item', 'item_code', 'in', item_list],
            //         ]
            //     }

            // }
        });
        cur_frm.set_query("bin_location", "storage_details", function (frm, cdt, cdn) {
            const selected_bins = [];

            cur_frm.doc.storage_details.forEach(row => {
                if (row.bin_location) {
                    selected_bins.push(row.bin_location);
                }
            });
            var child = locals[cdt][cdn];
            return {
                query: 'semah.custom_script.stock_entry.stock_entry.get_bin',
                filters: {
                    "selected_bins": selected_bins,
                    "item": child.item_code,
                    "expiry": child.expiry,
                    "qty":child.stored_qty
                    // ,"warehouse":child.t_ware_house
                }

            }
        });




        cur_frm.set_query("pallet", "storage_details", function (frm, cdt, cdn) {
            var child = locals[cdt][cdn];
            return {
                query: 'semah.custom_script.stock_entry.stock_entry.pallet_filter',
                filters: {
                    "item": child.item_code
                    // ,"warehouse":child.t_ware_house
                }

            }
        });



        cur_frm.set_query("batch_no", "storage_details", function (frm, cdt, cdn) {

            return {
                filters: [
                    ['Batch', 'item', '=', batch],
                    // ["name", "not in", item_not]
                ]
            }
        });
        // cur_frm.cscript.onload = function (frm) {
        cur_frm.set_query("uom", "items", function () {
            return {

                filters: [
                    ['UOM', 'name', 'in', uomlist],
                ]
                // filters: { "customer_": cur_frm.doc.customer_nm,"sub":cur_frm.doc.customer_nm }
            }

        });
        // }

        cur_frm.cscript.onload = function (frm) {
            cur_frm.set_query("item_code", "items", function () {
                if (!cur_frm.doc.sub_customer) {
                    return {

                        filters: [
                            ['Item', 'customer_', '=', cur_frm.doc.customer_nm],
                        ]
                        // filters: { "customer_": cur_frm.doc.customer_nm,"sub":cur_frm.doc.customer_nm }
                    }
                } else {
                    return {

                        filters: [
                            ['Item', 'customer_', '=', cur_frm.doc.customer_nm],
                            ["Item", "sub_customer", '=', cur_frm.doc.sub_customer]
                        ]
                        // filters: { "customer_": cur_frm.doc.customer_nm,"sub":cur_frm.doc.customer_nm }
                    }
                }
            });
        }
        $(frm.wrapper).on('grid-row-render', function (e, grid_row) {
            if (in_list(['Storage details'], grid_row.doc.doctype)) {
                // if (grid_row) {
                //     if (grid_row.doc.display_stored_in == "Pallet") {
                //         grid_row.columns_list[8].df.read_only = 1
                //     }
                // }
            }
            if (cur_frm.doc.stock_entry_type == 'Transfer to Quarantine') {
                if (in_list(['Stock Entry Detail'], grid_row.doc.doctype)) {
                    if (grid_row) {
                        grid_row.columns_list[3].df.read_only = 1
                    }
                }
            }
        });

    },

    // before_submit(frm) {
    //     var storage = cur_frm.doc.storage_details
    //     var item = cur_frm.doc.items
    //     var all_list = []

    //     var raw = cur_frm.doc.items
    //     for (var i = 0; i < raw.length; i++) {
    //         if (!raw[i]["batch_no"])
    //             all_list.push(raw[i]["item_code"])
    //     }
    //     let findDuplicates = arr => arr.filter((item, index) => arr.indexOf(item) != index)
    //     var duplicate = (findDuplicates(all_list))
    //     if (duplicate.length !== 0) {
    //         frappe.throw("Item " + duplicate + " is already in list with out batch no")
    //     }

    //     for (var i = 0; i < item.length; i++) {
    //         var ttl = 0
    //         for (var j = 0; j < storage.length; j++) {
    //             if (item[i].item_code == storage[j].item_code && item[i].batch_no == storage[j].batch_no) {
    //                 ttl = ttl + storage[j].stored_qty
    //             }
    //         }
    //         if (item[i].qty != ttl) {

    //             frappe.throw(item[i].item_code + " Qty should not be greater or lesser than Stored qty! or check batch No again!")

    //         }
    //     }
    // },


    purpose: function (frm) {
        if (cur_frm.doc.stock_entry_type == 'Material Receipt') {


            $('[data-fieldname="s_warehouse"]').css("display", "none");

            // frm.fields_dict["items"].grid.set_column_disp("s_warehouse",true);

            cur_frm.fields_dict.items.grid.update_docfield_property("s_warehouse", "hidden", 1);
            cur_frm.set_df_property("get_stock_and_rate", "hidden", 1);
            $('[data-fieldname="apply_putaway_rule"]').css("display", "none");
            $('[data-fieldname="basic_rate"]').css("display", "none");

            setTimeout(() => {
                cur_frm.set_df_property("additional_costs_section", "hidden", 1);
            }, 10);

        } else {
            $('[data-fieldname="s_warehouse"]').css("display", "");

            $('[data-fieldname="get_stock_and_rate"]').css("display", "");
            $('[data-fieldname="apply_putaway_rule"]').css("display", "");
            $('[data-fieldname="basic_rate"]').css("display", "");

        }

    },

    customer_nm: function (frm) {
        if (cur_frm.doc.customer_nm) {
            frappe.call({
                doc: cur_frm.doc,
                method: 'get_warehouse_of_customer',
                freeze: true,
                freeze_message: "fetching warehouse ... ",
                callback: function (r, rt) {
                    console.log(r.message, "1")
                    if (r.message) {
                        frm.trigger("options");


                        var cust_warehouse = r.message.customer_warehouse
                        if (cur_frm.doc.docstatus == 0) {

                            if (cust_warehouse && cur_frm.doc.stock_entry_type == 'Material Receipt') {
                                cur_frm.set_value("to_warehouse", cust_warehouse)
                            }
                            else {
                                cur_frm.set_value("to_warehouse", undefined)

                            }
                        }

                        frm.trigger("to_warehouse");




                    }
                    else {
                        if (cur_frm.doc.docstatus == 0) {
                            cur_frm.set_value("to_warehouse", undefined)
                        }
                    }



                }
            });
        }
    },
    from_warehouse: function (frm) {
        if (cur_frm.doc.stock_entry_type == "Quarantine Item Issue to Customer" && cur_frm.doc.from_warehouse) {
            // frappe.db.get_doc('Warehouse', cur_frm.doc.from_warehouse)
            //     .then(r => {
            //         while (bin_location.length > 0) {
            //             bin_location.pop();
            //         }
            //         var bin = r.bin_location
            //         if (bin) {
            //             for (var i = 0; i < bin.length; i++) {
            //                 bin_location.push(bin[i].bin_location_name)
            //             }
            //             frm.fields_dict.storage_details.grid.update_docfield_property('bin_location', 'options', bin_location)
            //             cur_frm.refresh_fields('storage_details')
            //         }
            //     })
            $('[data-fieldname="t_ware_house"] .static-area').html("Source")
        }
    },
    to_warehouse: function (frm) {
        // if (cur_frm.doc.to_warehouse) {
        //     frappe.db.get_doc('Warehouse', cur_frm.doc.to_warehouse)
        //         .then(r => {
        //             while (bin_location.length > 0) {
        //                 bin_location.pop();
        //             }
        //             var bin = r.bin_location
        //             if (bin) {
        //                 for (var i = 0; i < bin.length; i++) {
        //                     bin_location.push(bin[i].bin_location_name)
        //                 }
        //                 frm.fields_dict.storage_details.grid.update_docfield_property('bin_location', 'options', bin_location)
        //                 cur_frm.refresh_fields('storage_details')
        //             }
        //         })
        // }
        if (cur_frm.doc.stock_entry_type == "Quarantine Item Issue to Customer" && cur_frm.doc.from_warehouse) {
            // frappe.db.get_doc('Warehouse', cur_frm.doc.from_warehouse)
            //     .then(r => {
            //         while (bin_location.length > 0) {
            //             bin_location.pop();
            //         }
            //         var bin = r.bin_location
            //         if (bin) {
            //             for (var i = 0; i < bin.length; i++) {
            //                 bin_location.push(bin[i].bin_location_name)
            //             }
            //             frm.fields_dict.storage_details.grid.update_docfield_property('bin_location', 'options', bin_location)
            //             cur_frm.refresh_fields('storage_details')
            //         }
            //     })
            $('[data-fieldname="t_ware_house"] .static-area').html("Source")
        }

    },
    options: function (frm) {
        frappe.db.get_doc('Customer', cur_frm.doc.customer_nm)
            .then(r => {
                if (r) {
                    var sub = [" ",];
                    var sub_customer = r.sub_customer
                    for (var i = 0; i < sub_customer.length; i++) {
                        sub.push(sub_customer[i].sub_customer_full_name)
                    }
                    frm.set_df_property("sub_customer", "options", sub);
                }
            })


    },
    before_save: function (frm) {
        if (cur_frm.doc.storage_details) {
            var area = cur_frm.doc.storage_details
            var total = 0
            for (var i = 0; i < area.length; i++) {
                var check_nan = isNaN(parseFloat(area[i].area_used))
                // if (area[i].length == 0) {
                //     frappe.throw("length can't be zero in row " + (i + 1))

                // }
                // if (area[i].width == 0) {
                //     frappe.throw("width can't be zero in row " + (i + 1))

                // }
                // if (area[i].heigth == 0 && area[i].display_stored_in == "Pallet") {
                //     frappe.throw("heigth can't be zero in row " + (i + 1))

                // }
                // if(area[i].heigth !=0 ||  area[i].display_stored_in=="CBM"  ){
                //     frappe.throw("heigth must  be zero in row "+(i+1))

                // }
                if (check_nan == false) {
                    total = total + area[i].area_used
                }
            }
            if (total) {
                cur_frm.set_value("total_area_used", total)

            }
        }


    },
    select: function (frm, cdt, cdn) {
        frappe.call({
            method: "updatestorage",
            async: false,
            doc: frm.doc,
            args: {
                'bin': bin_location
            },
        });
        cur_frm.refresh_fields("storage_details")
        calculateTotalStoredQuantity2();
    },


    cal_areaused: function (frm) {
        if (cur_frm.doc.storage_details) {
            var area = cur_frm.doc.storage_details
            var total = 0
            for (var i = 0; i < area.length; i++) {
                var check_nan = isNaN(parseFloat(area[i].area_used))
                if (check_nan == false) {
                    total = total + area[i].area_used
                }
            }
            if (total) {
                cur_frm.set_value("total_area_used", total)

            }
        }



    },





});
// frappe.ui.form.on('material reciept', {
//     item_code: function (frm, cdt, cdn) {
//         var child = locals[cdt][cdn];
//         if (cur_frm.doc.stock_entry_type == 'Material Receipt') {
//             frappe.call({
//                 method: "semah.custom_script.stock_entry.stock_entry.item_uom",
//                 args: {
//                     'item_code': child.item_code
//                 },
//                 callback: function(r) {
//                     uomlist=r.message

//                 }
//             })
//             cur_frm.refresh_fields("storage_details")
//         }





//     },
// })
frappe.ui.form.on('Stock Entry Detail', {
    item_code: function (frm, cdt, cdn) {
        var child = locals[cdt][cdn];
        if (cur_frm.doc.stock_entry_type == 'Material Receipt') {
            cur_frm.doc.items[child.idx - 1].allow_zero_valuation_rate = 1
            item_list.push(child.item_code)
        }

        var item = locals[cdt][cdn];
        let quick = frm.get_docfield("items", "batch_no");
        quick.get_route_options_for_new_doc = function () {
            // if (frm.is_new()) return;
            return {
                "item": item.item_code,
            }
        }
        if (cur_frm.doc.stock_entry_type == 'Transfer to Quarantine' && child.t_warehouse && child.idx == 1 && !cur_frm.doc.to_warehouse && cur_frm.doc.docstatus == 0) {
            cur_frm.set_value("to_warehouse", child.t_warehouse)
        }
    },
    items_add: function (frm) {
        if (cur_frm.doc.stock_entry_type == 'Material Receipt') {
            $('[data-fieldname="s_warehouse"]').css("display", "none");
            $('[data-fieldname="get_stock_and_rate"]').css("display", "none");
            $('[data-fieldname="apply_putaway_rule"]').css("display", "none");
            $('[data-fieldname="basic_rate"]').css("display", "none");
            cur_frm.set_df_property("additional_costs_section", "hidden", 1);
        } else {
            $('[data-fieldname="s_warehouse"]').css("display", "");
            $('[data-fieldname="get_stock_and_rate"]').css("display", "");
            $('[data-fieldname="apply_putaway_rule"]').css("display", "");
            $('[data-fieldname="basic_rate"]').css("display", "");
        }
        frm.trigger("update_item");

    },
    items_remove: function (frm) {
        frm.trigger("update_item");
    },

})


frappe.ui.form.on('Storage details', {
    // Storage_details_add:function(frm,cdt,cdn){
    //     var storage = locals[cdt][cdn]
    //     frappe.model.set_value(cdt, cdn, "sub_customer", cur_frm.doc.sub_customer)

    // },
    bin_location: function (frm, cdt, cdn) {
        var storage = locals[cdt][cdn]
        if (storage.bin_location) {

            frappe.call({
                method: "get_pallet",
                doc: cur_frm.doc,
                args: { "bin": storage.bin_location,"expiry": storage.expiry },
                callback: function (r) {
                    if (r.message) {
                        console.log(r.message)
                        storage.pallet = r.message
                        cur_frm.refresh()
                    }
                }
            });
        }
    },

    batch_no: function (frm, cdt, cdn) {
        var storage = locals[cdt][cdn]
        if (!storage.item_code) {
            frappe.throw("First add item in row " + storage.idx)
        }
        batch = storage.item_code
        // if (storage.batch_no) {
        //     frappe.db.get_doc('Batch', storage.batch_no)
        //         .then(r => {
        //             console.log(r)

        //             if (storage.display_stored_in == "CBM") {
        //                 var area = parseFloat(storage.length) * parseFloat(storage.width) * parseFloat(storage.height)
        //                 frappe.model.set_value(cdt, cdn, "area_used", area)
        //             }
        //             if (storage.display_stored_in == "Pallet") {
        //                 var area = parseFloat(storage.length) * parseFloat(storage.width)
        //                 frappe.model.set_value(cdt, cdn, "area_used", area)
        //             }

        //         })
        // }
    },
    item_code: function (frm, cdt, cdn) {
        var storage = locals[cdt][cdn]
        batch = storage.item_code

    },
    display_stored_in: function (frm, cdt, cdn) {
        var child = locals[cdt][cdn]
        if (child.display_stored_in == "Pallet") {
            // grid_row.storage_details[0].df.read_only = 1
            $('[data-fieldname="height"]').attr('disabled', 'disabled');

            cur_frm.doc.storage_details[child.idx - 1].height = 0

        } else {

            cur_frm.doc.storage_details[child.idx - 1].height = undefined
            $('[data-fieldname="height"]').removeAttr("disabled");

        }

    },

    length: function (frm, cdt, cdn) {
        var storage = locals[cdt][cdn]
        frm.trigger("cal_areaused")
        if (storage.length < 0 || storage.length == 0) {
            storage.length = 0
            frappe.throw("length can't be nagetive or zero")
        }

        if (storage.width && storage.height && storage.length && storage.height) {
            var area = parseFloat(storage.length) * parseFloat(storage.width) * parseFloat(storage.height) * parseFloat(storage.stored_qty)
            frappe.model.set_value(cdt, cdn, "area_used", area)
        }
        if (storage.width && storage.length && !storage.height) {
            var area = parseFloat(storage.length) * parseFloat(storage.width) * parseFloat(storage.stored_qty)
            frappe.model.set_value(cdt, cdn, "area_used", area)
        }

    },
    width: function (frm, cdt, cdn) {
        frm.trigger("cal_areaused")
        var storage = locals[cdt][cdn]
        if (storage.width < 0 || storage.width == 0) {
            storage.width = 0
            frappe.throw("width can't be nagetive or zero")
        }
        if (storage.width && storage.height && storage.length && storage.height) {
            var area = parseFloat(storage.length) * parseFloat(storage.width) * parseFloat(storage.height) * parseFloat(storage.stored_qty)
            frappe.model.set_value(cdt, cdn, "area_used", area)
        }
        if (storage.width && storage.length && !storage.height) {
            var area = parseFloat(storage.length) * parseFloat(storage.width) * parseFloat(storage.stored_qty)
            frappe.model.set_value(cdt, cdn, "area_used", area)
        }

    },
    height: function (frm, cdt, cdn) {
        frm.trigger("cal_areaused")
        var storage = locals[cdt][cdn]
        if (storage.height < 0 || storage.width == 0) {
            storage.height = 0
            frappe.throw("height can't be nagetive or zero")
        }

        if (storage.width && storage.height && storage.length && storage.height) {
            if (storage.width == 0) {
                storage.height = 0
                frappe.throw("height can't be nagetive or zero")
            }
            var area = parseFloat(storage.length) * parseFloat(storage.width) * parseFloat(storage.height) * parseFloat(storage.stored_qty)
            frappe.model.set_value(cdt, cdn, "area_used", area)
        }
        if (storage.width && storage.length && !storage.height) {
            var area = parseFloat(storage.length) * parseFloat(storage.width) * parseFloat(storage.stored_qty)
            frappe.model.set_value(cdt, cdn, "area_used", area)
        }

    },
    stored_qty: function (frm, cdt, cdn) {
        var storage = locals[cdt][cdn]
        if (storage.width && storage.height && storage.length && storage.height) {
            var area = parseFloat(storage.length) * parseFloat(storage.width) * parseFloat(storage.height) * parseFloat(storage.stored_qty)
            frappe.model.set_value(cdt, cdn, "area_used", area)
        }
        if (storage.width && storage.length && !storage.height) {
            var area = parseFloat(storage.length) * parseFloat(storage.width) * parseFloat(storage.stored_qty)
            frappe.model.set_value(cdt, cdn, "area_used", area)
        }

    },







    storage_details_add: function (frm, cdt, cdn) {
        frappe.model.set_value(cdt, cdn, "t_ware_house", cur_frm.doc.to_warehouse)
        frappe.model.set_value(cdt, cdn, "sub_customer", cur_frm.doc.sub_customer)
        var child = locals[cdt][cdn];
        // if(!cur_frm.doc.material_item){
        //     frm.trigger("stock_item")
        // }
        // if (cur_frm.doc.customer_nm) {
        //     frappe.db.get_doc('Customer', cur_frm.doc.customer_nm)
        //         .then(r => {
        //             if (r) {
        //                 var sub = [" ",];
        //                 var sub_customer = r.sub_customer
        //                 for (var i = 0; i < sub_customer.length; i++) {
        //                     sub.push(sub_customer[i].sub_customer_full_name)
        //                 }
        //                 frm.fields_dict.storage_details.grid.update_docfield_property('sub_customer', 'options', sub)
        //             }
        //         })
        //     frappe.model.set_value(cdt, cdn, "sub_customer", cur_frm.doc.sub_customer)
        // }

        // if (cur_frm.doc.stock_entry_type == 'Material Receipt') {
        //     var itms = cur_frm.doc.items
        //     for (var i = 0; i < itms.length; i++) {
        //         item_list.push(itms[i].item_code)
        //     }
        //     // item_list.push(child.item_code)
        // }

    },



})




frappe.ui.form.on("Stock Entry Detail", "form_render", function (frm, cdt, cdn) {
    var child = locals[cdt][cdn];
    if (cur_frm.doc.stock_entry_type == 'Material Receipt') {
        cur_frm.fields_dict.items.grid.update_docfield_property("basic_rate", "hidden", 1);
        cur_frm.fields_dict.items.grid.update_docfield_property("basic_amount", "hidden", 1);
        cur_frm.fields_dict.items.grid.update_docfield_property("amount", "hidden", 1);
        cur_frm.fields_dict.items.grid.update_docfield_property("additional_cost", "hidden", 1);
        cur_frm.fields_dict.items.grid.update_docfield_property("valuation_rate", "hidden", 1);
        cur_frm.fields_dict.items.grid.update_docfield_property("accounting", "hidden", 1);

        frappe.call({
            method: "semah.custom_script.stock_entry.stock_entry.get_item_uom",
            async: false,
            args: {
                'item_code': child.item_code
            },
            callback: function (r) {
                console.log(r.message)
                uomlist = r.message

            }
        })
        cur_frm.refresh_fields("storage_details")
    }
    // cur_frm.refresh_fields('items')



});



frappe.ui.form.on("Storage details", "form_render", function (frm, cdt, cdn) {
    var storage = locals[cdt][cdn];

    // if (storage.display_stored_in == "CBM") {
    //     var area = parseFloat(storage.length) * parseFloat(storage.width) * parseFloat(storage.height)
    //     frappe.model.set_value(cdt, cdn, "area_used", area)
    // }
    // if (storage.display_stored_in == "Pallet") {
    //     var area = parseFloat(storage.length) * parseFloat(storage.width)
    //     frappe.model.set_value(cdt, cdn, "area_used", area)
    // }

});

const stock_extend =
    // select_batch_and_serial_no
    (frm, item) => {
        let get_warehouse_type_and_name = (item) => {
            let value = '';
            if (frm.fields_dict.from_warehouse.disp_status === "Write") {
                value = cstr(item.s_warehouse) || '';
                return {
                    type: 'Source Warehouse',
                    name: value
                };
            } else {
                value = cstr(item.t_warehouse) || '';
                return {
                    type: 'Target Warehouse',
                    name: value
                };
            }
        }

        if (item && !item.has_serial_no && !item.has_batch_no) return;
        if (frm.doc.purpose === 'Material Receipt') return;

        frappe.require("assets/semah/js/utlis/serial_no_batch_selector.js", function () {
            new erpnext.SerialNoBatchSelector({
                frm: frm,
                item: item,
                warehouse_details: get_warehouse_type_and_name(item),
            });
        });
    }


// })

$.extend(cur_frm.cscript,
    erpnext.stock.select_batch_and_serial_no = stock_extend,

);


//on refresh 
// frappe.ui.form.on("Stock Entry", "refresh", function(frm, cdt, cdn) {
//     var total_qty = 0;
//     $.each(frm.doc.items || [], function(i, d) {
//         total_qty += flt(d.qty);
//     });
//     console.log("Total Quantity: ", total_qty);
//     frm.set_value("total_items", total_qty);
// });
//  for real time 
frappe.ui.form.on('Stock Entry Detail', {
    qty: function (frm, cdt, cdn) {
        calculateTotalQuantity(frm);
    },
    items_remove: function (frm, cdt, cdn) {
        calculateTotalQuantity(frm);
    },
});

function calculateTotalQuantity(frm) {
    var total_qty = 0;
    $.each(frm.doc.items || [], function (i, d) {
        total_qty += flt(d.qty);
    });
    frm.set_value('total_items', total_qty);
}
frappe.ui.form.on('Storage details', {
    refresh: function (frm) {
        calculateTotalStoredQuantity(frm);
    },
    stored_qty: function (frm, cdt, cdn) {
        calculateTotalStoredQuantity(frm);
    },
    storage_details_remove: function (frm, cdt, cdn) {
        calculateTotalStoredQuantity(frm);
    },

});

function calculateTotalStoredQuantity(frm) {
    var total_stored_qty = 0;
    $.each(frm.doc.storage_details || [], function (i, d) {
        total_stored_qty += flt(d.stored_qty);
    });
    console.log(total_stored_qty);
    frm.set_value('total_storage_quantity', total_stored_qty);
}


function calculateTotalStoredQuantity2() {
    // Assuming that 'cur_frm' or the necessary data is accessible globally or within this scope
    var total_stored_qty = 0;

    $.each(cur_frm.doc.storage_details || [], function (i, d) {
        total_stored_qty += flt(d.stored_qty);
    });

    // Assuming 'cur_frm' is accessible and you want to set the value in the current form
    cur_frm.set_value('total_storage_quantity', total_stored_qty);
}