from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class FruitVegImport(models.Model):
    _name = 'bhx.fruit.veg.import'
    _description = 'Nhập rau củ trái cây'
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
        string='Ngày nhập',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    time_slot = fields.Selection([
        ('morning', 'Sáng (06:00 - 10:00)'),
        ('afternoon', 'Chiều (11:00 - 14:00)'),
        ('evening', 'Tối (17:00 - 20:00)'),
    ], string='Ca nhập hàng', required=True, default='morning', tracking=True)
    supplier_id = fields.Many2one(
        'res.partner',
        string='Nhà cung cấp / Vườn',
        required=True,
        tracking=True,
    )
    origin = fields.Char(string='Xuất xứ / Vùng trồng')
    harvest_date = fields.Date(string='Ngày thu hoạch')
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Kho nhập',
        required=True,
        tracking=True,
    )
    responsible_id = fields.Many2one(
        'res.users',
        string='Người nhận hàng',
        default=lambda self: self.env.user,
        tracking=True,
    )
    vehicle_plate = fields.Char(string='Biển số xe')
    temperature_check = fields.Float(string='Nhiệt độ bảo quản (°C)')
    note = fields.Text(string='Ghi chú')
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('receiving', 'Đang nhận hàng'),
        ('quality_check', 'Kiểm tra chất lượng'),
        ('done', 'Hoàn thành'),
        ('cancel', 'Đã huỷ'),
    ], string='Trạng thái', default='draft', tracking=True, required=True)

    line_ids = fields.One2many(
        'bhx.fruit.veg.import.line',
        'import_id',
        string='Chi tiết rau củ',
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
                vals['name'] = self.env['ir.sequence'].next_by_code('bhx.fruit.veg.import') or _('New')
        return super().create(vals_list)

    def action_start_receiving(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Vui lòng thêm sản phẩm trước khi bắt đầu.'))
        self.write({'state': 'receiving'})

    def action_quality_check(self):
        self.ensure_one()
        self.write({'state': 'quality_check'})

    def _create_stock_picking(self):
        """Tạo phiếu nhập kho Odoo (stock.picking) để cập nhật tồn kho dự trữ."""
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

        moves = []
        for line in self.line_ids:
            if line.weight <= 0:
                continue
            moves.append((0, 0, {
                'name': line.product_id.name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.weight,
                'product_uom': line.product_id.uom_id.id,
                'location_id': location_src.id,
                'location_dest_id': location_dest.id,
                'origin': self.name,
            }))

        if not moves:
            raise UserError(_('Không có hàng nào để nhập kho (trọng lượng = 0).'))

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
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            if hasattr(move, 'picked'):
                move.picked = True
        picking.with_context(skip_immediate=True, skip_backorder=True).button_validate()
        return picking

    def action_confirm_done(self):
        self.ensure_one()

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

    def action_cancel(self):
        self.ensure_one()
        if self.state == 'done':
            raise UserError(_('Không thể huỷ phiếu đã hoàn thành.'))
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.write({'state': 'draft'})


class FruitVegImportLine(models.Model):
    _name = 'bhx.fruit.veg.import.line'
    _description = 'Chi tiết nhập rau củ trái cây'

    import_id = fields.Many2one(
        'bhx.fruit.veg.import',
        string='Phiếu nhập',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Sản phẩm',
        required=True,
    )
    category = fields.Selection([
        ('vegetable', 'Rau củ'),
        ('fruit', 'Trái cây'),
        ('herb', 'Rau thơm / Gia vị'),
        ('mushroom', 'Nấm'),
        ('other', 'Khác'),
    ], string='Loại', required=True, default='vegetable')
    origin_detail = fields.Char(string='Chi tiết xuất xứ')
    weight = fields.Float(string='Trọng lượng nhận (kg)', required=True, default=0)
    expected_weight = fields.Float(string='Trọng lượng đặt (kg)', default=0)
    rejected_weight = fields.Float(string='Trọng lượng loại (kg)', default=0)
    quality_grade = fields.Selection([
        ('A', 'Loại A - Tốt'),
        ('B', 'Loại B - Khá'),
        ('C', 'Loại C - Trung bình'),
    ], string='Phân loại chất lượng', default='A')
    freshness_check = fields.Boolean(string='Đủ độ tươi', default=True)
    unit_price = fields.Float(string='Đơn giá (đ/kg)', required=True, default=0)
    subtotal = fields.Float(
        string='Thành tiền',
        compute='_compute_subtotal',
        store=True,
    )
    note = fields.Char(string='Ghi chú')

    @api.depends('weight', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.weight * line.unit_price

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.unit_price = self.product_id.standard_price
