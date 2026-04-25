from odoo import models, fields, api
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# Cấu hình ngưỡng tồn kho theo nhóm hàng BHX
# ─────────────────────────────────────────────────────────
BHX_THRESHOLDS = [
    {
        'key': 'veg',
        'keywords': ['rau', 'củ', 'quả', 'veg', 'trái cây'],
        'min': 20,
        'label': 'BHX Rau củ quả',
        'import_model': 'bhx.fruit.veg.import',
        'line_model':   'bhx.fruit.veg.import.line',
        'qty_field':    'expected_weight',   # tên trường số lượng trong line
    },
    {
        'key': 'fresh',
        'keywords': ['fresh', 'hàng fresh', 'tươi', 'thịt', 'cá'],
        'min': 30,
        'label': 'BHX Hàng Fresh',
        'import_model': 'bhx.fresh.import',
        'line_model':   'bhx.fresh.import.line',
        'qty_field':    'expected_weight',
    },
    {
        'key': 'fmcg',
        'keywords': ['fmcg'],
        'min': 50,
        'label': 'BHX FMCG',
        'import_model': 'bhx.fmcg.import',
        'line_model':   'bhx.fmcg.import.line',
        'qty_field':    'quantity',
    },
]


def _get_cfg(categ_name: str):
    """Trả về config ngưỡng phù hợp với danh mục sản phẩm, hoặc None nếu không khớp."""
    name = (categ_name or '').lower()
    for cfg in BHX_THRESHOLDS:
        if any(kw in name for kw in cfg['keywords']):
            return cfg
    return None


class StockMoveInherit(models.Model):
    """
    Hook vào stock.move._action_done để kiểm tra tồn kho ngay khi có
    giao dịch xuất hàng (bán, điều chuyển…).

    Khi tồn kho < ngưỡng định mức:
      1. Tạo cảnh báo bhx.stock.alert (low_stock).
      2. Tạo phiếu nhập hàng BHX tương ứng (FMCG / Fresh / Rau củ) ở trạng thái Nháp.
    """
    _inherit = 'stock.move'

    def _action_done(self, cancel_backorder=False):
        res = super()._action_done(cancel_backorder=cancel_backorder)

        # Chỉ xử lý các move XUẤT kho đã hoàn thành
        outgoing = self.filtered(
            lambda m: m.state == 'done'
                      and m.location_dest_id.usage in ('customer', 'production', 'transit')
                      and m.product_id.type == 'product'
                      and m.product_id.sale_ok
        )
        if not outgoing:
            return res

        # Kiểm tra từng cặp (sản phẩm, kho), tránh lặp
        seen = set()
        for move in outgoing:
            wh = (
                move.warehouse_id
                or (move.picking_id.picking_type_id.warehouse_id)
            )
            if not wh:
                continue
            key = (move.product_id.id, wh.id)
            if key in seen:
                continue
            seen.add(key)
            try:
                self._bhx_check_and_alert(move.product_id, wh)
            except Exception as e:
                _logger.error('BHX low-stock check failed for %s: %s', move.product_id.name, e)

        return res

    # ─────────────────────────────────────────────────────
    # Core logic
    # ─────────────────────────────────────────────────────

    def _bhx_check_and_alert(self, product, warehouse):
        """Kiểm tra tồn kho và tạo cảnh báo + phiếu nhập nếu dưới ngưỡng."""
        cfg = _get_cfg(product.categ_id.name)
        if not cfg:
            return  # Không thuộc nhóm hàng cần theo dõi

        threshold = cfg['min']
        current_qty = product.with_context(warehouse=warehouse.id).qty_available

        if current_qty >= threshold:
            return  # Còn đủ hàng

        StockAlert = self.env['bhx.stock.alert']

        # Tránh tạo trùng cảnh báo đang mở
        existing = StockAlert.search([
            ('product_id', '=', product.id),
            ('warehouse_id', '=', warehouse.id),
            ('alert_type', '=', 'low_stock'),
            ('state', 'in', ['new', 'processing']),
        ], limit=1)

        if existing:
            existing.write({'current_qty': current_qty})
            _logger.info('BHX: Updated low-stock alert for %s (qty=%s)', product.name, current_qty)
            return

        qty_to_order = max(threshold * 2 - current_qty, threshold)

        alert = StockAlert.create({
            'name': f'SẮP HẾT: {product.name} | Tồn: {int(current_qty)} | {warehouse.name}',
            'alert_type': 'low_stock',
            'priority': '3',
            'product_id': product.id,
            'warehouse_id': warehouse.id,
            'current_qty': current_qty,
            'min_qty': threshold,
            'max_qty': threshold * 3,
            'note': (
                f'[{cfg["label"]}] Tồn kho ({current_qty}) dưới mức tối thiểu ({threshold}). '
                f'Cần nhập thêm ít nhất {qty_to_order} sản phẩm.'
            ),
        })
        _logger.warning(
            'BHX LOW-STOCK: %s | kho: %s | tồn: %s | ngưỡng: %s',
            product.name, warehouse.name, current_qty, threshold,
        )

        # Tạo phiếu nhập hàng BHX tương ứng
        self._bhx_create_import(alert, product, warehouse, qty_to_order, cfg)

    def _bhx_create_import(self, alert, product, warehouse, qty_to_order, cfg):
        """
        Tạo phiếu nhập hàng BHX (bhx.fmcg.import / bhx.fresh.import / bhx.fruit.veg.import)
        ở trạng thái Nháp (draft), gộp nhiều sản phẩm vào 1 phiếu cùng nhà cung cấp nếu có.
        """
        import_model = cfg['import_model']
        qty_field    = cfg['qty_field']
        label        = cfg['label']

        # Tìm nhà cung cấp: ưu tiên NCC cấu hình trên sản phẩm, fallback Kho Trung Tâm
        seller = product.seller_ids[:1]
        if seller:
            partner    = seller.partner_id
            unit_price = seller.price or product.standard_price
        else:
            partner = (
                self.env['res.partner'].search([
                    ('name', 'ilike', 'Kho Trung Tâm'),
                    ('supplier_rank', '>', 0),
                ], limit=1)
                or self.env['res.partner'].search(
                    [('supplier_rank', '>', 0)], limit=1
                )
            )
            unit_price = product.standard_price

        if not partner:
            alert.note += '\n⚠️ Chưa có NCC — vui lòng tạo phiếu nhập hàng thủ công.'
            alert.state = 'new'
            return

        # Xây dựng vals dòng sản phẩm theo từng loại phiếu
        # Tự động tạo số lô và hạn dùng như logic cũ
        today_str = fields.Date.today().strftime('%m%d')
        lot_no = ""
        expiry_date = fields.Date.today()

        if import_model == 'bhx.fmcg.import':
            lot_no = f"LOT-FMCG-{product.id}-{today_str}"
            expiry_date = fields.Date.today() + timedelta(days=365)
        elif import_model == 'bhx.fresh.import':
            lot_no = f"LOT-FRESH-{product.id}-{today_str}"
            expiry_date = fields.Date.today() + timedelta(days=3)
        else: # fruit.veg
            lot_no = f"LOT-FRUIT-{product.id}-{today_str}"
            expiry_date = fields.Date.today() + timedelta(days=3)

        line_vals = {
            'product_id': product.id,
            'unit_price': unit_price,
            qty_field: qty_to_order,
            'lot_no': lot_no,
        }

        # Bổ sung expiry_date tùy theo model (line hay header)
        if import_model == 'bhx.fmcg.import':
            line_vals['expiry_date'] = expiry_date
        
        # Kiểm tra xem đã có phiếu nháp cùng NCC tại kho này chưa → gộp vào
        existing_import = self.env[import_model].search([
            ('supplier_id', '=', partner.id),
            ('warehouse_id', '=', warehouse.id),
            ('state', '=', 'draft'),
        ], limit=1)

        if existing_import:
            existing_import.write({'line_ids': [(0, 0, line_vals)]})
            import_doc = existing_import
            _logger.info('BHX Import: Added %s to existing %s (%s)', product.name, import_model, import_doc.name)
        else:
            # Tạo phiếu nhập mới
            header_vals = {
                'supplier_id': partner.id,
                'warehouse_id': warehouse.id,
                'line_ids': [(0, 0, line_vals)],
            }
            # Fresh và Fruit/Veg dùng expiry_date ở header
            if import_model in ['bhx.fresh.import', 'bhx.fruit.veg.import']:
                header_vals['expiry_date'] = expiry_date

            import_doc = self.env[import_model].create(header_vals)
            _logger.info('BHX Import: Created new %s: %s', import_model, import_doc.name)

        # Ghi liên kết vào cảnh báo
        alert.write({
            'state': 'processing',
            'note': alert.note + f'\n✅ Phiếu nhập [{label}]: {import_doc.name}',
        })
