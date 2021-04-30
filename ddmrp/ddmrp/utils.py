# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import print_function, unicode_literals
import frappe
from frappe.utils import flt, cstr, nowdate, nowtime,rounded, get_user_date_format, add_days, today, now
from pprint import pprint
import json

logs =[]
bom_dict,item_master_dict,bom_dlt_dict = [{} for i in range(3)]
stock_buffer_set = set()

def get_wo_reserved_qty(warehouses):
    '''get open reserved qty for work order'''
    return frappe.db.sql('''
        SELECT Date(wo.planned_start_date) date, "Work Order" ref_doctype, wo.name ref_docname,
            wo_item.source_warehouse as warehouse, wo_item.item_code, item.stock_uom,
            CASE WHEN ifnull(skip_transfer, 0) = 0 THEN
                (wo_item.required_qty - wo_item.transferred_qty)
            ELSE
                (wo_item.required_qty - wo_item.consumed_qty)
            END,
            wo.production_item
        FROM `tabWork Order` wo, `tabWork Order Item` wo_item
        INNER JOIN `tabItem` item on wo_item.item_code = item.name
        WHERE
            wo_item.source_warehouse in %s  and wo_item.parent = wo.name
            and wo.docstatus = 1  and wo.status not in ("Stopped", "Completed")
            and 
            CASE WHEN ifnull(skip_transfer, 0) = 0 THEN
                wo_item.required_qty > wo_item.transferred_qty
            else
                wo_item.required_qty > wo_item.consumed_qty
            end
    ''', (warehouses,),)

def get_sub_contract_reserved_qty(item_code, warehouse):
    #reserved qty
    reserved_qty_for_sub_contract = frappe.db.sql('''
        select ifnull(sum(itemsup.required_qty),0)
        from `tabPurchase Order` po, `tabPurchase Order Item Supplied` itemsup
        where
            itemsup.rm_item_code = %s
            and itemsup.parent = po.name
            and po.docstatus = 1
            and po.is_subcontracted = 'Yes'
            and po.status != 'Closed'
            and po.per_received < 100
            and itemsup.reserve_warehouse = %s''', (item_code, warehouse))[0][0]

    #Get Transferred Entries
    materials_transferred = frappe.db.sql("""
        select
            ifnull(sum(transfer_qty),0)
        from
            `tabStock Entry` se, `tabStock Entry Detail` sed, `tabPurchase Order` po
        where
            se.docstatus=1
            and se.purpose='Send to Subcontractor'
            and ifnull(se.purchase_order, '') !=''
            and (sed.item_code = %(item)s or sed.original_item = %(item)s)
            and se.name = sed.parent
            and se.purchase_order = po.name
            and po.docstatus = 1
            and po.is_subcontracted = 'Yes'
            and po.status != 'Closed'
            and po.per_received < 100
    """, {'item': item_code})[0][0]

    if reserved_qty_for_sub_contract > materials_transferred:
        reserved_qty_for_sub_contract = reserved_qty_for_sub_contract - materials_transferred
    else:
        reserved_qty_for_sub_contract = 0

    return reserved_qty_for_sub_contract    

def get_so_reserved_qty(warehouses):
    return frappe.db.sql("""
        select
            so_item.delivery_date, "Sales Order" ref_doctype, so.name ref_docname, 
            so_item.warehouse, so_item.item_code, stock_uom, (stock_qty * ((qty - delivered_qty) / qty))
        from `tabSales Order Item` so_item join
             `tabSales Order` so 
        on so.name = so_item.parent
        where so_item.warehouse in %s
            and (so_item.delivered_by_supplier is null or so_item.delivered_by_supplier = 0)
            and so.docstatus = 1  and so.status != 'Closed'
            and so_item.qty >= so_item.delivered_qty
    """, (warehouses,))    

def get_open_mr_qty(item_code, warehouse, date_to,date_operator):
    # Ordered Qty is always maintained in stock UOM
    inward_qty = frappe.db.sql("""
        select sum(mr_item.stock_qty - mr_item.ordered_qty)
        from `tabMaterial Request Item` mr_item, `tabMaterial Request` mr
        where mr_item.item_code=%s and mr_item.warehouse=%s
            and mr.material_request_type in ('Purchase', 'Manufacture', 'Customer Provided', 'Material Transfer')
            and mr_item.stock_qty > mr_item.ordered_qty and mr_item.parent=mr.name
            and mr.status!='Stopped' and mr.docstatus=1
            and mr.schedule_date %s %s
    """, (item_code, warehouse, date_operator, date_to))
    inward_qty = flt(inward_qty[0][0]) if inward_qty else 0

    outward_qty = frappe.db.sql("""
        select sum(mr_item.stock_qty - mr_item.ordered_qty)
        from `tabMaterial Request Item` mr_item, `tabMaterial Request` mr
        where mr_item.item_code=%s and mr_item.warehouse=%s
            and mr.material_request_type = 'Material Issue'
            and mr_item.stock_qty > mr_item.ordered_qty and mr_item.parent=mr.name
            and mr.status!='Stopped' and mr.docstatus=1
            and mr.schedule_date %s %s
    """, (item_code, warehouse, date_operator, date_to))
    outward_qty = flt(outward_qty[0][0]) if outward_qty else 0

    requested_qty = inward_qty - outward_qty

    return requested_qty

def get_open_po_qty(item_code, warehouse, date_to, date_operator):
    ordered_qty = frappe.db.sql("""
        select sum((po_item.qty - po_item.received_qty)*po_item.conversion_factor)
        from `tabPurchase Order Item` po_item, `tabPurchase Order` po
        where po_item.item_code=%s and po_item.warehouse=%s
        and po_item.qty > po_item.received_qty and po_item.parent=po.name
        and po.status not in ('Closed', 'Delivered') and po.docstatus=1
        and po_item.delivered_by_supplier = 0
        and po_item.schedule_date %s %s""",
        (item_code, warehouse, date_operator, date_to))

    return flt(ordered_qty[0][0]) if ordered_qty else 0

def get_open_wo_qty(item_code, warehouse, date_to, date_operator):
    planned_qty = frappe.db.sql("""
        select sum(qty - produced_qty) from `tabWork Order`
        where production_item = %s and fg_warehouse = %s and status not in ("Stopped", "Completed")
        and docstatus=1 and qty > produced_qty
        and planned_end_date %s %s""",
        (item_code, warehouse, date_operator, date_to))

    return flt(planned_qty[0][0]) if planned_qty else 0

def get_incoming_qty(item_code, warehouse, date_to, outside_dlt=False):
    date_operator = ">" if outside_dlt else "<="
    return (get_open_po_qty(item_code, warehouse, date_to, date_operator) +
            get_open_wo_qty(item_code, warehouse, date_to, date_operator) +
            get_open_mr_qty(item_code, warehouse, date_to, date_operator)
        )
def convert_to_dict(data_list):
    """convert list of list [[key1,value11,value12],[key2,value21,value22]] from db.sql or get_list
	 to dict {key1:[value11,value12], key2:[value21,value22]}  to improve lookup performance
    """
    data = dict.fromkeys({d[0] if type(d) in (list,tuple) else d.name for d in data_list})
    for d in data_list:
        key, value = (d[0], d[1:]) if type(d) in (list,tuple) else (d.name, d)
        if data[key] and value:
            data[key].append(value)
        else:
            data[key] = [value]
    return data

def get_draft_po(warehouses, item_code=None):
    """po created by stock buffer, as qty inprogress"""
    sql = """select po_item.item_code,
         sum(po_item.qty*po_item.conversion_factor) qty
        from `tabPurchase Order Item` po_item, `tabPurchase Order` po
        where po_item.warehouse in %s
        po_item.parent=po.name and po.docstatus=0
        and po_item.delivered_by_supplier = 0
        group by po_item.item_code        
        """
    return frappe.db.sql(sql, (warehouses))

def get_supply(warehouses=None, plant=None, sap_interface=False, item_code=None, date_to=None, with_order_detail = False, debug=0):
    """
        either plant or warehouse required, if plant passed in get data from interface table
        case1: filter by warehouses only, return item code, date
        case2  filter by warehouses and item code, return grouped by date only
        case3  filter by warehouses and with order numbers output, not sum and groupby
    """
    if sap_interface == '1':
        return get_interface_data(type='demand', plant=plant, item_code = item_code,
            date_to=date_to,with_order_detail= with_order_detail)
    else:    
        # with item_code has the basic common fields
        output_fields = ['t.date', 't.uom', 'sum(t.qty)']
        po_fields = ['po_item.schedule_date date','po_item.uom',
            'sum((po_item.qty - IFNULL(po_item.received_qty,0))*po_item.conversion_factor) qty']
        wo_fields = ['Date(planned_end_date) date','stock_uom uom', 'sum(qty - produced_qty) qty']

        output_group_fields = ['t.date','t.uom']
        po_group_fields = ['po_item.schedule_date','po_item.uom']
        wo_group_fields = ['Date(planned_end_date)','stock_uom']
        if item_code:
            if not date_to: date_to = add_days(today(), 365)
            cond_po = ' and po_item.item_code = %s and po_item.schedule_date <= %s '
            cond_wo = ' and production_item = %s and Date(planned_end_date) <= %s '
        else:
            cond_po = cond_wo = ''

        if with_order_detail:                
            output_fields[-1] = output_fields[-1].replace('sum','')
            po_fields[-1] = po_fields[-1].replace('sum','')
            wo_fields[-1] = wo_fields[-1].replace('sum','')
            output_fields[1:1] = ['t.ref_doctype','t.ref_docname',
                            't.warehouse','t.item_code',]
            po_fields[1:1] = ['"Purchase Order" ref_doctype','po_item.parent ref_docname',
                            'po_item.warehouse','po_item.item_code item_code']
            wo_fields[1:1] = ['"Work Order" ref_doctype','name ref_docname',
                            'fg_warehouse as warehouse','production_item item_code']   
        elif not item_code:		        
            output_fields[0:0] = ['t.item_code']
            po_fields[0:0] = ['po_item.item_code item_code'] 
            wo_fields[0:0] = ['production_item item_code']
            output_group_fields[0:0] = ['t.item_code']
            po_group_fields[0:0] = ['po_item.item_code'] 
            wo_group_fields[0:0] = ['production_item']
        
        sql = """select {output_fields} from (
        select {po_fields}
            from `tabPurchase Order Item` po_item, `tabPurchase Order` po
            where po_item.warehouse in %s
            and po_item.qty > IFNULL(po_item.received_qty,0) and po_item.parent=po.name
            and po.status not in ('Closed', 'Delivered') and po.docstatus=1
            and po_item.delivered_by_supplier = 0 {cond_po}
            {po_group_by}
            union all
            select {wo_fields} from `tabWork Order`
            where fg_warehouse in %s and status not in ("Stopped", "Completed")
            and docstatus=1 and qty > IFNULL(produced_qty,0) {cond_wo}
            {wo_group_by}
        ) t {output_group_by}
            """.format(output_fields = ','.join(output_fields),
                        po_fields= ','.join(po_fields),
                        wo_fields = ','.join(wo_fields),
                        po_group_by = ' group by %s' % ','.join(po_group_fields) if not with_order_detail else '',
                        wo_group_by = ' group by %s' % ','.join(wo_group_fields) if not with_order_detail else '',					
                        output_group_by = ' group by %s' % ','.join(output_group_fields) if not with_order_detail else '',										
                        cond_po = cond_po,
                        cond_wo = cond_wo
                    )
        params = (warehouses, item_code, date_to, warehouses,item_code, date_to,) if item_code else (warehouses,warehouses,) 
        return frappe.db.sql(sql, params,debug=debug)
    
def get_demand(warehouses=None,plant=None, sap_interface=False, item_code=None, 
            date_to=None, with_order_detail = False, debug=0):
    """when with item_code and date_to, set as where condition, and group by date only"""
    if sap_interface == '1':
        return get_interface_data(type='demand', plant=plant, item_code = item_code,
            date_to=date_to, with_order_detail= with_order_detail)
    else:          
        output_fields = ['t.date', 't.uom', 'sum(t.qty)']
        so_fields = ['so_item.delivery_date date','so_item.uom',
            'sum( so_item.qty - IFNULL(so_item.delivered_qty,0) - IFNULL(so_item.returned_qty) ) qty']
        wo_fields = ['Date(wo.planned_start_date) date','item.stock_uom', 
            """sum(CASE WHEN ifnull(skip_transfer, 0) = 0 THEN
                    (wo_item.required_qty - wo_item.transferred_qty)
                    ELSE
                    (wo_item.required_qty - wo_item.consumed_qty)
                    END)
            qty"""]

        output_group_fields = ['t.date','t.uom']
        so_group_fields = ['so_item.delivery_date','so_item.uom']
        wo_group_fields = ['Date(wo.planned_start_date)','item.stock_uom']
        if item_code:
            if not date_to: date_to = add_days(today(), 365)
            cond_so = ' and so_item.item_code = %s and so_item.delivery_date <= %s '
            cond_wo = ' and wo_item.item_code = %s and Date(wo.planned_start_date) <= %s '
        else:
            cond_so = cond_wo = ''

        if with_order_detail:                
            output_fields[-1] = output_fields[-1].replace('sum','')
            so_fields[-1] = so_fields[-1].replace('sum','')
            wo_fields[-1] = wo_fields[-1].replace('sum(','(')
            output_fields[1:1] = ['t.ref_doctype','t.ref_docname',
                            't.warehouse','t.item_code',]
            so_fields[1:1] = ['"Sales Order" ref_doctype','so_item.parent ref_docname',
                            'so_item.warehouse','so_item.item_code item_code']
            wo_fields[1:1] = ['"Work Order" ref_doctype','wo.name ref_docname',
                            'wo_item.source_warehouse as warehouse','wo_item.item_code item_code']   
        elif not item_code:		        
            output_fields[0:0] = ['t.item_code']
            so_fields[0:0] = ['so_item.item_code item_code'] 
            wo_fields[0:0] = ['wo_item.item_code item_code']
            output_group_fields[0:0] = ['t.item_code']
            so_group_fields[0:0] = ['so_item.item_code'] 
            wo_group_fields[0:0] = ['wo_item.item_code']    
               
        sql = """select {output_fields} from (
            select {so_fields}
                from `tabSales Order Item` so_item, `tabSales Order` so
                where so_item.warehouse in %s
                and so_item.qty > IFNULL(so_item.delivered_qty,0) and so_item.parent=so.name
                and so.status in ('To Deliver', 'To Deliver and Bill') and so.docstatus=1
                and so_item.delivered_by_supplier = 0 {cond_so}
                {so_group_by}

            union all
            
            select {wo_fields} 
                FROM `tabWork Order` wo, `tabWork Order Item` wo_item
                INNER JOIN `tabItem` item on wo_item.item_code = item.name
                WHERE
                    wo_item.source_warehouse in %s  and wo_item.parent = wo.name
                    and wo.docstatus = 1  and wo.status not in ("Stopped", "Completed")
                    and wo.qty > IFNULL(wo.produced_qty,0)
                    and 
                        CASE WHEN ifnull(wo.skip_transfer, 0) = 0 THEN
                            wo_item.required_qty > wo_item.transferred_qty
                        else
                            wo_item.required_qty > wo_item.consumed_qty
                        end            
                {cond_wo}
                {wo_group_by}
            ) t {output_group_by}
                """.format(output_fields = ','.join(output_fields),
                            so_fields= ','.join(so_fields),
                            wo_fields = ','.join(wo_fields),
                            so_group_by = ' group by %s' % ','.join(so_group_fields) if not with_order_detail else '',
                            wo_group_by = ' group by %s' % ','.join(wo_group_fields) if not with_order_detail else '',					
                            output_group_by = ' group by %s' % ','.join(output_group_fields) if not with_order_detail else '',										
                            cond_so = cond_so,
                            cond_wo = cond_wo
                        )
        params = (warehouses, item_code, date_to, warehouses,item_code, date_to,) if item_code else (warehouses,warehouses,)        
        return frappe.db.sql(sql, params, debug=debug)

def get_interface_data(type, plant, item_code=None,date_to=None, with_order_detail=True, debug=None):
    fields = ['due_date', 'uom', 'sum(open_qty)']    
    group_fields = ['due_date', 'uom']    
    if item_code:
        if not date_to: date_to = add_days(today(), 365)
        cond = ' and material = %s and due_date <= %s'        
    else:
            cond = ''
    if with_order_detail:                
        fields[-1] = fields[-1].replace('sum','')        
        fields[1:1] = ['order_category as ref_doctype','order_number as ref_docname',
            "'' as warehouse",'material as item_code']
    elif not item_code:		        
        fields = ['material as item_code'] + fields
        group_fields[1:1] = ['material']
    order_category = ['Sales Order','Dependent Demand'] if type=='demand' else ['Purchase Order','Production Order']
    params = (order_category, plant) if not item_code else (order_category,plant,item_code)      
    sql = """select {fields}      
        from `tabOpen Orders`
        where propose = 0 and order_category in %s and plant=%s {cond}
        {group_by}""".format(
            fields = ','.join(fields),					
            group_by = ' group by %s' % ','.join(group_fields) if not with_order_detail else '',					
            cond = cond)        
    return frappe.db.sql(sql, params, debug=debug)

def get_on_hand(warehouses=None,plant=None, sap_interface=False, item_code=None, debug=0):
    if sap_interface == '1':
        return get_sap_stock(plant=plant, item_code = item_code)
    else:    
        cond = ' and item_code =%s ' if item_code else ''
        params = (warehouses,) if not item_code else (warehouses,item_code,)
        sql = """select item_code,
            sum(actual_qty) available,
            sum(ordered_qty + indented_qty + planned_qty) incoming,
            sum(reserved_qty + reserved_qty_for_production + reserved_qty_for_sub_contract) outgoing,    
            sum(projected_qty) on_hand_un_res
            from `tabBin`
            where warehouse in %s {0}       
            group by item_code""".format(cond)
        return frappe.db.sql(sql, params,debug = debug)

def get_sap_stock(plant, item_code=None, debug=0):
    cond = ' and item_code =%s ' if item_code else ''
    params = (plant,) if not item_code else (plant,item_code,)
    sql = """select item_code,
        sum(qty) available,
        0 incoming,
        0 outgoing,    
        sum(qty) on_hand_un_res
        from `tabSAP Stock`
        where plant = %s {0}       
        group by item_code""".format(cond)
    return frappe.db.sql(sql, params,debug = debug)

def get_consumption_from_sle(warehouses,item_code=None, date_from=None, date_to=None, debug=0):
    fields = ['posting_date']
    cond = ['']
    params = [warehouses]
    
    if item_code:
        cond.append('item_code =%s')
        params.append(item_code)
    else:
        fields = ['item_code'] + fields

    if date_from:
        cond.append('posting_date >=%s')
        params.append(date_from)

    if date_to:
        cond.append('posting_date <=%s')
        params.append(date_to)

    sql = """select {0}, sum(actual_qty*-1)     
        from `tabStock Ledger Entry`
        where warehouse in %s and is_cancelled = 0 and actual_qty < 0
        {1}
        group by {0}""".format(','.join(fields), ' and '.join(cond))
    return frappe.db.sql(sql, tuple(params), debug=debug)

def get_demand_estimate(plant,item_code=None, date_to=None, date_from=None, debug=0):
    fields = ['item_code as name', 'date_start', 'date_end', 'daily_qty']
    filters = {'plant': plant}
    
    return frappe.get_all('Demand Estimate', filters= filters, fields=fields)

def get_warehouses(plant):
	def get():
		return [r[0] for r in frappe.db.get_values('Warehouse',{'plant':plant})]
		
	warehouses = frappe.cache().hget("Plant-Warehouses", plant, get)    
	return warehouses

def get_item_plant_qty_available(item_code, plant):
    warehouses = get_warehouses(plant)
    qty = get_on_hand(warehouses, item_code)
    return qty[0][1] if qty else 0

def plan_days(date, days, plant):
    plant = frappe.get_cached_doc('Plant', plant)
    return add_days_for_holiday_list(date, days, plant.holiday_list, plant.company)

def add_days_for_holiday_list(date, days, holiday_list = None, company = None):
    schedule_date = add_days(date, days)
    if not holiday_list and company:
        holiday_list = frappe.get_cached_value('Company',  company,  "default_holiday_list")        
    if holiday_list:
        holidays = frappe.db.sql_list('''select holiday_date from `tabHoliday` where parent=%s''', holiday_list)    
        for i in range(abs(days)):
            if schedule_date in holidays:
                schedule_date = add_days(schedule_date, 1 if days>0 else -1)                
    return schedule_date

def get_bom_dict(plant):
    fields=['item as name','item as parent_item_code', 'quantity','`tabBOM Item`.item_code',
        '`tabBOM Item`.stock_uom','`tabBOM Item`.stock_qty']
    filters={'docstatus':1,'is_default':1, 'plant': plant}
    data_list = frappe.get_all('BOM', filters= filters, fields = fields)
    return convert_to_dict(data_list)

@frappe.whitelist()
def insert_multi(doctype, docs, fields:list=[], batchsize=1000, debug = 0):
    """case 1: fields and list of list
       case 2: list of dict with each key as fieldname/fields
    """
    std_fields = ['owner','modified_by','creation','modified']
    field_index = {}
    missing_fields = []
    #print(docs)
    if docs and isinstance(docs, str):
        docs = json.loads(docs)

    if not docs or not isinstance(docs, list): return

    if fields:
        field_index = {f:i for i, f in enumerate(fields) if f in std_fields + ['name']}
        missing_fields = std_fields + ['name'] - field_index.keys()
        fields.extend(missing_fields)        
    else:
        for f in std_fields:
            docs[0][f]  = ''
        if not 'name' in docs[0]:
            docs[0]['name']  = frappe.generate_hash(length=10)
        fields = docs[0].keys()
    sql = """insert into `tab{doctype}`
            ({fields}) values """.format(
            doctype=doctype,
            fields=", ".join(["`" + c + "`" for c in fields]))
    placeholders = ''
    values =[]
    total_records, col_count = len(docs),len(fields)
    rowcount = 0
    for idx, d in enumerate(docs):
        imod = idx % batchsize
        if isinstance(d, list):
            doc_values = d
            #1. overwrite standard field if passed in
            for field, index in field_index:                
                if field in ['owner','modified_by']:                    
                    d[index] = frappe.session.user
                elif field in ['creation','modified']:
                    d[index] = now()
                elif field == 'name' and not d[index]:                
                    d[index] = frappe.generate_hash(length=10)
            #2 append standard field       
            for field in missing_fields:
                if field in ['owner','modified_by']:                    
                    d.append(frappe.session.user)
                elif field in ['creation','modified']:
                    d.append(now())
                elif field == 'name':                
                    d.append(frappe.generate_hash(length=10))
        else:            
            d['owner'], d['modified_by'] = [frappe.session.user] * 2
            d['creation'],d['modified']  = [now()] * 2
            if not 'name' in d:
                d['name'] = frappe.generate_hash(length=10)
            doc_values = list(d.values())
        rec_placeholder = '(%s)' %(", ".join(["%s"] * col_count))        
        placeholders = '%s, %s' %(placeholders , rec_placeholder) if placeholders else rec_placeholder
        
        values.extend(doc_values)

        if (idx > 0 and imod==0) or (idx == total_records-1):
            try:
                s = '%s %s' %(sql, placeholders)                
                frappe.db.sql(s, values, debug = debug)
                rowcount += frappe.db._cursor.rowcount
            except Exception as e:
                print(idx,s,values)
                raise
            
            placeholders = ''
            values =[]
    return f"Inserted {rowcount} {doctype} records"

def get_precision(dt, field):
    def get():
        return frappe.get_precision(dt, field)
	
    return frappe.cache().hget("field_precision", dt+field, get)    	

def _get_longest_path(plant, bom_item):    
    print('startd get_longest_path %s' % bom_item)
    bom_line_ids = bom_dict.get(bom_item)
    if not bom_line_ids: return 0.0
    paths = [0] * len(bom_line_ids)
    i = 0
    for line in bom_line_ids:
        item_code = line.item_code                
        if not item_code in stock_buffer_set:                    
            item_plant_doc = item_master_dict.get(item_code)
            procurement_type = item_plant_doc.procurement_type
            # If component is manufactured we continue exploding.
            if procurement_type == 'Manufacture':
                if item_code in bom_dlt_dict:
                    paths[i] += bom_dlt_dict[item_code]
                    print('calculated bom %s dlt reused ' % item_code)
                else:
                    dlt =  item_plant_doc and item_plant_doc.get('ipt', 0) or 0
                    paths[i] += dlt                
                    line_boms = bom_dict.get(item_code)
                    pprint('line_boms=%s' % line_boms)                    
                    if line_boms:
                        paths[i] += _get_longest_path(plant, item_code)
                    else:
                        create_log("No Valid BOM found for Manufactured Component", 
                            type='Error', item_code = item_code, plant = plant)            
            elif procurement_type == 'Buy': # assuming they are purchased,                      
                paths[i] = item_plant_doc and item_plant_doc.get('pdt',0) + item_plant_doc.get('gr_time',0) or 0
                if not paths[i]:
                    create_log("Planned delivery time or GR processing time not maintained for Buy Component", 
                            type='Error', item_code = item_code, plant = plant)                    
                    pprint(logs[-1])
            elif procurement_type == 'Transfer': # assuming they are purchased,                
                paths[i] = item_plant_doc and item_plant_doc.get('transit_time',0) or 0
                if not paths[i]:
                    create_log("Transit time not maintained for Transfer Component", 
                            type='Error', item_code = item_code, plant = plant)                    
                    pprint(logs[-1])
            print('path %s dlt=%s' %(i, paths[i]))        
        i += 1
    return max(paths)

def compute_dlt(plant = None, item_code = None, automatic = False):
    """backround run, save log to log table"""
    if plant:
        plants = [plant]
    else:
        plant_list = frappe.get_all('Plant')
        plants = [p.name for p in plant_list] if plant_list else []
    
    logs.clear()           
    for plant in plants:
        item_master_dict.clear()
        bom_dict.clear()
        stock_buffer_set.clear()
        bom_dlt_dict.clear()

        data = frappe.get_all('Stock Buffer', filters={'plant': plant, 'active': 1}, fields='item_code')
        stock_buffer_set.update({d.item_code for d in data})
        #pprint(stock_buffer_set)
        data = frappe.get_all('Item Plant', filters={'plant': plant}, 
            fields=['item_code','procurement_type','ipt','pdt','gr_time'])
        item_master_dict.update({d.item_code:d for d in data})
        print('item_master count=%s' % (len(item_master_dict)))
        #pprint(item_master_dict)

        fields=['item as name', 'item','`tabBOM Item`.item_code']
        bom_filters={'docstatus':1,'is_default':1, 'plant': plant}
        bom_list = frappe.get_all('BOM', filters= bom_filters, fields = fields)        
        bom_dict.update(convert_to_dict(bom_list))
        print('item_master count=%s' % (len(item_master_dict)))
        #pprint('bom_dict=%s' % bom_dict)    
        
        logs.append({'source':'DLT', 'type':'Info','item_code':'', 'plant':plant, 'message': 'Started'})
        item_code_list = [item_code] if item_code else item_master_dict.keys()
        for item in item_code_list:        
            print('processing item =%s, item_master count=%s' % (item, len(item_master_dict)))
            item_master = item_master_dict.get(item)
            if item_master:
                procurement_type = item_master.procurement_type
                if  procurement_type == 'Buy':
                    dlt =  item_master.get('pdt', 0) + item_master.get('gr_time',0)  or 0
                elif procurement_type == 'Manufacture':
                    dlt =  item_master.ipt  or 0
                    dlt += _get_longest_path(plant, item)
                    bom_dlt_dict[item] = dlt
                    if dlt:
                        bom_filters['item'] = item
                        frappe.db.set_value('BOM', bom_filters, 'dlt', dlt)
                elif procurement_type == 'Transfer':    
                    dlt =  item_master.transit_time  or 0           

                if dlt:
                    frappe.db.set_value('Item Plant', {'item_code':item, 'plant':plant}, 'dlt', dlt)
                    frappe.db.set_value('Stock Buffer', {'item_code':item, 'plant':plant}, 'dlt', dlt)
                    print('item=%s, procurement_type=%s dlt=%s' % (item, procurement_type, dlt))
        logs.append({'source':'DLT', 'type':'Info','item_code':'', 'plant':plant, 'message': 'end'})

    if automatic: insert_multi('DDMRP Log', logs)            
    return logs

def create_log(msg='', type='Info', item_code='', plant=''):
    logs.append({'source':'DLT',
            'type': type,
            'item_code': item_code,
            'plant': plant,
            'message': msg  
        }
    )
