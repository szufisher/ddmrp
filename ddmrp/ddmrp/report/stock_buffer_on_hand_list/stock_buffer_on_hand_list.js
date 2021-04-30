frappe.query_reports["stock_buffer_on_hand_list"] = {
	"filters": [
		{
			"fieldname": "Plant",
			"label": __("Plant"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Plant",
			
		},
		{
			"fieldname":"item_code",
			"label": __("Material"),
            "fieldtype": "Link",
            "options":"Item",
			"width": "80",			
        },
        {
			"fieldname":"planning_priority_level",
			"label": __("Plan Alert Level"),
            "fieldtype": "Select",
            "options":["1_Red",'2_Yellow','3_Green'],
			"width": "80",			
        },
        {
			"fieldname":'execution_priority_level',
			"label": __("On Hand Alert Level"),
            "fieldtype": "Select",
            "options":["1_Red",'2_Yellow','3_Green'],
			"width": "80",			
		},		
	],

	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);     
        let color;
        let pl = data['Plan Level'];
        color = pl && pl.split("_")[1].toLowerCase() || undefined;
        if (color && column.fieldname==="Available"){
            //value = "<span style='color:" + color + "'>" + value + "</span>";
            value =`<div style='margin:0px;padding-left:5px;background-color:${color}!important;'>${value}</div>`
        }
        let el = data['Execution Level'];
        color = el && el.split("_")[1].toLowerCase() || undefined;
        if (color && column.fieldname==="On Hand"){
            value =`<p style='margin:0px;padding-left:5px;background-color:${color}!important;'>${value}</p>`
            //value = "<span style='color:black; background:" + color + "'>" + value + "</span>";
        }		
		return value;
    }    
};