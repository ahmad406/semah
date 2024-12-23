frappe.listview_settings['Item'] = {
    refresh: function (listview) {
        $('[data-fieldname="sub_customer"]').css("display", "");

   
//         var df = {
   
//             fieldname: "sub_customer",
   
//             label:"Sub customer",
   
//             fieldtype: "Data",
   
//             //options:"Item",
   
//             onchange: function(){
   
//                 listview.start = 0;
   
//                 listview.refresh();
   
//                 listview.on_filter_change();
   
//             },
   
//         }
   
//         listview.page.add_field(df);
   
    }
   };