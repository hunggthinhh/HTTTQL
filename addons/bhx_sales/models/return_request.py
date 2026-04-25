from odoo import models, fields, api, _
from odoo.exceptions import UserError

class BhxReturnRequest(models.Model):
    _name = 'bhx.return.request'
    _description = 'Yêu cầu Đổi/Trả hàng'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(
        string='Mã phiếu', default='New',
        readonly=True, copy=False, tracking=True
    )
    order_id = fields.Many2one(
        'bhx.sales.order', string='Đơn hàng gốc',
        required=True, tracking=True
    )
    shift_id = fields.Many2one(
        related='order_id.shift_id', store=True,
        string='Ca bán hàng'
    )
    note = fields.Text(string='Lý do đổi/trả')
    state = fields.Selection([
        ('draft', 'Mới tạo'),
        ('approved', 'Đã xác nhận'),
        ('cancel', 'Hủy'),
    ], string='Trạng thái', default='draft', tracking=True)

    line_ids = fields.One2many(
        'bhx.return.request.line', 'return_id',
        string='Chi tiết hàng trả'
    )
    return_picking_id = fields.Many2one(
        'stock.picking', string='Phiếu nhập kho hoàn',
        readonly=True, copy=False
    )
    refund_amount = fields.Monetary(
        string='Tổng tiền hoàn',
        compute='_compute_refund', store=True,
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        related='order_id.currency_id', store=True
    )
    approved_by = fields.Many2one(
        'res.users', string='Người xác nhận',
        readonly=True, copy=False
    )
    approved_date = fields.Datetime(
        string='Ngày xác nhận',
        readonly=True, copy=False
    )

    @api.depends('line_ids.return_qty', 'line_ids.refund_unit_price')
    def _compute_refund(self):
        for r in self:
            r.refund_amount = sum(
                l.return_qty * l.refund_unit_price for l in r.line_ids
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('bhx.return.request')
                    or 'New'
                )
        return super().create(vals_list)

    def action_approve(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Không có sản phẩm nào để xử lý đổi/trả.'))
        if self.state != 'draft':
            raise UserError(_('Phiếu này đã được xử lý rồi.'))

        # 1. Cộng lại tồn kho kệ lẻ (bhx_inventory_display)
        for line in self.line_ids:
            display_line = self.env['bhx.display.location.line'].search([
                ('product_id', '=', line.product_id.id),
                ('location_id.warehouse_id', '=', self.order_id.warehouse_id.id)
            ], limit=1)
            if display_line:
                display_line.current_qty += line.return_qty

        # 2. Tạo phiếu nhập kho
        picking = self._create_return_picking()

        # 3. Tính tổng qty đã trả (kể cả phiếu này) để cập nhật state đơn gốc
        all_approved_lines = self.env['bhx.return.request.line'].search([
            ('order_line_id.order_id', '=', self.order_id.id),
            ('return_id.state', '=', 'approved'),
        ])
        # Cộng thêm lines của phiếu hiện tại (chưa approved nên chưa được tính)
        current_return_by_line = {l.order_line_id.id: l.return_qty for l in self.line_ids}

        total_purchased = sum(self.order_id.line_ids.mapped('qty'))
        total_returned = sum(all_approved_lines.mapped('return_qty'))
        total_returned += sum(current_return_by_line.values())

        if total_returned >= total_purchased:
            new_order_state = 'refund'
        else:
            new_order_state = 'partial_refund'

        self.order_id.write({'state': new_order_state})

        # 4. Cập nhật phiếu
        self.write({
            'state': 'approved',
            'return_picking_id': picking.id if picking else False,
            'approved_by': self.env.user.id,
            'approved_date': fields.Datetime.now(),
        })
        self.message_post(body=_('Đã xác nhận phiếu đổi/trả. Tổng tiền hoàn: %s') % f'{self.refund_amount:,.0f} VND')

    def action_cancel(self):
        self.ensure_one()
        if self.state == 'approved':
            raise UserError(_('Không thể hủy phiếu đã xác nhận.'))
        self.write({'state': 'cancel'})

    def _create_return_picking(self):
        """Tạo phiếu nhập kho (incoming) để cộng lại tồn kho Odoo khi hoàn hàng."""
        self.ensure_one()
        warehouse = self.order_id.warehouse_id
        location_dest = warehouse.lot_stock_id

        try:
            location_src = self.env.ref('stock.stock_location_customers')
        except Exception:
            location_src = self.env['stock.location'].search(
                [('usage', '=', 'customer')], limit=1
            )

        picking_type = self.env['stock.picking.type'].search([
            ('warehouse_id', '=', warehouse.id),
            ('code', '=', 'incoming'),
        ], limit=1)

        if not picking_type or not location_src:
            self.message_post(body=_('Cảnh báo: Không tìm thấy loại phiếu nhập kho. Tồn kho Odoo chưa được cộng.'))
            return False

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': location_src.id,
            'location_dest_id': location_dest.id,
            'origin': self.name,
            'move_type': 'direct',
        })

        for line in self.line_ids:
            if line.return_qty <= 0:
                continue

            move = self.env['stock.move'].create({
                'name': line.product_id.name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.return_qty,
                'product_uom': line.product_id.uom_id.id,
                'location_id': location_src.id,
                'location_dest_id': location_dest.id,
                'picking_id': picking.id,
                'state': 'draft',
            })

            move._action_confirm()

            # Odoo 17: dùng `quantity` + `picked`
            if 'quantity' in move._fields:
                move.quantity = line.return_qty
            if hasattr(move, 'picked'):
                move.picked = True

        try:
            picking.with_context(
                skip_immediate=True,
                skip_backorder=True,
            ).button_validate()
        except Exception as e:
            self.message_post(body=_('Lỗi validate phiếu nhập kho: %s') % str(e))

        return picking

class BhxReturnRequestLine(models.Model):
    _name = 'bhx.return.request.line'
    _description = 'Chi tiết yêu cầu đổi/trả'

    return_id = fields.Many2one(
        'bhx.return.request', required=True, ondelete='cascade'
    )
    order_line_id = fields.Many2one(
        'bhx.sales.order.line', string='Dòng đơn hàng gốc',
        required=True
    )
    product_id = fields.Many2one(
        related='order_line_id.product_id', store=True,
        string='Sản phẩm'
    )
    purchased_qty = fields.Float(
        related='order_line_id.qty', store=True,
        string='SL đã mua'
    )
    return_qty = fields.Float(
        string='SL trả', default=1
    )
    refund_unit_price = fields.Float(
        string='Đơn giá hoàn',
        compute='_compute_price', store=True
    )

    @api.depends('order_line_id')
    def _compute_price(self):
        for l in self:
            if l.order_line_id and l.order_line_id.qty:
                l.refund_unit_price = l.order_line_id.subtotal / l.order_line_id.qty
            else:
                l.refund_unit_price = 0.0

    @api.constrains('return_qty')
    def _check_qty(self):
        for line in self:
            if line.return_qty <= 0:
                raise UserError(_('Số lượng trả phải lớn hơn 0.'))

            # Tính tổng đã trả trước đó (phiếu đã approved, không tính phiếu hiện tại)
            already_returned = self.env['bhx.return.request.line'].search([
                ('order_line_id', '=', line.order_line_id.id),
                ('return_id.state', '=', 'approved'),
                ('return_id', '!=', line.return_id.id),
            ])
            total_returned = sum(already_returned.mapped('return_qty'))

            if line.return_qty + total_returned > line.purchased_qty:
                raise UserError(_(
                    'Sản phẩm "%s": Tổng số lượng trả (%s) vượt quá số lượng đã mua (%s).'
                ) % (line.product_id.name, line.return_qty + total_returned, line.purchased_qty))