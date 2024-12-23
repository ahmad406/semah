frappe.ui.form.on("Batch", {

onload:function(frm){
    cur_frm.set_df_property('expiry_date', 'reqd', 1)
}



})