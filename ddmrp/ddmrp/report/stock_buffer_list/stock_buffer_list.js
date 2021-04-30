frappe.query_reports["stock buffer list"] = {
	"formatter": function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data); 
        console.log(value);        
        let pl = data['Plan Level'];
        let color = pl && pl.split("_")[1].toLowerCase() || undefined;
        if (color && column.fieldname==="Available"){
            //value = "<span style='color:" + color + "'>" + value + "</span>";
            value =`<div style='margin:0px;padding-left:5px;background-color:${color}!important;'>${value}</div>`
        }
        let el = data['Execution Level'];
        let color = el && el.split("_")[1].toLowerCase() || undefined;
        if (color && column.fieldname==="On Hand"){
            value =`<p style='margin:0px;padding-left:5px;background-color:${color}!important;'>${value}</p>`
            //value = "<span style='color:black; background:" + color + "'>" + value + "</span>";
        }		
		return value;
    }    
};