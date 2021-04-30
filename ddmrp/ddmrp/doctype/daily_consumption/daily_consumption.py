# -*- coding: utf-8 -*-
# Copyright (c) 2021, Fisher and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
# import frappe
from frappe.model.document import Document

class DailyConsumption(Document):
	pass

def get_daily_qty():
	sql = """select material, posting_date, sum(qty) from `tabDaily Consumption` 
			where qty>0 and material_doc not in (select cancelled_material_doc from 
				`tabDaily Consumption`)
			group by material,posting_date"""
	data = frappe.db.sql(sql)
	return