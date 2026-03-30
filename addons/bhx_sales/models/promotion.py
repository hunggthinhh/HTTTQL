from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Promotion(models.Model):
    _name = 'bhx.promotion'
    _description = 'Chương trình khuyến mãi'
    _inherit = ['mail.thread']
    _order = 'date_from desc'

    name = fields.Char(string='Tên chương trình KM', required=True, tracking=True)
    code = fields.Char(string='Mã KM', copy=False)
    promo_type = fields.Selection([
        ('discount_pct', 'Giảm % giá'),
        ('discount_amt', 'Giảm số tiền cố định'),
        ('buy_x_get_y', 'Mua X tặng Y'),
        ('gift', 'Tặng quà'),
        ('combo', 'Combo / Bộ sản phẩm'),
        ('member', 'Dành cho thành viên'),
    ], string='Loại khuyến mãi', required=True, default='discount_pct')
    discount_pct = fields.Float(string='% Giảm giá', default=0)
    discount_amt = fields.Monetary(string='Số tiền giảm', currency_field='currency_id', default=0)
    min_order_amt = fields.Monetary(
        string='Đơn hàng tối thiểu', currency_field='currency_id', default=0,
    )
    date_from = fields.Date(string='Ngày bắt đầu', required=True, tracking=True)
    date_to = fields.Date(string='Ngày kết thúc', required=True, tracking=True)
    warehouse_ids = fields.Many2many('stock.warehouse', string='Áp dụng tại cửa hàng')
    product_ids = fields.Many2many('product.product', string='Sản phẩm áp dụng')
    applies_all = fields.Boolean(string='Áp dụng tất cả sản phẩm', default=True)
    usage_limit = fields.Integer(string='Số lần dùng tối đa (0 = không giới hạn)', default=0)
    usage_count = fields.Integer(string='Đã sử dụng', default=0, readonly=True)
    description = fields.Text(string='Mô tả / Điều kiện áp dụng')
    active = fields.Boolean(default=True, tracking=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    state = fields.Selection([
        ('upcoming', 'Sắp diễn ra'),
        ('active', 'Đang áp dụng'),
        ('expired', 'Đã kết thúc'),
    ], string='Trạng thái', compute='_compute_state', store=True)

    @api.depends('date_from', 'date_to')
    def _compute_state(self):
        today = fields.Date.today()
        for rec in self:
            if rec.date_from and rec.date_to:
                if today < rec.date_from:
                    rec.state = 'upcoming'
                elif today > rec.date_to:
                    rec.state = 'expired'
                else:
                    rec.state = 'active'
            else:
                rec.state = 'upcoming'

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(_('Ngày bắt đầu phải trước ngày kết thúc!'))
