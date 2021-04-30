# -*- coding: utf-8 -*-
# Copyright (c) 2021, Fisher and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
# import frappe
from frappe.model.document import Document
from ddmrp.utils import compute_dlt

class DDMRPRun(Document):
	def run(self):
		if self.action == 'DLT':
			result = compute_dlt(self.plant)
		elif self.action == 'Low Level Code':
			mrp = frappe.get_single(self.action)
			result = mrp._low_level_code_calculation()			
		elif self.action == 'Multi Level MRP':
			mrp = frappe.get_single(self.action)
			result = mrp.run_mrp_multi_level()
		elif self.action == 'ADU':
			result = cron_ddmrp_adu()
		elif self.action == 'DDMRP':
			result = cron_ddmrp()
		return result

