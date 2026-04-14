from odoo import models, fields, api, _
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
    delivery_note = fields.Char(string='Số phiếu giao hàng')
    vehicle_plate = fields.Char(string='Biển số xe')
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
        self.write({'state': 'checking'})

    def _create_stock_picking(self):
        """
        HÀM QUAN TRỌNG: Tạo phiếu nhập kho và GHI NHỚ HSD VÀO LÔ HÀNG ODOO.
        Nếu xóa đoạn này, hệ thống sẽ không thể cảnh báo HSD.
        """
        self.ensure_one()
        warehouse = self.warehouse_id
        location_dest = warehouse.lot_stock_id
        location_src = self.env.ref('stock.stock_location_suppliers')

        picking_type = self.env['stock.picking.type'].search([
            ('warehouse_id', '=', warehouse.id),
            ('code', '=', 'incoming'),
        ], limit=1)
        if not picking_type:
            raise UserError(_('Không tìm thấy loại phiếu nhập kho.'))

        picking = self.env['stock.picking'].create({
            'partner_id': self.supplier_id.id,
            'picking_type_id': picking_type.id,
            'location_id': location_src.id,
            'location_dest_id': location_dest.id,
            'origin': self.name,
        })

        moves_count = 0
        for line in self.line_ids:
            # Chỉ tạo phiếu nhập cho những dòng có số lượng > 0
            if line.checked_qty <= 0:
                continue
            
            moves_count += 1
            move = self.env['stock.move'].create({
                'name': line.product_id.name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.checked_qty,
                'product_uom': line.product_uom_id.id,
                'location_id': location_src.id,
                'location_dest_id': location_dest.id,
                'picking_id': picking.id,
                'picking_type_id': picking_type.id,
            })
            move._action_confirm()

            # TỰ ĐỘNG TẠO LÔ HÀNG VÀ GÁN HSD
            lot_name = line.lot_no or f"LOT-{self.name}-{line.product_id.id}"
            lot_vals = {
                'name': lot_name,
                'product_id': line.product_id.id,
                'company_id': self.company_id.id,
            }
            # Gán HSD nếu User có nhập
            if line.expiry_date:
                lot_vals['expiration_date'] = line.expiry_date
                
            lot = self.env['stock.lot'].create(lot_vals)

            self.env['stock.move.line'].create({
                'product_id': line.product_id.id,
                'product_uom_id': line.product_uom_id.id,
                'location_id': location_src.id,
                'location_dest_id': location_dest.id,
                'picking_id': picking.id,
                'move_id': move.id,
                'lot_id': lot.id,
                'quantity': line.checked_qty,
            })

        if moves_count == 0:
            raise UserError(_('LỖI: Bạn chưa nhập "SL thực nhận" cho sản phẩm nào. Hệ thống không thể nhập kho với số lượng bằng 0.'))

        picking.action_assign()
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
    lot_no = fields.Char(string='Số lô / HSD')
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
