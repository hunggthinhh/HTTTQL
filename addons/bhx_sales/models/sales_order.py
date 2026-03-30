from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SalesOrder(models.Model):
    _name = 'bhx.sales.order'
    _description = 'Đơn hàng bán lẻ'
    _inherit = ['mail.thread']
    _order = 'date_order desc, id desc'

    name = fields.Char(
        string='Mã đơn hàng', required=True, copy=False,
        readonly=True, default=lambda self: _('New'), tracking=True,
    )
    date_order = fields.Datetime(
        string='Thời gian đặt hàng',
        default=fields.Datetime.now, tracking=True,
    )
    shift_id = fields.Many2one('bhx.sales.shift', string='Ca bán hàng', tracking=True)
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Cửa hàng', required=True,
        related='shift_id.warehouse_id', store=True,
    )
    cashier_id = fields.Many2one(
        'res.users', string='Thu ngân',
        default=lambda self: self.env.user,
    )
    customer_phone = fields.Char(string='SĐT khách hàng (thành viên)')
    customer_name = fields.Char(string='Tên khách hàng')
    payment_method = fields.Selection([
        ('cash', 'Tiền mặt'),
        ('card', 'Thẻ ngân hàng'),
        ('transfer', 'Chuyển khoản'),
        ('ewallet', 'Ví điện tử (Momo/ZaloPay/...)'),
        ('voucher', 'Voucher'),
        ('mixed', 'Kết hợp nhiều hình thức'),
    ], string='Phương thức thanh toán', required=True, default='cash')
    promotion_id = fields.Many2one('bhx.promotion', string='Chương trình KM áp dụng')
    discount_amount = fields.Monetary(
        string='Giảm giá', currency_field='currency_id', default=0,
    )
    subtotal = fields.Monetary(
        string='Tạm tính', compute='_compute_amounts',
        store=True, currency_field='currency_id',
    )
    total_amount = fields.Monetary(
        string='Thành tiền', compute='_compute_amounts',
        store=True, currency_field='currency_id',
    )
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    note = fields.Text(string='Ghi chú đơn hàng')
    state = fields.Selection([
        ('draft', 'Mới'),
        ('done', 'Đã thanh toán'),
        ('cancel', 'Đã huỷ'),
        ('refund', 'Đã hoàn hàng'),
    ], string='Trạng thái', default='draft', tracking=True)

    line_ids = fields.One2many('bhx.sales.order.line', 'order_id', string='Chi tiết hàng mua')

    @api.depends('line_ids.subtotal', 'discount_amount')
    def _compute_amounts(self):
        for order in self:
            order.subtotal = sum(order.line_ids.mapped('subtotal'))
            order.total_amount = max(0, order.subtotal - order.discount_amount)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('bhx.sales.order') or _('New')
        return super().create(vals_list)

    def action_done(self):
        if not self.line_ids:
            raise UserError(_('Vui lòng thêm sản phẩm trước khi thanh toán.'))
        
        # Tự động trừ tồn kho kệ lẻ (Module 2)
        for line in self.line_ids:
            display_lines = self.env['bhx.display.location.line'].search([
                ('product_id', '=', line.product_id.id),
                ('location_id.warehouse_id', '=', self.warehouse_id.id)
            ], limit=1) # Ưu tiên trừ ở kệ đầu tiên tìm thấy
            for display_line in display_lines:
                display_line.current_qty -= line.qty

        self.write({'state': 'done'})

    def action_cancel(self):
        if self.state == 'done':
            raise UserError(_('Dùng "Hoàn hàng" cho đơn đã thanh toán.'))
        self.write({'state': 'cancel'})

    def action_refund(self):
        self.ensure_one()
        if self.state != 'done':
            raise UserError(_('Chỉ hoàn hàng đơn đã thanh toán.'))
        self.write({'state': 'refund'})


class SalesOrderLine(models.Model):
    _name = 'bhx.sales.order.line'
    _description = 'Chi tiết đơn hàng bán lẻ'

    order_id = fields.Many2one('bhx.sales.order', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Sản phẩm', required=True)
    barcode = fields.Char(related='product_id.barcode', store=True, string='Barcode')
    product_uom_id = fields.Many2one('uom.uom', related='product_id.uom_id', store=True)
    qty = fields.Float(string='Số lượng', required=True, default=1)
    unit_price = fields.Float(string='Đơn giá', required=True, default=0)
    discount_pct = fields.Float(string='Chiết khấu (%)', default=0)
    subtotal = fields.Float(
        string='Thành tiền', compute='_compute_subtotal', store=True,
    )
    note = fields.Char(string='Ghi chú')

    @api.depends('qty', 'unit_price', 'discount_pct')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.qty * line.unit_price * (1 - line.discount_pct / 100)

    @api.onchange('product_id')
    def _onchange_product(self):
        if self.product_id:
            self.unit_price = self.product_id.lst_price
