frappe.listview_settings['Stock Buffer'] = {
	fields: ["actual_qty", "incoming_dlt_qty", "qualified_demand",
		"net_flow_position", "procure_recommended_qty",
		"planning_priority_level","execution_priority_level"],
	total_fields : 12,	
	refresh: function(){		
		this.set_field_color('execution_priority_level', 'actual_qty');
		this.set_field_color('planning_priority_level','net_flow_position');
	},
	onload: function(){
		this.refresh();
	},
	_set_field_color: function (fieldname, field, color) {
		var cells = $(`div.frappe-list > div.result div.list-row [data-filter^=${fieldname}]`);
		var my_color, value;
		cells.each(function () {
			value = $(this).attr('data-filter');
			value = value && value.split(',=,')[1] || undefined;
			my_color = value && value.split("_")[1].toLowerCase() || undefined;			
			if (my_color) {
				$(this).parents('.list-row').find('div a[data-filter^="' + field + '"] div').css('background', my_color).css('color', 'black');
				//$(this).css('background', my_color).css('color', 'black');				
			}
			console.log($(this).find('div')[0]);
		});
	},
	get set_field_color() {
		return this._set_field_color;
	},
	set set_field_color(value) {
		this._set_field_color = value;
	},
	color_cell: function(fieldname, value1=3000, value2=1000){
		var cells = $(`div.frappe-list > div.result div.list-row a[data-filter^=${fieldname}]`)
		var my_color, value
		cells.each(function(){
			value = $(this).attr('data-filter');
			value = parseFloat(value.split(',=,')[1]);
			if (value >= value1){
				my_color = 'green'
			}else if (value >= value2) {
				my_color = 'yellow'
			}else{
				my_color = 'red'
			}
			console.log(my_color);
			$(this).find('div').css('background',my_color).css('color','black');
			console.log($(this).find('div')[0]);
		})	
	},
	
	formatters:{
		//actual_qty: function(value, df, doc){
		//	console.log(doc);		
		//	return this.get_cell_color(doc, value, 'execution_priority_level') || value;			
		//},
		//net_flow_position: function(value, df, doc){
		//	return this.get_cell_color(doc, value, 'planning_priority_level') || value;			
		//},
		get_cell_color: function(doc, value, fieldname){
			var color_field = doc[fieldname];						
			let color = color_field && color_field.split("_")[1].toLowerCase() || undefined;
			console.log('color')
			console.log(color)
			if (color){
				value =`<div style='margin:0px;padding-left:5px;background-color:${color}!important;'>${value}</div>`            
			}
			console.log(value)		
			return value;
		}
	}
};