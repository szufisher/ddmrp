// Copyright (c) 2021, Fisher and contributors
// For license information, please see license.txt

frappe.ui.form.on('DDMRP Action', {
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
				if(r.message) frm.events.set_table(frm, r.message, "logs"); 
			}				
		});
	},
	set_table: function(frm, message,tablename){
        frm.clear_table(tablename);
        message.forEach(function(doc) {
            var c = frm.add_child(tablename);
            for (const [key, value] of Object.entries(doc)) {                
                c[key] = value;
            }                        
        });
        //frm.grids[0].grid.grid_pagination.setup_pagination();
        frm.get_field(tablename).grid.wrapper.find('.grid-add-row').hide();
        refresh_field(tablename);
        frm.refresh();
    }
});
