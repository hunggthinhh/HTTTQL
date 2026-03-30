from odoo import models, fields, api, _
from odoo.exceptions import UserError


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
        ('write_off', 'Xuất huỷ / Hàng lỗi hỏng'),
    ], string='Loại điều chỉnh', required=True, default='increase', tracking=True)
    reason = fields.Selection([
        ('count_diff', 'Chênh lệch kiểm kê'),
        ('damage', 'Hàng hư / Vỡ / Rò rỉ'),
        ('theft', 'Mất mát / Trộm cắp'),
        ('expired', 'Hết hạn sử dụng'),
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
        self.write({
            'state': 'approved',
            'approved_id': self.env.user.id,
        })

    def action_done(self):
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
    lot_id = fields.Many2one('stock.lot', string='Số lô / HSD')
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
            if adj_type in ('increase', 'display_return'):
                line.qty_after = line.qty_before + line.qty_change
            elif adj_type in ('decrease', 'write_off', 'transfer'):
                line.qty_after = line.qty_before - line.qty_change
            else:
                line.qty_after = line.qty_before + line.qty_change
