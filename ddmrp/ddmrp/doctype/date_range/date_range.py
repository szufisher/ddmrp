# -*- coding: utf-8 -*-
# Copyright (c) 2021, Fisher and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
# import frappe
from datetime import datetime
from frappe.utils import DATE_FORMAT
from frappe.model.document import Document

class DateRange(Document):
    def validate(self):
        f = DATE_FORMAT
        if self.date_start and self.date_end:
            self.days = abs((datetime.strptime(self.date_end, f)-datetime.strptime(self.date_start,f)).days) + 1
