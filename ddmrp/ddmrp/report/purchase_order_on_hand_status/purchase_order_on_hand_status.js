// Copyright (c) 2016, Fisher and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Purchase Order On-Hand Status"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Company",
			"reqd": 1,
			"default": frappe.defaults.get_default("company")
		},
		{
			"fieldname": "plant",
			"label": __("Plant"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Plant",						
		},
		{
			"fieldname": "execution_priority_level",
			"label": __("On-Hand Priority"),
			"fieldtype": "MultiSelectList",
			"width": "80",
			get_data: function(txt) {
				let status = ['1_Red','2_Yellow','3_Green']
				let options = []
				for (let option of status){
					options.push({
						"value": option,
						"description": ""
					})
				}
				return options
			}
			//"default": 0
		},
		{
			"fieldname":"from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"width": "80",
			"reqd": 1,
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			"fieldname":"to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"width": "80",
			"reqd": 1,
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "purchase_order",
			"label": __("Purchase Order"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Purchase Order",
			"get_query": () =>{
				return {
					filters: { "docstatus": 1 }
				}
			}
		},
		{
			"fieldname": "status",
			"label": __("Status"),
			"fieldtype": "MultiSelectList",
			"width": "80",
			get_data: function(txt) {
				let status = ["To Bill", "To Receive", "To Receive and Bill", "Completed"]
				let options = []
				for (let option of status){
					options.push({
						"value": option,
						"description": ""
					})
				}
				return options
			}
		},		
	],

	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		let format_fields = ["execution_priority_level", "on-hand_percent"];
		if (in_list(format_fields, column.fieldname) && data && data["execution_priority_level"]) {
			var color_field = data["execution_priority_level"];						
			let color = color_field && color_field.split("_")[1].toLowerCase() || undefined;			
			if (color){
				value =`<div style='margin:0px;padding-left:5px;background-color:${color}!important;'>${value}</div>`            
			}			
		}
		return value;
	}
};
