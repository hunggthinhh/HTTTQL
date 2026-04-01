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
    shift_id = fields.Many2one('bhx.sales.shift', string='Ca bán hàng', required=True, tracking=True)
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Cửa hàng', required=True,
        readonly=True, store=True,
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
    ], string='Trạng thái', default='draft', tracking=True)

    line_ids = fields.One2many('bhx.sales.order.line', 'order_id', string='Chi tiết hàng mua')
    picking_id = fields.Many2one('stock.picking', string='Phiếu xuất kho', readonly=True, copy=False)

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
