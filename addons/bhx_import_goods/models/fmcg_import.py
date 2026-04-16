from odoo import models, fields, api, _
from datetime import timedelta
from odoo.exceptions import UserError, ValidationError


class FmcgImport(models.Model):
    _name = 'bhx.fmcg.import'
    _description = 'Kiểm hàng nhập kho FMCG'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Mã phiếu nhập',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    date = fields.Date(
        string='Ngày nhập kho',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    supplier_id = fields.Many2one(
        'res.partner',
        string='Nhà cung cấp',
        required=True,
        tracking=True,
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Kho nhập',
        required=True,
        tracking=True,
    )
    responsible_id = fields.Many2one(
        'res.users',
        string='Người phụ trách',
        default=lambda self: self.env.user,
        tracking=True,
    )
    def _default_vehicle_plate(self):
        import random
        prefix = random.choice(['51C', '51D', '60C', '61C', '50H', '29C', '61D', '51R'])
        suffix = f"{random.randint(100, 999)}.{random.randint(10, 99)}"
        return f"{prefix}-{suffix}"

    def _default_delivery_note(self):
        import random
        from datetime import datetime
        return f"DN-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

    delivery_note = fields.Char(string='Số phiếu giao hàng', default=lambda self: self._default_delivery_note())
    vehicle_plate = fields.Char(string='Biển số xe', default=lambda self: self._default_vehicle_plate())
    note = fields.Text(string='Ghi chú')
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('checking', 'Đang kiểm hàng'),
        ('done', 'Hoàn thành'),
        ('cancel', 'Đã huỷ'),
    ], string='Trạng thái', default='draft', tracking=True, required=True)

    line_ids = fields.One2many(
        'bhx.fmcg.import.line',
        'import_id',
        string='Chi tiết hàng nhập',
    )

    total_qty = fields.Float(
        string='Tổng số lượng',
        compute='_compute_totals',
        store=True,
    )
    total_value = fields.Monetary(
        string='Tổng giá trị',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Tiền tệ',
        default=lambda self: self.env.company.currency_id,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Công ty',
        default=lambda self: self.env.company,
    )

    @api.depends('line_ids.checked_qty', 'line_ids.subtotal')
    def _compute_totals(self):
        for rec in self:
            rec.total_qty = sum(rec.line_ids.mapped('checked_qty'))
            rec.total_value = sum(rec.line_ids.mapped('subtotal'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('bhx.fmcg.import') or _('New')
        return super().create(vals_list)

    def action_start_checking(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Vui lòng thêm ít nhất một sản phẩm trước khi bắt đầu kiểm hàng.'))
        
        # Tự động đề xuất Hạn sử dụng và Số lượng thực nhận
        suggested_expiry = fields.Date.today() + timedelta(days=365)
        for line in self.line_ids:
            if not line.expiry_date:
                line.expiry_date = suggested_expiry
            if line.checked_qty == 0:
                line.checked_qty = line.quantity

        self.write({'state': 'checking'})

    def _create_stock_picking(self):
        """Tạo phiếu nhập kho Odoo (stock.picking) để cập nhật tồn kho dự trữ."""
        self.ensure_one()
        warehouse = self.warehouse_id
        location_dest = warehouse.lot_stock_id  # Kho dự trữ chính
        location_src = self.env.ref('stock.stock_location_suppliers')

        picking_type = self.env['stock.picking.type'].search([
            ('warehouse_id', '=', warehouse.id),
            ('code', '=', 'incoming'),
        ], limit=1)
        if not picking_type:
            raise UserError(_('Không tìm thấy loại phiếu nhập kho cho kho "%s".') % warehouse.name)

        moves = []
        for line in self.line_ids:
            if line.checked_qty <= 0:
                continue
            moves.append((0, 0, {
                'name': line.product_id.name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.checked_qty,
                'product_uom': line.product_uom_id.id,
                'location_id': location_src.id,
                'location_dest_id': location_dest.id,
                'origin': self.name,
            }))

        if not moves:
            raise UserError(_('Không có hàng nào để nhập kho (số lượng = 0).'))

        picking = self.env['stock.picking'].create({
            'partner_id': self.supplier_id.id,
            'picking_type_id': picking_type.id,
            'location_id': location_src.id,
            'location_dest_id': location_dest.id,
            'origin': self.name,
            'move_ids': moves,
        })
        picking.action_confirm()
        picking.action_assign()
        # Điền đủ số lượng thực nhận
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            if hasattr(move, 'picked'):
                move.picked = True
        picking.with_context(skip_immediate=True, skip_backorder=True).button_validate()
        return picking

    def action_confirm_done(self):
        self.ensure_one()
        for line in self.line_ids:
            if line.checked_qty < 0:
                raise ValidationError(_('Số lượng kiểm không được âm.'))

        # Phương án B: Nhập vào kho dự trữ Odoo (stock.quant)
        picking = self._create_stock_picking()
        self.write({'state': 'done', 'picking_id': picking.id})

        # --- Tạo cảnh báo Date nếu HSD < 30 ngày ---
        today = fields.Date.today()
        limit_date = today + timedelta(days=30)
        for line in self.line_ids:
            if line.expiry_date and line.expiry_date < limit_date:
                alert_type = 'expired' if line.expiry_date <= today else 'near_expiry'
                priority = '3' if alert_type == 'expired' else '2'
                
                # Kiểm tra xem sản phẩm này đã có cảnh báo date chưa để tránh trùng lặp quá nhiều
                existing_alert = self.env['bhx.stock.alert'].search([
                    ('product_id', '=', line.product_id.id),
                    ('warehouse_id', '=', self.warehouse_id.id),
                    ('expiry_date', '=', line.expiry_date),
                    ('state', 'in', ['new', 'processing']),
                    ('alert_type', 'in', ['near_expiry', 'expired'])
                ], limit=1)
                
                if not existing_alert:
                    self.env['bhx.stock.alert'].create({
                        'name': f'DATE: {line.product_id.name} (Nhập từ {self.name})',
                        'alert_type': alert_type,
                        'priority': priority,
                        'product_id': line.product_id.id,
                        'warehouse_id': self.warehouse_id.id,
                        'expiry_date': line.expiry_date,
                        'current_qty': line.checked_qty,
                        'note': f'Hàng nhập có hạn dùng ngắn ({line.expiry_date}). Lô: {line.lot_no or "N/A"}. Cần ưu tiên bán trước.',
                    })

        # Tự động gỡ cảnh báo tồn kho nếu có (hết hàng -> có hàng)
        try:
            if 'bhx.stock.alert' in self.env:
                product_ids = self.line_ids.mapped('product_id').ids
                alerts = self.env['bhx.stock.alert'].search([
                    ('warehouse_id', '=', self.warehouse_id.id),
                    ('product_id', 'in', product_ids),
                    ('state', 'in', ['new', 'processing']),
                    ('alert_type', 'in', ['low_stock', 'out_of_stock'])
                ])
                if alerts:
                    alerts.write({
                        'state': 'resolved',
                        'note': f'Đã tự động xử lý bởi phiếu nhập hàng {self.name}'
                    })
        except Exception:
            pass

    picking_id = fields.Many2one(
        'stock.picking',
        string='Phiếu nhập kho Odoo',
        readonly=True,
        copy=False,
    )

    def action_cancel(self):
        self.ensure_one()
        if self.state == 'done':
            raise UserError(_('Không thể huỷ phiếu đã hoàn thành.'))
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.ensure_one()
        self.write({'state': 'draft'})


class FmcgImportLine(models.Model):
    _name = 'bhx.fmcg.import.line'
    _description = 'Chi tiết hàng nhập FMCG'

    import_id = fields.Many2one(
        'bhx.fmcg.import',
        string='Phiếu nhập',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Sản phẩm',
        required=True,
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Đơn vị tính',
        related='product_id.uom_id',
        store=True,
    )
    barcode = fields.Char(
        string='Mã barcode',
        related='product_id.barcode',
        store=True,
    )
    lot_no = fields.Char(string='Số lô')
    expiry_date = fields.Date(string='Hạn sử dụng')
    quantity = fields.Float(string='SL đặt hàng', required=True, default=0)
    checked_qty = fields.Float(string='SL thực nhận', default=0)
    damaged_qty = fields.Float(string='SL hàng lỗi', default=0)
    unit_price = fields.Float(string='Đơn giá', required=True, default=0)
    subtotal = fields.Float(
        string='Thành tiền',
        compute='_compute_subtotal',
        store=True,
    )
    remark = fields.Char(string='Ghi chú dòng')

    @api.depends('checked_qty', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.checked_qty * line.unit_price

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.unit_price = self.product_id.standard_price
            if not self.expiry_date:
                self.expiry_date = fields.Date.today() + timedelta(days=365)
            if not self.lot_no:
                self.lot_no = f"LOT-FMCG-{self.product_id.id}-{fields.Date.today().strftime('%m%d')}"
