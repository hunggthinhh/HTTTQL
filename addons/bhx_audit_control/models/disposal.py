from odoo import models, fields, api, _
from odoo.exceptions import UserError


class Disposal(models.Model):
    _name = 'bhx.disposal'
    _description = 'Phiếu xử lý / Huỷ hàng'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Mã phiếu huỷ', required=True, copy=False,
        readonly=True, default=lambda self: _('New'), tracking=True,
    )
    date = fields.Date(
        string='Ngày xử lý', required=True,
        default=fields.Date.today, tracking=True,
    )
    disposal_type = fields.Selection([
        ('expire', 'Hàng hết hạn'),
        ('damage', 'Hàng hư hỏng / Vỡ / Rò rỉ'),
        ('quality', 'Không đạt chất lượng'),
        ('recall', 'Thu hồi từ nhà cung cấp'),
        ('other', 'Lý do khác'),
    ], string='Lý do huỷ', required=True, default='expire', tracking=True)
    disposal_method = fields.Selection([
        ('destroy', 'Tiêu huỷ tại chỗ'),
        ('return_supplier', 'Trả về nhà cung cấp'),
        ('donate', 'Từ thiện / Cho'),
        ('sell_off', 'Bán thanh lý'),
    ], string='Phương thức xử lý', required=True, default='destroy', tracking=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Cửa hàng', required=True, tracking=True)
    responsible_id = fields.Many2one(
        'res.users', string='Người thực hiện',
        default=lambda self: self.env.user, tracking=True,
    )
    approved_id = fields.Many2one('res.users', string='Người phê duyệt', tracking=True)
    witness_name = fields.Char(string='Người chứng kiến')
    note = fields.Text(string='Ghi chú / Mô tả tình trạng')
    photo_evidence = fields.Char(string='Số biên bản / Mã hình ảnh')
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('confirm', 'Chờ duyệt'),
        ('approved', 'Đã duyệt'),
        ('done', 'Đã thực hiện'),
        ('cancel', 'Đã huỷ'),
    ], string='Trạng thái', default='draft', tracking=True)

    line_ids = fields.One2many('bhx.disposal.line', 'disposal_id', string='Chi tiết hàng huỷ')
    total_value = fields.Monetary(
        string='Tổng giá trị huỷ',
        compute='_compute_total', store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.depends('line_ids.subtotal')
    def _compute_total(self):
        for rec in self:
            rec.total_value = sum(rec.line_ids.mapped('subtotal'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('bhx.disposal') or _('New')
        return super().create(vals_list)

    def action_confirm(self):
        if not self.line_ids:
            raise UserError(_('Vui lòng thêm sản phẩm cần huỷ.'))
        self.write({'state': 'confirm'})

    def action_approve(self):
        self.write({'state': 'approved', 'approved_id': self.env.user.id})

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        if self.state == 'done':
            raise UserError(_('Không thể huỷ phiếu đã thực hiện.'))
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.write({'state': 'draft'})


class DisposalLine(models.Model):
    _name = 'bhx.disposal.line'
    _description = 'Chi tiết hàng huỷ'

    disposal_id = fields.Many2one('bhx.disposal', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Sản phẩm', required=True)
    product_uom_id = fields.Many2one('uom.uom', related='product_id.uom_id', store=True)
    lot_id = fields.Many2one('stock.lot', string='Số lô')
    expiry_date = fields.Date(string='Hạn sử dụng')
    qty = fields.Float(string='Số lượng huỷ', required=True)
    unit_cost = fields.Float(string='Giá vốn', required=True)
    subtotal = fields.Float(string='Giá trị huỷ', compute='_compute_subtotal', store=True)
    condition = fields.Selection([
        ('expired', 'Hết hạn'),
        ('damaged', 'Hư hỏng / Vỡ'),
        ('contaminated', 'Nhiễm bẩn'),
        ('other', 'Khác'),
    ], string='Tình trạng', default='expired')
    note = fields.Char(string='Ghi chú')

    @api.depends('qty', 'unit_cost')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.qty * line.unit_cost

    @api.onchange('product_id')
    def _onchange_product(self):
        if self.product_id:
            self.unit_cost = self.product_id.standard_price
