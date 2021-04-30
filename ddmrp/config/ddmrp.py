from __future__ import unicode_literals
from frappe import _
import frappe


def get_data():
	config = [
		{
			"label": _("Strategic Inventory Positioning"),
			"items": [
				{
					"type": "doctype",
					"name": "Stock Buffer",
					"description": "Stock Buffer",				
				}
            ]
        },
        {
			"label": _("Buffer Profiles and Levels"),
			"items": [
				{
					"type": "doctype",
					"name": "Lead Time Factor",					
				},
                {
					"type": "doctype",
					"name": "Variability Factor",					
				},
                {
					"type": "doctype",
					"name": "Stock Profile",					
				},
                {
					"type": "doctype",
					"name": "Calculation Method",					
				},
                {
					"type": "doctype",
					"name": "Demand Estimate",					
				},
                {
					"type": "doctype",
					"name": "Stock Buffer",					
				},
            ]
        },
        {
			"label": _("Dynamic Adjustments"),
			"items": [
				{
					"type": "doctype",
					"name": "Date Range Type",					
				},
                {
					"type": "doctype",
					"name": "Date Range",					
				},
                {
					"type": "doctype",
					"name": "DDMRP Adjustment",					
				},
                {
					"type": "doctype",
					"name": "DDMRP Adjustment Demand",					
				},
            ]
        },
        {
			"label": _("Demand Driven Planning"),
			"items": [
				{
					"type": "doctype",
					"name": "Multi Level MRP",					
				},
                {
					"type": "doctype",
					"name": "MRP Move",					
				},
                {
					"type": "doctype",
					"name": "Planned Order",					
				},
                {
					"type": "doctype",
					"name": "MRP Inventory",					
				},
                {
					"type": "doctype",
					"name": "Stock Buffer",					
				},
            ]
        },
        {
			"label": _("Visible and Collaborative Execution"),
			"items": [
				{
					"type": "report",
					"name": "stock_buffer_on_hand_list",					
				}
            ]
        },
    ]
	return config	    