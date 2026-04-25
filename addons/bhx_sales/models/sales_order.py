from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


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
    shift_id = fields.Many2one('bhx.sales.shift', string='Ca bán hàng', required=True, tracking=True)
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Cửa hàng', required=True,
        readonly=True, store=True,
    )
    return_request_ids = fields.One2many(
        'bhx.return.request', 'order_id',
        string='Phiếu đổi/trả'
    )
    return_request_count = fields.Integer(
        string='Số phiếu đổi/trả',
        compute='_compute_return_count'
    )

    @api.onchange('shift_id')
    def _onchange_shift_id(self):
        if self.shift_id:
            self.warehouse_id = self.shift_id.warehouse_id.id
            self.date_order = fields.Datetime.now()

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
        ('partial_refund', 'Hoàn một phần'), #new
    ], string='Trạng thái', default='draft', tracking=True)

    line_ids = fields.One2many('bhx.sales.order.line', 'order_id', string='Chi tiết hàng mua')
    picking_id = fields.Many2one('stock.picking', string='Phiếu xuất kho', readonly=True, copy=False)

    @api.depends('line_ids.subtotal', 'discount_amount')
    def _compute_amounts(self):
        for order in self:
            order.subtotal = sum(order.line_ids.mapped('subtotal'))
            order.total_amount = max(0, order.subtotal - order.discount_amount)

    @api.depends('return_request_ids')
    def _compute_return_count(self):
        for order in self:
            order.return_request_count = len(order.return_request_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('bhx.sales.order') or _('New')
        return super().create(vals_list)

    def action_done(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Vui lòng thêm sản phẩm trước khi thanh toán.'))

        # Nếu là Chuyển khoản và đang nháp -> Hiện QR chờ thanh toán (trừ khi gọi từ webhook)
        if self.payment_method == 'transfer' and self.state == 'draft' and not self.env.context.get('skip_qr_wizard'):
            return self.action_show_qr_wizard()

        # 1. Tự động trừ tồn kho kệ lẻ (Module 2 - Custom Field)
        for line in self.line_ids:
            display_lines = self.env['bhx.display.location.line'].search([
                ('product_id', '=', line.product_id.id),
                ('location_id.warehouse_id', '=', self.warehouse_id.id)
            ], limit=1) # Ưu tiên trừ ở kệ đầu tiên tìm thấy
            for display_line in display_lines:
                display_line.current_qty -= line.qty

        # 2. Tạo phiếu xuất kho Odoo để trừ tồn kho thực tế
        picking = self._create_stock_picking()
        
        self.write({
            'state': 'done',
            'picking_id': picking.id if picking else False
        })

    def _create_stock_picking(self):
        """Tạo phiếu xuất kho Odoo (stock.picking) để trừ tồn kho thực tế - Bản cưỡng bức v2."""
        self.ensure_one()
        warehouse = self.warehouse_id
        location_src = warehouse.lot_stock_id
        
        # Tìm vị trí khách hàng
        try:
            location_dest = self.env.ref('stock.stock_location_customers')
        except:
            location_dest = self.env['stock.location'].search([('usage', '=', 'customer')], limit=1)

        # Tìm loại phiếu xuất kho
        picking_type = self.env['stock.picking.type'].search([
            ('warehouse_id', '=', warehouse.id),
            ('code', '=', 'outgoing'),
        ], limit=1)
        if not picking_type:
            picking_type = self.env['stock.picking.type'].search([('code', '=', 'outgoing')], limit=1)

        if not picking_type or not location_dest:
            return False

        # 1. Tạo phiếu kho trước
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': location_src.id,
            'location_dest_id': location_dest.id,
            'origin': self.name,
            'move_type': 'direct',
        })

        # 2. Tạo Stock Moves và gán số lượng
        for line in self.line_ids:
            if line.qty <= 0:
                continue
            
            # Tạo Stock Move
            move = self.env['stock.move'].create({
                'name': line.product_id.name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.qty,
                'product_uom': line.product_uom_id.id,
                'location_id': location_src.id,
                'location_dest_id': location_dest.id,
                'picking_id': picking.id,
                'warehouse_id': warehouse.id,
                'procure_method': 'make_to_stock',
                'state': 'draft',
            })
            
            # Xác nhận move
            move._action_confirm()
            
            # Gán số lượng thực tế trực tiếp vào move (Odoo sẽ tự tạo/cập nhật move line chuẩn)
            if 'quantity' in move._fields:
                move.quantity = line.qty
            if 'quantity_done' in move._fields:
                move.quantity_done = line.qty
                
            if hasattr(move, 'picked'):
                move.picked = True

        # 3. Validate phiếu kho
        try:
            picking.with_context(
                skip_immediate=True, 
                skip_backorder=True,
            ).button_validate()
        except Exception as e:
            self.message_post(body=_("LỖI TRỪ KHO: %s") % str(e))
                
        return picking

    def action_show_qr_wizard(self):
        """Mở wizard hiển thị mã QR thanh toán"""
        self.ensure_one()
        view = self.env.ref('bhx_sales.view_bhx_payment_qr_wizard_form')
        return {
            'name': _('Thanh toán VietQR'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'bhx.payment.qr.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': {
                'default_order_id': self.id,
                'default_qr_url': self._generate_vietqr_url(),
                'default_amount': self.total_amount,
                'default_order_name': self.name,
            }
        }

    def _generate_vietqr_url(self):
        """Tạo link VietQR từ cấu hình SePay"""
        self.ensure_one()
        company = self.company_id
        
        bank_id = getattr(company, 'sepay_bank_id', 'MB') or 'MB'
        account_no = getattr(company, 'sepay_account_no', '123456789') or '123456789'
        account_name = getattr(company, 'sepay_account_name', 'CONG TY BACH HOA XANH') or 'CONG TY BACH HOA XANH'
        
        base_url = "https://img.vietqr.io/image"
        template = "compact2"
        
        amount = int(self.total_amount)
        description = self.name 
        
        url = f"{base_url}/{bank_id}-{account_no}-{template}.png?amount={amount}&addInfo={description}&accountName={account_name}"
        return url

    def action_done_and_next(self):
        self.action_done()
        return {
            'name': _('Đơn hàng mới'),
            'type': 'ir.actions.act_window',
            'res_model': 'bhx.sales.order',
            'view_mode': 'form',
            'context': {
                'default_shift_id': self.shift_id.id,
                'default_warehouse_id': self.warehouse_id.id,
            },
            'target': 'current',
        }


    def action_cancel(self):
        if self.state in ('done', 'refund', 'partial_refund'):
            raise UserError(_('Dùng "Hoàn hàng" cho đơn đã thanh toán.'))
        self.write({'state': 'cancel'})

    def action_refund(self):
        self.ensure_one()
        if self.state != 'done':
            raise UserError(_('Chỉ hoàn hàng đơn đã thanh toán.'))
        self.write({'state': 'refund'})

    def action_open_return_wizard(self):
        """Mở wizard chọn sản phẩm đổi/trả."""
        self.ensure_one()
        if self.state not in ('done', 'partial_refund'):
            raise UserError(_('Chỉ có thể đổi/trả đơn hàng đã thanh toán.'))

        # Chỉ đưa vào wizard những dòng còn hàng có thể trả
        lines_with_available = []
        for line in self.line_ids:
            approved = self.env['bhx.return.request.line'].search([
                ('order_line_id', '=', line.id),
                ('return_id.state', '=', 'approved'),
            ])
            returned = sum(approved.mapped('return_qty'))
            if line.qty - returned > 0:
                lines_with_available.append(line.id)

        if not lines_with_available:
            raise UserError(
                _('Tất cả sản phẩm trong đơn hàng này đã được hoàn trả hết.')
            )

        wizard = self.env['bhx.return.wizard'].create({
            'order_id': self.id,
            'line_ids': [(0, 0, {'order_line_id': lid})
                         for lid in lines_with_available],
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Chọn sản phẩm đổi/trả'),
            'res_model': 'bhx.return.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_view_return_requests(self):
        """Xem danh sách phiếu đổi/trả của đơn hàng này."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Phiếu đổi/trả — %s') % self.name,
            'res_model': 'bhx.return.request',
            'view_mode': 'tree,form',
            'domain': [('order_id', '=', self.id)],
        }

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
