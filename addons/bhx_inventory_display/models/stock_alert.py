from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date, timedelta


class StockAlert(models.Model):
    _name = 'bhx.stock.alert'
    _description = 'Cảnh báo tồn kho'
    _inherit = ['mail.thread']
    _order = 'alert_type, priority desc, create_date desc'

    name = fields.Char(string='Tiêu đề cảnh báo', required=True, tracking=True)
    alert_type = fields.Selection([
        ('low_stock', 'Sắp hết hàng'),
        ('out_of_stock', 'Hết hàng'),
        ('near_expiry', 'Sắp hết hạn'),
        ('expired', 'Đã hết hạn'),
        ('overstock', 'Tồn kho quá nhiều'),
        ('temperature', 'Bất thường nhiệt độ'),
    ], string='Loại cảnh báo', required=True, tracking=True)
    priority = fields.Selection([
        ('0', 'Thấp'),
        ('1', 'Trung bình'),
        ('2', 'Cao'),
        ('3', 'Khẩn cấp'),
    ], string='Mức độ ưu tiên', default='1', tracking=True)
    product_id = fields.Many2one('product.product', string='Sản phẩm', required=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Kho / Cửa hàng', required=True)
    lot_id = fields.Many2one('stock.lot', string='Số lô')
    expiry_date = fields.Date(string='Hạn sử dụng')
    days_to_expiry = fields.Integer(
        string='Số ngày còn lại',
        compute='_compute_days_to_expiry',
        store=True,
    )
    current_qty = fields.Float(string='Tồn kho hiện tại')
    min_qty = fields.Float(string='Mức tối thiểu')
    max_qty = fields.Float(string='Mức tối đa')
    responsible_id = fields.Many2one(
        'res.users', string='Người xử lý',
        default=lambda self: self.env.user,
    )
    note = fields.Text(string='Hướng xử lý / Ghi chú')
    state = fields.Selection([
        ('new', 'Mới'),
        ('processing', 'Đang xử lý'),
        ('resolved', 'Đã xử lý'),
        ('ignored', 'Bỏ qua'),
    ], string='Trạng thái', default='new', tracking=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company,
    )

    @api.depends('expiry_date')
    def _compute_days_to_expiry(self):
        today = date.today()
        for rec in self:
            if rec.expiry_date:
                rec.days_to_expiry = (rec.expiry_date - today).days
            else:
                rec.days_to_expiry = 0

    def action_processing(self):
        self.write({'state': 'processing'})

    def action_resolved(self):
        self.write({'state': 'resolved'})

    def action_ignore(self):
        self.write({'state': 'ignored'})

    def action_reopen(self):
        self.write({'state': 'new'})

    def action_add_to_replenishment(self):
        # Lọc ra các cảnh báo chưa được xử lý và có cùng kho
        alerts = self.filtered(lambda a: a.state in ('new', 'processing'))
        if not alerts:
            raise UserError(_('Không có cảnh báo nào hợp lệ để châm hàng.'))
            
        warehouses = alerts.mapped('warehouse_id')
        if len(warehouses) > 1:
            raise UserError(_('Vui lòng chỉ chọn các cảnh báo cùng một cửa hàng/kho.'))

        # Tạo đợt châm hàng mới
        replenishment = self.env['bhx.replenishment'].create({
            'warehouse_id': warehouses[0].id,
            'state': 'draft',
        })

        for alert in alerts:
            # Tìm vị trí trưng bày của sản phẩm này tại kho tương ứng
            display_line = self.env['bhx.display.location.line'].search([
                ('product_id', '=', alert.product_id.id),
                ('location_id.warehouse_id', '=', alert.warehouse_id.id)
            ], limit=1)

            if display_line:
                self.env['bhx.replenishment.line'].create({
                    'replenishment_id': replenishment.id,
                    'product_id': alert.product_id.id,
                    'location_id': display_line.location_id.id,
                    'qty_to_replenish': alert.max_qty - alert.current_qty,
                })
                alert.write({'state': 'processing', 'note': f'Đã thêm vào đợt châm hàng: {replenishment.name}'})

        return {
            'name': _('Đợt châm hàng vừa tạo'),
            'type': 'ir.actions.act_window',
            'res_model': 'bhx.replenishment',
            'view_mode': 'form',
            'res_id': replenishment.id,
            'target': 'current',
        }

    def action_create_import_order(self):
        self.ensure_one()
        if self.state == 'resolved':
            raise UserError(_('Cảnh báo này đã được xử lý.'))

        product = self.product_id
        categ_name = product.categ_id.name.lower() if product.categ_id else ''
        
        # Xác định loại phiếu nhập dựa vào category
        import_model = 'bhx.fmcg.import'
        if any(keyword in categ_name for keyword in ['tươi', 'sống', 'thịt', 'cá', 'sữa', 'fresh']):
            import_model = 'bhx.fresh.import'
        elif any(keyword in categ_name for keyword in ['rau', 'củ', 'quả', 'trái cây', 'fruit', 'veg']):
            import_model = 'bhx.fruit.veg.import'

        # Tạo phiếu nhập nháp
        qty_to_import = self.max_qty - self.current_qty
        if qty_to_import <= 0:
            qty_to_import = self.min_qty # Ít nhất nhập bằng mức tối thiểu

        line_vals = {
            'product_id': product.id,
            'unit_price': product.standard_price,
        }
        # Phân biệt tên trường số lượng
        if import_model == 'bhx.fmcg.import':
            line_vals['quantity'] = qty_to_import
        else:
            line_vals['expected_weight'] = qty_to_import

        # Mặc định nhà cung cấp là Kho trung tâm
        central_warehouse = self.env['res.partner'].search([('name', 'ilike', 'Kho trung tâm')], limit=1)
        if not central_warehouse:
            central_warehouse = self.env['res.partner'].create({
                'name': 'Kho trung tâm',
                'is_company': True,
                'supplier_rank': 1,
            })
        supplier_id = central_warehouse.id

        vals = {
            'warehouse_id': self.warehouse_id.id,
            'supplier_id': supplier_id,
            'line_ids': [(0, 0, line_vals)]
        }
        
        # Bổ sung Hạn sử dụng cho hàng Fresh (bắt buộc)
        if import_model == 'bhx.fresh.import':
            vals['expiry_date'] = self.expiry_date or (fields.Date.today() + timedelta(days=3))
        
        new_import = self.env[import_model].create(vals)
        self.write({'state': 'processing', 'note': f'Đã tạo phiếu nhập: {new_import.name}'})

        return {
            'name': _('Phiếu nhập hàng đã tạo'),
            'type': 'ir.actions.act_window',
            'res_model': import_model,
            'view_mode': 'form',
            'res_id': new_import.id,
            'target': 'current',
        }
