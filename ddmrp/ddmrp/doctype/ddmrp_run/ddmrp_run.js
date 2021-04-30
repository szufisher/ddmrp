// Copyright (c) 2021, Fisher and contributors
// For license information, please see license.txt

frappe.ui.form.on('DDMRP Run', {
	refresh: function(frm) {
		frm.disable_save();
	},
	run: function(frm){
		frm.call("run").then((r)=>{
			console.log(r);
            if(r.message){
				frappe.msgprint('Action Done, for details please check logs')
			}				
		});
	}
});