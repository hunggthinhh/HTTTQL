from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class StockAdjustment(models.Model):
    _name = 'bhx.stock.adjustment'
    _description = 'Điều chỉnh tồn kho nội bộ'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Mã phiếu điều chỉnh',
        required=True, copy=False, readonly=True,
        default=lambda self: _('New'), tracking=True,
    )
    date = fields.Date(
        string='Ngày điều chỉnh',
        required=True, default=fields.Date.today, tracking=True,
    )
    adjustment_type = fields.Selection([
        ('increase', 'Tăng tồn kho'),
        ('decrease', 'Giảm tồn kho'),
        ('transfer', 'Chuyển khu trưng bày'),
    ], string='Loại điều chỉnh', required=True, default='increase', tracking=True)
    reason = fields.Selection([
        ('count_diff', 'Chênh lệch kiểm kê'),
        ('damage', 'Hàng hư / Vỡ / Rò rỉ'),
        ('theft', 'Mất mát / Trộm cắp'),
        ('display_replenish', 'Bổ sung quầy trưng bày'),
        ('display_return', 'Hoàn kho từ quầy trưng bày'),
        ('other', 'Lý do khác'),
    ], string='Lý do', required=True, default='count_diff')
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Kho / Cửa hàng', required=True, tracking=True,
    )
    responsible_id = fields.Many2one(
        'res.users', string='Người thực hiện',
        default=lambda self: self.env.user, tracking=True,
    )
    approved_id = fields.Many2one(
        'res.users', string='Người phê duyệt', tracking=True,
    )
    note = fields.Text(string='Ghi chú')
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('confirm', 'Chờ duyệt'),
        ('approved', 'Đã duyệt'),
        ('done', 'Hoàn thành'),
        ('cancel', 'Đã huỷ'),
    ], string='Trạng thái', default='draft', tracking=True)
    line_ids = fields.One2many(
        'bhx.stock.adjustment.line', 'adjustment_id', string='Chi tiết điều chỉnh',
    )
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company,
    )
    inventory_count_id = fields.Many2one('bhx.inventory.count', string='Từ phiếu kiểm kê', readonly=True)
    alert_id = fields.Many2one('bhx.stock.alert', string='Từ cảnh báo', readonly=True)
    overstock_msg = fields.Char(compute='_compute_overstock_msg')

    def _compute_overstock_msg(self):
        overstock_count = self.env['bhx.stock.alert'].search_count([
            ('alert_type', '=', 'overstock'),
            ('state', 'in', ['new', 'processing'])
        ])
        msg = _('CHÚ Ý: Có %s sản phẩm đang bị quá tải trên kệ. Cần tạo phiếu rút hàng!') % overstock_count if overstock_count else False
        for rec in self:
            rec.overstock_msg = msg

    @api.constrains('line_ids', 'reason')
    def _check_return_lines(self):
        for rec in self:
            if rec.reason == 'display_return':
                if not rec.line_ids:
                    raise ValidationError(_('Phiếu rút hàng từ quầy trưng bày phải có ít nhất một dòng chi tiết.'))
                for line in rec.line_ids:
                    if not line.display_location_id:
                        raise ValidationError(_('Vui lòng chọn Kệ trưng bày cho sản phẩm %s để thực hiện rút hàng.') % line.product_id.name)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('bhx.stock.adjustment') or _('New')
        return super().create(vals_list)

    def action_confirm(self):
        if not self.line_ids:
            raise UserError(_('Vui lòng thêm ít nhất một sản phẩm.'))
        self.write({'state': 'confirm'})

    def action_approve(self):
        self.ensure_one()
        self.write({
            'state': 'approved',
            'approved_id': self.env.user.id,
        })

    def _apply_stock_moves(self):
        """Sử dụng cơ chế kiểm kê chuẩn của Odoo (stock.quant) để tăng/giảm kho."""
        self.ensure_one()
        warehouse = self.warehouse_id
        location_internal = warehouse.lot_stock_id

        if self.adjustment_type in ['increase', 'decrease']:
            for line in self.line_ids:
                if line.qty_change <= 0:
                    continue
                
                # Tìm lượng tồn hiện tại trong kho dự trữ
                domain = [
                    ('product_id', '=', line.product_id.id),
                    ('location_id', '=', location_internal.id),
                ]
                if line.lot_id:
                    domain.append(('lot_id', '=', line.lot_id.id))
                
                quant = self.env['stock.quant'].search(domain, limit=1)
                current_qty = quant.quantity if quant else 0.0
                
                # Tính toán số lượng mới
                if self.adjustment_type == 'increase':
                    new_qty = current_qty + line.qty_change
                else:
                    new_qty = current_qty - line.qty_change

                # Cập nhật tồn kho qua chức năng Inventory Adjustment
                quant_vals = {
                    'product_id': line.product_id.id,
                    'location_id': location_internal.id,
                    'inventory_quantity': new_qty,
                }
                if line.lot_id:
                    quant_vals['lot_id'] = line.lot_id.id
                    
                # Tạo hoặc update stock.quant (dùng sudo để tránh lỗi phân quyền nếu có)
                quant_record = self.env['stock.quant'].sudo().with_context(inventory_mode=True).create(quant_vals)
                quant_record.action_apply_inventory()

        # Cập nhật số lượng trên kệ trưng bày (nếu có chọn kệ)
        for line in self.line_ids:
            if line.display_location_id:
                display_line = self.env['bhx.display.location.line'].search([
                    ('location_id', '=', line.display_location_id.id),
                    ('product_id', '=', line.product_id.id)
                ], limit=1)
                
                if display_line:
                    if self.adjustment_type == 'increase':
                        display_line.current_qty += line.qty_change
                    elif self.adjustment_type == 'decrease':
                        display_line.current_qty -= line.qty_change
                    elif self.adjustment_type == 'transfer':
                        if self.reason == 'display_replenish':
                            display_line.current_qty += line.qty_change
                        elif self.reason == 'display_return':
                            display_line.current_qty -= line.qty_change
                else:
                    # Nếu kệ chưa có sản phẩm này nhưng cần thêm vào
                    if self.adjustment_type == 'increase' or (self.adjustment_type == 'transfer' and self.reason == 'display_replenish'):
                        self.env['bhx.display.location.line'].create({
                            'location_id': line.display_location_id.id,
                            'product_id': line.product_id.id,
                            'current_qty': line.qty_change,
                            'capacity': max(10, line.qty_change * 2), # Default capacity
                        })

    def action_done(self):
        self.ensure_one()
        self._apply_stock_moves()
        self.write({'state': 'done'})

    def action_cancel(self):
        if self.state == 'done':
            raise UserError(_('Không thể huỷ phiếu đã hoàn thành.'))
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.write({'state': 'draft'})


class StockAdjustmentLine(models.Model):
    _name = 'bhx.stock.adjustment.line'
    _description = 'Chi tiết điều chỉnh tồn kho'

    adjustment_id = fields.Many2one(
        'bhx.stock.adjustment', required=True, ondelete='cascade',
    )
    product_id = fields.Many2one('product.product', string='Sản phẩm', required=True)
    product_uom_id = fields.Many2one(
        'uom.uom', string='ĐVT',
        related='product_id.uom_id', store=True,
    )
    lot_id = fields.Many2one('stock.lot', string='Số lô')
    display_location_id = fields.Many2one('bhx.display.location', string='Kệ trưng bày (Nếu có)')
    qty_before = fields.Float(string='Tồn kho trước')
    qty_change = fields.Float(string='Số lượng điều chỉnh', required=True)
    qty_after = fields.Float(
        string='Tồn kho sau',
        compute='_compute_qty_after',
        store=True,
    )
    note = fields.Char(string='Ghi chú dòng')

    @api.depends('qty_before', 'qty_change', 'adjustment_id.adjustment_type')
    def _compute_qty_after(self):
        for line in self:
            adj_type = line.adjustment_id.adjustment_type
            if adj_type == 'increase':
                line.qty_after = line.qty_before + line.qty_change
            elif adj_type in ('decrease', 'transfer'):
                line.qty_after = line.qty_before - line.qty_change
            else:
                line.qty_after = line.qty_before + line.qty_change

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if not self.product_id:
            return
        
        warehouse = self.adjustment_id.warehouse_id or self.env['stock.warehouse'].search([], limit=1)
        if warehouse:
            # 1. Tồn kho hệ thống
            self.qty_before = self.product_id.with_context(warehouse=warehouse.id).qty_available
            
            # 2. Số lô
            quant = self.env['stock.quant'].search([
                ('product_id', '=', self.product_id.id),
                ('location_id', 'child_of', warehouse.lot_stock_id.id),
                ('lot_id', '!=', False),
                ('quantity', '>', 0)
            ], order='in_date desc', limit=1)
            
            if quant:
                self.lot_id = quant.lot_id
            else:
                lot = self.env['stock.lot'].search([('product_id', '=', self.product_id.id)], order='create_date desc', limit=1)
                if lot:
                    self.lot_id = lot
            
            # 3. Kệ trưng bày
            display_line = self.env['bhx.display.location.line'].search([
                ('product_id', '=', self.product_id.id),
                ('location_id.warehouse_id', '=', warehouse.id)
            ], limit=1)
            if display_line:
                self.display_location_id = display_line.location_id
