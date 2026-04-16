from odoo import models, fields, api, _
from datetime import timedelta

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
        ('alert', 'Cảnh báo Date/Kiểm kê'),
        ('empty_shelf', 'Xử lý kệ trống'),
        ('pos', 'Bán hàng POS'),
        ('count', 'Kiểm kê'),
        ('goods_ctrl', 'Kiểm soát hàng hóa'),
        ('disposal', 'Xử lý hàng'),
        ('adjustment', 'Điều chỉnh tồn kho'),
        ('overstock_withdrawal', 'Rút hàng quá tải')
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
            elif rec.code == 'empty_shelf':
                rec.count_pending = self.env['bhx.stock.alert'].search_count([
                    ('state', 'in', ['new', 'processing']),
                    ('alert_type', 'in', ['low_stock', 'out_of_stock'])
                ])
            elif rec.code == 'alert':
                # Đếm cảnh báo (Hết hạn, Sắp hết hạn, Yêu cầu kiểm kê, Yêu cầu kiểm soát) 
                # Chốt: Hiển thị nếu là Kiểm kê/Kiểm soát HOẶC có Hạn sử dụng < 30 ngày (bất kể loại nào)
                today = fields.Date.today()
                limit_date = fields.Date.to_string(today + timedelta(days=30))
                rec.count_pending = self.env['bhx.stock.alert'].search_count([
                    ('state', 'in', ['new', 'processing']),
                    '|',
                    ('alert_type', 'in', ['audit_required', 'control_required']),
                    '&', ('expiry_date', '!=', False), ('expiry_date', '<', limit_date)
                ])
            elif rec.code == 'pos':
                # Giả sử POS thì số đơn hàng hôm nay
                rec.count_pending = self.env['bhx.sales.order'].search_count([('state', '=', 'draft')])
            elif rec.code == 'count':
                rec.count_pending = self.env['bhx.inventory.count'].search_count([('state', 'in', ['draft', 'in_progress', 'review'])])
            elif rec.code == 'goods_ctrl':
                rec.count_pending = self.env['bhx.goods.control'].search_count([('state', '=', 'draft')])
            elif rec.code == 'disposal':
                rec.count_pending = self.env['bhx.disposal'].search_count([('state', 'in', ['draft', 'confirm'])])
            elif rec.code == 'adjustment':
                rec.count_pending = self.env['bhx.stock.adjustment'].search_count([('state', 'in', ['draft', 'confirm', 'approved'])])
            elif rec.code == 'overstock_withdrawal':
                rec.count_pending = self.env['bhx.stock.alert'].search_count([
                    ('alert_type', '=', 'overstock'),
                    ('state', 'in', ['new', 'processing'])
                ])
            else:
                rec.count_pending = 0

    def action_open_records(self):
        self.ensure_one()
        action = {}
        if self.code == 'fmcg':
            action = self.env.ref('bhx_import_goods.action_fmcg_import').sudo().read()[0]
            action['domain'] = [('state', 'in', ['draft', 'checking'])]
        elif self.code == 'fresh':
            action = self.env.ref('bhx_import_goods.action_fresh_import').sudo().read()[0]
            action['domain'] = [('state', 'in', ['draft', 'receiving', 'temp_check'])]
        elif self.code == 'fruit':
            action = self.env.ref('bhx_import_goods.action_fruit_veg_import').sudo().read()[0]
            action['domain'] = [('state', 'in', ['draft', 'receiving', 'quality_check'])]
        elif self.code == 'replenish':
            action = self.env.ref('bhx_inventory_display.action_bhx_replenishment').sudo().read()[0]
            action['domain'] = [('state', 'in', ['draft', 'in_progress'])]
        elif self.code == 'empty_shelf':
            action = self.env.ref('bhx_inventory_display.action_stock_alert').sudo().read()[0]
            action['domain'] = [
                ('state', 'in', ['new', 'processing']),
                ('alert_type', 'in', ['low_stock', 'out_of_stock'])
            ]
        elif self.code == 'alert':
            today = fields.Date.today()
            limit_date = fields.Date.to_string(today + timedelta(days=30))
            action = self.env.ref('bhx_inventory_display.action_stock_alert').sudo().read()[0]
            action['domain'] = [
                ('state', 'in', ['new', 'processing']),
                '|',
                ('alert_type', 'in', ['audit_required', 'control_required']),
                '&', ('expiry_date', '!=', False), ('expiry_date', '<', limit_date)
            ]
        elif self.code == 'pos':
            action = self.env.ref('bhx_sales.action_sales_order').sudo().read()[0]
            action['domain'] = [('state', '=', 'draft')]
        elif self.code == 'count':
            action = self.env.ref('bhx_audit_control.action_inventory_count').sudo().read()[0]
            action['domain'] = [('state', 'in', ['draft', 'in_progress', 'review'])]
        elif self.code == 'goods_ctrl':
            action = self.env.ref('bhx_audit_control.action_goods_control').sudo().read()[0]
            action['domain'] = [('state', '=', 'draft')]
        elif self.code == 'disposal':
            action = self.env.ref('bhx_audit_control.action_disposal').sudo().read()[0]
            action['domain'] = [('state', 'in', ['draft', 'confirm'])]
        elif self.code == 'adjustment':
            action = self.env.ref('bhx_inventory_display.action_stock_adjustment').sudo().read()[0]
            action['domain'] = [('state', 'in', ['draft', 'confirm', 'approved'])]
        elif self.code == 'overstock_withdrawal':
            action = self.env.ref('bhx_inventory_display.action_stock_alert').sudo().read()[0]
            action['domain'] = [
                ('alert_type', '=', 'overstock'),
                ('state', 'in', ['new', 'processing'])
            ]
        
        # Override name to show it's filtered
        if 'name' in action:
            action['name'] = '%s (Cần xử lý)' % action['name']
        return action
