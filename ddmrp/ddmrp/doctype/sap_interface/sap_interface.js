// Copyright (c) 2021, Fisher and contributors
// For license information, please see license.txt

frappe.ui.form.on('SAP Interface', {
	refresh: function(frm) {
        frm.disable_save();
        frm.get_field('run').$wrapper.find('button').attr('class','btn btn-primary btn-default')
	},
	run: function(frm){
        frappe.call({method:"run",
                    doc:frm.doc,
                    freeze: true,
                    freeze_message:__('Running...')}).then((r)=>{			
            if(r.message){
				console.log(r.message);
				frappe.msgprint(r.message, 'process ok'); 
			}				
		});
	}
});
