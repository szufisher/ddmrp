# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import date_diff, today, getdate, flt
from frappe import _
from erpnext.stock.report.stock_analytics.stock_analytics import (get_period_date_ranges, get_period)

def execute(filters=None):
	columns, data = [], []

	validate_filters(filters)

	if not filters.get("age"):
		filters["age"] = 0

	columns = get_columns(filters)
	conditions = get_conditions(filters)

	data = get_data(conditions, filters)		
	return columns, data, None, None

def validate_filters(filters):
	from_date, to_date = filters.get("from_date"), filters.get("to_date")

	if not from_date and to_date:
		frappe.throw(_("From and To Dates are required."))
	elif date_diff(to_date, from_date) < 0:
		frappe.throw(_("To Date cannot be before From Date."))

def get_conditions(filters):
	conditions = ""
	if filters.get("from_date"):
		conditions += " and planned_start_date >= %(from_date)s"
		
	if filters.get("to_date"):
		conditions += " and planned_start_date <=  %(to_date)s"

	if filters.get("company"):
		conditions += " and wo.company = %(company)s"

	if filters.get("sales_order"):
		conditions += " and wo.sales_order in %(sales_order)s"

	if filters.get("status"):
		conditions += " and wo.status in %(status)s"

	if filters.get("production_item"):
		conditions += " and wo.production_item in %(production_item)s"

	if filters.get("plant"):
		conditions += " and sb.plant = %(plant)s"

	if filters.get("execution_priority_level"):
		conditions += " and sb.execution_priority_level in %(execution_priority_level)s"

	return conditions

def get_data(conditions, filters):
	data = frappe.db.sql("""
		SELECT	
			sb.execution_priority_level,sb.on_hand_percent,
			wo.name, wo.status, wo.sales_order, wo.production_item, wo.qty, wo.produced_qty,
			wo.planned_start_date, wo.planned_end_date, wo.actual_start_date, wo.actual_end_date, 
			wo.lead_time					
		FROM
			`tabWork Order` wo		
		JOIN
			`tabWarehouse` w 
			ON w.name = wo.fg_warehouse		
		LEFT JOIN `tabStock Buffer` sb
			ON w.plant = sb.plant and wo.production_item = sb.item_code
		WHERE			
			wo.status not in ('Stopped', 'Closed','Cancelled')
			and wo.docstatus = 1
			{0}		
		ORDER BY planned_start_date ASC
	""".format(conditions), filters, as_dict=1)

	res = []
	for d in data:
		start_date = d.actual_start_date or d.planned_start_date
		d.age = 0

		if d.status != 'Completed':
			d.age = date_diff(today(), start_date)

		if filters.get("age") <= d.age:
			res.append(d)

	return res

def get_columns(filters):
	columns = [
		{
			"label":_("On-Hand Priority"),
			"fieldname": "execution_priority_level",
			"fieldtype": "Data",
			"width": 110
		},
		{
			"label":_("On-Hand %"),
			"fieldname": "on-hand_percent",
			"fieldtype": "Percent",
			"width": 80
		},
		{
			"label": _("Order Number"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Work Order",
			"width": 130
		},
	]

	if not filters.get("status"):
		columns.append(
			{
				"label": _("Status"),
				"fieldname": "status",
				"width": 100
			},
		)

	columns.extend([
		{
			"label": _("Production Item"),
			"fieldname": "production_item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 130
		},
		{
			"label": _("Produce Qty"),
			"fieldname": "qty",
			"fieldtype": "Float",
			"width": 110
		},
		{
			"label": _("Produced Qty"),
			"fieldname": "produced_qty",
			"fieldtype": "Float",
			"width": 110
		},
		{
			"label": _("Sales Order"),
			"fieldname": "sales_order",
			"fieldtype": "Link",
			"options": "Sales Order",
			"width": 90
		},
		{
			"label": _("Planned Start Date"),
			"fieldname": "planned_start_date",
			"fieldtype": "Date",
			"width": 150
		},
		{
			"label": _("Planned End Date"),
			"fieldname": "planned_end_date",
			"fieldtype": "Date",
			"width": 150
		}
	])

	if filters.get("status") != 'Not Started':
		columns.extend([
			{
				"label": _("Actual Start Date"),
				"fieldname": "actual_start_date",
				"fieldtype": "Date",
				"width": 100
			},
			{
				"label": _("Actual End Date"),
				"fieldname": "actual_end_date",
				"fieldtype": "Date",
				"width": 100
			},
			{
				"label": _("Age"),
				"fieldname": "age",
				"fieldtype": "Float",
				"width": 110
			},
		])

	if filters.get("status") == 'Completed':
		columns.extend([
			{
				"label": _("Lead Time (in mins)"),
				"fieldname": "lead_time",
				"fieldtype": "Float",
				"width": 110
			},
		])

	return columns