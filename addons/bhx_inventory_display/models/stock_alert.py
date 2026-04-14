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
        ('audit_required', 'Yêu cầu kiểm kê'),
        ('control_required', 'Yêu cầu kiểm soát'),
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

    inventory_count_ids = fields.One2many('bhx.inventory.count', 'alert_id', string='Phiếu kiểm kê')
    goods_control_ids = fields.One2many('bhx.goods.control', 'alert_id', string='Phiếu kiểm soát')
    disposal_ids = fields.One2many('bhx.disposal', 'alert_id', string='Phiếu huỷ hàng')

    count_inventory = fields.Integer(compute='_compute_audit_counts', string='Số kiểm kê')
    count_goods_control = fields.Integer(compute='_compute_audit_counts', string='Số kiểm soát')
    count_disposal = fields.Integer(compute='_compute_audit_counts', string='Số xử lý')

    @api.depends('inventory_count_ids', 'goods_control_ids', 'disposal_ids')
    def _compute_audit_counts(self):
        for rec in self:
            rec.count_inventory = len(rec.inventory_count_ids)
            rec.count_goods_control = len(rec.goods_control_ids)
            rec.count_disposal = len(rec.disposal_ids)

    def action_view_inventory(self):
        action = self.env.ref('bhx_audit_control.action_inventory_count').sudo().read()[0]
        action['domain'] = [('alert_id', '=', self.id)]
        action['context'] = {'default_alert_id': self.id}
        return action

    def action_view_goods_control(self):
        action = self.env.ref('bhx_audit_control.action_goods_control').sudo().read()[0]
        action['domain'] = [('alert_id', '=', self.id)]
        action['context'] = {'default_alert_id': self.id}
        return action

    def action_view_disposal(self):
        action = self.env.ref('bhx_audit_control.action_disposal').sudo().read()[0]
        action['domain'] = [('alert_id', '=', self.id)]
        action['context'] = {'default_alert_id': self.id}
        return action

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

            location_id = display_line.location_id.id if display_line else False
            
            if not location_id:
                # Nếu hàng chưa từng có trên kệ, lấy đại 1 kệ trong cửa hàng
                any_location = self.env['bhx.display.location'].search([
                    ('warehouse_id', '=', alert.warehouse_id.id)
                ], limit=1)
                location_id = any_location.id if any_location else False

            if location_id:
                qty_to_rep = alert.max_qty - alert.current_qty
                if qty_to_rep <= 0:
                    qty_to_rep = 10 # Gợi ý mặc định 10 nếu không có min/max rõ ràng
                    
                self.env['bhx.replenishment.line'].create({
                    'replenishment_id': replenishment.id,
                    'product_id': alert.product_id.id,
                    'location_id': location_id,
                    'qty_to_replenish': qty_to_rep,
                })
                alert.write({'state': 'processing', 'note': f'Đã thêm vào đợt châm hàng: {replenishment.name}'})
            else:
                alert.write({'note': 'Lỗi: Cửa hàng chưa có kệ trưng bày nào!'})

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

    def action_create_inventory_count(self):
        self.ensure_one()
        if self.state == 'resolved':
            raise UserError(_('Cảnh báo này đã được xử lý.'))
            
        count_vals = {
            'alert_id': self.id,
            'warehouse_id': self.warehouse_id.id,
            'note': f'Tạo từ cảnh báo: {self.name}',
            'count_type': 'spot',
            'line_ids': [(0, 0, {
                'product_id': self.product_id.id,
                'lot_id': self.lot_id.id if self.lot_id else False,
                'expiry_date': self.expiry_date,
                'qty_system': self.current_qty,
            })]
        }
        
        new_count = self.env['bhx.inventory.count'].create(count_vals)
        self.write({'state': 'processing', 'note': f'Đã tạo phiếu kiểm kê: {new_count.name}'})
        
        return {
            'name': _('Phiếu kiểm kê'),
            'type': 'ir.actions.act_window',
            'res_model': 'bhx.inventory.count',
            'view_mode': 'form',
            'res_id': new_count.id,
            'target': 'current',
        }

    def action_create_goods_control(self):
        self.ensure_one()
        if self.state == 'resolved':
            raise UserError(_('Cảnh báo này đã được xử lý.'))
            
        ctrl_vals = {
            'alert_id': self.id,
            'warehouse_id': self.warehouse_id.id,
            'check_type': 'random',
            'note': f'Tạo từ cảnh báo: {self.name}',
            'line_ids': [(0, 0, {
                'product_id': self.product_id.id,
                'lot_id': self.lot_id.id if self.lot_id else False,
                'expiry_date': self.expiry_date,
                'qty_on_display': self.current_qty,
            })]
        }
        new_ctrl = self.env['bhx.goods.control'].create(ctrl_vals)
        self.write({'state': 'processing', 'note': f'Đã tạo phiếu kiểm soát: {new_ctrl.name}'})
        
        return {
            'name': _('Phiếu kiểm soát'),
            'type': 'ir.actions.act_window',
            'res_model': 'bhx.goods.control',
            'view_mode': 'form',
            'res_id': new_ctrl.id,
            'target': 'current',
        }

    def action_create_disposal(self):
        self.ensure_one()
        if self.state == 'resolved':
            raise UserError(_('Cảnh báo này đã được xử lý.'))
            
        reason = 'expire'
        if self.alert_type == 'expired':
            reason = 'expire'
        else:
            reason = 'other'
            
        disposal_vals = {
            'alert_id': self.id,
            'warehouse_id': self.warehouse_id.id,
            'disposal_type': reason,
            'note': f'Tạo từ cảnh báo: {self.name}',
            'line_ids': [(0, 0, {
                'product_id': self.product_id.id,
                'lot_id': self.lot_id.id if self.lot_id else False,
                'expiry_date': self.expiry_date,
                'qty': self.current_qty,
                'unit_cost': self.product_id.standard_price,
            })]
        }
        
        new_disposal = self.env['bhx.disposal'].create(disposal_vals)
        self.write({'state': 'processing', 'note': f'Đã tạo phiếu huỷ hàng: {new_disposal.name}'})
        
        return {
            'name': _('Phiếu xử lý/huỷ hàng'),
            'type': 'ir.actions.act_window',
            'res_model': 'bhx.disposal',
            'view_mode': 'form',
            'res_id': new_disposal.id,
            'target': 'current',
        }

    @api.model
    def cron_generate_audit_alerts(self):
        # Tự động tạo cảnh báo kiểm kê khi phát hiện tồn kho âm
        locations = self.env['bhx.display.location.line'].search([
            ('current_qty', '<', 0)
        ])
        for loc in locations:
            existing_alert = self.search([
                ('product_id', '=', loc.product_id.id),
                ('warehouse_id', '=', loc.location_id.warehouse_id.id),
                ('state', 'in', ['new', 'processing']),
                ('alert_type', '=', 'audit_required')
            ], limit=1)
            
            if not existing_alert:
                store_wh = loc.location_id.warehouse_id
                self.create({
                    'name': f'YÊU CẦU KIỂM KÊ: {loc.product_id.name} (Tồn kho âm)',
                    'alert_type': 'audit_required',
                    'priority': '3',
                    'product_id': loc.product_id.id,
                    'warehouse_id': store_wh.id,
                    'current_qty': loc.current_qty,
                    'min_qty': loc.min_qty,
                    'max_qty': loc.max_qty or (loc.min_qty * 2),
                    'note': f'Hệ thống ghi nhận tồn kho vật lý bị âm ({loc.current_qty}) tại {loc.location_id.name}. Yêu cầu kiểm kê.',
                    'responsible_id': self.env.ref('base.user_root').id,
                })

    @api.model
    def cron_generate_expiry_alerts(self):
        """Tự động quét toàn bộ kho để tìm hàng sắp hết hạn và ĐÓNG các cảnh báo đã hết hàng."""
        today = date.today()
        near_expiry_threshold = today + timedelta(days=15)
        
        # 1. ĐỐNG CẢNH BÁO CŨ: Nếu tồn kho của lô đó đã về 0
        active_expiry_alerts = self.search([
            ('state', 'in', ['new', 'processing']),
            ('alert_type', 'in', ['near_expiry', 'expired']),
            ('lot_id', '!=', False)
        ])
        for alert in active_expiry_alerts:
            # Kiểm tra tồn kho của Lô hàng này tại các kho nội bộ
            quants = self.env['stock.quant'].search([
                ('product_id', '=', alert.product_id.id),
                ('lot_id', '=', alert.lot_id.id),
                ('location_id.usage', '=', 'internal'),
                ('quantity', '>', 0)
            ])
            if not quants:
                alert.write({'state': 'resolved', 'note': '[Tự động] Đóng cảnh báo vì tồn kho lô đã hết.'})

        # 2. TẠO CẢNH BÁO MỚI (Lô có Date và còn tồn kho)
        lots = self.env['stock.lot'].search([
            ('expiration_date', '!=', False)
        ])
        
        for lot in lots:
            # Kiểm tra tồn kho thực tế của lô này
            quants = self.env['stock.quant'].search([
                ('lot_id', '=', lot.id),
                ('quantity', '>', 0),
                ('location_id.usage', '=', 'internal')
            ])
            if not quants:
                continue
            
            exp_date = lot.expiration_date.date()
            current_qty = sum(quants.mapped('quantity'))
            warehouse = quants[0].location_id.warehouse_id
            
            alert_type = False
            priority = '1'
            
            if exp_date <= today:
                alert_type = 'expired'
                priority = '3'
            elif exp_date <= near_expiry_threshold:
                alert_type = 'near_expiry'
                priority = '2'
                
            if alert_type:
                existing = self.search([
                    ('product_id', '=', lot.product_id.id),
                    ('lot_id', '=', lot.id),
                    ('state', 'in', ['new', 'processing']),
                    ('alert_type', '=', alert_type)
                ], limit=1)
                
                if not existing:
                    self.create({
                        'name': f'DATE: {lot.product_id.name} (Lô: {lot.name})',
                        'alert_type': alert_type,
                        'priority': priority,
                        'product_id': lot.product_id.id,
                        'lot_id': lot.id,
                        'warehouse_id': warehouse.id if warehouse else self.env.ref('bhx_import_goods.bhx_warehouse').id,
                        'expiry_date': exp_date,
                        'current_qty': current_qty,
                        'note': f'Lô hàng {lot.name} sắp/đã hết hạn vào ngày {exp_date}.',
                    })
