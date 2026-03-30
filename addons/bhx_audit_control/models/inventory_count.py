from odoo import models, fields, api, _
from odoo.exceptions import UserError


class InventoryCount(models.Model):
    _name = 'bhx.inventory.count'
    _description = 'Phiếu kiểm kê hàng hoá'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Mã phiếu kiểm kê', required=True, copy=False,
        readonly=True, default=lambda self: _('New'), tracking=True,
    )
    date = fields.Date(string='Ngày kiểm kê', required=True, default=fields.Date.today, tracking=True)
    count_type = fields.Selection([
        ('full', 'Kiểm kê toàn bộ'),
        ('cycle', 'Kiểm kê luân phiên (Cycle Count)'),
        ('spot', 'Kiểm kê đột xuất'),
        ('expiry', 'Kiểm tra hạn sử dụng'),
    ], string='Loại kiểm kê', required=True, default='cycle', tracking=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Kho / Cửa hàng', required=True, tracking=True)
    zone = fields.Selection([
        ('fmcg', 'Khu FMCG'),
        ('fruit_veg', 'Khu Rau củ trái cây'),
        ('fresh', 'Khu Hàng Fresh'),
        ('all', 'Toàn bộ cửa hàng'),
    ], string='Khu vực kiểm kê', default='all', tracking=True)
    responsible_id = fields.Many2one(
        'res.users', string='Trưởng nhóm kiểm kê',
        default=lambda self: self.env.user, tracking=True,
    )
    approved_id = fields.Many2one('res.users', string='Người phê duyệt', tracking=True)
    start_time = fields.Datetime(string='Bắt đầu kiểm kê')
    end_time = fields.Datetime(string='Kết thúc kiểm kê')
    note = fields.Text(string='Ghi chú / Hướng dẫn')
    state = fields.Selection([
        ('draft', 'Kế hoạch'),
        ('in_progress', 'Đang kiểm kê'),
        ('review', 'Chờ xét duyệt'),
        ('approved', 'Đã duyệt'),
        ('cancel', 'Đã huỷ'),
    ], string='Trạng thái', default='draft', tracking=True)

    line_ids = fields.One2many('bhx.inventory.count.line', 'count_id', string='Chi tiết kiểm kê')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    total_products = fields.Integer(compute='_compute_summary', store=True, string='Tổng SP')
    total_diff = fields.Float(compute='_compute_summary', store=True, string='Tổng chênh lệch')
    has_diff = fields.Boolean(compute='_compute_summary', store=True, string='Có chênh lệch')

    @api.depends('line_ids.qty_diff')
    def _compute_summary(self):
        for rec in self:
            rec.total_products = len(rec.line_ids)
            rec.total_diff = sum(abs(l.qty_diff) for l in rec.line_ids)
            rec.has_diff = any(l.qty_diff != 0 for l in rec.line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('bhx.inventory.count') or _('New')
        return super().create(vals_list)

    def action_start(self):
        if not self.line_ids:
            raise UserError(_('Vui lòng thêm sản phẩm cần kiểm kê trước khi bắt đầu.'))
        self.write({'state': 'in_progress', 'start_time': fields.Datetime.now()})

    def action_review(self):
        self.write({'state': 'review', 'end_time': fields.Datetime.now()})

    def action_approve(self):
        # Tự động cập nhật lại tồn kho kệ lẻ (Module 2) từ số liệu kiểm đếm thực tế
        for line in self.line_ids:
            display_lines = self.env['bhx.display.location.line'].search([
                ('product_id', '=', line.product_id.id),
                ('location_id.warehouse_id', '=', self.warehouse_id.id)
            ], limit=1)
            for display_line in display_lines:
                display_line.current_qty = line.qty_counted
        
        self.write({'state': 'approved', 'approved_id': self.env.user.id})

    def action_cancel(self):
        if self.state == 'approved':
            raise UserError(_('Không thể huỷ phiếu đã phê duyệt.'))
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.write({'state': 'draft'})


class InventoryCountLine(models.Model):
    _name = 'bhx.inventory.count.line'
    _description = 'Chi tiết kiểm kê'

    count_id = fields.Many2one('bhx.inventory.count', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Sản phẩm', required=True)
    product_uom_id = fields.Many2one('uom.uom', related='product_id.uom_id', store=True)
    barcode = fields.Char(related='product_id.barcode', store=True, string='Barcode')
    lot_id = fields.Many2one('stock.lot', string='Số lô')
    expiry_date = fields.Date(string='Hạn sử dụng')
    qty_system = fields.Float(string='Tồn kho hệ thống')
    qty_counted = fields.Float(string='Số lượng kiểm đếm thực tế')
    qty_diff = fields.Float(
        string='Chênh lệch',
        compute='_compute_diff', store=True,
    )
    diff_reason = fields.Char(string='Lý do chênh lệch')
    location_detail = fields.Char(string='Vị trí trong kho / kệ')
    note = fields.Char(string='Ghi chú')

    @api.depends('qty_system', 'qty_counted')
    def _compute_diff(self):
        for line in self:
            line.qty_diff = line.qty_counted - line.qty_system
