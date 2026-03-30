from odoo import models, fields

class InventoryCount(models.Model):
    _inherit = 'bhx.inventory.count'

    alert_id = fields.Many2one('bhx.stock.alert', string='Từ cảnh báo tồn kho', readonly=True)

class GoodsControl(models.Model):
    _inherit = 'bhx.goods.control'

    alert_id = fields.Many2one('bhx.stock.alert', string='Từ cảnh báo tồn kho', readonly=True)

class Disposal(models.Model):
    _inherit = 'bhx.disposal'

    alert_id = fields.Many2one('bhx.stock.alert', string='Từ cảnh báo tồn kho', readonly=True)
