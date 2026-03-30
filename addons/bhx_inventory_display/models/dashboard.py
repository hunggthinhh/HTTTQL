from odoo import models, fields, api, _

class InventoryDashboard(models.Model):
    _name = 'bhx.inventory.dashboard'
    _description = 'Thẻ Nghiệp vụ Bách Hóa Xanh'
    _order = 'sequence, id'

    name = fields.Char(string='Tên Nghiệp vụ', required=True)
    sequence = fields.Integer(string='Thứ tự', default=10)
    code = fields.Selection([
        ('fmcg', 'Kiểm hàng FMCG'),
        ('fresh', 'Nhập hàng Tươi Sống'),
        ('fruit', 'Nhập Rau Củ Quả'),
        ('replenish', 'Đợt châm hàng'),
        ('alert', 'Cảnh báo Tồn/Date'),
        ('pos', 'Bán hàng POS')
    ], string='Mã nghiệp vụ', required=True)
    color = fields.Integer(string='Color Index', default=0)
    
    count_pending = fields.Integer(
        string='Số lượng Cần xử lý',
        compute='_compute_count_pending'
    )

    def _compute_count_pending(self):
        for rec in self:
            if rec.code == 'fmcg':
                rec.count_pending = self.env['bhx.fmcg.import'].search_count([('state', 'in', ['draft', 'checking'])])
            elif rec.code == 'fresh':
                rec.count_pending = self.env['bhx.fresh.import'].search_count([('state', 'in', ['draft', 'receiving', 'temp_check'])])
            elif rec.code == 'fruit':
                rec.count_pending = self.env['bhx.fruit.veg.import'].search_count([('state', 'in', ['draft', 'receiving', 'quality_check'])])
            elif rec.code == 'replenish':
                rec.count_pending = self.env['bhx.replenishment'].search_count([('state', 'in', ['draft', 'in_progress'])])
            elif rec.code == 'alert':
                # Đếm tất cả cảnh báo mới hoặc đang xử lý (Hết hạn, Sắp hết hạn, Sắp hết hàng, Hết hàng)
                count = self.env['bhx.stock.alert'].search_count([
                    ('state', 'in', ['new', 'processing']),
                    ('alert_type', 'in', ['low_stock', 'out_of_stock', 'near_expiry', 'expired'])
                ])
                rec.count_pending = count
            elif rec.code == 'pos':
                # Giả sử POS thì số đơn hàng hôm nay
                rec.count_pending = self.env['bhx.sales.order'].search_count([('state', '=', 'draft')])
            else:
                rec.count_pending = 0

    def action_open_records(self):
        self.ensure_one()
        action = {}
        if self.code == 'fmcg':
            action = self.env.ref('bhx_import_goods.action_fmcg_import').read()[0]
            action['domain'] = [('state', 'in', ['draft', 'checking'])]
        elif self.code == 'fresh':
            action = self.env.ref('bhx_import_goods.action_fresh_import').read()[0]
            action['domain'] = [('state', 'in', ['draft', 'receiving', 'temp_check'])]
        elif self.code == 'fruit':
            action = self.env.ref('bhx_import_goods.action_fruit_veg_import').read()[0]
            action['domain'] = [('state', 'in', ['draft', 'receiving', 'quality_check'])]
        elif self.code == 'replenish':
            action = self.env.ref('bhx_inventory_display.action_bhx_replenishment').read()[0]
            action['domain'] = [('state', 'in', ['draft', 'in_progress'])]
        elif self.code == 'alert':
            action = self.env.ref('bhx_inventory_display.action_stock_alert').read()[0]
            action['domain'] = [('alert_type', 'in', ['near_expiry', 'expired'])]
        elif self.code == 'pos':
            action = self.env.ref('bhx_sales.action_sales_order').read()[0]
            action['domain'] = [('state', '=', 'draft')]
        
        # Override name to show it's filtered
        if 'name' in action:
            action['name'] = '%s (Cần xử lý)' % action['name']
        return action
