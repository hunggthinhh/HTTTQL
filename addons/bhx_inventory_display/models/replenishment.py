from odoo import models, fields, api, _
from odoo.exceptions import UserError


class Replenishment(models.Model):
    _name = 'bhx.replenishment'
    _description = 'Đợt châm hàng'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Mã đợt châm hàng',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    date = fields.Datetime(
        string='Ngày tạo',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Kho cửa hàng',
        required=True,
        tracking=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Người phụ trách',
        default=lambda self: self.env.user,
        tracking=True,
    )
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('in_progress', 'Đang thực hiện'),
        ('done', 'Hoàn thành'),
        ('cancel', 'Đã huỷ'),
    ], string='Trạng thái', default='draft', tracking=True, required=True)

    line_ids = fields.One2many(
        'bhx.replenishment.line',
        'replenishment_id',
        string='Chi tiết châm hàng',
    )
    
    total_items = fields.Integer(
        string='Tổng số mặt hàng',
        compute='_compute_total_items',
    )

    @api.depends('line_ids')
    def _compute_total_items(self):
        for rec in self:
            rec.total_items = len(rec.line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('bhx.replenishment') or _('New')
        return super().create(vals_list)

    def action_confirm(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Vui lòng thêm sản phẩm trước khi bắt đầu châm hàng.'))
        self.write({'state': 'in_progress'})

    def action_done(self):
        self.ensure_one()
        # Cập nhật tồn kho trên kệ trưng bày
        for line in self.line_ids:
            # Kiểm tra còn đủ hàng trong kho không
            quant = self.env['stock.quant'].search([
                ('product_id', '=', line.product_id.id),
                ('location_id', '=', self.warehouse_id.lot_stock_id.id),
            ], limit=1)
            available_qty = quant.quantity - quant.reserved_quantity if quant else 0

            if line.qty_to_replenish > available_qty:
                raise UserError(
                    _('Không đủ hàng trong kho để châm cho sản phẩm "%s"!\n'
                      'Tồn kho hiện tại: %.2f - Yêu cầu: %.2f')
                    % (line.product_id.display_name, available_qty, line.qty_to_replenish)
                )

            display_line = self.env['bhx.display.location.line'].search([
                ('location_id', '=', line.location_id.id),
                ('product_id', '=', line.product_id.id)
            ], limit=1)

            if display_line:
                display_line.current_qty += line.qty_to_replenish
            else:
                # Nếu sản phẩm chưa có trên kệ này, tạo mới luôn
                self.env['bhx.display.location.line'].create({
                    'location_id': line.location_id.id,
                    'product_id': line.product_id.id,
                    'current_qty': line.qty_to_replenish,
                    'min_qty': 5, # Mặc định tối thiểu là 5
                    'max_qty': 20, # Mặc định tối đa là 20
                })

        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancel'})


class ReplenishmentLine(models.Model):
    _name = 'bhx.replenishment.line'
    _description = 'Chi tiết đợt châm hàng'

    replenishment_id = fields.Many2one(
        'bhx.replenishment',
        string='Đợt châm hàng',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one('product.product', string='Sản phẩm', required=True)
    location_id = fields.Many2one('bhx.display.location', string='Vị trí kệ trưng bày')
    expiry_date = fields.Date(string='Hạn sử dụng')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Tự động tìm và điền vị trí kệ khi chọn sản phẩm."""
        if not self.product_id:
            return
        warehouse = self.replenishment_id.warehouse_id
        if not warehouse:
            return
        # Ưu tiên tìm kệ mà sản phẩm này đang được trưng bày
        display_line = self.env['bhx.display.location.line'].search([
            ('product_id', '=', self.product_id.id),
            ('location_id.warehouse_id', '=', warehouse.id),
        ], limit=1)
        if display_line:
            self.location_id = display_line.location_id
            self.qty_to_replenish = max(1, (display_line.max_qty or display_line.min_qty * 2) - display_line.current_qty)
        
        if display_line:
            self.location_id = display_line.location_id
            self.qty_to_replenish = max(1, (display_line.max_qty or display_line.min_qty * 2) - display_line.current_qty)
        
        # --- Tìm HSD gợi ý (Ưu tiên từ các đợt nhập hàng gần nhất) ---
        import_line = False
        # 1. FMCG
        import_line = self.env['bhx.fmcg.import.line'].search([
            ('product_id', '=', self.product_id.id),
            ('expiry_date', '!=', False)
        ], order='id desc', limit=1)
        
        # 2. Fresh (nếu không thấy FMCG)
        if not import_line:
            import_line = self.env['bhx.fresh.import.line'].search([
                ('product_id', '=', self.product_id.id),
                ('expiry_date', '!=', False)
            ], order='id desc', limit=1)
            
        # 3. Fruit & Veg
        if not import_line:
            import_line = self.env['bhx.fruit.veg.import.line'].search([
                ('product_id', '=', self.product_id.id),
                ('expiry_date', '!=', False)
            ], order='id desc', limit=1)
            
        if import_line:
            self.expiry_date = import_line.expiry_date
        else:
            # Fallback: Lấy theo số lô tồn kho nếu không thấy lịch sử nhập
            lot = self.env['stock.lot'].search([('product_id', '=', self.product_id.id)], order='expiration_date asc', limit=1)
            if lot:
                self.expiry_date = lot.expiration_date
    
    current_shelf_qty = fields.Float(
        string='Tồn trên kệ',
        compute='_compute_shelf_qty',
        readonly=True,
    )
    warehouse_stock_qty = fields.Float(
        string='Tồn trong kho dự trữ',
        compute='_compute_shelf_qty',
        readonly=True,
    )
    qty_to_replenish = fields.Float(string='SL châm thêm', default=1, required=True)
    uom_id = fields.Many2one('uom.uom', string='ĐVT', related='product_id.uom_id')

    @api.depends('product_id', 'location_id')
    def _compute_shelf_qty(self):
        for line in self:
            if line.product_id and line.location_id:
                display_line = self.env['bhx.display.location.line'].search([
                    ('location_id', '=', line.location_id.id),
                    ('product_id', '=', line.product_id.id)
                ], limit=1)
                line.current_shelf_qty = display_line.current_qty if display_line else 0

                # Tồn kho thực tế trong kho dự trữ
                warehouse = line.replenishment_id.warehouse_id
                if warehouse:
                    quant = self.env['stock.quant'].search([
                        ('product_id', '=', line.product_id.id),
                        ('location_id', '=', warehouse.lot_stock_id.id),
                    ], limit=1)
                    line.warehouse_stock_qty = (quant.quantity - quant.reserved_quantity) if quant else 0
                else:
                    line.warehouse_stock_qty = 0
            else:
                line.current_shelf_qty = 0
                line.warehouse_stock_qty = 0
