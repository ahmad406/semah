// Copyright (c) 2025, Dconnex and contributors
// For license information, please see license.txt

let scannerDialog = null;
let html5QrCode = null;

frappe.ui.form.on('Stock Bin and Pallet Scanner', {
    onload(frm) {
        if (typeof Html5Qrcode === "undefined") {
            const script = document.createElement("script");
            script.src = "https://cdnjs.cloudflare.com/ajax/libs/html5-qrcode/2.3.8/html5-qrcode.min.js"; // v2.3.8
            script.onerror = () => frappe.msgprint('Failed to load scanner library. Please check your internet connection.');
            document.head.appendChild(script);
            frm.disable_save();
        } 
      
    },
    refresh:function(frm){
        frm.disable_save();
    },

    scan: function(frm) {
        showBarcodeScanner(frm, 'source_bin');
    },
    source_bin:function(frm){
        frm.trigger("show_bin_details")

    },
    show_bin_details:function(frm){
        frappe.call({
            method: "show_bin_info",
			doc: cur_frm.doc,
            callback: function(r) {
                if (r.message) {
                    
                    if (r.message=="No Show"){
                        frm.set_df_property('show_detaiil', 'options', r.message); 
                    }
                    else{
                        frm.set_df_property('show_detaiil', 'options', r.message); 
                    }
                 
                   cur_frm.refresh()
                }
            }
        });

    }
});

// function setupClick(frm) {
//     const field = frm.fields_dict['source_bin'];
//     if (field?.input) {
//         field.input.onclick = function () {
//             showBarcodeScanner(frm, 'source_bin');
//         };
//     }
// }

async function cleanupScanner() {
    if (html5QrCode) {
        try {
            await html5QrCode.stop();
            await html5QrCode.clear();
            html5QrCode = null;
        } catch (e) {
            console.warn('Error cleaning up scanner:', e);
        }
    }
    // Clear container contents
    const container = document.getElementById('qr-reader-container');
    if (container) {
        container.innerHTML = '';
    }
}

async function waitForElement(elementId, timeout = 5000) {
    const startTime = Date.now();
    while (Date.now() - startTime < timeout) {
        const element = document.getElementById(elementId);
        if (element) {
            return element;
        }
        await new Promise(resolve => setTimeout(resolve, 50));
    }
    console.warn(`Element ${elementId} not found within ${timeout}ms`);
    return null;
}

async function showBarcodeScanner(frm, fieldname) {
    await cleanupScanner();

    if (!scannerDialog) {
        scannerDialog = new frappe.ui.Dialog({
            title: 'Scan Barcode',
            // size: 'extra-large',
            fields: [
                {
                    fieldname: 'scanner_html',
                    fieldtype: 'HTML',
                    options: `
                    <div id="qr-reader-container" style="width:100%; max-width:400px; aspect-ratio: 1 / 1; margin: auto;">
                        <div id="qr-reader" style="width:100%; height:100%;"></div>
                    </div>`
                    
                }
            ],
            primary_action_label: 'Close',
            primary_action() {
                scannerDialog.hide();
            },
            onhide: async function () {
                await cleanupScanner();
            }
        });
    }

    scannerDialog.show();

    const container = await waitForElement('qr-reader-container');
    if (!container) {
        frappe.msgprint('Failed to find scanner container. Please try again.');
        scannerDialog.hide();
        return;
    }

    container.innerHTML = '<div id="qr-reader" style="width:100%; height:100%;"></div>';
    const qrReader = document.getElementById('qr-reader');
    if (!qrReader) {
        frappe.msgprint('Failed to initialize scanner element. Please try again.');
        scannerDialog.hide();
        return;
    }

    try {
        html5QrCode = new Html5Qrcode("qr-reader");
        await html5QrCode.start(
            { facingMode: "environment" },
            {
                fps: 10,
                qrbox: { width: 250, height: 250 }
            },
            async (qrCodeMessage) => {
                frm.set_value(fieldname, qrCodeMessage);
                await cleanupScanner();
                scannerDialog.hide();
            },
            (errorMessage) => {
                console.log('Scan error:', errorMessage); 
            }
        );
    } catch (err) {
        console.error('Scanner initialization error:', err);
        frappe.msgprint('Failed to start scanner: ' + err.message);
        await cleanupScanner();
        scannerDialog.hide();
    }
}