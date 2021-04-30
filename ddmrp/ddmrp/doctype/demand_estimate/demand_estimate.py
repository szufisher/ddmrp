# -*- coding: utf-8 -*-
# Copyright (c) 2021, Fisher and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import today
from dateutil import parser
from datetime import datetime, timedelta
from pprint import pprint
from six import string_types

class DemandEstimate(Document):
    def validate(self):
        self._compute_daily_qty()
        self.check_stock_qty()

    def check_stock_qty(self):
        if not self.stock_uom:
            self.stock_uom = self.uom
        if self.uom == self.stock_uom:
            self.stock_uom_qty = self.qty

    def _compute_daily_qty(self):        
        if not self.days and self.date_end and self.date_start:
            self.days = (self.date_end-self.date_start).days
            
        if self.days:
            self.daily_qty = self.qty / self.days
        else:
            self.daily_qty = 0.0

    def get_quantity_by_date_range(self, date_start, date_end):
        """To be used in other modules"""
        # Check if the dates overlap with the period
        period_date_start = self.date_start
        period_date_end = self.date_end
        # We need only the periods that overlap the dates introduced by the user.
        if period_date_start <= date_end and period_date_end >= date_start:
            overlap_date_start = max(period_date_start, date_start)
            overlap_date_end = min(period_date_end, date_end)
            days = (abs(overlap_date_end-overlap_date_start)).days + 1
            return days * self.daily_qty
        return 0.0

    def check_bom_exist(self):
        filters ={'item': self.item_code,
                'plant':self.plant,
                'is_default':1,
                'docstatus':1}
        return frappe.db.count('BOM', filters = filters)  

    def generate_component_demand_estimate(self, debug=0):
        from ddmrp.ddmrp.utils import insert_multi

        def get_bom_components(parent_item, plant, req_qty, date_start):
            result = []
            if isinstance(date_start, str):
                date_start = parser.parse(date_start)   #datetime.strptime(date_start, "%Y-%m-%d") 
            component_list = frappe.db.sql(sql, (plant, parent_item), as_dict=True, debug = debug) or []            
            for component in component_list:
                #no need to shift the date per in-house production time 
                #component.date = date_start - timedelta(days= component.ipt or 0)
                component.date = date_start
                component.qty = req_qty * component.stock_qty / component.quantity
                if debug: print('component %s' % component)
                filters = {"item_code": component.item_code, "plant":plant, "active":1}
                if frappe.db.count("Stock Buffer", filters):
                    result.append(component)
                if component.procurement_type == 'Manufacture':
                    if debug:
                        print(component.item_code, plant, component.qty, component.date)
                    result.extend(get_bom_components(component.item_code, plant, component.qty, component.date))                                                        
            if debug: print('result = %s' % result[:2])                        
            return result

        sql = """select header.ipt, B.quantity, BI.item_code, BI.stock_qty, BI.stock_uom, child.procurement_type 
                    from `tabBOM` B inner join `tabBOM Item` BI on B.name = BI.parent 
					inner join `tabItem Plant` header on B.item = header.item_code and
                                header.plant = B.plant
					inner join `tabItem Plant` child on BI.item_code = child.item_code and
                                child.plant = B.plant                                
					where B.docstatus=1 and B.is_default=1  and 
                        header.plant = %s and B.item = %s"""
        # called from js, the date field is passed in as str type
        if isinstance(self.date_start, string_types):
            self.date_end = parser.parse(self.date_end) 
            self.date_start = parser.parse(self.date_start) 
        days = self.date_end - self.date_start
        bom_components = get_bom_components(self.item_code, self.plant, self.stock_uom_qty or self.qty, self.date_start)
        if debug: print(bom_components)                
        date_dict = {c.date:None for c in bom_components}
        if debug: print(date_dict)
        date_range_list = []
        for date_start in date_dict:
            date_end = date_start + days
            date_range = frappe.db.get_value('Date Range', filters ={'date_start': date_start, 
                                                                    'date_end': date_end,
                                                                    'active':1})
            cur_date_dict = frappe._dict({'name': date_range,
                            'date_start': date_start,
                            'date_end': date_end}
            )
            if not date_range:
                cur_date_dict['name'] = '%s_%s' %(date_start.strftime('%y%m%d'), date_end.strftime('%y%m%d'))
                date_range_list.append(cur_date_dict)
            date_dict[date_start] = cur_date_dict
        if debug: print(date_dict)    
        component_estimate_list = []
        counter = 0        
        for c in bom_components:            
            counter += 1
            days = (date_dict[c.date].date_end - date_dict[c.date].date_start).days
            component_estimate_list.append({
                'name' : '%s_%s_%s_%s' %(c.item_code,self.name,date_dict[c.date].name,  counter),
                'date_range': date_dict[c.date].name,
                'date_start': date_dict[c.date].date_start,
                'date_end': date_dict[c.date].date_end,
                'days': days,
                'daily_qty':c.qty / days,
                'qty': c.qty,
                'uom': c.stock_uom,
                'stock_uom_qty': c.qty,
                'stock_uom': c._stock_uom,
                'stock_buffer': '%s_%s' %(c.item_code, self.plant),
                'item_code': c.item_code,
                'plant': self.plant,
                'parent_demand': self.name,
                'parent_item_code': self.item_code,
                'company': self.company
            })
        pprint(component_estimate_list[:3]) 
        #delete the previously generated records        
        frappe.db.delete('Demand Estimate', {'parent_demand': self.name})
        insert_multi('Date Range', date_range_list)            
        insert_multi('Demand Estimate', component_estimate_list)
        frappe.db.commit()

        return component_estimate_list

@frappe.whitelist()
def create_demand(docnames):
    import json

    docnames = json.loads(docnames)
    cnt = 0
    for d in docnames:
        demand = frappe.get_doc('Demand Estimate', d) 
        cnt += len(demand.generate_component_demand_estimate())
    return cnt