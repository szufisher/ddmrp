# -*- coding: utf-8 -*-
# Copyright (c) 2021, Fisher and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
import random
import operator as py_operator
from collections import defaultdict
from datetime import datetime, timedelta, date
from datetime import timedelta as td
from dateutil import parser
from math import pi,sqrt
from frappe.utils import rounded, get_user_date_format, add_days, today, now
from ddmrp.ddmrp.utils import get_precision
try:
    import numpy as np
    import pandas as pd
    from bokeh.plotting import figure
    from bokeh.io import output_file, show
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


class StockBufferSimulation(Document):
    def simulate(self):
        """3 set of fields with suffix, such as adu1, adu2, adu3"""  
        self.save()
        self.reload()   #call from web page, field datetype is str intead of datetime
        actual = self.begin_stock
        suffix = self.version
        dlt = self.dlt
        sigma = self.sigma or dlt * 0.2
        random_dlt = [int(random.normalvariate(dlt, sigma)) for _ in range(len(self.items))]
        supply, receive, available, propose, stock_out_days, total_stock = [0]* 6
        pending_propose = []
        for row_no, d in enumerate(self.items):
            # clear preious simulation remark
            if d.get(f'remark{suffix}'):  d.set(f'remark{suffix}', '')
            
            pending_receive = pending_propose[0] if pending_propose else ''
            if pending_receive and d.date >= pending_receive[0] + timedelta(days=pending_receive[1]):
                receive = pending_receive[-1]
                pending_propose.pop(0)    #FIFO
            else:
                receive = 0
            self.calc_adu(row_no, d, suffix)
            d.set(f'dlt{suffix}', random_dlt.pop()) #set random dlt
            dd_variation, lt_variation = [],[] 
            if self.safety_calc_method != 'Factor':
                dd_variation, lt_variation = self.get_variation(row_no, d, suffix)

            self.calc_buffer_zone(d, suffix, demand_variation= dd_variation, lead_time_variation = lt_variation)            		            
            self.calc_demand(row_no, d, suffix)
            d.set(f'supply{suffix}', supply + propose - receive)
            d.set(f'receive{suffix}', receive)
            d.set(f'actual{suffix}', actual + receive - d.demand)
            available = d.get(f'actual{suffix}') + d.get(f'supply{suffix}')
            d.set(f'available{suffix}', available)
            max_stock = d.get(f'tog{suffix}')
            reorder_point = d.get(f'toy{suffix}')
            propose = max_stock - available if available < reorder_point else 0            
            if row_no <0:
                print(f'max {max_stock}, reorder_point {reorder_point}, available {available}, propose {propose}')
            if propose:
                propose = self.adjust_propose(propose, d, suffix)                        
                pending_propose.append([d.date, d.get(f'dlt{suffix}'), propose])                
            if actual < 0:
                stock_out_days += 1                        
            d.set(f'propose{suffix}', propose)
            supply = d.get(f'supply{suffix}')
            actual = d.get(f'actual{suffix}')
            total_stock += actual
        self.set(f'avg_stock{suffix}', round(total_stock / len(self.items),3) )
        self.set(f'stock_out_days{suffix}', stock_out_days)
        self.set_parameter(suffix)

        self.save()
        msg = f"avg stock {self.get(f'avg_stock{suffix}')}, stock out days:{self.get(f'stock_out_days{suffix}')}"
        return msg

    def set_parameter(self, suffix):
        safety_calc_method = self.safety_calc_method
        param_dict = {
            'ADU': self.adu,
            'ADU Calc': self.adu_calculation_method,
            'ADU Horizon' : self.adu_horizon,
            'Buffer Calc': safety_calc_method,
            'Min Order Qty': self.minimum_order_quantity,
            'Qty Multiple': self.qty_multiple,
            'Order Cycle': self.order_cycle,
            'Spike Horizon': self.order_spike_horizon,
            'Spike threshold': self.order_spike_threshold,
            'Sigma': self.sigma
        }
        if safety_calc_method == 'Factor':
            param_dict.update({
                'Leadtime Factor': self.lead_time_factor,
                'Variability Factor': self.variability_factor
            })
        else:
            param_dict.update({
                'Beta': self.beta,
                'Y': self.y
            })
        p = '\n'.join([f'{_(k)}:{v}' for k,v in param_dict.items()])
        self.set(f'param{suffix}', p)

    def get_variation(self, row_no, row, suffix):
        demand_variation, lead_time_variation = [], []
        horizon = self.adu_horizon        
        rows = self.items        
        for i in range(row_no, row_no - horizon, -1):
            if i >= 0:
                demand_variation.append(rows[i].demand)
                lead_time_variation.append(rows[i].get(f'dlt{suffix}'))

        return demand_variation, lead_time_variation

    def calc_adu(self, row_no, row, suffix):        
        calculation_method = self.adu_calculation_method
        horizon = self.adu_horizon
        if calculation_method == 'Fixed':
            row.set(f'adu{suffix}', self.adu)
        elif calculation_method == 'Consumption':
            current_date = row.date
            end_of_horizon = current_date - timedelta(days = horizon)
            first_date = self.items[0].date            
            rows = self.items
            total_adu = 0
            for i in range(row_no, row_no - horizon, -1):                 
                if i >= 0:                                        
                    end_date = rows[i].date
                    if end_date >= end_of_horizon:
                        total_adu += rows[i].demand
                    else:
                        break

            days = horizon if end_date > first_date else (current_date -  end_date).days + 1
            if row_no < 40: print('calc adu', row_no, first_date, current_date,end_date, end_of_horizon,  days, total_adu)
            row.set(f'adu{suffix}', total_adu / days)

    def calc_buffer_zone(self, row, suffix, demand_variation = [], lead_time_variation = []):                
        adu = row.get(f'adu{suffix}')
        dlt = row.get(f'dlt{suffix}')
        b = self.beta or 1.02
        y = self.y or 1.15
        yellow = adu  * dlt
        if self.safety_calc_method == 'Factor':
            lead_time_factor = self.lead_time_factor or 0
            variability_factor = self.variability_factor or 0
            red_base = yellow * lead_time_factor
            red_safety = red_base * variability_factor
            red = red_base + red_safety
        else:
            cv = lambda x: np.std(x, ddof=1) / np.mean(x)           # * 100            
            red_base = float(adu * (b * sqrt(dlt) + y)) or 0
            red = float(red_base * (1+ sqrt(cv(demand_variation)**2) + cv(lead_time_variation)**2*dlt)) or 0
            #print(f'red_base={red_base}, red={red}')

        green = max(red_base, self.minimum_order_quantity or 0, self.order_cycle * adu)
        if np.isnan(red):
            print(f'row {row} red is none')
            red = 0
                        
        row.set(f'tor{suffix}', red)
        row.set(f'toy{suffix}', red + yellow)
        row.set(f'tog{suffix}', red + yellow + green)	                    

    def calc_demand(self, row_no, row, suffix):
        spike = 0
        threshold = self.order_spike_threshold  or row.get(f'tor{suffix}') * 0.5
        if threshold:
            horizon = self.order_spike_horizon or round(row.get(f'dlt{suffix}'))
            end_of_horizon = row.date + timedelta(days = horizon)            
            rows = self.items            
            max = len(rows)
            msg = []
            for i in range(row_no, row_no + horizon):
                if i < max:                                
                    if rows[i].date > end_of_horizon:
                        break
                    day_qty = rows[i].demand
                    if day_qty > threshold:
                        spike += day_qty
                        msg.append(f'spike {day_qty} on {rows[i].date}')
            if msg: row.set(f'remark{suffix}', '\n'.join(msg))            
            if row_no < 0: print('calc demand', row.date, end_of_horizon, row.demand, spike)                                            
        row.set(f'demand{suffix}', row.demand + spike)

    def adjust_propose(self, adjusted_qty, row, suffix):
        rounding = get_precision(self.doctype, 'uom')
        propose_original = round(adjusted_qty, rounding)
        min_qty = self.minimum_order_quantity
        if adjusted_qty < min_qty:
            adjusted_qty = min_qty                
        # Apply qty multiple and minimum quantity (maximum quantity applies on the procure wizard)
        remainder = self.qty_multiple > 0 and adjusted_qty % self.qty_multiple or 0.0
        if rounded(remainder, precision=rounding) > 0:
            adjusted_qty += self.qty_multiple - remainder
        if rounded(adjusted_qty - min_qty, precision=rounding) < 0:
            adjusted_qty = min_qty
        msg =  f'{propose_original} adjusted to min order qunaity'
        old_remark = row.get(f'remark{suffix}')
        remark = msg if not old_remark else '\n'.join([msg, old_remark])
        row.set(f'remark{suffix}', remark)
        return adjusted_qty

    def get_planning_history_chart(self, suffix ='1'):        
        def stacked(df, categories):
            areas = {}
            last = np.zeros(len(df[categories[0]]))
            for cat in categories:
                _next = last + df[cat]
                areas[cat] = np.hstack((last[::-1], _next))
                last = _next
            return areas
                
        #history = frappe.get_all("DDMRP History", filters={"stock_buffer": "warehouse_计算器"}, fields='*',  order_by="date")
        fields = ["tor", "toy", "tog", "available","actual","supply","demand"]
        history = frappe.get_all("Stock Buffer Simulation Item", filters={"parent": self.name}, fields='*',  order_by="date")
        N = len(history)
        categories = [f'{f}{suffix}' for f in fields]
        #categories = ["top_of_red", "top_of_yellow", "top_of_green", "net_flow_position","on_hand_position","supply","demand"]
        if N < 2 or (N and not history[0].get(f'demand{suffix}')):  # not enough or no simulation data
            return
        data = {}
        dates = [r.date for r in history]
        data["date"] = dates
        for idx, f in enumerate(categories):
            if 0 < idx < 3:
                data[f] = [r.get(f) - r.get(categories[idx-1]) for r in history]
            else:    
                data[f] = [r.get(f) for r in history]                
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
        hover = HoverTool(tooltips=[("qty", "$y %s" % unit)], point_policy="follow_mouse")
        p.add_tools(hover)
        for i, c in enumerate(categories[3:]):
            if i == 2: continue   #skip supply line            
            line_dash = 'dotted' if i==0 else 'solid'
            line_color = 'blue' if i != 2 else 'orange'
            p.line(dates, data[c], line_width=3, line_dash = line_dash)     #line_color = line_color,
        script, div = components(p)
        script = script[33:-10] # remove script tag <script type="text/javascript">js code</script>'
        return div, script
