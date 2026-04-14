from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class FreshImport(models.Model):
    _name = 'bhx.fresh.import'
    _description = 'Nhập hàng Fresh (Thịt, Cá, Hải sản...)'
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
    date = fields.Datetime(
        string='Thời gian nhập',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
    )
    fresh_type = fields.Selection([
        ('meat', 'Thịt heo / Bò / Gà'),
        ('seafood', 'Hải sản / Cá'),
        ('egg', 'Trứng'),
        ('dairy', 'Sản phẩm sữa tươi'),
        ('processed', 'Thực phẩm chế biến sẵn'),
        ('other', 'Khác'),
    ], string='Loại hàng Fresh', required=True, default='meat', tracking=True)
    supplier_id = fields.Many2one(
        'res.partner',
        string='Nhà cung cấp',
        required=True,
        tracking=True,
    )
    slaughter_date = fields.Date(string='Ngày giết mổ / Sản xuất')
    expiry_date = fields.Date(string='Hạn sử dụng', required=True, tracking=True)
    vehicle_plate = fields.Char(string='Biển số xe vận chuyển')
    temperature_arrival = fields.Float(string='Nhiệt độ khi đến (°C)')
    temperature_storage = fields.Float(string='Nhiệt độ bảo quản yêu cầu (°C)')
    health_cert_no = fields.Char(string='Số giấy chứng nhận ATTP')
    veterinary_cert = fields.Boolean(string='Có chứng nhận thú y', default=False)
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Kho nhập / Tủ lạnh',
        required=True,
        tracking=True,
    )
    responsible_id = fields.Many2one(
        'res.users',
        string='Người nhận hàng',
        default=lambda self: self.env.user,
        tracking=True,
    )
    vn_standard_check = fields.Boolean(string='Đạt tiêu chuẩn TCVN', default=True)
    note = fields.Text(string='Ghi chú / Vấn đề phát hiện')
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('receiving', 'Đang nhận hàng'),
        ('temp_check', 'Kiểm nhiệt độ & ATTP'),
        ('done', 'Đã nhập kho'),
        ('reject', 'Từ chối nhận'),
        ('cancel', 'Đã huỷ'),
    ], string='Trạng thái', default='draft', tracking=True, required=True)

    line_ids = fields.One2many(
        'bhx.fresh.import.line',
        'import_id',
        string='Chi tiết hàng Fresh',
    )
    total_weight = fields.Float(
        string='Tổng trọng lượng (kg)',
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
        default=lambda self: self.env.company.currency_id,
    )
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
    )

    @api.depends('line_ids.weight', 'line_ids.subtotal')
    def _compute_totals(self):
        for rec in self:
            rec.total_weight = sum(rec.line_ids.mapped('weight'))
            rec.total_value = sum(rec.line_ids.mapped('subtotal'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('bhx.fresh.import') or _('New')
        return super().create(vals_list)

    @api.constrains('temperature_arrival', 'fresh_type')
    def _check_temperature(self):
        temp_limits = {
            'meat': 7,
            'seafood': 4,
            'dairy': 6,
            'egg': 20,
            'processed': 8,
        }
        for rec in self:
            limit = temp_limits.get(rec.fresh_type)
            if limit and rec.temperature_arrival > limit:
                raise ValidationError(
                    _('Nhiệt độ khi đến (%.1f°C) vượt ngưỡng cho phép (%d°C) đối với loại %s!') %
                    (rec.temperature_arrival, limit, dict(rec._fields['fresh_type'].selection).get(rec.fresh_type))
                )

    def action_start_receiving(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Vui lòng thêm sản phẩm trước khi bắt đầu.'))
        self.write({'state': 'receiving'})

    def action_temp_check(self):
        self.ensure_one()
        self.write({'state': 'temp_check'})

    def _create_stock_picking(self):
        """Tạo phiếu nhập kho Odoo và gán HSD vào Lô hàng."""
        self.ensure_one()
        warehouse = self.warehouse_id
        location_dest = warehouse.lot_stock_id
        location_src = self.env.ref('stock.stock_location_suppliers')

        picking_type = self.env['stock.picking.type'].search([
            ('warehouse_id', '=', warehouse.id),
            ('code', '=', 'incoming'),
        ], limit=1)
        if not picking_type:
            raise UserError(_('Không tìm thấy loại phiếu nhập kho cho kho "%s".') % warehouse.name)

        # 1. Tạo Phiếu kho
        picking = self.env['stock.picking'].create({
            'partner_id': self.supplier_id.id,
            'picking_type_id': picking_type.id,
            'location_id': location_src.id,
            'location_dest_id': location_dest.id,
            'origin': self.name,
        })

        # 2. Tạo Moves và Move Lines thủ công để gán Lô & HSD
        for line in self.line_ids:
            if line.weight <= 0:
                continue
            
            move = self.env['stock.move'].create({
                'name': line.product_id.name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.weight,
                'product_uom': line.product_id.uom_id.id,
                'location_id': location_src.id,
                'location_dest_id': location_dest.id,
                'picking_id': picking.id,
                'picking_type_id': picking_type.id,
            })
            
            move._action_confirm()

            # Tạo Số lô (Lot) và gán HSD
            lot_name = line.lot_no or f"LOT-{self.name}-{line.product_id.id}"
            lot = self.env['stock.lot'].create({
                'name': lot_name,
                'product_id': line.product_id.id,
                'company_id': self.company_id.id,
                'expiration_date': self.expiry_date, # Gán HSD từ phiếu nhập Fresh
            })

            # Tạo Move Line để gán Lot
            ml_vals = {
                'product_id': line.product_id.id,
                'product_uom_id': line.product_uom_id.id,
                'location_id': location_src.id,
                'location_dest_id': location_dest.id,
                'picking_id': picking.id,
                'move_id': move.id,
                'lot_id': lot.id,
            }
            if 'quantity' in self.env['stock.move.line']._fields:
                ml_vals['quantity'] = line.weight
            else:
                ml_vals['quantity_done'] = line.weight
                
            self.env['stock.move.line'].create(ml_vals)

        # 3. Hoàn thành phiếu kho
        picking.action_assign()
        picking.with_context(skip_immediate=True, skip_backorder=True).button_validate()
        return picking

    def action_confirm_done(self):
        self.ensure_one()
        if not self.health_cert_no:
            raise UserError(_('Vui lòng nhập số giấy chứng nhận ATTP trước khi hoàn thành.'))

        # Phương án B: Nhập vào kho dự trữ Odoo (stock.quant)
        picking = self._create_stock_picking()
        self.write({'state': 'done', 'picking_id': picking.id})

        # Tự động gỡ cảnh báo tồn kho nếu có
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

    def action_reject(self):
        self.ensure_one()
        self.write({'state': 'reject'})

    def action_cancel(self):
        self.ensure_one()
        if self.state == 'done':
            raise UserError(_('Không thể huỷ phiếu đã nhập kho.'))
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.write({'state': 'draft'})


class FreshImportLine(models.Model):
    _name = 'bhx.fresh.import.line'
    _description = 'Chi tiết hàng Fresh'

    import_id = fields.Many2one(
        'bhx.fresh.import',
        string='Phiếu nhập',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Sản phẩm',
        required=True,
    )
    product_code = fields.Char(
        string='Mã SKU',
        related='product_id.default_code',
        store=True,
    )
    cut_type = fields.Char(string='Phần / Bộ phận')
    lot_no = fields.Char(string='Số lô')
    weight = fields.Float(string='Trọng lượng nhận (kg)', required=True, default=0)
    expected_weight = fields.Float(string='Trọng lượng đặt (kg)', default=0)
    rejected_weight = fields.Float(string='Trọng lượng loại (kg)', default=0)
    unit_price = fields.Float(string='Đơn giá (đ/kg)', required=True, default=0)
    subtotal = fields.Float(
        string='Thành tiền',
        compute='_compute_subtotal',
        store=True,
    )
    color_check = fields.Boolean(string='Màu sắc đạt', default=True)
    smell_check = fields.Boolean(string='Mùi đạt', default=True)
    texture_check = fields.Boolean(string='Độ dai / Kết cấu đạt', default=True)
    note = fields.Char(string='Ghi chú')

    @api.depends('weight', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.weight * line.unit_price

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.unit_price = self.product_id.standard_price
