// Copyright (c) 2016, Fisher and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Multilevel BOM"] = {
    "filters": [
        {
            "fieldname": "plant",
            "label": __("Plant"),
            "fieldtype": "Link",
            "reqd": 1,
            "width": "80",
            "options": "Plant",
            
        },
        {
            "fieldname":"item_code",
            "label": __("Material"),
            "fieldtype": "Link",
            "depends_on":"plant",
            "reqd": 1,
            "options":"Item",
            "width": "80",            
        },
        {
            "fieldname": "required_qty",
            "label": __("Required Qty"),
            "fieldtype": "Float",
            "default": 1            
        },
        {
            "fieldname": "show_buffer_info",
            "label": __("Show Buffer Info"),
            "fieldtype": "Check",
            "default": 1            
        }
    ],
    "formatter": function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        let buffered = data['buffered'];
        if (buffered && column.fieldname==="buffered"){
            value =`<img src="/assets/ddmrp/images/icon_buffer.PNG">`;
        }
		return value;
    }    
};
