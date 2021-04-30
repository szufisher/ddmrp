# Copyright (c) 2013, Fisher and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

def execute(filters=None):
    columns, data = [], []
    columns = get_columns( filters.get('show_buffer_info') )
    get_data(data , filters)
    return columns, data

def get_columns(show_buffer_info = False):
    columns = [           
            {
                "label": _("Item Code"),
                "fieldtype": "Link",
                "fieldname": "item_code",
                "options": "Item",            
                "width": 120
            },
            {
                "label": _("Item Name"),
                "fieldtype": "Data",                
                "fieldname": "item_name",                
                "width": 150
            },
            # {
            #     "label": _("Level"),
            #     "fieldtype": "Int",
            #     "fieldname": "level",
            #     "hidden": 1,            
            #     "width": 50
            # },
            {
                "label": _("Qty Per"),
                "fieldtype": "Float",
                "fieldname": "qty_per",
                "width": 80
            },
            {
                "label": _("Qty"),
                "fieldtype": "Float",
                "fieldname": "qty",
                "width": 60
            },
            {
                "label": _("UOM"),
                "fieldtype": "Link",
                "options": "UOM",
                "fieldname": "uom",
                "width": 60
            },
            {
                "label": _("PDT"),
                "fieldtype": "Float",
                "fieldname": "pdt",
                "width": 60
            },
            {
                "label": _("IPT"),
                "fieldtype": "Float",
                "fieldname": "ipt",
                "width": 60
            },
            {
                "label": _("DLT"),
                "fieldtype": "Float",
                "fieldname": "dlt",
                "width": 60
            },
            {
                "label": _("Buffered"),
                "fieldtype": "Check",
                "fieldname": "buffered",
                "width": 60
            }
        ]
    if show_buffer_info:
        buffer_info_columns= [
            {
                "label": _("ADU"),
                "fieldtype": "Float",
                "fieldname": "adu",
                "width": 60
            },
            {
                "label": _("TOR"),
                "fieldtype": "Float",
                "fieldname": "top_of_red",
                "width": 60
            },
            {
                "label": _("TOY"),
                "fieldtype": "Float",
                "fieldname": "top_of_yellow",
                "width": 60
            },
            {
                "label": _("TOG"),
                "fieldtype": "Float",
                "fieldname": "top_of_green",
                "width": 60
            },
            {
                "label": _("On Demand"),
                "fieldtype": "Float",
                "fieldname": "qualified_demand",
                "width": 60
            },
            {
                "label": _("Available"),
                "fieldtype": "Float",
                "fieldname": "net_flow_position",
                "width": 60
            },
            {
                "label": _("On Hand"),
                "fieldtype": "Float",
                "fieldname": "actual_qty",
                "width": 60
            },
            {
                "label": _("On Supply"),
                "fieldtype": "Float",
                "fieldname": "incoming_dlt_qty",
                "width": 60
            },
            {
                "label": _("On Hand Priority"),
                "fieldtype": "Data",
                "fieldname": "execution_priority_level",
                "width": 60
            },
            {
                "label": _("Plan Priority"),
                "fieldtype": "Data",
                "fieldname": "planning_priority_level",
                "width": 60
            }
        ]
        columns.extend(buffer_info_columns)
    
    return columns

def get_data(data, filters=None, debug=0):
    from ddmrp.ddmrp.utils import convert_to_dict

    plant = filters.get('plant')
    item_code = filters.get('item_code')
    req_qty = filters.get('required_qty', 1)

    def get_bom_items(bom_no, req_qty, level=0):
        result = []
        bom_items_list = bom_dict.get(bom_no) or []
        for bom_item in bom_items_list:
            bom_item['level'] = level
            bom_item['indent'] = level
            bom_item.qty = req_qty * bom_item.stock_qty / bom_item.quantity            
            if debug: print('component %s' % bom_item)            
            result.append(bom_item)
            if bom_item.procurement_type == 'Manufacture':
                if debug: print(bom_item.item_code, bom_item.qty, bom_item.date)
                result.extend(get_bom_items(bom_item.bom_no, bom_item.qty,level=level+1))
        if debug: print('result = %s' % result[:2])                        
        return result

    sql = """select bom.name, bom.quantity, {fields} item_plant.procurement_type,item_plant.ipt,item_plant.pdt,
        item_plant.dlt, 
        CASE
            WHEN buffer.name is Null
               THEN 0
               ELSE 1
        END as buffered,
        buffer.adu, buffer.top_of_red, buffer.top_of_yellow, buffer.top_of_green, 
        buffer.actual_qty, buffer.incoming_dlt_qty, buffer.qualified_demand, buffer.net_flow_position,
        buffer.on_hand_percent, buffer.execution_priority_level, buffer.planning_priority_level, buffer.execution_priority_level
        from {tables}
        where bom.docstatus=1 and bom.is_active=1 and bom.plant = %s {order_by} """
    # add top level item as level 0    
    fields = """bom.uom, bom.item item_code, bom.item_name, 1 stock_qty,
                         1 qty_per,bom.name bom_no, 0 indent, %s qty,"""    
    tables = """ `tabBOM` bom left join `tabItem Plant` item_plant on bom.item = item_plant.item_code
                and bom.plant = item_plant.plant
                left join `tabStock Buffer` buffer on bom.item=buffer.item_code and bom.plant = buffer.plant"""
    order_by = ""
    s = sql.format(fields = fields, tables = tables, order_by = order_by)
    s += " and bom.is_default=1 and bom.item = %s limit 1"
    data.extend(frappe.db.sql(s,(req_qty,plant,item_code,),as_dict = 1))

    fields = """bom_item.uom, bom_item.item_code, bom_item.item_name, bom_item.stock_qty,
                         bom_item.stock_qty/bom.quantity qty_per,bom_item.bom_no,"""    
    tables = """ `tabBOM` bom join `tabBOM Item` bom_item on bom_item.parent = bom.name
        left join `tabItem Plant` item_plant on bom_item.item_code = item_plant.item_code
                and bom.plant = item_plant.plant
        left join `tabStock Buffer` buffer on bom_item.item_code=buffer.item_code and bom.plant = buffer.plant"""
    order_by = "order by bom_item.idx"
    s = sql.format(fields = fields, tables = tables, order_by = order_by)
    bom_dict = convert_to_dict(frappe.db.sql(s,(plant,),as_dict = 1))

    f = {'plant':plant,'item':item_code,'is_active':1,'is_default':1,'docstatus':1}
    bom_name = frappe.db.get_value('BOM', f)
    data.extend(get_bom_items(bom_no = bom_name, req_qty = req_qty, level = 1))

    return data


