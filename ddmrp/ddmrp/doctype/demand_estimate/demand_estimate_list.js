frappe.listview_settings['Demand Estimate'] = {	
	onload: function(listview) {
		listview.page.add_actions_menu_item(__("Create Components Demand Estimate"), function() {
            const docnames = listview.get_checked_items(true).map(docname => docname.toString());
            frappe
			.call({
				method: 'ddmrp.ddmrp.doctype.demand_estimate.demand_estimate.create_demand',
				freeze: true,
				args: {
					docnames: docnames					
				}
			})
			.then((r) => {
                let cnt = r.message;
                if (cnt) frappe.msgprint('Created ' + cnt + ' demand estimate records')
			});           
		});
	}
};