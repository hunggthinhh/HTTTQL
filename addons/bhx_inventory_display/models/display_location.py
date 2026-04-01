from odoo import models, fields, api, _
from odoo.exceptions import UserError


class DisplayLocation(models.Model):
    _name = 'bhx.display.location'
    _description = 'Vị trí trưng bày hàng hoá'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'zone, aisle, shelf_no'

    name = fields.Char(string='Tên vị trí', required=True, tracking=True)
    code = fields.Char(string='Mã vị trí', required=True, copy=False, tracking=True)
    zone = fields.Selection([
        ('fmcg', 'Khu FMCG'),
        ('fruit_veg', 'Khu Rau củ trái cây'),
        ('fresh', 'Khu Hàng Fresh / Đông lạnh'),
        ('personal_care', 'Khu Chăm sóc cá nhân'),
        ('household', 'Khu Gia dụng'),
        ('beverage', 'Khu Đồ uống'),
        ('baby', 'Khu Mẹ & Bé'),
        ('other', 'Khu khác'),
    ], string='Khu vực', required=True, tracking=True)
    location_type = fields.Selection([
        ('shelf', 'Kệ hàng'),
        ('fridge', 'Tủ lạnh / Tủ đông'),
        ('rack', 'Giá đỡ'),
        ('floor', 'Trưng bày sàn'),
        ('end_cap', 'Đầu kệ (End-cap)'),
        ('checkout', 'Khu thu ngân'),
        ('promotion', 'Khu khuyến mãi'),
    ], string='Loại vị trí', required=True, default='shelf')
    aisle = fields.Char(string='Dãy / Lối đi')
    shelf_no = fields.Integer(string='Số kệ')
    level = fields.Selection([
        ('1', 'Tầng 1 (thấp)'),
        ('2', 'Tầng 2'),
        ('3', 'Tầng 3'),
        ('4', 'Tầng 4 (cao)'),
    ], string='Tầng kệ')
    capacity = fields.Float(string='Sức chứa tối đa (đơn vị)')
    temperature_min = fields.Float(string='Nhiệt độ tối thiểu (°C)')
    temperature_max = fields.Float(string='Nhiệt độ tối đa (°C)')
    active = fields.Boolean(default=True)
    note = fields.Text(string='Ghi chú')
    warehouse_id = fields.Many2one('stock.warehouse', string='Cửa hàng / Kho', required=True)
    responsible_id = fields.Many2one('res.users', string='Người phụ trách quầy kệ')

    product_line_ids = fields.One2many(
        'bhx.display.location.line',
        'location_id',
        string='Sản phẩm trưng bày',
    )
    product_count = fields.Integer(
        string='Số loại sản phẩm',
        compute='_compute_product_count',
        store=True,
    )

    @api.depends('product_line_ids')
    def _compute_product_count(self):
        for rec in self:
            rec.product_count = len(rec.product_line_ids)

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code, warehouse_id)', 'Mã vị trí phải là duy nhất trong cùng cửa hàng!'),
    ]

    def action_view_products(self):
        self.ensure_one()
        return {
            'name': f'Sản phẩm tại {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'bhx.display.location.line',
            'view_mode': 'tree,form',
            'domain': [('location_id', '=', self.id)],
            'context': {'default_location_id': self.id},
        }


class DisplayLocationLine(models.Model):
    _name = 'bhx.display.location.line'
    _description = 'Sản phẩm tại vị trí trưng bày'
    _order = 'location_id, sequence'

    location_id = fields.Many2one(
        'bhx.display.location',
        string='Vị trí trưng bày',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one('product.product', string='Sản phẩm', required=True)
    product_uom_id = fields.Many2one(
        'uom.uom', string='ĐVT',
        related='product_id.uom_id', store=True,
    )
    min_qty = fields.Float(string='Số lượng tối thiểu trưng bày', default=1)
    max_qty = fields.Float(string='Số lượng tối đa trưng bày')
    current_qty = fields.Float(string='Số lượng hiện tại')
    planogram_pos = fields.Char(string='Vị trí planogram (hàng x cột)')
    facing = fields.Integer(string='Số mặt hàng (Facing)', default=1)
    is_promo = fields.Boolean(string='Hàng khuyến mãi')
    note = fields.Char(string='Ghi chú')

    def write(self, vals):
        res = super(DisplayLocationLine, self).write(vals)
        if 'current_qty' in vals:
            for line in self:
                line._check_low_stock_alert()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        lines = super(DisplayLocationLine, self).create(vals_list)
        for line in lines:
            line._check_low_stock_alert()
        return lines

    def _check_low_stock_alert(self):
        self.ensure_one()
        if self.current_qty < self.min_qty:
            alert_type = 'out_of_stock' if self.current_qty <= 0 else 'low_stock'
            existing_alert = self.env['bhx.stock.alert'].search([
                ('product_id', '=', self.product_id.id),
                ('warehouse_id', '=', self.location_id.warehouse_id.id),
                ('state', 'in', ['new', 'processing']),
                ('alert_type', 'in', ['low_stock', 'out_of_stock'])
            ], limit=1)
            
            if not existing_alert:
                try:
                    store_wh = self.env.ref('bhx_import_goods.bhx_warehouse')
                except Exception:
                    store_wh = self.location_id.warehouse_id
                self.env['bhx.stock.alert'].create({
                    'name': f'HẾT HÀNG: {self.product_id.name}' if alert_type == 'out_of_stock' else f'⚠️ SẮP HẾT: {self.product_id.name}',
                    'alert_type': alert_type,
                    'priority': '3' if alert_type == 'out_of_stock' else '2',
                    'product_id': self.product_id.id,
                    'warehouse_id': store_wh.id,
                    'current_qty': self.current_qty,
                    'min_qty': self.min_qty,
                    'max_qty': self.max_qty or (self.min_qty * 2),
                    'note': f'Sản phẩm tại {self.location_id.name} đang ở mức báo động.',
                    'responsible_id': self.env.ref('base.user_root').id, # OdooBot
                })


    status = fields.Selection([
        ('ok', 'Đủ hàng'),
        ('low', 'Sắp hết'),
        ('empty', 'Hết hàng'),
    ], string='Trạng thái', compute='_compute_status', store=True)

    @api.depends('current_qty', 'min_qty')
    def _compute_status(self):
        for line in self:
            if line.current_qty <= 0:
                line.status = 'empty'
            elif line.current_qty < line.min_qty:
                line.status = 'low'
            else:
                line.status = 'ok'
