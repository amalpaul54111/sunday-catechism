// Copyright (c) 2026, amal@zimplify.tech and contributors
// For license information, please see license.txt

frappe.ui.form.on('Your DocType Name', {
    validate: function(frm) {
        // Fetch values and handle nulls
        let first = frm.doc.first_name ? frm.doc.first_name.trim() : '';
        let middle = frm.doc.middle_name ? frm.doc.middle_name.trim() : '';
        let last = frm.doc.last_name ? frm.doc.last_name.trim() : '';
        
        // Build the array, filter out empty strings, and join
        let full_name = [first, middle, last].filter(Boolean).join(' ');
        
        frm.set_value('full_name', full_name);
    }
});