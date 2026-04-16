from odoo import models, fields, api
from datetime import date, timedelta

class InventoryCount(models.Model):
    _inherit = 'bhx.inventory.count'

    alert_id = fields.Many2one('bhx.stock.alert', string='Từ cảnh báo tồn kho', readonly=True)

    def action_approve(self):
        res = super(InventoryCount, self).action_approve()
        if self.alert_id:
            self.alert_id.write({
                'state': 'resolved',
                'note': f'[Tự động] Đóng cảnh báo thông qua phiếu kiểm kê {self.name}'
            })
        
        # --- Tạo cảnh báo Date mới nếu phát hiện hàng sắp hết hạn ---
        self._generate_expiry_alerts()
        
        # --- Tạo phiếu điều chỉnh tồn kho tự động nếu có chênh lệch ---
        self._create_adjustment_from_diff()
        
        return res

    def _generate_expiry_alerts(self):
        today = date.today()
        for line in self.line_ids:
            if not line.expiry_date:
                continue
            
            categ_name = line.product_id.categ_id.name or ''
            days_threshold = 30
            if 'Fresh' in categ_name:
                days_threshold = 7
            elif 'Rau củ' in categ_name:
                days_threshold = 3
            
            if line.expiry_date < today + timedelta(days=days_threshold):
                alert_type = 'expired' if line.expiry_date <= today else 'near_expiry'
                priority = '3' if alert_type == 'expired' else '2'
                
                # Tránh tạo trùng lặp
                existing = self.env['bhx.stock.alert'].search([
                    ('product_id', '=', line.product_id.id),
                    ('warehouse_id', '=', self.warehouse_id.id),
                    ('expiry_date', '=', line.expiry_date),
                    ('state', 'in', ['new', 'processing']),
                    ('alert_type', 'in', ['near_expiry', 'expired'])
                ], limit=1)
                
                if not existing:
                    self.env['bhx.stock.alert'].create({
                        'name': f'DATE: {line.product_id.name} (Từ kiểm kê {self.name})',
                        'alert_type': alert_type,
                        'priority': priority,
                        'product_id': line.product_id.id,
                        'warehouse_id': self.warehouse_id.id,
                        'expiry_date': line.expiry_date,
                        'current_qty': line.qty_counted,
                        'note': f'Phát hiện hàng sắp hết hạn ({line.expiry_date}) trong quá trình kiểm kê.',
                    })

    def _create_adjustment_from_diff(self):
        """Tạo phiếu điều chỉnh tồn kho tự động từ các dòng chênh lệch kiểm kê."""
        increase_lines = []
        decrease_lines = []
        
        for line in self.line_ids:
            if line.qty_diff > 0:
                increase_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'qty_before': line.qty_system,
                    'qty_change': line.qty_diff,
                    'lot_id': line.lot_id.id if line.lot_id else False,
                }))
            elif line.qty_diff < 0:
                decrease_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'qty_before': line.qty_system,
                    'qty_change': abs(line.qty_diff),
                    'lot_id': line.lot_id.id if line.lot_id else False,
                }))
        
        if increase_lines:
            adj = self.env['bhx.stock.adjustment'].create({
                'adjustment_type': 'increase',
                'reason': 'count_diff',
                'warehouse_id': self.warehouse_id.id,
                'inventory_count_id': self.id,
                'note': f'Tự động tạo từ phiếu kiểm kê {self.name} (Tăng tồn do dư hàng)',
                'line_ids': increase_lines,
            })
            adj.action_approve()
            
        if decrease_lines:
            adj = self.env['bhx.stock.adjustment'].create({
                'adjustment_type': 'decrease',
                'reason': 'count_diff',
                'warehouse_id': self.warehouse_id.id,
                'inventory_count_id': self.id,
                'note': f'Tự động tạo từ phiếu kiểm kê {self.name} (Giảm tồn do thiếu hàng)',
                'line_ids': decrease_lines,
            })
            adj.action_approve()

    @api.onchange('zone', 'warehouse_id')
    def _onchange_zone_warehouse(self):
        """Tự động hiện danh sách sản phẩm theo khu vực kiểm kê."""
        if not self.zone or not self.warehouse_id:
            return
        
        self.line_ids = [(5, 0, 0)]
        
        categ_mapping = {
            'fmcg': ['bhx_import_goods.category_fmcg'],
            'fresh': ['bhx_import_goods.category_fresh'],
            'fruit_veg': ['bhx_import_goods.category_fruit_veg'],
            'all': ['bhx_import_goods.category_fmcg', 'bhx_import_goods.category_fresh', 'bhx_import_goods.category_fruit_veg']
        }
        
        ext_ids = categ_mapping.get(self.zone, [])
        categ_ids = []
        for ext_id in ext_ids:
            try:
                categ = self.env.ref(ext_id)
                if categ:
                    categ_ids.append(categ.id)
            except:
                continue
        
        if not categ_ids:
            return

        products = self.env['product.product'].search([
            ('type', '=', 'product'),
            ('categ_id', 'child_of', categ_ids)
        ])
        
        new_lines = []
        for product in products:
            line_vals = {
                'product_id': product.id,
                'qty_system': product.with_context(warehouse=self.warehouse_id.id).qty_available,
            }
            
            display_line = self.env['bhx.display.location.line'].search([
                ('product_id', '=', product.id),
                ('location_id.warehouse_id', '=', self.warehouse_id.id)
            ], limit=1)
            if display_line:
                line_vals['location_detail'] = display_line.location_id.name
            
            quant = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('location_id', 'child_of', self.warehouse_id.lot_stock_id.id),
                ('lot_id', '!=', False),
                ('quantity', '>', 0)
            ], order='in_date desc', limit=1)
            
            if quant:
                line_vals['lot_id'] = quant.lot_id.id
                line_vals['expiry_date'] = quant.lot_id.expiration_date
            else:
                lot = self.env['stock.lot'].search([('product_id', '=', product.id)], order='create_date desc', limit=1)
                if lot:
                    line_vals['lot_id'] = lot.id
                    line_vals['expiry_date'] = lot.expiration_date
                else:
                    import_line = self.env['bhx.fmcg.import.line'].search([
                        ('product_id', '=', product.id),
                        ('lot_no', '!=', False)
                    ], order='id desc', limit=1)
                    if import_line:
                        related_lot = self.env['stock.lot'].search([
                            ('product_id', '=', product.id),
                            ('name', '=', import_line.lot_no)
                        ], limit=1)
                        if related_lot:
                            line_vals['lot_id'] = related_lot.id
                            line_vals['expiry_date'] = related_lot.expiration_date
                        else:
                            line_vals['expiry_date'] = import_line.expiry_date

            if not line_vals.get('expiry_date'):
                today = date.today()
                categ_name = product.categ_id.name or ''
                if 'FMCG' in categ_name:
                    line_vals['expiry_date'] = today + timedelta(days=365)
                elif 'Fresh' in categ_name:
                    line_vals['expiry_date'] = today + timedelta(days=7)
                elif 'Rau củ' in categ_name:
                    line_vals['expiry_date'] = today + timedelta(days=3)
                else:
                    line_vals['expiry_date'] = today + timedelta(days=30)
            
            new_lines.append((0, 0, line_vals))
            
        self.line_ids = new_lines

class InventoryCountLine(models.Model):
    _inherit = 'bhx.inventory.count.line'

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if not self.product_id:
            return
        
        warehouse = self.count_id.warehouse_id or self.env['stock.warehouse'].search([], limit=1)
        if warehouse:
            self.qty_system = self.product_id.with_context(warehouse=warehouse.id).qty_available
            
            display_line = self.env['bhx.display.location.line'].search([
                ('product_id', '=', self.product_id.id),
                ('location_id.warehouse_id', '=', warehouse.id)
            ], limit=1)
            if display_line:
                self.location_detail = display_line.location_id.name
            
            quant = self.env['stock.quant'].search([
                ('product_id', '=', self.product_id.id),
                ('location_id', 'child_of', warehouse.lot_stock_id.id),
                ('lot_id', '!=', False),
                ('quantity', '>', 0)
            ], order='in_date desc', limit=1)
            
            if quant:
                self.lot_id = quant.lot_id
                self.expiry_date = quant.lot_id.expiration_date
            else:
                lot = self.env['stock.lot'].search([('product_id', '=', self.product_id.id)], order='create_date desc', limit=1)
                if lot:
                    self.lot_id = lot
                    self.expiry_date = lot.expiration_date
                else:
                    import_line = self.env['bhx.fmcg.import.line'].search([
                        ('product_id', '=', self.product_id.id),
                        ('lot_no', '!=', False)
                    ], order='id desc', limit=1)
                    if import_line:
                        related_lot = self.env['stock.lot'].search([
                            ('product_id', '=', self.product_id.id),
                            ('name', '=', import_line.lot_no)
                        ], limit=1)
                        if related_lot:
                            self.lot_id = related_lot
                            self.expiry_date = related_lot.expiration_date
                        else:
                            self.expiry_date = import_line.expiry_date

            if not self.expiry_date:
                today = date.today()
                categ_name = self.product_id.categ_id.name or ''
                if 'FMCG' in categ_name:
                    self.expiry_date = today + timedelta(days=365)
                elif 'Fresh' in categ_name:
                    self.expiry_date = today + timedelta(days=7)
                elif 'Rau củ' in categ_name:
                    self.expiry_date = today + timedelta(days=3)
                else:
                    self.expiry_date = today + timedelta(days=30)

class GoodsControl(models.Model):
    _inherit = 'bhx.goods.control'

    alert_id = fields.Many2one('bhx.stock.alert', string='Từ cảnh báo tồn kho', readonly=True)

    def action_done(self):
        res = super(GoodsControl, self).action_done()
        if self.alert_id:
            self.alert_id.write({
                'state': 'resolved',
                'note': f'[Tự động] Đóng cảnh báo thông qua phiếu kiểm soát {self.name}'
            })
        
        # --- Tạo cảnh báo Date mới nếu phát hiện hàng sắp hết hạn ---
        self._generate_expiry_alerts()
        return res

    def _generate_expiry_alerts(self):
        today = date.today()
        for line in self.line_ids:
            if not line.expiry_date:
                continue
            
            categ_name = line.product_id.categ_id.name or ''
            days_threshold = 30
            if 'Fresh' in categ_name:
                days_threshold = 7
            elif 'Rau củ' in categ_name:
                days_threshold = 3
            
            if line.expiry_date < today + timedelta(days=days_threshold):
                alert_type = 'expired' if line.expiry_date <= today else 'near_expiry'
                priority = '3' if alert_type == 'expired' else '2'
                
                existing = self.env['bhx.stock.alert'].search([
                    ('product_id', '=', line.product_id.id),
                    ('warehouse_id', '=', self.warehouse_id.id),
                    ('expiry_date', '=', line.expiry_date),
                    ('state', 'in', ['new', 'processing']),
                    ('alert_type', 'in', ['near_expiry', 'expired'])
                ], limit=1)
                
                if not existing:
                    self.env['bhx.stock.alert'].create({
                        'name': f'DATE: {line.product_id.name} (Từ kiểm soát {self.name})',
                        'alert_type': alert_type,
                        'priority': priority,
                        'product_id': line.product_id.id,
                        'warehouse_id': self.warehouse_id.id,
                        'expiry_date': line.expiry_date,
                        'current_qty': line.qty_on_display,
                        'note': f'Phát hiện hàng sắp hết hạn ({line.expiry_date}) trong quá trình kiểm soát hàng ngày.',
                    })

class GoodsControlLine(models.Model):
    _inherit = 'bhx.goods.control.line'

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if not self.product_id:
            return
        
        warehouse = self.control_id.warehouse_id or self.env['stock.warehouse'].search([], limit=1)
        if warehouse:
            display_line = self.env['bhx.display.location.line'].search([
                ('product_id', '=', self.product_id.id),
                ('location_id.warehouse_id', '=', warehouse.id)
            ], limit=1)
            if display_line:
                self.location_detail = display_line.location_id.name
            
            quant = self.env['stock.quant'].search([
                ('product_id', '=', self.product_id.id),
                ('location_id', 'child_of', warehouse.lot_stock_id.id),
                ('lot_id', '!=', False),
                ('quantity', '>', 0)
            ], order='in_date desc', limit=1)
            
            if quant:
                self.lot_id = quant.lot_id
                self.expiry_date = quant.lot_id.expiration_date
            else:
                lot = self.env['stock.lot'].search([('product_id', '=', self.product_id.id)], order='create_date desc', limit=1)
                if lot:
                    self.lot_id = lot
                    self.expiry_date = lot.expiration_date
                else:
                    import_line = self.env['bhx.fmcg.import.line'].search([
                        ('product_id', '=', self.product_id.id),
                        ('lot_no', '!=', False)
                    ], order='id desc', limit=1)
                    if import_line:
                        related_lot = self.env['stock.lot'].search([
                            ('product_id', '=', self.product_id.id),
                            ('name', '=', import_line.lot_no)
                        ], limit=1)
                        if related_lot:
                            self.lot_id = related_lot
                            self.expiry_date = related_lot.expiration_date
                        else:
                            self.expiry_date = import_line.expiry_date

            if not self.expiry_date:
                today = date.today()
                categ_name = self.product_id.categ_id.name or ''
                if 'FMCG' in categ_name:
                    self.expiry_date = today + timedelta(days=365)
                elif 'Fresh' in categ_name:
                    self.expiry_date = today + timedelta(days=7)
                elif 'Rau củ' in categ_name:
                    self.expiry_date = today + timedelta(days=3)
                else:
                    self.expiry_date = today + timedelta(days=30)

class Disposal(models.Model):
    _inherit = 'bhx.disposal'

    alert_id = fields.Many2one('bhx.stock.alert', string='Từ cảnh báo tồn kho', readonly=True)
    
    def action_approve(self):
        res = super(Disposal, self).action_approve()
        if self.alert_id:
            self.alert_id.write({
                'state': 'resolved', 
                'note': f'[Tự động] Đóng cảnh báo thông qua phiếu huỷ hàng {self.name}'
            })
        return res
