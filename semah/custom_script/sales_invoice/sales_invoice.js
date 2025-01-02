frappe.ui.form.on("Sales Invoice", {
    onload: function (frm) {
        if (frm.doc.return_against && cur_frm.is_new()) {
            cur_frm.set_value("naming_series", "ACC-SINV-RET-.YYYY.-")
        }
    }

})