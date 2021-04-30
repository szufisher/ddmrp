// Copyright (c) 2016, Fisher and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Stock Requirements List"] = {
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
			//"depends_on":"plant",
			"reqd": 1,
            "options":"Item",
			"width": "80",			
		},
		{
			"fieldname": "summary_level",
			"label": __("Summary Level"),
			"fieldtype": "Select",
			"options":['','Date','Week','Month'],
			"width": "80",						
		},
        // {
		// 	"fieldname":"planning_priority_level",
		// 	"label": __("Plan Alert Level"),
        //     "fieldtype": "Select",
        //     "options":["1_Red",'2_Yellow','3_Green'],
		// 	"width": "80",			
        // },
        // {
		// 	"fieldname":'execution_priority_level',
		// 	"label": __("On Hand Alert Level"),
        //     "fieldtype": "Select",
        //     "options":["1_Red",'2_Yellow','3_Green'],
		// 	"width": "80",			
		// },
		// {
		// 	"fieldname":'filter',
		// 	"label": __("Filter"),
        //     "fieldtype": "Select",
        //     "options":["Only Supply",'Only Demand and Stock'],
		// 	"width": "80",			
		// },
		// {
		// 	"fieldname":'show_parnter',
		// 	"label": __("Show Supplier/Customer"),
        //     "fieldtype": "Check",            
		// 	"width": "40",			
		// },					
	],
};
