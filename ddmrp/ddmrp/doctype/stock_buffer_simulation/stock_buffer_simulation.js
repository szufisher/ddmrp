// Copyright (c) 2021, Fisher and contributors
// For license information, please see license.txt

frappe.ui.form.on('Stock Buffer Simulation', {
	refresh: function(frm) {
		frm.get_field('simulate').$wrapper.find('button').attr('class','btn btn-primary btn-default')
		var versions = [1,2,3]
		versions.forEach((suffix)=>{
			frm.call("get_planning_history_chart",{'suffix':suffix}).then((r)=>{			
				if(r.message){
					var chart = r.message;
					//console.log(chart[1].length);
					//console.log(chart[1]);
					frm.events['show_chart'](frm, 'ddmrp_chart'+suffix, chart[0], chart[1])								
				}
			});
		})		
	},
	show_chart: function(frm, field, chart_div, chart_script){
		frm.get_field(field).html(chart_div);
		var script = document.createElement('script');
		script.innerHTML = chart_script;
		document.body.appendChild(script);
	},
	simulate: function(frm){
		frappe.call({method:"simulate",
                    doc:frm.doc,
                    freeze: true,
                    freeze_message:__('Running...')}).then((r)=>{			
            if(r.message){
				frm.refresh();
				console.log(r.message);
				frappe.msgprint(r.message, 'process ok'); 
			}				
		});
	}
});
