# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import copy
from frappe import _
from frappe.utils import flt, date_diff, getdate

def execute(filters=None):
	if not filters:
		return [], []

	validate_filters(filters)

	columns = get_columns(filters)
	conditions = get_conditions(filters)

	data = get_data(conditions, filters)

	if not data:
		return [], [], None, []

	#data, chart_data = prepare_data(data, filters)

	return columns, data, None, None

def validate_filters(filters):
	from_date, to_date = filters.get("from_date"), filters.get("to_date")

	if not from_date and to_date:
		frappe.throw(_("From and To Dates are required."))
	elif date_diff(to_date, from_date) < 0:
		frappe.throw(_("To Date cannot be before From Date."))

def get_conditions(filters):
	conditions = ""
	if filters.get("from_date") and filters.get("to_date"):
		conditions += " and po.transaction_date between %(from_date)s and %(to_date)s"

	if filters.get("company"):
		conditions += " and po.company = %(company)s"

	if filters.get("purchase_order"):
		conditions += " and po.name = %(purchase_order)s"

	if filters.get("status"):
		conditions += " and po.status in %(status)s"

	if filters.get("plant"):
		conditions += " and sb.plant = %(plant)s"

	if filters.get("execution_priority_level"):
		conditions += " and sb.execution_priority_level in %(execution_priority_level)s"

	return conditions

def get_data(conditions, filters):
	data = frappe.db.sql("""
		SELECT			
			sb.execution_priority_level,sb.on_hand_percent,
			po.transaction_date as date,
			poi.schedule_date as required_date,
			po.name as purchase_order,
			po.status, po.supplier, poi.item_code,
			poi.qty, poi.received_qty,
			(poi.qty - poi.received_qty) AS pending_qty,
			IFNULL(pii.qty, 0) as billed_qty,
			poi.base_amount as amount,
			(poi.received_qty * poi.base_rate) as received_qty_amount,
			(poi.billed_amt * IFNULL(po.conversion_rate, 1)) as billed_amount,
			(poi.base_amount - (poi.billed_amt * IFNULL(po.conversion_rate, 1))) as pending_amount,
			poi.warehouse as warehouse,
			po.company, poi.name
		FROM
			`tabPurchase Order` po
		INNER JOIN
			`tabPurchase Order Item` poi
			ON poi.parent = po.name 
		JOIN
			`tabWarehouse` w 
			ON w.name = poi.warehouse
		LEFT JOIN `tabPurchase Invoice Item` pii
			ON pii.po_detail = poi.name
		LEFT JOIN `tabStock Buffer` sb
			ON w.plant = sb.plant and poi.item_code = sb.item_code
		WHERE			
			po.status not in ('Completed', 'Stopped', 'Closed','Cancelled')
			and po.docstatus = 1
			{0}
		GROUP BY poi.name
		ORDER BY po.transaction_date ASC
	""".format(conditions), filters, as_dict=1)

	return data

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
			"label":_("Date"),
			"fieldname": "date",
			"fieldtype": "Date",
			"width": 90
		},
		{
			"label":_("Required By"),
			"fieldname": "required_date",
			"fieldtype": "Date",
			"width": 90
		},
		{
			"label": _("Purchase Order"),
			"fieldname": "purchase_order",
			"fieldtype": "Link",
			"options": "Purchase Order",
			"width": 160
		},
		{
			"label":_("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 130
		},
		{
			"label": _("Supplier"),
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 130
		}]

	if not filters.get("group_by_po"):
		columns.append({
			"label":_("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 100
		})

	columns.extend([
		{
			"label": _("Qty"),
			"fieldname": "qty",
			"fieldtype": "Float",
			"width": 120,
			"convertible": "qty"
		},
		{
			"label": _("Received Qty"),
			"fieldname": "received_qty",
			"fieldtype": "Float",
			"width": 120,
			"convertible": "qty"
		},
		{
			"label": _("Pending Qty"),
			"fieldname": "pending_qty",
			"fieldtype": "Float",
			"width": 80,
			"convertible": "qty"
		},
		{
			"label": _("Billed Qty"),
			"fieldname": "billed_qty",
			"fieldtype": "Float",
			"width": 80,
			"convertible": "qty"
		},
		{
			"label": _("Qty to Bill"),
			"fieldname": "qty_to_bill",
			"fieldtype": "Float",
			"width": 80,
			"convertible": "qty"
		},
		{
			"label": _("Amount"),
			"fieldname": "amount",
			"fieldtype": "Currency",
			"width": 110,
			"options": "Company:company:default_currency",
			"convertible": "rate"
		},
		{
			"label": _("Billed Amount"),
			"fieldname": "billed_amount",
			"fieldtype": "Currency",
			"width": 110,
			"options": "Company:company:default_currency",
			"convertible": "rate"
		},
		{
			"label": _("Pending Amount"),
			"fieldname": "pending_amount",
			"fieldtype": "Currency",
			"width": 130,
			"options": "Company:company:default_currency",
			"convertible": "rate"
		},
		{
			"label": _("Received Qty Amount"),
			"fieldname": "received_qty_amount",
			"fieldtype": "Currency",
			"width": 130,
			"options": "Company:company:default_currency",
			"convertible": "rate"
		},
		{
			"label": _("Warehouse"),
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 100
		},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 100
		}
	])

	return columns
