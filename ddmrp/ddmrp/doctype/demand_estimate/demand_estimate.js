// Copyright (c) 2021, Fisher and contributors
// For license information, please see license.txt

frappe.ui.form.on('Demand Estimate', {
	refresh: function(frm){
		frm.call('check_bom_exist').then( (r)=>{
			console.log(r.message);
			if (r.message && r.message>0){
				console.log('my message reached');
				frm.add_custom_button(__('Generate Components Demand Estimate'), function() {
					frm.call('generate_component_demand_estimate').then( (r)=>{
						console.log(r);
						frappe.msgprint('Created '+ r.message.length + ' component demand records');
					})
				}, __('Create'));
			}
		})
	},
	stock_buffer: function(frm) {
		frm.toggle_enable(['item_code','plant','stock_uom','company'], false);
	}
});

// var data = cur_frm.doc.items;
// data.forEach(function(e){ console.log(e.date);
// if (e.date != '2021-04-25'){console.log(e.idx); console.log('hidden');
// $("[data-idx="+e.idx+"]").hide()
// }
// })
