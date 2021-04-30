// Copyright (c) 2016, Fisher and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Work Order On-Hand Status"] = {
	"filters": [
		{
			label: __("Company"),
			fieldname: "company",
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1
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
			fieldname: "fiscal_year",
			label: __("Fiscal Year"),
			fieldtype: "Link",
			options: "Fiscal Year",
			default: frappe.defaults.get_user_default("fiscal_year"),
			reqd: 1,
			on_change: function(query_report) {
				var fiscal_year = query_report.get_values().fiscal_year;
				if (!fiscal_year) {
					return;
				}
				frappe.model.with_doc("Fiscal Year", fiscal_year, function(r) {
					var fy = frappe.model.get_doc("Fiscal Year", fiscal_year);
					frappe.query_report.set_filter_value({
						from_date: fy.year_start_date,
						to_date: fy.year_end_date
					});
				});
			}
		},
		{
			label: __("From Posting Date"),
			fieldname:"from_date",
			fieldtype: "Date",
			default: frappe.defaults.get_user_default("year_start_date"),
			reqd: 1
		},
		{
			label: __("To Posting Date"),
			fieldname:"to_date",
			fieldtype: "Date",
			default: frappe.defaults.get_user_default("year_end_date"),
			reqd: 1,
		},
		{
			label: __("Status"),
			fieldname: "status",
			fieldtype: "MultiSelectList",
			options: ["Not Started", "In Process"]
		},
		{
			label: __("Sales Orders"),
			fieldname: "sales_order",
			fieldtype: "MultiSelectList",
			get_data: function(txt) {
				return frappe.db.get_link_options('Sales Order', txt);
			}
		},
		{
			label: __("Production Item"),
			fieldname: "production_item",
			fieldtype: "MultiSelectList",
			get_data: function(txt) {
				return frappe.db.get_link_options('Item', txt);
			}
		},
		{
			label: __("Age"),
			fieldname:"age",
			fieldtype: "Int",
			default: "0"
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