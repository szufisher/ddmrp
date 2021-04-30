from __future__ import unicode_literals
from frappe import _

def get_data():
	return {
		'fieldname': 'stock_buffer',
		'non_standard_fieldnames': {
			'MRP Move': 'item_plant'			
		},
		'internal_links': {
			
		},
		'transactions': [
			{
				'label': _('ADU Related'),
				'items': ['Demand Estimate']
			},
			{
				'label': _('Adjustment'),
				'items': ['DDMRP Adjustment', 'DDMRP Adjustment Demand']
			},
			{
				'label': _('Demand Related'),
				'items': ['MRP Move']
			},
			{
				'label': _('History'),
				'items': ['DDMRP History']
			}
		]
	}
