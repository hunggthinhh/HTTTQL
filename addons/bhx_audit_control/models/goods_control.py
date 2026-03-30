from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date, timedelta


class GoodsControl(models.Model):
    _name = 'bhx.goods.control'
    _description = 'Kiểm soát hàng hoá theo ngày'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'check_date desc'

    name = fields.Char(
        string='Mã phiếu kiểm soát', required=True, copy=False,
        readonly=True, default=lambda self: _('New'), tracking=True,
    )
    check_date = fields.Date(
        string='Ngày kiểm soát', required=True,
        default=fields.Date.today, tracking=True,
    )
    check_type = fields.Selection([
        ('morning', 'Kiểm soát đầu ca sáng'),
        ('noon', 'Kiểm soát giữa ca'),
        ('closing', 'Kiểm soát cuối ngày'),
        ('random', 'Kiểm tra đột xuất'),
    ], string='Loại kiểm soát', required=True, default='morning')
    warehouse_id = fields.Many2one('stock.warehouse', string='Cửa hàng', required=True, tracking=True)
    responsible_id = fields.Many2one(
        'res.users', string='Nhân viên thực hiện',
        default=lambda self: self.env.user,
    )
    note = fields.Text(string='Ghi chú tổng hợp')
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('done', 'Hoàn thành'),
        ('cancel', 'Đã huỷ'),
    ], string='Trạng thái', default='draft', tracking=True)

    line_ids = fields.One2many('bhx.goods.control.line', 'control_id', string='Danh sách kiểm soát')

    total_checked = fields.Integer(compute='_compute_summary', store=True, string='Tổng SP kiểm')
    total_issue = fields.Integer(compute='_compute_summary', store=True, string='SP có vấn đề')

    @api.depends('line_ids.has_issue')
    def _compute_summary(self):
        for rec in self:
            rec.total_checked = len(rec.line_ids)
            rec.total_issue = len(rec.line_ids.filtered('has_issue'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('bhx.goods.control') or _('New')
        return super().create(vals_list)

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.write({'state': 'draft'})


class GoodsControlLine(models.Model):
    _name = 'bhx.goods.control.line'
    _description = 'Chi tiết kiểm soát hàng hoá'

    control_id = fields.Many2one('bhx.goods.control', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Sản phẩm', required=True)
    lot_id = fields.Many2one('stock.lot', string='Số lô')
    expiry_date = fields.Date(string='Hạn sử dụng')
    days_to_expiry = fields.Integer(
        string='Số ngày còn lại',
        compute='_compute_days_to_expiry', store=True,
    )
    qty_on_display = fields.Float(string='SL trưng bày')
    package_ok = fields.Boolean(string='Bao bì nguyên vẹn', default=True)
    price_tag_ok = fields.Boolean(string='Giá đúng / rõ ràng', default=True)
    placement_ok = fields.Boolean(string='Đặt đúng vị trí', default=True)
    freshness_ok = fields.Boolean(string='Còn tươi / đạt chất lượng', default=True)
    issue_type = fields.Selection([
        ('none', 'Không có'),
        ('near_expiry', 'Sắp hết hạn'),
        ('expired', 'Đã hết hạn'),
        ('damage', 'Hư hỏng / Vỡ'),
        ('wrong_price', 'Sai giá'),
        ('wrong_location', 'Sai vị trí'),
        ('low_stock', 'Sắp hết'),
    ], string='Loại vấn đề', default='none')
    has_issue = fields.Boolean(
        string='Có vấn đề',
        compute='_compute_has_issue', store=True,
    )
    action_taken = fields.Char(string='Hành động xử lý')
    note = fields.Char(string='Ghi chú')

    @api.depends('expiry_date')
    def _compute_days_to_expiry(self):
        today = date.today()
        for line in self:
            if line.expiry_date:
                line.days_to_expiry = (line.expiry_date - today).days
            else:
                line.days_to_expiry = 0

    @api.depends('package_ok', 'price_tag_ok', 'placement_ok', 'freshness_ok', 'issue_type')
    def _compute_has_issue(self):
        for line in self:
            line.has_issue = (
                not line.package_ok or
                not line.price_tag_ok or
                not line.placement_ok or
                not line.freshness_ok or
                line.issue_type != 'none'
            )
