frappe.after_ajax(() => {
    const interval = setInterval(() => {
        document.querySelectorAll('button').forEach(btn => {
            if (btn.textContent.trim() === 'PDF') {
                btn.remove();
            }
        });
    }, 500);

    // Stop checking after 5 seconds
    setTimeout(() => clearInterval(interval), 5000);
});


