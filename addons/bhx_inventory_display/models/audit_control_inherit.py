from odoo import models, fields

class InventoryCount(models.Model):
    _inherit = 'bhx.inventory.count'

    alert_id = fields.Many2one('bhx.stock.alert', string='Từ cảnh báo tồn kho', readonly=True)

    def action_approve(self):
        res = super(InventoryCount, self).action_approve()
        if self.alert_id:
            self.alert_id.write({
                'state': 'resolved',
                'note': f'[Tự động] Đóng cảnh báo thông qua phiếu kiểm kê {self.name}'
            })
        return res

class GoodsControl(models.Model):
    _inherit = 'bhx.goods.control'

    alert_id = fields.Many2one('bhx.stock.alert', string='Từ cảnh báo tồn kho', readonly=True)

    def action_done(self):
        res = super(GoodsControl, self).action_done()
        if self.alert_id:
            self.alert_id.write({
                'state': 'resolved',
                'note': f'[Tự động] Đóng cảnh báo thông qua phiếu kiểm soát {self.name}'
            })
        return res

class Disposal(models.Model):
    _inherit = 'bhx.disposal'

    alert_id = fields.Many2one('bhx.stock.alert', string='Từ cảnh báo tồn kho', readonly=True)
    
    def action_approve(self):
        res = super(Disposal, self).action_approve()
        if self.alert_id:
            self.alert_id.write({
                'state': 'resolved', 
                'note': f'[Tự động] Đóng cảnh báo thông qua phiếu huỷ hàng {self.name}'
            })
        return res
