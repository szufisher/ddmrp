# Copyright (c) 2013, Fisher and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt
from ddmrp.ddmrp.utils import *
import operator

def execute(filters=None):	
	data = []	
	columns = get_columns( filters.get('summary_level') )
	get_data(data , filters)
	return columns, data

def get_columns(summary_level):
	if not summary_level:
		return [
			{
				"label": _("Date"),
				"fieldtype": "Date",
				"fieldname": "date",			
				"width": 80
			},
			{
				"label": _("MRP Element"),
				"fieldtype": "Link",
				"fieldname": "ref_doctype",
				"options": "DocType",			
				"width": 120
			},
			{
				"label": _("MRP Element Data"),
				"fieldtype": "Dynamic Link",
				"fieldname": "ref_docname",
				"options": "ref_doctype",
				"width": 150
			},
			{
				"label": _("Receipts/Requirements"),
				"fieldtype": "Float",
				"fieldname": "qty",
				"width": 150
			},
			{
				"label": _("Available Qty"),
				"fieldtype": "Float",
				"fieldname": "available_qty",
				"width": 120
			},
			{
				"label": _("Warehouse"),
				"fieldtype": "Link",
				"fieldname": "warehouse",
				"options":"Warehouse",
				"width": 120
			}		
		]
	else:
		return [
		{
			"label": _("%s" % summary_level),
			"fieldtype": "Data",
			"fieldname": "period",			
			"width": 80
		},				
		{
			"label": _("Requirements"),
			"fieldtype": "Float",
			"fieldname": "requirement_qty",
			"width": 150
		},
		{
			"label": _("Receipts"),
			"fieldtype": "Float",
			"fieldname": "receive_qty",
			"width": 150
		},
		{
			"label": _("Available Qty"),
			"fieldtype": "Float",
			"fieldname": "available_qty",
			"width": 120
		}]

def get_data(data, filters):
	def get_period(in_date, summary_level):
		if summary_level == 'Date':
			res = in_date
		elif summary_level == 'Week':
			week_tuple = in_date.isocalendar()
			res = 'W %s/%s' % (week_tuple[1], week_tuple[0])
		else:
			res = in_date.strftime("M %m/%Y")
		return res	
		
	plant = filters.plant
	item_code = filters.item_code
	warehouses = get_warehouses(plant)
	sap_interface = frappe.db.get_value('DDMRP Settings', None, 'sap_interface_active')
	summary_level = filters.get('summary_level')

	supply_list = get_supply(warehouses, plant=plant, sap_interface= sap_interface, item_code = item_code, with_order_detail = True)
	demand_list = get_demand(warehouses, plant=plant, sap_interface= sap_interface, item_code = item_code, with_order_detail = True)
	on_hand = get_on_hand(warehouses, item_code)
	#tag suppy as 1, demand as 2 for sorting and negate the qty later on
	combine_list = [list(s)+[1] for s in supply_list] + [list(d)+[2] for d in demand_list]
	#sort by date, then supply:1 or demand:2
	combine_list = sorted(combine_list, key=operator.itemgetter(0, -1))	
	open_on_hand = flt(on_hand[0][1]) if on_hand else 0	
	if not summary_level:
		data.append([today(),'Stock','', open_on_hand, open_on_hand])
	else:
		data.append(['Stock','', '', open_on_hand])	
	running_availability = open_on_hand
	requirement_qty = receive_qty = 0
	row_cnt = len(combine_list)
	for idx, d in enumerate(combine_list):
		# negate demand qty 
		qty = flt(d[-2] * -1 if d[-1] == 2 else d[-2])
		if summary_level:
			period = get_period(d[0], summary_level)
			if qty > 0:
				requirement_qty += qty
			else:
				receive_qty += qty
			# addup and output per period change	
			if (idx == row_cnt - 1 or period != get_period(combine_list[idx+1][0], summary_level)) :
				running_availability += requirement_qty + receive_qty
				data.append([period, receive_qty, requirement_qty, running_availability])
				requirement_qty = receive_qty = 0
		else:
			running_availability += qty
			# date, ref doctype, ref docname, d[3] warehouse			
			data.append(d[:3] + [qty, running_availability,d[3]] )

	return data
