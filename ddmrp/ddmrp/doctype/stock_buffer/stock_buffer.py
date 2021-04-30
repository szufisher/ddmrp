# -*- coding: utf-8 -*-
# Copyright (c) 2020, Fisher and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import operator as py_operator
from collections import defaultdict
from datetime import datetime, timedelta, date
from datetime import timedelta as td
from dateutil import parser
from math import pi
from frappe.model.document import Document
from frappe.utils import rounded, get_user_date_format, add_days, today, now
from erpnext.stock.get_item_details import get_conversion_factor
from ddmrp.ddmrp.utils import *
try:
    import numpy as np
    import pandas as pd
    from bokeh.plotting import figure
    from bokeh.embed import components
    from bokeh.models import Legend, ColumnDataSource, LabelSet
    from bokeh.models import HoverTool, DatetimeTickFormatter
except (ImportError, IOError) as err:
    raise

OPERATORS = {
    "<": py_operator.lt,
    ">": py_operator.gt,
    "<=": py_operator.le,
    ">=": py_operator.ge,
    "==": py_operator.eq,
    "=": py_operator.eq,
    "!=": py_operator.ne,
}

_PRIORITY_LEVEL = [("1_red", "Red"), ("2_yellow", "Yellow"), ("3_green", "Green")]

DDMRP_COLOR = {
    "0_dark_red": "#8B0000",
    "1_red": "#ff0000",
    "2_yellow": "#ffff00",
    "3_green": "#33cc33",
}

PLANING_COLORS = [
    DDMRP_COLOR["1_red"],
    DDMRP_COLOR["2_yellow"],
    DDMRP_COLOR["3_green"],
]
EXECUTION_COLORS = [
    DDMRP_COLOR["0_dark_red"],
    DDMRP_COLOR["1_red"],
    DDMRP_COLOR["2_yellow"],
    DDMRP_COLOR["3_green"],
    DDMRP_COLOR["2_yellow"],
    DDMRP_COLOR["1_red"],
    DDMRP_COLOR["0_dark_red"],
]

supply_dict, demand_dict, on_hand_dict, draft_po_dict = [{} for i in range(4)]  # {'item_code1':[value1,value2], 'item_code2':[value1,value2]}
calculation_method_dict, demand_estimate_dict, stock_ledger_dict = [{} for i in range(3)]
buffer_profile_dict, ltaf_dict, daf_dict, daf_components_dict = [{} for i in range(4)]
bom_dict, item_plant_dict, stock_buffer_dict, source_list_dict = [{} for i in range(4)]
bom_header_dict, dependent_demand_dict,uom_conversion_dict = [{} for i in range(3)]
logs,new_orders =[], []

class StockBuffer(Document):
    def validate(self):
        self.update_comment_date()

    def update_comment_date(self):
        if ((self.is_new() and self.comment) or 
            (self._doc_before_save and self._doc_before_save.comment != self.comment) ):
            self.comment_date = today()        

    def _compute_ddmrp_chart(self):
        """This method use the Bokeh library to create a buffer depiction."""
        self.ddmrp_chart = "%s%s" % self.get_ddmrp_chart()
        self.save()

    def get_ddmrp_chart(self):
        p = figure(plot_width=300, plot_height=400, y_axis_label="Quantity")
        p.xaxis.visible = False
        p.toolbar.logo = None
        red = p.vbar(
            x=1, bottom=0, top=self.top_of_red, width=1, color="red", legend=False
        )
        yellow = p.vbar(
            x=1,
            bottom=self.top_of_red,
            top=self.top_of_yellow,
            width=1,
            color="yellow",
            legend=False,
        )
        green = p.vbar(
            x=1,
            bottom=self.top_of_yellow,
            top=self.top_of_green,
            width=1,
            color="green",
            legend=False,
        )
        net_flow = p.line(
            [0, 2], [self.net_flow_position, self.net_flow_position], line_width=2,line_dash="dotted"
        )
        on_hand = p.line(
            [0, 2],
            [
                self.actual_qty,
                self.actual_qty,
            ],
            line_width=2
            
        )
        legend = Legend(
            items=[
                (_("Red Zone"), [red]),
                (_("Yellow Zone"), [yellow]),
                (_("Green Zone"), [green]),
                (_("Net Flow Position"), [net_flow]),
                (_("On-Hand Position"), [on_hand]),
            ]
        )
        labels_source_data = {
            "height": [
                self.net_flow_position,
                self.actual_qty,    #qty_available_not_res,
                self.top_of_red,
                self.top_of_yellow,
                self.top_of_green,
            ],
            "weight": [0.25, 1.75, 1, 1, 1],
            "names": [
                self.net_flow_position,
                self.qty_available_not_res,
                self.top_of_red,
                self.top_of_yellow,
                self.top_of_green,
            ],
        }
        source = ColumnDataSource(data=labels_source_data)
        labels = LabelSet(
            x="weight",
            y="height",
            text="names",
            y_offset=1,
            render_mode="canvas",
            text_font_size="8pt",
            source=source,
            text_align="center",
        )
        p.add_layout(labels)
        p.add_layout(legend, "below")

        script, div = components(p)
        #script = script.replace(r'<script type="text/javascript">','').replace(r'</script>','')
        script = script[33:-10] # remove script tag <script type="text/javascript">js code</script>'
        return div, script

    def get_ddmrp_demand_supply_chart(self):        
        result = {}        
        # Prepare data:
        demand_data = self._get_demand_by_days()
        mrp_data ={} # self._get_qualified_mrp_moves()
        supply_data = self._get_incoming_by_days()
        width = timedelta(days=0.4)
        date_format = ["%y-%m-%d"] # get_user_date_format()

        # Plot demand data:
        if demand_data: # or mrp_data:
            x_demand = list(demand_data.keys())
            y_demand = list(demand_data.values())
            #x_mrp = list(mrp_data.keys())
            #y_mrp = list(mrp_data.values())

            p = figure(
                plot_width=500,
                plot_height=400,
                y_axis_label="Quantity",
                x_axis_type="datetime",
            )
            p.toolbar.logo = None
            p.sizing_mode = "stretch_both"
            # TODO: # p.xaxis.label_text_font = "helvetica"
            p.xaxis.formatter = DatetimeTickFormatter(
                hours=date_format,
                days=date_format,
                months=date_format,
                years=date_format,
            )
            p.xaxis.major_label_orientation = pi / 4

            if demand_data:
                p.vbar(
                    x=x_demand,
                    width=width,
                    bottom=0,
                    top=y_demand,
                    color="firebrick",
                )
            if mrp_data:
                p.vbar(
                    x=x_mrp, width=width, bottom=0, top=y_mrp, color="lightsalmon"
                )
            p.line(
                [
                    datetime.today() - timedelta(days=1),
                    datetime.today() + timedelta(days=self.order_spike_horizon),
                ],
                [self.order_spike_threshold, self.order_spike_threshold],
                line_width=2,
                line_dash="dashed",
            )

            unit = self.uom
            hover = HoverTool(
                tooltips=[("qty", "$y %s" % unit)], point_policy="follow_mouse"
            )
            p.add_tools(hover)

            script, div = components(p)

            result['demand_chart'] = [div, script[33:-10]]
            #self.ddmrp_demand_chart = "{}{}".format(div, script)        

        # Plot supply data:
        if supply_data:
            x_supply = list(supply_data.keys())
            y_supply = list(supply_data.values())

            p = figure(
                plot_width=500,
                plot_height=400,
                y_axis_label="Quantity",
                x_axis_type="datetime",
            )
            p.toolbar.logo = None
            p.sizing_mode = "stretch_both"
            p.xaxis.formatter = DatetimeTickFormatter(
                hours=date_format,
                days=date_format,
                months=date_format,
                years=date_format,
            )
            p.xaxis.major_label_orientation = pi / 4
            p.x_range.flipped = True

            # White line to have similar proportion to demand chart.
            p.line(
                [
                    datetime.today() - timedelta(days=1),
                    datetime.today() + timedelta(days=self.order_spike_horizon),
                ],
                [self.order_spike_threshold, self.order_spike_threshold],
                line_width=2,
                line_dash="dashed",
                color="white",
            )

            p.vbar(x=x_supply, width=width, bottom=0, top=y_supply, color="grey")

            unit = self.uom
            hover = HoverTool(
                tooltips=[("qty", "$y %s" % unit)], point_policy="follow_mouse"
            )
            p.add_tools(hover)

            script, div = components(p)
        
            result['supply_chart']=[div, script[33:-10]]
            #self.ddmrp_demand_chart = "{}{}".format(div, script)        

        return result            

    def _quantity_in_progress(self):
        """Return Quantities that are not yet in virtual stock but should
        be deduced from buffers (example: purchases created from buffers)"""
        draft_qty =  draft_po_dict.get(self.item_code)       
        return draft_qty[0] if draft_qty else 0

    def _compute_red_zone(self):
        if self.replenish_method in ["Replenish", "Min Max"]:
            buffer_profile = buffer_profile_dict.get(self.buffer_profile)
            lead_time_factor = buffer_profile.lead_time_factor or 0
            variability_factor = buffer_profile.variability_factor or 0
            self.red_base_qty = self.dlt * self.adu * lead_time_factor
            self.red_safety_qty = self.red_base_qty * variability_factor                
            self.red_zone_qty = self.red_base_qty + self.red_safety_qty
        else:
            self.red_zone_qty = self.red_override
        self.top_of_red = self.red_zone_qty    
        self._compute_order_spike_threshold()
    
    def _compute_green_zone(self):        
        if self.replenish_method in ["Replenish", "Min Max"]:
            buffer_profile = buffer_profile_dict.get(self.buffer_profile)
            lead_time_factor = buffer_profile.lead_time_factor or 0
            # Using imposed or desired minimum order cycle
            self.green_zone_oc = self.order_cycle * self.adu                
            # Using lead time factor
            self.green_zone_lt_factor = self.dlt * self.adu * lead_time_factor
            # Using minimum order quantity
            self.green_zone_moq = self.minimum_order_quantity
            # The biggest option of the above will be used as the green zone value
            self.green_zone_qty = max(self.green_zone_oc, self.green_zone_lt_factor, self.green_zone_moq)
        else:
            self.green_zone_qty = self.green_override
        self.top_of_green = self.green_zone_qty + self.top_of_yellow

    def _compute_yellow_zone(self):        
        if self.replenish_method == "Min Max":
            self.yellow_zone_qty = 0
        elif self.replenish_method == "Replenish":
            self.yellow_zone_qty = self.dlt * self.adu
        else:
            self.yellow_zone_qty = self.yellow_override
        self.top_of_yellow = self.yellow_zone_qty + self.red_zone_qty
    
    def _compute_procure_recommended_qty(self):        
        subtract_qty = self._quantity_in_progress()
        procure_recommended_qty = 0.0
        if self.net_flow_position < self.top_of_yellow:
            qty = self.top_of_green - self.net_flow_position - subtract_qty
            if qty >= 0.0:
                procure_recommended_qty = qty
        else:
            if subtract_qty > 0.0:
                procure_recommended_qty -= subtract_qty

        adjusted_qty = self._adjust_procure_qty(procure_recommended_qty) if procure_recommended_qty > 0.0 else 0.0
        self.procure_recommended_qty = adjusted_qty

    def _adjust_procure_qty(self, qty):
        from erpnext.stock.get_item_details import get_conversion_factor
        # If there is a procure UoM we apply it before anything.
        # This means max, min and multiple quantities are relative to the procure UoM.        
        adjusted_qty = qty
        minimum_order_quantity = self.minimum_order_quantity        
        if self.procure_uom and self.procure_uom != self.uom:            
            adjusted_qty = qty * get_conversion_factor(self.item_code, self.procure_uom)
        if adjusted_qty < minimum_order_quantity:
            adjusted_qty = minimum_order_quantity                
        # Apply qty multiple and minimum quantity (maximum quantity applies on the procure wizard)
        remainder = self.qty_multiple > 0 and adjusted_qty % self.qty_multiple or 0.0
        rounding = get_precision(self.doctype, 'procure_uom' if self.procure_uom else 'uom')
        if rounded(remainder, precision=rounding) > 0:
            adjusted_qty += self.qty_multiple - remainder
        if rounded(adjusted_qty - minimum_order_quantity, precision=rounding) < 0:
            adjusted_qty = minimum_order_quantity
        return adjusted_qty
    
    def _compute_order_spike_threshold(self):
        if not self.order_spike_threshold:
            self.order_spike_threshold = 0.5 * self.red_zone_qty

    def _compute_order_spike_horizon(self):
        if not self.order_spike_horizon:
            self.order_spike_horizon = self.dlt

    def _compute_dlt(self):
        item_plant_doc = item_plant_dict.get(self.item_code)        
        if self.procurement_type == "Transfer":
            dlt = self.lead_days
        elif self.procurement_type == "Buy":
            if item_plant_doc:
                dlt = item_plant_doc.get('dlt',0) + item_plant_doc.get('gr_time',0) 
        else:            
            dlt = item_plant_doc and item_plant_doc.get('dlt',0)            
        self.dlt = dlt + self.extra_lead_time
        
        ltaf_to_apply = ltaf_dict.get(self.name) or []    
        ltaf = 1        
        for factor_dict in ltaf_to_apply:
            ltaf *= factor_dict.value
        prev = self.dlt
        self.dlt *= ltaf
        self._compute_order_spike_horizon()
        if ltaf != 1:
            create_log("LTAF=%s applied to %s. DLT: %s -> %s" % (ltaf, self.name, prev, self.dlt),
                item_code = self.item_code, plant = self.plant)
    
    def _get_product_sellers(self):
        """:returns the default sellers for a single buffer."""        
        all_sellers = self.item_code.seller_ids.filtered(
            lambda r: not r.company_id or r.company_id == self.company_id
        )
        # specific for variant
        sellers = all_sellers.filtered(lambda s: s.item_code == self.item_code)
        if not sellers:
            # generic no variant
            sellers = all_sellers.filtered(lambda s: not s.item_code)
        if not sellers:
            # fallback to all sellers
            sellers = all_sellers
        return sellers

    def _compute_main_supplier(self):        
        if self.procurement_type == "Buy":
            suppliers = self._get_product_sellers()
            self.main_supplier_id = suppliers[0].name if suppliers else False
        else:
            self.main_supplier_id = False

    def _compute_distributed_source_location_qty(self):
        to_compute_per_location = {}        
        location = self.distributed_source_location_id
        if not location:
            self.distributed_source_location_qty = 0.0            
        to_compute_per_location.setdefault(location.id, set())        

        # batch computation per location to_compute_per_location[location.id].add(self.id)
        for location_id, buffer_ids in to_compute_per_location.items():
            buffers = self.browse(buffer_ids).with_context(location=location_id)
            for buf in buffers:
                buf.distributed_source_location_qty = buf.item_code.free_qty

    def _search_distributed_source_location_qty(self, operator, value):
        if operator not in OPERATORS:
            raise exceptions.UserError(_("Unsupported operator %s") % (operator,))
        buffers = self.search([("distributed_source_location_id", "!=", False)])
        operator_func = OPERATORS[operator]
        buffers = buffers.filtered(
            lambda buf: operator_func(buf.distributed_source_location_qty, value)
        )
        return [("id", "in", buffers.ids)]

    def onchange_adu(self):
        self._calc_adu()

    def _compute_product_available_qty(self):
        qty = on_hand_dict.get(self.item_code)
        if qty:
            self.actual_qty,self.incoming_qty,self.out_going_qty, self.qty_available_not_res = qty[0]
            self.virtual_qty = self.actual_qty + self.incoming_qty - self.out_going_qty

    def _get_demand_estimate_qty(self, date_start, date_end):
        qty = 0.0
        estimates = demand_estimate_dict.get(self.item_code) or []                    
        for est in estimates:
            print(est)
            if est.date_start <= date_end and est.date_end >= date_start:
                overlap_date_start = max(est.date_start, date_start)
                overlap_date_end = min(est.date_end, date_end)
                days = (abs(overlap_date_end-overlap_date_start)).days + 1
                print(overlap_date_start,overlap_date_end,days)
                qty += days * est.daily_qty                                                
        return qty    

    def _calc_adu_past_demand(self):        
        horizon = calculation_method_dict[self.adu_calculation_method].horizontal_past or 1        
        # today is excluded to be sure that is a past day and all moves
        # for that day are done (or at least the expected date is in the past).
        date_start = plan_days(date.today(), -1 * horizon, self.plant)        
        date_end = plan_days(date.today(), -1, self.plant)
        calculation_method_source = calculation_method_dict[self.adu_calculation_method].source_past
        if calculation_method_source == "Estimate":
            qty = self._get_demand_estimate_qty(date_start, date_end)                                                              
            return qty / horizon             
        elif calculation_method_source == "Actual":
            qty = 0.0
            moves = stock_ledger_dict.get(self.item_code) or []            
            for move in moves:
                if date_start <= move[0] <= date_end:
                    qty += move[1]
            return qty / horizon
        else:
            return 0.0    

    def _calc_adu_future_demand(self):        
        horizon = calculation_method_dict[self.adu_calculation_method].horizontal_future or 1        
        date_start = date.today()
        date_end = plan_days(date_start, horizon, self.plant)                
        #date_to = date_to.replace(hour=date_from.hour, minute=date_from.minute, second=date_from.second,)        
        calculation_method_source = calculation_method_dict[self.adu_calculation_method].source_future
        if calculation_method_source == "Estimate":
            qty = self._get_demand_estimate_qty(date_start, date_end)                                                              
            return qty / horizon        
        else:
            return 0.0

    def _calc_adu_blended(self):        
        past_comp = self._calc_adu_past_demand()
        fp = self.adu_calculation_method.factor_past
        future_comp = self._calc_adu_future_demand()
        ff = self.adu_calculation_method.factor_future
        return past_comp * fp + future_comp * ff

    def _calc_adu(self):        
        if self.calculation_method == "fixed":
            self.adu = self.adu_fixed
        elif self.calculation_method == "past":
            self.adu = self._calc_adu_past_demand()
        elif self.calculation_method == "future":
            self.adu = self._calc_adu_future_demand()
        elif self.calculation_method == "blended":
            self.adu = self._calc_adu_blended()
        self._calc_adu_daf()    
        return True

    def _get_incoming_supply_date_limit(self):
        # The safety factor allows to control the date limit
        factor =  1   #self.plant_id.nfp_incoming_safety_factor or
        horizon = int(self.dlt) * factor
        # For purchased products we use calendar days, not work days
        if (self.procurement_type != "Buy"):
            date_to = plan_days(date.today(), horizon, self.plant)
        else:
            date_to = date.today() + timedelta(days=horizon)
        return date_to

    def _get_incoming_by_days(self):
        date_to = self._get_incoming_supply_date_limit()
        warehouses = get_warehouses(self.plant)                
        moves = get_supply(warehouses, self.item_code, date_to)        
        incoming_by_days = {m[0]:m[1] for m in moves}
        
        return incoming_by_days

    def _get_demand_by_days(self):
        horizon = self.order_spike_horizon
        date_to = plan_days(date.today(), horizon, self.plant)  
        warehouses = get_warehouses(self.plant)
        sap_interface = frappe.db.get_value('DDMRP Settings', None, 'sap_interface_active')                
        moves = get_demand(warehouses, plant=self.plant, sap_interface=sap_interface,
            item_code = self.item_code, date_to = date_to)               
        demand_by_days = {m[0]:m[1] for m in moves}
        
        return demand_by_days

    def _calc_qualified_demand(self, current_date=False):
        today_date = current_date or date.today()
        end_date = today_date + timedelta(days=self.order_spike_horizon or self.dlt)
        self.qualified_demand = 0.0
        demand_by_days = demand_dict.get(self.item_code) or []
        # dependent demand for item as sales order item's BOM component        
        #demand_by_days.extend(dependent_demand_dict.get(self.item_code) or [])

        for delivery_date, uom, qty in demand_by_days:
            qty = get_item_stock_uom_qty(self.item_code, uom, qty)
            if (delivery_date <= today_date or 
                (qty >= self.order_spike_threshold and today_date < delivery_date< end_date)):
                self.qualified_demand += qty

        return True

    def _calc_supply(self):
        date_to = self._get_incoming_supply_date_limit()
        self.incoming_dlt_qty = 0
        self.incoming_outside_dlt_qty = 0
        supply_by_days = supply_dict.get(self.item_code) or []
        for delivery_date, uom, qty in supply_by_days:
            qty = get_item_stock_uom_qty(self.item_code, uom, qty)
            if delivery_date<= date_to:
                self.incoming_dlt_qty += qty
            else:        
                self.incoming_outside_dlt_qty += qty                 

    def _calc_incoming_dlt_qty(self):
        date_to = self._get_incoming_supply_date_limit()
        self.incoming_dlt_qty = 0
        self.incoming_outside_dlt_qty = 0
        supply_by_days = supply_dict.get(self.item_code) or []
        for delivery_date,uom, qty in supply_by_days:
            qty = get_item_stock_uom_qty(self.item_code, uom, qty)
            if delivery_date<= date_to:
                self.incoming_dlt_qty += qty
            else:        
                self.incoming_outside_dlt_qty += qty                 
# """         if self.procurement_type == "purchased":
#             cut_date = self._get_incoming_supply_date_limit()            
#             pols = self.purchase_line_ids.filtered(
#                 lambda l: l.date_planned > to_datetime(cut_date)
#                 and l.order_id.state in ("draft", "sent")
#             )
#             self.rfq_outside_dlt_qty = sum(pols.mapped("product_qty"))
#         else:
#             self.rfq_outside_dlt_qty = 0.0
#  """        return True

    def _calc_net_flow_position(self):                
        self.net_flow_position = (
            #self.qty_available_not_res
            self.actual_qty               
            + self.incoming_dlt_qty
            - self.qualified_demand
        )
        usage = 0.0
        if self.top_of_green:
            usage = round((self.net_flow_position / self.top_of_green * 100), 2)
        self.net_flow_position_percent = usage
        return True

    def _calc_distributed_source_location(self):
        """Compute source location used for replenishment of distributed buffer
        It follows the rules of the default route until it finds a "Take from
        stock" rule. The source location depends on many factors (route on
        warehouse, product, category, ...), that's why it is updated only
        on refresh of the buffer.
        """
        record = self
        
    def _calc_planning_priority(self):        
        if self.net_flow_position >= self.top_of_yellow:
            self.planning_priority_level = "3_Green"
        elif self.net_flow_position >= self.top_of_red:
            self.planning_priority_level = "2_Yellow"
        else:
            self.planning_priority_level = "1_Red"

    def _calc_execution_priority(self):        
        if self.qty_available_not_res >= self.top_of_red:
            self.execution_priority_level = "3_Green"
        elif self.qty_available_not_res >= self.top_of_red * 0.5:
            self.execution_priority_level = "2_Yellow"
        else:
            self.execution_priority_level = "1_Red"
        if self.top_of_red:
            self.on_hand_percent = round(
                (
                    (self.qty_available_not_res / self.top_of_red)
                    * 100
                ),
                2,
            )
        else:
            self.on_hand_percent = 0.0

    def _procure_qty_to_order(self, rounding):
        qty_to_order = self.procure_recommended_qty
        #rounding = get_precision(self.meta.doctype, 'procure_uom')
        if (
            self.procurement_type == "Transfer"
            and frappe.db.get_value('Buffer Profile', self.buffer_profile, 'replenish_distributed_limit_to_free_qty')
        ):
            # If we don't procure more than what we have in stock, we prevent backorders on the replenishment
            if (
                flt(self.distributed_source_location_qty, rounding) -
                flt(self.procure_min_qty,rounding) < 0
            ):
                # the free qty is below the minimum we want to move, do not move anything
                return 0
            else:
                # move only what we have in stock
                return min(qty_to_order, self.distributed_source_location_qty)
        return qty_to_order

    def do_auto_procure(self):
        #if not self.auto_procure:
        #    return False
        #rounding = get_precision(self.meta.doctype, 'procure_uom')
        qty_to_order = self._procure_qty_to_order(3)
        procurement_type = self.procurement_type
        
        if qty_to_order:                        
            new_order = {   'plant':self.plant,
                            'material':self.item_code,
                            'proposed': 1,
                            'open_qty': qty_to_order,
                            'uom':self.procure_uom or self.uom,                            
                            'due_date': date.today() + timedelta(days=self.dlt),
                            'partner': '',
                            'sync_status':'Pending',
                            'remarks':''
                }
            if procurement_type == "Buy":
                source_list = source_list_dict.get(self.item_code) or []
                new_order['order_category'] = 'Purchase Order'
                                
                if not source_list:
                    msg = f'missing source list for item {self.item_code}'
                    print(msg)
                    new_order['sync_status'] = 'Blocked'
                    new_order['remarks'] = msg
                else:
                    for source in source_list:                    
                        new_order['partner'] = source.get('supplier')
                        quota = source.get('quota_percent')
                        if quota:
                            new_order['open_qty'] = qty_to_order * quota
                            new_order['remarks'] = f'Applied quota {quota}'
                        else:
                            break
            else:
                new_order['order_category'] = 'Production Order'
            new_orders.append(new_order)
        return True

    def _prepare_history_data(self):        
        data = {
            "stock_buffer": self.name,
            "item_code":self.item_code,
            "plant": self.plant,
            "date": now(),
            "name": '%s-%s-%s' %(self.item_code,self.plant,today()),
            "top_of_red": self.top_of_red,
            "top_of_yellow": self.top_of_yellow,
            "top_of_green": self.top_of_green,
            "on_hand_position": self.qty_available_not_res,
            "supply": self.incoming_dlt_qty,
            "demand": self.qualified_demand,
            "on_hand_position": self.qty_available_not_res,
            "adu": self.adu,
        }
        return data

    def get_planning_history_chart(self):
        def stacked(df, categories):
            areas = {}
            last = np.zeros(len(df[categories[0]]))
            for cat in categories:
                _next = last + df[cat]
                areas[cat] = np.hstack((last[::-1], _next))
                last = _next
            return areas
        
        history = frappe.get_all("DDMRP History", filters={"stock_buffer": self.name},
            fields='*',  order_by="date")
        if len(history) < 2:
            return 

        N = len(history)
        categories = ["top_of_red", "top_of_yellow", "top_of_green",
                    "net_flow_position","on_hand_position","supply","demand"]
        data = {}

        dates = [r.date for r in history]
        data["date"] = dates
        data[categories[0]] = [r.top_of_red for r in history]
        data[categories[1]] = [r.top_of_yellow - r.top_of_red for r in history]
        data[categories[2]] = [r.top_of_green - r.top_of_yellow for r in history]
        data[categories[3]] = [r.net_flow_position for r in history]
        data[categories[4]] = [r.on_hand_position for r in history]
        data[categories[5]] = [r.supply for r in history]
        data[categories[6]] = [r.demand for r in history]

        df = pd.DataFrame(data)
        df = df.set_index(["date"])

        areas = stacked(df, categories)

        x2 = np.hstack((data["date"][::-1], data["date"]))

        tops = [
            max([
                data[categories[0]][i] + data[categories[1]][i] + data[categories[2]][i],
                data[categories[3]][i],
                data[categories[4]][i],
                data[categories[5]][i],
                data[categories[6]][i]                
            ])
            for i in range(N)
        ]
        top_y = max(tops)
        p = figure(
            x_range=(dates[0], dates[-1]),
            y_range=(0, top_y),
            x_axis_type="datetime",
        )
        p.sizing_mode = "stretch_both"
        p.toolbar.logo = None

        p.grid.minor_grid_line_color = "#eeeeee"
        p.patches(
            [x2] * len(areas),
            [areas[cat] for cat in categories],
            color=PLANING_COLORS,
            alpha=0.8,
            line_color=None,
        )
        date_format = frappe.utils.DATE_FORMAT
        p.xaxis.formatter = DatetimeTickFormatter(
            #hours=date_format,
            days=date_format,
            months=date_format,
            years=date_format,
        )
        p.xaxis.major_label_orientation = pi / 4
        p.xaxis.axis_label_text_font = "helvetica"

        unit = self.uom
        hover = HoverTool(
            tooltips=[("qty", "$y %s" % unit)], point_policy="follow_mouse"
        )
        p.add_tools(hover)
        
        p.line(dates, data["on_hand_position"], line_width=3, line_dash="dotted")
        p.line(dates, data["supply"], line_width=3)
        p.line(dates, data["demand"], line_width=3)
        p.line(dates, data["net_flow_position"], line_width=3)

        script, div = components(p)
        script = script[33:-10] # remove script tag <script type="text/javascript">js code</script>'
        return div, script

    def get_execution_history_chart(self):
        start_stack = 0

        def stacked(df, categories):
            areas = {}
            last = np.zeros(len(df[categories[0]]))
            last += start_stack
            for cat in categories:
                _next = last + df[cat]
                areas[cat] = np.hstack((last[::-1], _next))
                last = _next
            return areas
        dt = "DDMRP History"
        filters = {"stock_buffer": self.name}
        history_oh = frappe.get_all(dt, filters=filters, fields='on_hand_position',
            order_by="on_hand_position desc", limit=1
        )
        if not history_oh: return 

        history_tog = frappe.get_all(dt, filters=filters, fields='top_of_green',
            order_by ="top_of_green desc", limit=1
        )
        finish_stack = max(history_oh[0].on_hand_position, history_tog[0].top_of_green)

        history = frappe.get_all(dt, filters=filters, fields='on_hand_position',
             order_by="on_hand_position asc", limit=1
        )
        start_stack = history[0].on_hand_position
        if start_stack >= 0.0:
            start_stack = 0.0
        
        history = frappe.get_all(dt, filters=filters, fields='*', order_by="date")
        if len(history) < 2:            
            return

        N = len(history)

        categories = [
            "dark_red_low",
            "top_of_red_low",
            "top_of_yellow_low",
            "top_of_green",
            "top_of_yellow",
            "top_of_red",
            "dark_red",
        ]
        data = {}

        dates = [r.date for r in history]
        data["date"] = dates
        data[categories[0]] = [(0 - start_stack) for r in history]
        data[categories[1]] = [(r.top_of_red / 2) for r in history]
        data[categories[2]] = [(r.top_of_red / 2) for r in history]
        data[categories[3]] = [r.top_of_green - r.top_of_yellow for r in history]
        data[categories[4]] = [
            r.top_of_yellow - r.top_of_red - (r.top_of_green - r.top_of_yellow)
            for r in history
        ]
        data[categories[5]] = [r.top_of_green - r.top_of_yellow for r in history]
        data[categories[6]] = [
            finish_stack
            - r.top_of_red
            - (r.top_of_green - r.top_of_yellow)
            - (r.top_of_yellow - r.top_of_red - (r.top_of_green - r.top_of_yellow))
            - (r.top_of_green - r.top_of_yellow)
            for r in history
        ]

        data["on_hand_position"] = [r.on_hand_position for r in history]

        df = pd.DataFrame(data)
        df = df.set_index(["date"])

        areas = stacked(df, categories)

        x2 = np.hstack((data["date"][::-1], data["date"]))

        tops = [
            data[categories[0]][i]
            + data[categories[1]][i]
            + data[categories[2]][i]
            + data[categories[3]][i]
            + data[categories[4]][i]
            + data[categories[5]][i]
            + data[categories[6]][i]
            for i in range(N)
        ]
        top_y = max(tops)
        p = figure(
            x_range=(dates[0], dates[-1]),
            y_range=(start_stack, top_y),
            x_axis_type="datetime",
        )
        p.sizing_mode = "stretch_both"
        p.toolbar.logo = None

        p.grid.minor_grid_line_color = "#eeeeee"
        p.patches(
            [x2] * len(areas),
            [areas[cat] for cat in categories],
            color=EXECUTION_COLORS,
            alpha=0.8,
            line_color=None,
        )
        date_format = frappe.utils.DATE_FORMAT
        p.xaxis.formatter = DatetimeTickFormatter(
            hours=date_format,
            days=date_format,
            months=date_format,
            years=date_format,
        )
        p.xaxis.major_label_orientation = pi / 4

        unit = self.uom
        hover = HoverTool(
            tooltips=[("qty", "$y %s" % unit)], point_policy="follow_mouse"
        )
        p.add_tools(hover)

        p.line(dates, data["on_hand_position"], line_width=3, line_dash="dotted")

        script, div = components(p)
        script = script[33:-10] # remove script tag <script type="text/javascript">js code</script>'
        return div, script

    def _calc_adu_daf(self):
        """Apply DAFs if existing for the buffer."""        
        dafs_to_apply = daf_dict.get(self.name) or []    
        daf = 1        
        for factor_dict in dafs_to_apply:
            daf *= factor_dict.value
        prev = self.adu
        self.adu *= daf
        if daf != 1:
            create_log("DAF={} applied to {}. ADU: {} -> {}".format(daf, self.name, prev, self.adu),
                item_code = self.item_code, plant = self.plant)
        # Compute generated demand to be applied to components:
        dafs_to_explode = daf_components_dict.get(self.name) or []
        for daf in dafs_to_explode:
            prev = self.adu
            increased_demand = prev * daf.value - prev
            self.explode_demand_to_components(daf, increased_demand, self.uom)        

    def explode_demand_to_components(self, daf, demand, uom_id): 
        """bom_dict={"bom_item":[{'quantity':100, "item_code":component-item,"stock_qty":1},{}]
        """     
        if self.item_code not in bom_dict:
            return

        #this is not needed because no uom conversion needed, bom header quantity on line is available
        def _get_extra_demand(bom, line, buffer_id, factor):
            qty = factor * line.product_qty / bom.product_qty
            extra = line.product_uom_id._compute_quantity(qty, buffer_id.product_uom)
            return extra

        def _create_demand(bom_item, factor=1, level=0, clt=0):
            demand_list = []
            level += 1
            item_plant_doc = item_plant_dict.get(bom_item)
            in_house_production_time = item_plant_doc and item_plant_doc.ipt or 0
            clt += in_house_production_time

            for line in bom_dict.get(bom_item) or []:
                if line.item_code in stock_buffer_dict:
                    #buffer_id = line.buffer_id
                    #extra_demand = _get_extra_demand(bom, line, buffer_id, factor)
                    extra_demand = factor * line.stock_qty / line.quantity
                    date_start = daf.date_start - td(days=clt)
                    date_end = daf.date_end - td(days=clt)
                    demand_list.append(
                        {
                            "stock_buffer": '%s_%s' %(line.item_code, self.plant),
                            "item_code": line.item_code,
                            "plant": self.plant,
                            "buffer_origin": self.name,
                            "item_code_origin": self.item_code,
                            "extra_demand": extra_demand,
                            "date_start": date_start,
                            "date_end": date_end,
                        }
                    )                
                child_bom = bom_dict.get(line.item_code)
                if child_bom:
                    line_qty = line.stock_qty
                    new_factor = factor * line_qty / bom[0].quantity
                    _create_demand(line.item_code, new_factor, level, clt)
        #bom uom use item's stock uom, no uom conversion needed
        initial_factor = demand
        demand_list = []
        demand_list.extend(_create_demand(self.item_code, factor=initial_factor) or [])
        if demand_list: insert_multi('DDMRP Adjustment Demand', demand_list)
        return True

def cron_ddmrp_adu(plant=None, item_code=None, automatic=False):
    """calculate ADU for each DDMRP buffer. Called by cronjob."""
    logs.clear()
    create_log("Start cron_ddmrp_adu.", plant = plant)
    filters={'active': 1}
    if item_code: filters['item_code'] = item_code
    if plant: filters['plant'] = plant
    buffers = frappe.get_all('Stock Buffer', fields=['name', 'plant'],
        filters = filters, order_by='plant', as_list = 1)
    i = 0
    j = len(buffers)
    fields = ['name','method_name','calculation_method','source_past','horizontal_past',
            'factor_past','source_future','horizontal_future','factor_future']
    calculation_method_list = frappe.get_all('ADU Calculation Method', fields=fields)
    calculation_method_dict.update({c.name:c for c in calculation_method_list})

    plant = ''
    for b, p in buffers:
        try:
            if p != plant:
                plant = p
                warehouses = get_warehouses(p)
                populate_uom_conversion_dict(plant)                
                sql = """select max(horizontal_past) from `tabADU Calculation Method` cm 
                        inner join `tabStock Buffer` sb on sb.adu_calculation_method = cm.name
                        where cm.calculation_method='past' and source_past='actual' and sb.plant=%s"""
                max_horizontal_past = frappe.db.sql(sql,(plant,)) 
                date_to = date.today() - timedelta(days=-1)
                days = days=max_horizontal_past and max_horizontal_past[0][0] or 365
                date_from = date.today() - timedelta(days=days)
                consumption_list = get_consumption_from_sle(warehouses, date_from=date_from, date_to= date_to)
                stock_ledger_dict.update(convert_to_dict(consumption_list))
                demand_estimate_dict.update(convert_to_dict(get_demand_estimate(plant)))                
                filters = {"adjustment_type":"Demand Adjustment Factor",
                     "plant": plant,
                     "date_start":("<=", today()),
                     "date_end":(">=", today())
                }                
                
                data = frappe.get_all("DDMRP Adjustment", filters = filters, fields=['stock_buffer as name','value'])
                daf_dict.update(convert_to_dict(data))

                filters.pop("date_start")
                data = frappe.get_all("DDMRP Adjustment", filters = filters, 
                    fields=['stock_buffer as name','date_start','date_end', 'value'])
                daf_components_dict.update(convert_to_dict(data))

                bom_dict.update(get_bom_dict(plant))
                data = frappe.get_all('Item Plant', filters={'plant': plant}, 
                    fields=['item_code','ipt','pdt','gr_time','dlt'])
                item_plant_dict.update({d.item_code:d for d in data})
            i += 1
            buffer = frappe.get_doc('Stock Buffer', b)
            create_log("ddmrp cron_adu: {}. ({}/{})".format(buffer.name, i, j), type='Debug',                
                item_code = buffer.item_code, plant = buffer.plant)
            buffer._calc_adu()
            buffer.save()
        except Exception:
            create_log("Fail to compute ADU for buffer %s" % b, type='Error')
            if not automatic:
                raise
    create_log("End cron_ddmrp_adu.", plant = plant)
    if automatic: insert_multi('DDMRP Log', logs)            
    return logs

def cron_actions(self, only_nfp=False):
    """This method is meant to be inherited by other modules in order to  enhance extensibility."""    
    self._compute_dlt()
    self._compute_red_zone()
    self._compute_yellow_zone()
    self._compute_green_zone()
    self._compute_product_available_qty()
    if not only_nfp or only_nfp == "out":
        self._calc_qualified_demand()
    if not only_nfp or only_nfp == "in":
        self._calc_supply()
    self._calc_net_flow_position()
    self._compute_procure_recommended_qty()
    #self._calc_distributed_source_location()
    self._calc_planning_priority()
    self._calc_execution_priority()    
    self.do_auto_procure()    
    return True

def cron_ddmrp(plant=None, item_code=None, automatic=False):
    """Calculate key DDMRP parameters for each buffer.Called by cronjob."""
    logs.clear()
    new_orders.clear()
    create_log("Start cron_ddmrp.", plant = plant)
    filters={'active': 1}
    if plant: filters['plant'] = plant
    if item_code: filters['item_code'] = item_code
    
    buffers = frappe.get_all('Stock Buffer', fields=['name', 'plant'], 
        filters = filters, order_by='plant', as_list = 1)
    i = 0
    j = len(buffers)
    plant = ''
    history_list = []
    for b, p in buffers:
        if p != plant:                        
            warehouses = get_warehouses(p)
            plant = p
            populate_uom_conversion_dict(plant)
            sap_interface = frappe.db.get_value('DDMRP Settings', None, 'sap_interface_active')

            on_hand_dict.update(convert_to_dict(get_on_hand(warehouses)))
            demand_dict.update(convert_to_dict(get_demand(warehouses, plant=plant, sap_interface=sap_interface)))
            supply_dict.update(convert_to_dict(get_supply(warehouses, plant=plant, sap_interface=sap_interface)))
            filters = {"adjustment_type":"Lead Time Adjustment Factor",
                     "plant": plant,
                     "date_start":("<=", today()),
                     "date_end":(">=", today())
            }
            fields=['stock_buffer as name','value']
            data = frappe.get_all("DDMRP Adjustment", filters = filters, fields = fields)
            ltaf_dict.update(convert_to_dict(data))
            
            filters.update({"adjustment_type":"Demand Adjustment Factor"})
            data = frappe.get_all("DDMRP Adjustment", filters = filters, fields = fields)
            daf_dict.update(convert_to_dict(data))

            sql = """select bf.name, ltf.value lead_time_factor, vf.value variability_factor
                from `tabBuffer Profile` bf 
                    join `tabLead Time Factor` ltf  on bf.lead_time_factor= ltf.name
                    join `tabVariability Factor` vf on bf.variability_factor=vf.name"""
            data = frappe.db.sql(sql, as_dict=1)                    
            buffer_profile_dict.update({d.name:d for d in data})

            #remove previous history data to allow run ddmrp again manually
            frappe.db.delete('DDMRP History',{'plant':plant, 'date': today()})

            data = frappe.get_all('Item Plant', filters={'plant': plant}, 
                    fields=['item_code','ipt','pdt','gr_time','dlt'])
            item_plant_dict.update({d.item_code:d for d in data})

            filters.pop("date_start")
            data = frappe.get_all("DDMRP Adjustment", filters = filters, 
                fields=['stock_buffer as name','date_start','date_end','value'])
            daf_components_dict.update(convert_to_dict(data))

            fields = ['item_code as name', 'supplier', 'quota_percent']
            data = frappe.get_all("Source List", fields = fields, filters={'plant':plant})
            source_list_dict.update(convert_to_dict(data))

            #calc_dependent_demand(plant)

        i += 1
        buffer = frappe.get_doc('Stock Buffer', b)
        create_log("ddmrp cron: {}. ({}/{})".format(buffer.name, i, j), type='Debug',
            item_code = buffer.item_code, plant = buffer.plant)
        try:                        
            cron_actions(buffer)
            history_list.append(buffer._prepare_history_data())
            buffer.save()
        except Exception:
            create_log("Fail updating buffer %s" % buffer.name, type='Error',
                item_code = buffer.item_code, plant = buffer.plant)
            if not automatic:
                raise
    if history_list: insert_multi('DDMRP History', history_list)
    pprint(new_orders)
    if new_orders: insert_multi('Open Orders', new_orders)          
    create_log("End cron_ddmrp.", plant = plant)
    if automatic: insert_multi('DDMRP Log', logs)            
    return logs

def calc_dependent_demand(plant, debug=False):
    """derive dependent demand for component of sales order items' BOM""" 

    def get_bom_no(item_code):
        """get bom no, first active bom or the is default one if exist"""
        bom_no = ''
        bom_list = bom_header_dict.get(item_code) or []
        for bom in bom_list:
            bom_no = bom.bom_no if not bom_no else bom_no
            if bom.is_default:
                bom_no = bom.bom_no
                break

        return bom_no

    def get_bom_items(bom_no, req_qty, start_date):
        result = []
        bom_items_list = bom_dict.get(bom_no) or []
        for bom_item in bom_items_list:
            bom_item.qty = req_qty * bom_item.stock_qty / bom_item.quantity
            bom_item.date = start_date
            if debug: print('component %s' % bom_item)
            if stock_buffer_dict.get(bom_item.item_code):
                result.append(bom_item)
            if bom_item.procurement_type == 'Manufacture':
                if debug: print(bom_item.item_code, bom_item.qty, bom_item.date)
                result.extend(get_bom_items(bom_item.bom_no, bom_item.qty, start_date))
        if debug: print('result = %s' % result[:2])                        
        return result

    def update_dependent_demand(item_code, bom_items):
        """[[delivery date, qty],]"""
        dependent_demand = dependent_demand_dict.get(item_code)
        if dependent_demand:
            dependent_demand_dict[item_code] = dependent_demand_dict[item_code].extend(bom_items)
        else:
            dependent_demand_dict[item_code] = bom_items
            
    sap_interface = frappe.db.get_value('DDMRP Settings', None, 'sap_interface_active')
    warehouses = get_warehouses(plant)
    populate_uom_conversion_dict(plant)
    sales_order_list = get_demand(warehouses=warehouses, plant=plant, with_order_detail=True, 
        sap_interface=sap_interface)

    bom_dict.clear()
    fields=['name','item as parent_item_code', 'quantity','`tabBOM Item`.item_code',
        '`tabBOM Item`.stock_uom','`tabBOM Item`.stock_qty','`tabBOM Item`.bom_no']
    filters={'docstatus':1,'is_default':1, 'plant': plant}
    bom_list = frappe.get_all('BOM', filters= filters, fields = fields)    
    bom_dict.update(convert_to_dict(bom_list) )

    bom_header_dict.clear()
    filters.pop('is_default',None)
    fields = ['item as name','name as bom_no','is_default']
    bom_list = frappe.get_all('BOM', filters= filters, fields = fields)    
    bom_dict.update(convert_to_dict(bom_list))

    dependent_demand_dict.clear()

    for (start_date, _, _, _, item_code,uom, qty) in sales_order_list:
        qty = get_item_stock_uom_qty(item_code, uom, qty)
        bom_no = get_bom_no(item_code)
        bom_items = get_bom_items(bom_no, qty, start_date)
        if bom_items:
            update_dependent_demand(item_code, [[b.date,b.qty] for b in bom_items]) 

def populate_uom_conversion_dict(plant):
    """{'10615121': [('PC', 1.0)], '11257409': [('Nos', 1.0)]}"""
    if uom_conversion_dict:
        return
    s = """select item.name, ucd.uom, ucd.conversion_factor from tabItem item inner join
        `tabUOM Conversion Detail` ucd on ucd.parent = item.name inner join
        `tabItem Plant` ip on ip.item_code=item.name where plant = %s"""
    uom_conversion_list = frappe.db.sql(s,(plant,))
    uom_conversion_dict.update(convert_to_dict(uom_conversion_list))

def get_item_stock_uom_qty(item_code, uom, qty):
    """uom_conversion_dict data structure {'item_code':['uom',conversion_factor]}
       e.g {'10615121': [('PC', 'PC', 1.0)], '11257409': [('Nos', 'Nos', 1.0)]}
    """
    conversion = 1
    ucd_list = uom_conversion_dict.get(item_code) or []
    for ucd in ucd_list:
        if ucd[0] == uom:
            conversion = ucd[1]
            break
    return qty * conversion
	
def create_log(msg='', type='Info', item_code='', plant=''):
    logs.append({'source':'Stock Buffer',
            'type': type,
            'item_code': item_code,
            'plant': plant,
            'message': msg  
        }
    )    