# -*- coding: utf-8 -*-
# Copyright (c) 2021, Fisher and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import requests
import json
import math
from ddmrp.ddmrp.utils import get_warehouses
import pandas as pd

class SAPInterface(Document):
    def run(self):
        args = {"plant": self.plant,
                "sync_type": self.sync_type}        
        #args = json.loads(args)
        print(args)
        url = 'http://%s:8090' % get_local_ip()  #'http://139.24.193.54:8090'
        res = requests.post(url, json = args)
        try:
            return json.loads(res.text).get('data')
        except:
            return 'Failed get sap data'        

def get_local_ip():
    return getattr(frappe.local.request, "remote_addr", "NOTFOUND")        

def sync_open_onhand_stock(plant):
    location_list = get_warehouses(plant)
    location_list = [l.split(' - ')[0] for l in location_list]
    material_list = frappe.get_all('Item Plant', filters={'plant': plant}, 
        fields='item_code', as_list = 1) or []
    material_list = [m[0] for m in material_list]
    args ={'tcode':'MB52', 'material': material_list, 'location': location_list, 'plant':plant}
    stock_list = call_sap_tcode(args)
    if stock_list:
        sap_interface = frappe.db.get_value('DDMRP Settings', None, 'sap_interface_active')
        if sap_interface == '1':         
            df = pd.DataFrame(stock_list)
            df = df.groupby(df['item_code'])['available_qty','quality_insp']
            df = df.sum().reset_index()
            docs = df.T.to_dict().values()  #convert to list of dict
            docs = [{'item_code':d.item_code,'plant':plant,'qty': d.available_qty + d.quality_insp, 
                    'uom':d.unit} for d in docs]
            frappe.db.delete('SAP Stock', {'plant': plant})
            return insert_multi('SAP Stock', docs)
        else:           
            stock_recon_doc = frappe.new_doc('Stock Reconciliation')
            company = frappe.db.get_value('Plant', plant, 'company')
            company_abbr = frappe.db.get_value('Company', company, 'abbr')
            stock_recon_doc.company = company
            stock_recon_doc.purpose = 'Stock Reconciliation'

            items =[{'item_code':s.get('material'),
                    'qty': s.get('available_qty',0) + s.get('quality_insp',0),
                    'warehouse':'%s - %s' %(s['location'],company_abbr),
                    'valuation_rate': 0.01
                    } for s in stock_list]
            for item in items:		
                stock_recon_doc.append('items',item)                
            stock_recon_doc.save()
            stock_recon_doc.submit()

    return stock_recon_doc

@frappe.whitelist()
def sync_sap_data(data=[]):
    """sync multiple docs list in one transaction commit
       data [{'doctype':'', docs:[], columns:[]},{}]
    """
    from ddmrp.ddmrp.utils import insert_multi

    if data and isinstance(data, str):
        data = json.loads(data)

    if not data:
        return    
    msg = []
    for d in data:
        doctype = d.get('doctype')
        docs= d.get('docs')
        columns = d.get('columns')

        filters = {}
        if columns and 'plant' in columns:
            field_index = columns.index('plant')
            plant = docs[0] and docs[0][field_index]
            filters.update({'plant': plant})

        if doctype=='Open Orders':
            doc0 = docs[0]
            if columns and doc0: # list of list
                order_category = doc0[columns.index('order_category')]                
            else: # list of dict
                order_category = docs[0].get('order_category')                
            filters.update({'order_category': order_category,                            
                            'proposed':0
                            })
        else:
            filters.update({'name':('like','%')})

        frappe.db.delete(doctype, filters)
        msg.append(insert_multi(doctype, docs, columns))

    return msg