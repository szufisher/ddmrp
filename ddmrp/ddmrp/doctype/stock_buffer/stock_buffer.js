// Copyright (c) 2020, Fisher and contributors
// For license information, please see license.txt

frappe.ui.form.on('Stock Buffer', {
	refresh: function(frm) {
		if(frm.doc.active > 0) {
			frm.add_custom_button(__('Item Plant'), function() {				
				frappe.
					db.get_value('Item Plant', {'item_code': frm.doc.item_code, 'plant':frm.doc.plant},'name')
					.then(
						(r)=>{								
							frappe.set_route('Form','Item Plant', r.message.name)
					})
			}, __('View'));

			frm.add_custom_button(__('Stock Requirements List'), function() {
				frappe.route_options = {
					"plant": frm.doc.plant,
					"item_code": frm.doc.item_code,					
				};
				frappe.set_route("query-report", "Stock Requirements List");
			}, __('View'));
			
		};		
		frm.call("get_ddmrp_chart").then((r)=>{			
            if(r.message){
				var chart = r.message;
				frm.events['show_chart'](frm, 'buffer_summary', chart[0], chart[1])								
            }
		});
		frm.call("get_ddmrp_demand_supply_chart").then((r)=>{
			console.log(r);
            if(r.message){
				const charts = ['demand_chart','supply_chart'];	
				charts.forEach((chart_name,i)=>{
					var chart = r.message[chart_name];
					if (chart)	frm.events['show_chart'](frm, chart_name, chart[0], chart[1])
				})
			}				
		});
		frm.call("get_planning_history_chart").then((r)=>{			
            if(r.message){
				var chart = r.message;
				frm.events['show_chart'](frm, 'planning_history_chart', chart[0], chart[1])								
            }
		});
		frm.call("get_execution_history_chart").then((r)=>{			
            if(r.message){
				var chart = r.message;
				frm.events['show_chart'](frm, 'execution_history_chart', chart[0], chart[1])								
            }
		});
	},
	show_chart: function(frm, field, chart_div, chart_script){
		frm.get_field(field).html(chart_div);
		var script = document.createElement('script');
		script.innerHTML = chart_script;
		document.body.appendChild(script);
	}
})