# -*- coding: utf-8 -*-
# Copyright (c) 2021, Fisher and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from datetime import date, datetime, timedelta
import frappe
from frappe.model.document import Document
from ddmrp.ddmrp.utils import *
from pprint import pprint

logs =[]
item_plant_dict, bom_dict = [{} for i in range(2)]
stock_buffer_set = set()

class MultiLevelMRP(Document):
    mrp_move_counter, inventory_counter = 0,0        
    def _prepare_item_plant_data(self, item_plant_doc):
        """item_plant doc object"""                
        qty_available = get_item_plant_qty_available(item_plant_doc.item_code, item_plant_doc.plant)
        mrp_llc = frappe.get_cached_doc('Item', item_plant_doc.item_code).llc
        
        return {
            "item_plant": item_plant_doc.name,
            "mrp_qty_available": qty_available,
            "mrp_llc": mrp_llc,
        }
    
    def _prepare_mrp_move_data_from_stock_move(self, plant_doc, move_list):
        fields = ['mrp_date','ref_doctype','ref_docname','warehouse','item_code','uom','qty']
        print(move_list)
        move = frappe._dict()
        for i in range(len(fields)):            
            move[fields[i]] = move_list[i]
        if len(move_list) == 8:
            move['parent_item_code'] = move_list[-1]
        print(move)
        if (move.ref_doctype == 'Sales Order' or 
            (move.ref_doctype == 'Work Order' and move.get('parent_item_code')) ):
            mrp_type = "d"
            product_qty = -move.qty
        else:
            mrp_type = "s"
            product_qty = move.qty        
        
        if move.ref_doctype == 'Sales Order':            
            origin = "so"
        elif move.ref_doctype == 'Work Order':
            origin = "wo"            
        elif move.ref_doctype == 'Purchase Order':
            origin = "po"            
        mrp_date = date.today()
        if move.mrp_date and move.mrp_date > date.today():
            mrp_date = move.mrp_date
        self.mrp_move_counter += 1            
        return {
            "state":"draft",
            "ref_doctype": move.ref_doctype,
            "ref_docname": move.ref_docname,
            "item_plant": '%s_%s' %(move.item_code,plant_doc.name),
            "item_code": move.item_code,
            "uom": move.uom,
            "plant": plant_doc.name,
            "warehouse": move.warehouse,                      
            "company":plant_doc.company,
            "mrp_qty": product_qty,
            "current_qty": product_qty,
            "mrp_date": mrp_date,
            "current_date": move.mrp_date,
            "mrp_type": mrp_type,
            "mrp_origin": origin,            
            "parent_item_code": move.get('parent_item_code'),
            "name": '%s_%s' %(datetime.today().strftime('%y%m%d%H%M'), self.mrp_move_counter)
            #"note": order_number,                        
        }
    
    def _prepare_planned_order_data(self, item_plant_doc, qty, mrp_date_supply, mrp_action_date, name):
        return {
            "item_plant": item_plant_doc.name,
            "item_code":item_plant_doc.item_code,
            "planner":item_plant_doc.planner,
            "plant":item_plant_doc.plant,
            "uom":item_plant_doc.uom,
            "company":item_plant_doc.get("company"),
            "mrp_qty": qty,
            "due_date": mrp_date_supply,
            "order_release_date": mrp_action_date,
            "mrp_action": item_plant_doc.procurement_type,
            "qty_released": 0.0,
            "note": "Planned supply for: " + name,
            "fixed": False,
            "doctype":"Planned Order"
        }

    def _prepare_mrp_move_data_bom_explosion(self, item_plant_doc, bomline, qty, mrp_date_demand_2, name):
        key = item_plant_doc.item_code
        if key not in item_plant_dict:
            raise exceptions.Warning(_("No MRP product found")) 
        self.mrp_move_counter += 1            
        return {
            "state":"draft",
            "plant": item_plant_doc.plant,
            "company": item_plant_doc.get('company'),
            "item_code": bomline.item_code,
            "uom":bomline.stock_uom,
            "item_plant": '%s_%s' %(bomline.item_code,item_plant_doc.plant),
            "mrp_qty": -bomline.stock_qty,  # TODO: review with UoM
            #"current_qty": 0,
            "mrp_date": mrp_date_demand_2,
            #"current_date": '',
            "mrp_type": "d",
            "mrp_origin": "mrp",            
            "parent_item_code": bomline.parent_item_code,
            "name": '%s_%s' %(datetime.today().strftime('%y%m%d%H%M'), self.mrp_move_counter),
            "note": ("Demand Bom Explosion: %s"  % (item_plant_doc.item_code)),            
        }
    
    def _get_action_and_supply_dates(self, item_plant_doc, mrp_date):
        mrp_date_supply = date.today() if mrp_date < date.today() else mrp_date
        in_house_production_time = item_plant_doc.ipt or 0        
        mrp_action_date = plan_days(mrp_date, -1 * in_house_production_time, item_plant_doc.plant)
        
        return mrp_action_date, mrp_date_supply
    
    def explode_action(self, item_plant_doc, mrp_action_date, name, qty, action):
        """Explode requirements."""
        mrp_date_demand = mrp_action_date
        if mrp_date_demand < date.today():
            mrp_date_demand = date.today()
        item_code = item_plant_doc.item_code
        if not item_code in bom_dict:
            return False
        mrp_move_list = []
        for bomline in bom_dict[item_code]:
            if bomline.stock_qty <= 0.00:   # or bomline.item_code.type != "product":
                continue
            if self._exclude_from_mrp(bomline.item_code, item_plant_doc.plant,mrp_explosion=True):
                # Stop explosion.
                continue
            #if bomline._skip_bom_line(item_plant_id.item_code): dummy component
            #    continue
            # TODO: review: mrp_transit_time, mrp_inspection_time
            mrp_date_demand_2 = mrp_date_demand - timedelta(
                days=(item_plant_doc.ipt + item_plant_doc.inspection_time))
            move_data = self._prepare_mrp_move_data_bom_explosion(item_plant_doc, bomline, qty, mrp_date_demand_2, name)
            mrp_move_list.append(move_data)
            #mrpmove_id2 = frappe.get_doc(move_data).insert()
            if hasattr(action, "mrp_move_down_ids"):
                action.mrp_move_down_ids = [(4, mrpmove_id2)]
        insert_multi('MRP Move', mrp_move_list)
        return True
    
    def create_action(self, item_plant_doc, mrp_date, mrp_qty, name, values=None):
        if not values:
            values = {}
        action_date, date_supply = self._get_action_and_supply_dates(item_plant_doc, mrp_date)
        return self.create_planned_order(item_plant_doc, mrp_qty, name, date_supply, action_date, values=values)
    
    def create_planned_order(self,item_plant_doc,mrp_qty,name,mrp_date_supply,mrp_action_date,values=None):        
        if self._exclude_from_mrp(item_plant_doc.item_code, item_plant_doc.plant):
            values["qty_ordered"] = 0.0
            return values

        qty_ordered = values.get("qty_ordered", 0.0) if values else 0.0
        qty_to_order = mrp_qty
        while qty_ordered < mrp_qty:
            qty = adjust_qty_to_order(item_plant_doc, qty_to_order)
            qty_to_order -= qty
            order_data = self._prepare_planned_order_data(
                item_plant_doc, qty, mrp_date_supply, mrp_action_date, name
            )
            planned_order = frappe.get_doc(order_data).insert()
            qty_ordered = qty_ordered + qty

            if item_plant_doc.procurement_type == 'Manufacture':   # to be checked            
                self.explode_action(item_plant_doc, mrp_action_date, name, qty, planned_order)

        values["qty_ordered"] = qty_ordered
        log_msg = "[{}] {}: qty_ordered = {}".format(
            item_plant_doc.plant,
            item_plant_doc.item_code
            or item_plant_doc.item_code,
            qty_ordered,
        )
        create_log(log_msg, type='Debug')
        return values
   
    def _mrp_cleanup(self, plants=None):
        create_log("Start MRP Cleanup")
        domain = {}
        if plants:
            domain.update({"plant":("in", plants)})
        else:
            domain.update({"plant":("like", '%')})
        frappe.db.delete("MRP Move",domain)
        frappe.db.delete("MRP Inventory",domain)
        domain.update({"fixed":0})
        frappe.db.delete("Planned Order",domain)
        create_log("End MRP Cleanup")
        return True

    def _low_level_code_calculation(self):
        create_log("Start low level code calculation")
        counter = 999999
        llc = 0
        frappe.db.set_value('Item Plant',{'name':('like','%')},{"llc": llc})		
        products = frappe.db.get_values('Item Plant', {"llc":llc})
        if products:
            counter = len(products)
        log_msg = "Low level code 0 finished - Nbr. products: %s" % counter
        print(log_msg)
        create_log(log_msg)

        sql = """select BI.item_code from `tabBOM` B inner join `tabBOM Item` BI on B.name = BI.parent 
					inner join `tabItem Plant` header_item on B.item = header_item.item_code and
                                header_item.plant = B.plant
					inner join `tabItem Plant` child_item on BI.item_code = child_item.item_code and
                                child_item.plant = B.plant                                
					where B.docstatus=1 and B.is_default=1  and 
                        child_item.llc = %s and header_item.name in %s"""
        while counter:
            llc += 1
            print('llc=%s' % llc)
            products = frappe.db.get_values('Item Plant', {"llc": llc - 1})            
            if products:        
                bom_lines = frappe.db.sql(sql, (llc - 1, [p[0] for p in products]))
                if bom_lines:
                    frappe.db.set_value('Item Plant',{'item_code':('in',[b[0] for b in bom_lines])},{"llc": llc})
            counter = frappe.db.count('Item Plant', {"llc": llc})
            log_msg = "Low level code {} finished - Nbr. products: {}".format(llc, counter)
            print(log_msg)
            create_log(log_msg)            

        mrp_lowest_llc = llc
        create_log("End low level code calculation")
        print("End low level code calculation")
        return mrp_lowest_llc
    
    def _adjust_mrp_applicable(self, plants=None):
        """This method is meant to modify the products that are applicable to MRP Multi level calculation"""
        return True

    def _calculate_mrp_applicable(self, plants=None):
        create_log("Start Calculate MRP Applicable")
        domain = {'name':('like','%')}
        if plants:
            domain.update({"plant":("in", plants)})
        frappe.db.set_value("Item Plant",domain,{"mrp_applicable": 0})
        #domain.update({"item_code.type" "product")]
        frappe.db.set_value("Item Plant", domain, {"mrp_applicable": 1})
        self._adjust_mrp_applicable(plants)
        count_domain = {"mrp_applicable": 1}
        if plants:
            count_domain.update({"plant": ("in", plants)})
        counter = frappe.db.count("Item Plant", count_domain)
        log_msg = "End Calculate MRP Applicable: %s" % counter
        create_log(log_msg)
        return True
  
    def _init_mrp_move_from_forecast(self, item_plant):
        """This method is meant to be inherited to add a forecast mechanism."""
        return True
    
    def _init_mrp_move_from_stock_move(self, plant_doc):
        moves = []
        warehouses = get_warehouses(plant_doc.name)        
        moves.extend(get_supply(warehouses, with_order_detail = 1))
        moves.extend(get_so_reserved_qty(warehouses))
        moves.extend(get_wo_reserved_qty(warehouses))
        pprint(moves)
        mrp_moves = [self._prepare_mrp_move_data_from_stock_move(plant_doc, m) for m in moves]
        pprint(mrp_moves)
        insert_multi('MRP Move', mrp_moves, debug=1)
        return True
    
    def _prepare_mrp_move_data_from_purchase_order(self, poline, item_plant):
        mrp_date = date.today()
        if poline.date_planned > date.today():
            mrp_date = poline.date_planned
        return {
            "item_code": poline.item_code,
            "item_plant": item_plant,            
            "ref_doctype": 'Purchase Order',
            "ref_docname": poline.po,            
            "mrp_qty": poline.product_qty,
            "current_qty": poline.product_qty,
            "mrp_date": mrp_date,
            "current_date": poline.date_planned,
            "mrp_type": "s",
            "mrp_origin": "po",            
            "note": poline.po,            
            "doctype":"MRP Move"
        }
    
    def _init_mrp_move_from_purchase_order(self, item_plant):        
        po_lines = []
        for line in po_lines:
            mrp_move_data = self._prepare_mrp_move_data_from_purchase_order(line, item_plant)
            frappe.get_doc(mrp_move_data).insert()
   
    def _init_mrp_move(self, plant_doc):
        self._init_mrp_move_from_forecast(plant_doc)
        self._init_mrp_move_from_stock_move(plant_doc)
        #self._init_mrp_move_from_purchase_order(item_plant_doc)
    
    def _exclude_from_mrp(self, item_code, plant, mrp_explosion = 0):
        """ To extend with various logic where needed. """                                
        if item_code in stock_buffer_set and not mrp_explosion:
            return True        
        if not item_code in item_plant_dict:
            return True    
        return item_plant_dict[item_code].mrp_exclude

    def get_unique_key(self, plant, doctype):
        """return unique key list in a set for quick lookup check"""
        data = frappe.get_all(doctype, filters={'plant': plant, 'active': 1}, 
                    fields=['item_code'])
        return {d.item_code for d in data}   
    
    def _mrp_initialisation(self, plants=None):
        create_log("Start MRP initialisation")
        filters = {"mrp_applicable": 1}
        if not plants:
            plants = frappe.get_all('Plant', as_list = 1)
            plants = [p[0] for p in plants]
        else:
            filters["plant"] = ("in", plants)
        #init_counter = 0
        for plant in plants:
            plant_doc = frappe.get_cached_doc('Plant', plant)
            stock_buffer_set.update(self.get_unique_key(plant,'Stock Buffer'))
            data = frappe.get_all('Item Plant', filters={'plant': plant}, 
                fields=['item_code','plant','mrp_exclude'])
            item_plant_dict.update({d.item_code:d for d in data})
            bom_dict.update(get_bom_dict(plant))
            # for item_plant_doc in item_plant_list:                
            #     if item_plant_doc.plant == plant:
            #         if self._exclude_from_mrp(item_plant_doc.item_code, plant):
            #             continue
            #         init_counter += 1
            #         log_msg = "MRP Init: {} - {} ".format(init_counter, item_plant_doc.name)
            #         create_log(log_msg)
            self._init_mrp_move(plant_doc)
        create_log("End MRP initialisation")
    
    def _init_mrp_move_grouped_demand(self, nbr_create, item_plant_doc):
        last_date = None
        last_qty = 0.00
        onhand = item_plant_doc.qty_available
        grouping_delta = item_plant_doc.nbr_days
        move_list = frappe.get_all('MRP Move',{'item_plant': item_plant_doc.name},
                fields=['name','mrp_date','mrp_qty'])
        for move in move_list:            
            if self._exclude_move(move):
                continue
            if (
                last_date
                and (move.mrp_date >= last_date + timedelta(days=grouping_delta))
                and ( (onhand + last_qty + move.mrp_qty) < item_plant_doc.minimum_stock
                    or (onhand + last_qty) < item_plant_doc.minimum_stock
                )
            ):
                name = "Grouped Demand for %d Days" % grouping_delta
                qtytoorder = item_plant_doc.minimum_stock - onhand - last_qty
                cm = self.create_action(
                    item_plant_doc=item_plant_doc,
                    mrp_date=last_date,
                    mrp_qty=qtytoorder,
                    name=name,
                )
                qty_ordered = cm.get("qty_ordered", 0.0)
                onhand = onhand + last_qty + qty_ordered
                last_date = None
                last_qty = 0.00
                nbr_create += 1
            if (
                (onhand + last_qty + move.mrp_qty) < item_plant_doc.minimum_stock
                or (onhand + last_qty) < item_plant_doc.minimum_stock
            ):
                if not last_date or last_qty == 0.0:
                    last_date = move.mrp_date
                    last_qty = move.mrp_qty
                else:
                    last_qty += move.mrp_qty
            else:
                last_date = move.mrp_date
                onhand += move.mrp_qty

        if last_date and last_qty != 0.00:
            name = "Grouped Demand for %d Days" % grouping_delta
            qtytoorder = item_plant_doc.minimum_stock - onhand - last_qty
            cm = self.create_action(item_plant_doc=item_plant_doc, mrp_date=last_date, mrp_qty=qtytoorder, note=name)
            qty_ordered = cm.get("qty_ordered", 0.0)
            onhand += qty_ordered
            nbr_create += 1
        return nbr_create
    
    def _exclude_move(self, move):
        """Improve extensibility being able to exclude special moves."""
        return False
    
    def _mrp_calculation(self, mrp_lowest_llc, plants):
        create_log("Start MRP calculation")        
        counter = 0
        if not plants:
            plants = frappe.get_all('Plant', as_list = 1)
            plants =[p[0] for p in plants]
        for plant in plants:            
            llc = 0
            while mrp_lowest_llc > llc:                
                item_plant_List = frappe.get_all("Item Plant", filters={'llc':llc, 'plant':plant},
                    fields = '*') or []
                llc += 1
                warehouses = get_warehouses(plant)            
                on_hand_dict = convert_to_dict(get_on_hand(warehouses))
                for item_plant_doc in item_plant_List:                    
                    nbr_create = 0
                    #{'01109339': [(0.0, 0.0, 28.0, -28.0)]}
                    onhand = on_hand_dict.get(item_plant_doc.item_code)
                    item_plant_doc.qty_available = onhand and onhand[0][0] or 0
                    onhand = item_plant_doc.qty_available
                    if item_plant_doc.nbr_days == 0:
                        move_list = frappe.get_all('MRP Move',filters={'item_plant': item_plant_doc.name},
                            fields=['name','mrp_date','mrp_qty'])
                        for move in move_list:                            
                            if self._exclude_move(move):
                                continue
                            qtytoorder = item_plant_doc.minimum_stock- onhand- move.mrp_qty                            
                            if qtytoorder > 0.0:
                                cm = self.create_action(item_plant_doc=item_plant_doc, mrp_date=move.mrp_date,
                                    mrp_qty=qtytoorder,
                                    name=move.name,
                                )
                                qty_ordered = cm["qty_ordered"]
                                onhand += move.mrp_qty + qty_ordered
                                nbr_create += 1
                            else:
                                onhand += move.mrp_qty
                    else:
                        nbr_create = self._init_mrp_move_grouped_demand(nbr_create, item_plant_doc)

                    minimum_stock = item_plant_doc.minimum_stock or 0
                    if onhand < minimum_stock and nbr_create == 0:
                        qtytoorder = item_plant_doc.minimum_stock - onhand
                        cm = self.create_action(
                            item_plant_doc=item_plant_doc,
                            mrp_date=date.today(),
                            mrp_qty=qtytoorder,
                            name="Minimum Stock",
                        )
                        qty_ordered = cm["qty_ordered"]
                        onhand += qty_ordered
                    counter += 1

            log_msg = "MRP Calculation LLC {} Finished - Nbr. products: {}".format(llc - 1, counter)
            create_log(log_msg)

        create_log("End MRP calculation")
    
    def _get_demand_groups(self, item_plant_name):
        query = """
            SELECT mrp_date, sum(mrp_qty)
            FROM `tabMRP Move`
            WHERE item_plant = %(item_plant)s
            AND mrp_type = 'd'
            GROUP BY mrp_date
        """
        params = {"item_plant": item_plant_name}
        return query, params
    
    def _get_supply_groups(self, item_plant_name):
        query = """
                SELECT mrp_date, sum(mrp_qty)
                FROM `tabMRP Move`
                WHERE item_plant = %(item_plant)s
                AND mrp_type = 's'
                GROUP BY mrp_date
            """
        params = {"item_plant": item_plant_name}
        return query, params
    
    def _get_planned_order_groups(self, item_plant_name):
        query = """
            SELECT due_date, sum(mrp_qty)
            FROM `tabPlanned Order`
            WHERE item_plant = %(item_plant)s
            GROUP BY due_date
        """
        params = {"item_plant": item_plant_name}
        return query, params
    
    def _prepare_mrp_inventory_data(
        self,
        item_plant_doc,
        mdt,
        on_hand_qty,
        running_availability,
        demand_qty_by_date,
        supply_qty_by_date,
        planned_qty_by_date,
    ):
        """Return dict to create mrp.inventory records on MRP Multi Level Scheduler"""
        mrp_inventory_data = {"item_code": item_plant_doc.item_code, 
                                "plant":item_plant_doc.plant,
                                "uom":item_plant_doc.uom,
                                "procurement_type":item_plant_doc.procurement_type,                                 
                                "company": item_plant_doc.get('company'),
                                "date": mdt}
        demand_qty = demand_qty_by_date.get(mdt, 0.0)
        mrp_inventory_data["demand_qty"] = abs(demand_qty)
        supply_qty = supply_qty_by_date.get(mdt, 0.0)
        mrp_inventory_data["supply_qty"] = abs(supply_qty)
        mrp_inventory_data["initial_on_hand_qty"] = on_hand_qty
        on_hand_qty += supply_qty + demand_qty
        mrp_inventory_data["final_on_hand_qty"] = on_hand_qty
        # Consider that MRP plan is followed exactly:
        running_availability += (
            supply_qty + demand_qty + planned_qty_by_date.get(mdt, 0.0)
        )
        mrp_inventory_data["running_availability"] = running_availability
        self.inventory_counter += 1 
        mrp_inventory_data["name"] = '%s_%s' %(datetime.today().strftime('%y%m%d%H%M'), self.inventory_counter)
        #mrp_inventory_data['doctype'] = "MRP Inventory"
        return mrp_inventory_data, running_availability
    
    def _init_mrp_inventory(self, item_plant_doc):
        item_plant_name = item_plant_doc.name        
        # Read Demand
        demand_qty_by_date = {}
        query, params = self._get_demand_groups(item_plant_name)
        data = frappe.db.sql(query, params)
        for mrp_date, qty in data:
            demand_qty_by_date[mrp_date] = qty
        # Read Supply
        supply_qty_by_date = {}
        query, params = self._get_supply_groups(item_plant_name)
        data = frappe.db.sql(query, params)
        for mrp_date, qty in data:
            supply_qty_by_date[mrp_date] = qty
        # Read planned orders:
        planned_qty_by_date = {}
        query, params = self._get_planned_order_groups(item_plant_name)
        data = frappe.db.sql(query, params)
        for mrp_date, qty in data:
            planned_qty_by_date[mrp_date] = qty
        # Dates
        moves_dates = frappe.db.get_values('MRP Move',
            {"item_plant":item_plant_name},"mrp_date",order_by="mrp_date")
        moves_dates = [m[0] for m in moves_dates if m]
        action_dates = frappe.db.get_values("Planned Order",
            {"item_plant": item_plant_name},"due_date", order_by ="due_date")
        action_dates = [a[0] for a in action_dates if a]
        mrp_dates = set(moves_dates + action_dates)        
        on_hand_qty = get_item_plant_qty_available(item_plant_doc.item_code, item_plant_doc.plant)
        running_availability = on_hand_qty
        mrp_inventory_list = []
        for mdt in sorted(mrp_dates):
            mrp_inventory_data, running_availability = self._prepare_mrp_inventory_data(
                item_plant_doc,
                mdt,
                on_hand_qty,
                running_availability,
                demand_qty_by_date,
                supply_qty_by_date,
                planned_qty_by_date,
            )
            mrp_inventory_list.append(mrp_inventory_data)
        return mrp_inventory_list            
            #inv_doc = frappe.get_doc(mrp_inventory_data).insert()
            # attach planned orders to inventory
            #frappe.db.set_value("Planned Order", {"due_date": mdt,"item_plant":item_plant_name},
            #    {"mrp_inventory": inv_doc.name})
    
    def _mrp_final_process(self, plants=None):
        create_log("Start MRP final process")
        filters = {'llc':('<', 9999)}
        fields = ['name','item_code','plant','company','uom','planner','procurement_type']
        if plants:
            filters.update({'plant': ('in', plants)})
        
        item_plant_list = frappe.get_all('Item Plant', filters = filters, fields= fields) 
        mrp_inventory_list = []
        for item_plant_doc in item_plant_list:            
            # Build the time-phased inventory
            if self._exclude_from_mrp(item_plant_doc.item_code, item_plant_doc.plant):
                continue
            mrp_inventory_list.extend(self._init_mrp_inventory(item_plant_doc))
        if mrp_inventory_list:    
            insert_multi('MRP Inventory', mrp_inventory_list)
        # attach planned orders to inventory
        sql = """update `tabPlanned Order` po inner join `tabMRP Inventory` mi on
	                po.due_date = mi.date and po.item_code= mi.item_code and 
	                po.plant=mi.plant set po.mrp_inventory = mi.name"""
        frappe.db.sql(sql)            
        create_log("End MRP final process")

    def run_mrp_multi_level(self, plant=None, automatic = False):
        logs.clear()        
        if plant:
            plants = [plant]
        else:
            plants =[p.name for p in frappe.get_all('Plant')]
        self._mrp_cleanup(plants)
        mrp_lowest_llc = self._low_level_code_calculation()
        self._calculate_mrp_applicable(plants)
        self._mrp_initialisation(plants)
        self._mrp_calculation(mrp_lowest_llc, plants)
        self._mrp_final_process(plants)
        
        if automatic: insert_multi('DDMRP Log', logs)            
        return logs                
        #return True

def adjust_qty_to_order(self, qty_to_order):   
    if (not self.maximum_order_qty and not
            self.minimum_order_qty and self.qty_multiple == 1.0):
        return qty_to_order
    if qty_to_order < self.minimum_order_qty:
        return self.minimum_order_qty
    if self.qty_multiple:
        multiplier = ceil(qty_to_order / self.qty_multiple)
        qty_to_order = multiplier * self.qty_multiple
    if self.maximum_order_qty and qty_to_order > self.maximum_order_qty:
        return self.maximum_order_qty
    return qty_to_order

def create_log(msg='', type='Info', item_code='', plant=''):
    logs.append({'source':'Multi Level MRP',
            'type': type,
            'item_code': item_code,
            'plant': plant,
            'message': msg  
        }
    )
