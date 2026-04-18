import json
from odoo import http
from odoo.http import request


class BHXPosController(http.Controller):

    @http.route('/bhx/pos', type='http', auth='user')
    def bhx_pos_index(self, **kwargs):
        """Render giao diện POS Bách Hóa Xanh — standalone HTML"""
        shift_id = int(kwargs.get('shift_id', 0))
        shift = None
        if shift_id:
            s_rec = request.env['bhx.sales.shift'].browse(shift_id)
            if s_rec.exists() and s_rec.state == 'open':
                shift = s_rec
        
        if not shift:
            shift = request.env['bhx.sales.shift'].search([
                ('state', '=', 'open'),
                ('cashier_id', '=', request.env.user.id)
            ], limit=1)

        if not shift:
            return request.make_response(self._no_shift_html(), headers=[
                ('Content-Type', 'text/html; charset=utf-8')
            ])

        html = self._build_pos_html(shift, request.env.user)
        return request.make_response(html, headers=[
            ('Content-Type', 'text/html; charset=utf-8')
        ])

    @http.route('/bhx/pos/get_data', type='json', auth='user')
    def get_pos_data(self):
        categories = request.env['product.category'].search_read(
            [('name', 'ilike', 'BHX')],
            ['id', 'name']
        )
        products = request.env['product.product'].search_read(
            [('sale_ok', '=', True), ('type', 'in', ('product', 'consu'))],
            ['id', 'name', 'display_name', 'list_price', 'categ_id', 'barcode', 'uom_id', 'image_128'],
            order='display_name'
        )
        return {'categories': categories, 'products': products}

    @http.route('/bhx/pos/validate_order', type='json', auth='user')
    def validate_pos_order(self, order_data):
        try:
            shift = request.env['bhx.sales.shift'].browse(order_data.get('shift_id'))
            order_vals = {
                'shift_id': shift.id,
                'warehouse_id': shift.warehouse_id.id,
                'customer_phone': order_data.get('customer_phone'),
                'customer_name': order_data.get('customer_name'),
                'payment_method': order_data.get('payment_method', 'cash'),
                'line_ids': []
            }
            for line in order_data.get('lines', []):
                order_vals['line_ids'].append((0, 0, {
                    'product_id': line['product_id'],
                    'qty': line['qty'],
                    'unit_price': line['price'],
                    'discount_pct': line.get('discount_pct', 0),
                }))
            new_order = request.env['bhx.sales.order'].create(order_vals)
            
            # Nếu là chuyển khoản, không xác nhận ngay mà chờ Webhook
            if order_vals['payment_method'] == 'transfer':
                return {
                    'success': True, 
                    'order_name': new_order.name, 
                    'state': 'draft',
                    'qr_url': new_order._generate_vietqr_url()
                }

            new_order.action_done()
            return {'success': True, 'order_name': new_order.name, 'state': 'done'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route('/bhx/pos/check_order_status', type='json', auth='user')
    def check_order_status(self, order_name):
        order = request.env['bhx.sales.order'].search([('name', '=', order_name)], limit=1)
        if not order:
            return {'success': False, 'error': 'Order not found'}
        return {
            'success': True, 
            'state': order.state,
            'is_paid': (order.state == 'done')
        }


    @http.route('/bhx/pos/search_customer', type='json', auth='user')
    def search_customer(self, phone):
        customer = request.env['res.partner'].search_read(
            ['|', ('phone', '=', phone), ('mobile', '=', phone)],
            ['id', 'name', 'phone', 'mobile'],
            limit=1
        )
        return {'customer': customer[0] if customer else None}

    # ── HTML Builders ─────────────────────────────────────────────

    def _no_shift_html(self):
        return '''<!DOCTYPE html><html><head><meta charset="utf-8"><title>POS BHX</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{background:#0f172a;font-family:Inter,-apple-system,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;color:#f1f5f9}
.c{background:#1e293b;border-radius:16px;padding:48px;text-align:center;max-width:440px;box-shadow:0 20px 60px rgba(0,0,0,.5)}h2{color:#ef4444;margin:16px 0 8px}p{color:#94a3b8;margin-bottom:28px}
a{background:#10b981;color:#fff;padding:14px 28px;border-radius:8px;text-decoration:none;font-weight:600;display:inline-block}</style>
</head><body><div class="c"><div style="font-size:64px">⚠️</div><h2>Chưa mở ca bán hàng!</h2><p>Vui lòng quay lại Odoo để mở ca mới.</p><a href="/web">Quay lại Odoo</a></div></body></html>'''

    def _build_pos_html(self, shift, user):
        return f'''<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>POS Bách Hóa Xanh</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
/* ═══════════════════════════════════════════
   BHX POS v3 — Design System
   ═══════════════════════════════════════════ */
:root {{
  --g50:#f0fdf4;--g100:#dcfce7;--g400:#4ade80;--g500:#10b981;--g600:#059669;--g700:#047857;
  --b50:#eff6ff;--b400:#60a5fa;--b500:#3b82f6;--b600:#2563eb;
  --r400:#f87171;--r500:#ef4444;
  --a500:#f59e0b;
  --d50:#f8fafc;--d100:#f1f5f9;--d200:#e2e8f0;--d300:#cbd5e1;--d400:#94a3b8;--d500:#64748b;--d600:#475569;--d700:#334155;--d800:#1e293b;--d900:#0f172a;
  --radius:10px;--radius-lg:14px;
  --shadow-sm:0 1px 3px rgba(0,0,0,.3);--shadow-md:0 4px 12px rgba(0,0,0,.25);--shadow-lg:0 10px 30px rgba(0,0,0,.4);
  --ease:cubic-bezier(.4,0,.2,1);
}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{height:100%;overflow:hidden;font-family:'Inter',sans-serif;background:var(--d900);color:var(--d100);-webkit-font-smoothing:antialiased}}
button{{cursor:pointer;font-family:inherit;border:none;outline:none}}
input{{font-family:inherit;outline:none}}

/* ═══ SCREEN MANAGEMENT ═══ */
.scr{{display:none;height:100vh;flex-direction:column}}.scr.on{{display:flex}}

/* ═══ HEADER ═══ */
.hdr{{display:flex;align-items:center;gap:12px;padding:0 16px;background:var(--d800);border-bottom:1px solid rgba(255,255,255,.06);height:52px;flex-shrink:0}}
.hdr-brand{{display:flex;align-items:center;height:100%}}
.hdr-brand img{{height:28px;width:auto;object-fit:contain}}
.hdr-search{{flex:1;display:flex;align-items:center;gap:8px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.07);border-radius:8px;padding:0 12px;height:36px}}
.hdr-search input{{flex:1;background:0;border:0;color:var(--d100);font-size:.85rem}}.hdr-search input::placeholder{{color:var(--d500)}}
.hdr-meta{{display:flex;align-items:center;gap:10px;white-space:nowrap;font-size:.82rem}}
.badge{{background:rgba(16,185,129,.12);color:var(--g500);border:1px solid rgba(16,185,129,.25);border-radius:16px;padding:3px 10px;font-size:.75rem;font-weight:600}}
.hdr-exit{{color:var(--d400);text-decoration:none;padding:5px 10px;border-radius:6px;border:1px solid rgba(255,255,255,.08);font-size:.8rem}}

/* ═══ BODY (2-column) ═══ */
.bod{{display:flex;flex:1;overflow:hidden}}

/* ── LEFT PANEL: CART ── */
.cart-pnl{{width:340px;min-width:340px;background:var(--d800);display:flex;flex-direction:column;border-right:1px solid rgba(255,255,255,.06)}}
.cart-hdr{{padding:10px 14px;font-weight:700;font-size:.78rem;color:var(--d400);text-transform:uppercase;letter-spacing:.6px;border-bottom:1px solid rgba(255,255,255,.06)}}
.cart-list{{flex:1;overflow-y:auto;padding:8px}}
.cart-empty{{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;color:var(--d600);text-align:center;gap:6px}}
.cart-empty b{{font-size:2.5rem;opacity:.25}}.cart-empty p{{font-weight:600;color:var(--d500)}}

.ci{{display:flex;align-items:center;gap:8px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:var(--radius);padding:8px 10px;margin-bottom:5px;transition:background .15s var(--ease)}}
.ci:hover{{background:rgba(255,255,255,.06)}}
.ci-info{{flex:1;min-width:0}}.ci-name{{font-weight:600;font-size:.82rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.ci-meta{{color:var(--d500);font-size:.73rem;margin-top:1px}}
.ci-sub{{font-weight:700;color:var(--g500);font-size:.88rem;white-space:nowrap}}
.ci-qty{{display:flex;align-items:center;gap:5px;background:var(--d700);border-radius:6px;padding:3px 6px}}
.qb{{background:0;border:0;color:var(--d100);font-size:.9rem;width:16px;text-align:center}}.qb:hover{{color:var(--g400)}}
.qv{{font-weight:700;font-size:.82rem;min-width:18px;text-align:center}}
.ci-del{{background:0;border:0;color:var(--d600);font-size:.8rem;padding:2px 4px;border-radius:4px}}.ci-del:hover{{color:var(--r400);background:rgba(239,68,68,.1)}}

/* numpad mode */
.ci.active{{border-color:var(--b500);background:rgba(59,130,246,.08)}}

/* ── CUSTOMER INLINE ── */
.cust-bar{{padding:8px;border-top:1px solid rgba(255,255,255,0.06);background:rgba(0,0,0,0.1)}}
.cust-row{{display:grid;grid-template-columns:110px 1fr;gap:4px;width:100%}}
.cust-input{{width:100%;min-width:0;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:6px;color:var(--d100);padding:6px 8px;font-size:0.75rem;box-sizing:border-box}}
.cust-input::placeholder{{color:var(--d500)}}
.cust-input:focus{{border-color:var(--b500)}}

/* ── NUMPAD ── */
.npad-area{{border-top:1px solid rgba(255,255,255,.06);padding:8px 10px}}
.npad-modes{{display:flex;gap:4px;margin-bottom:6px}}
.npad-mode{{flex:1;padding:6px;border-radius:6px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);color:var(--d300);font-size:.75rem;font-weight:600;text-align:center}}
.npad-mode.on{{background:rgba(59,130,246,.15);border-color:var(--b500);color:var(--b400)}}
.npad{{display:grid;grid-template-columns:repeat(4,1fr);gap:4px}}
.nb{{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:12px 0;font-size:1.05rem;font-weight:600;color:var(--d100);transition:background .1s}}
.nb:hover{{background:rgba(255,255,255,.1)}}.nb:active{{transform:scale(.96)}}
.nb-q{{background:rgba(59,130,246,.1);border-color:rgba(59,130,246,.2);color:var(--b400);font-size:.78rem}}
.nb-del{{background:rgba(239,68,68,.1);border-color:rgba(239,68,68,.2);color:var(--r400)}}

/* ── CART FOOTER ── */
.cart-ft{{padding:12px 14px;border-top:1px solid rgba(255,255,255,.06);background:rgba(0,0,0,.12)}}
.ft-row{{display:flex;justify-content:space-between;color:var(--d400);font-size:.8rem;margin-bottom:4px}}
.ft-total{{display:flex;justify-content:space-between;font-size:1.2rem;font-weight:800;margin-bottom:12px}}
.btn-pay{{width:100%;background:linear-gradient(135deg,var(--g500),var(--g600));color:#fff;border-radius:var(--radius);padding:13px;font-size:.92rem;font-weight:700;box-shadow:0 4px 14px rgba(16,185,129,.35);transition:transform .15s var(--ease),box-shadow .15s var(--ease)}}
.btn-pay:hover:not(:disabled){{transform:translateY(-2px);box-shadow:0 6px 20px rgba(16,185,129,.45)}}
.btn-pay:disabled{{opacity:.35;cursor:not-allowed;transform:none;box-shadow:none}}

/* ═══ RIGHT PANEL: PRODUCTS ═══ */
.prod-pnl{{flex:1;display:flex;flex-direction:column;overflow:hidden}}
.cat-tabs{{display:flex;gap:6px;padding:8px 12px;border-bottom:1px solid rgba(255,255,255,.06);overflow-x:auto;flex-shrink:0}}
.cat-tabs::-webkit-scrollbar{{height:2px}}.cat-tabs::-webkit-scrollbar-thumb{{background:var(--d700);border-radius:2px}}
.cb{{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07);color:var(--d400);padding:5px 14px;border-radius:16px;font-size:.78rem;font-weight:500;white-space:nowrap}}
.cb.on{{background:var(--g500);border-color:var(--g500);color:#fff;font-weight:600}}
.pgrid{{flex:1;overflow-y:auto;padding:12px;display:grid;grid-template-columns:repeat(auto-fill,minmax(145px,1fr));gap:8px;align-content:start}}
.pgrid::-webkit-scrollbar{{width:4px}}.pgrid::-webkit-scrollbar-thumb{{background:var(--d700);border-radius:4px}}
.pcard{{background:var(--d800);border:1px solid rgba(255,255,255,.1);border-radius:var(--radius);overflow:hidden;cursor:pointer;transition:all .2s var(--ease);display:flex;flex-direction:column;position:relative;height:140px}}
.pcard:hover{{transform:translateY(-4px);border-color:var(--g500);box-shadow:var(--shadow-lg)}}
.pimg{{flex:1;background:#fff;display:flex;align-items:center;justify-content:center;overflow:hidden}}
.pimg img{{width:100%;height:100%;object-fit:contain;transition:transform .3s}}
.pcard:hover .pimg img{{transform:scale(1.1)}}
.pbody{{position:absolute;bottom:0;left:0;right:0;background:rgba(15,23,42,0.85);backdrop-filter:blur(4px);padding:6px 8px;border-top:1px solid rgba(255,255,255,0.1);display:flex;flex-direction:column;gap:2px}}
.pname{{font-size:.72rem;font-weight:700;color:#fff;line-height:1.2;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:1.7rem}}
.pprice{{font-size:.82rem;font-weight:800;color:var(--g400)}}
.puom{{font-size:.6rem;color:var(--d400);margin-left:4px}}
.ploading{{grid-column:1/-1;text-align:center;padding:48px;color:var(--d500)}}

/* ═══════════════════════════════════════════
   SCREEN 2: PAYMENT
   ═══════════════════════════════════════════ */
.pay-wrap{{display:flex;height:100vh}}
.pay-left{{width:250px;background:var(--d800);border-right:1px solid rgba(255,255,255,.06);padding:18px;display:flex;flex-direction:column;gap:12px;overflow-y:auto}}
.btn-back{{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);color:var(--d100);padding:9px 12px;border-radius:8px;font-size:.85rem;font-weight:500;text-align:left}}
.sec-title{{font-size:.7rem;font-weight:700;color:var(--d500);text-transform:uppercase;letter-spacing:.7px}}
.pm{{background:rgba(255,255,255,.03);border:2px solid rgba(255,255,255,.06);border-radius:var(--radius);padding:10px 12px;display:flex;align-items:center;gap:10px;font-size:.85rem;font-weight:500;margin-bottom:6px}}
.pm.on{{border-color:var(--g500);background:rgba(16,185,129,.08)}}
.pm-icon{{font-size:1.15rem}}
.pay-sum-box{{margin-top:auto;background:rgba(0,0,0,.15);border-radius:var(--radius);padding:12px;border:1px solid rgba(255,255,255,.06)}}
.ps-row{{display:flex;justify-content:space-between;font-size:.8rem;color:var(--d400);margin-bottom:5px}}
.ps-div{{height:1px;background:rgba(255,255,255,.06);margin:6px 0}}
.ps-total{{display:flex;justify-content:space-between;font-size:1rem;font-weight:700}}

.pay-center{{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px;gap:12px}}
.pay-big{{font-size:3rem;font-weight:800;color:var(--g500)}}
.pay-hint{{color:var(--d500);font-size:.82rem}}
.pay-numpad{{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;width:100%;max-width:340px}}
.pnb{{background:var(--d800);border:1px solid rgba(255,255,255,.07);color:var(--d100);border-radius:var(--radius);padding:15px 0;font-size:1.1rem;font-weight:600}}
.pnb:hover{{background:rgba(255,255,255,.08)}}.pnb:active{{transform:scale(.96)}}
.pnb-q{{background:rgba(59,130,246,.1);border-color:rgba(59,130,246,.2);color:var(--b400);font-size:.82rem}}
.pnb-d{{background:rgba(239,68,68,.1);border-color:rgba(239,68,68,.2);color:var(--r400)}}
.btn-confirm{{width:100%;max-width:340px;background:linear-gradient(135deg,var(--g500),var(--g600));color:#fff;border-radius:var(--radius-lg);padding:15px;font-size:.95rem;font-weight:700;box-shadow:var(--shadow-md)}}
.btn-confirm:disabled{{opacity:.45}}

.pay-right{{width:250px;background:var(--d800);border-left:1px solid rgba(255,255,255,.06);padding:18px;overflow-y:auto}}
.pay-right h4{{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.7px;color:var(--d500);margin-bottom:8px}}
.pr-cust{{background:rgba(255,255,255,.03);border-radius:8px;border:1px solid rgba(255,255,255,.06);padding:10px;font-size:.82rem;margin-bottom:16px}}
.pr-line{{display:flex;justify-content:space-between;font-size:.78rem;padding:5px 0;border-bottom:1px solid rgba(255,255,255,.04);color:var(--d400)}}
.pr-line:last-child{{border:none}}

/* ═══════════════════════════════════════════
   SCREEN 3: SUCCESS
   ═══════════════════════════════════════════ */
.ok-wrap{{display:flex;height:100vh}}
.ok-left{{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:48px;gap:14px;text-align:center}}
.ok-check{{font-size:4.5rem;animation:pop .5s var(--ease)}}
@keyframes pop{{0%{{transform:scale(0)}}70%{{transform:scale(1.2)}}100%{{transform:scale(1)}}}}
.ok-left h2{{font-size:1.8rem;font-weight:800;color:var(--g500)}}
.ok-order{{color:var(--d500);font-size:.9rem}}
.ok-acts{{display:flex;gap:10px;margin-top:6px}}
.btn-print,.btn-next{{display:flex;align-items:center;gap:6px;padding:12px 20px;border-radius:var(--radius);font-size:.9rem;font-weight:600}}
.btn-print{{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.08);color:var(--d100)}}
.btn-next{{background:linear-gradient(135deg,var(--g500),var(--g600));color:#fff;padding:14px 28px;box-shadow:var(--shadow-md)}}

.ok-right{{width:320px;background:#e2e8f0;padding:20px;overflow-y:auto;display:flex;justify-content:center}}
.rcpt{{background:#fff;width:100%;padding:20px;border-radius:8px;box-shadow:var(--shadow-md);font-family:'Courier New',monospace;color:var(--d900)}}
.rcpt-center{{text-align:center}}.rcpt-logo{{font-size:2rem}}.rcpt-name{{font-weight:700;font-size:.9rem;margin:6px 0 2px}}.rcpt-info{{font-size:.72rem;color:var(--d500)}}
.rcpt-div{{border-top:1px dashed var(--d400);margin:8px 0}}
.rcpt-cashier{{font-size:.76rem;color:var(--d600)}}
.rcpt-ln{{display:flex;justify-content:space-between;font-size:.76rem;margin-bottom:4px}}.rcpt-ln span:last-child{{font-weight:600}}
.rcpt-tot{{display:flex;justify-content:space-between;font-weight:700;font-size:.9rem}}.rcpt-method{{text-align:right;color:var(--d500);font-size:.76rem;margin-top:5px}}
.rcpt-foot{{text-align:center;font-size:.78rem;color:var(--d400);margin-top:8px}}

@media print {{
    body * {{ visibility: hidden; }}
    #rcpt-paper, #rcpt-paper * {{ visibility: visible; }}
    #rcpt-paper {{
        position: fixed;
        left: 0;
        top: 0;
        width: 80mm;
        padding: 5mm;
        margin: 0;
        box-shadow: none;
        background: white;
        color: black;
        font-size: 12px;
        border: none;
    }}
    .ok-left, .hdr, .pay-left, .pay-center, .pay-right {{ display: none !important; }}
}}
</style>
</head>
<body>
<div id="app">

<!-- ════════ SCREEN 1: MAIN ════════ -->
<div id="s1" class="scr on">
  <div class="hdr">
    <div class="hdr-brand"><img src="/bhx_sales/static/src/img/logo.png" alt="BHX Logo"/></div>
    <div class="hdr-search"><span>🔍</span><input id="search" placeholder="Tìm sản phẩm hoặc quét mã vạch..." autocomplete="off"/></div>
    <div class="hdr-meta"><span class="badge">{shift.name}</span><span>👤 {user.name}</span><a href="/web" class="hdr-exit">⬅ Thoát</a></div>
  </div>
  <div class="bod">
    <div class="cart-pnl">
      <div class="cart-hdr">🛒 Giỏ hàng</div>
      <div class="cart-list" id="cart-list"><div class="cart-empty"><b>🛒</b><p>Chưa có sản phẩm</p></div></div>
      <!-- Customer Inline -->
      <div class="cust-bar">
        <div class="cust-row"><input class="cust-input" id="c-phone" placeholder="📱 SĐT khách hàng"/><input class="cust-input" id="c-name" placeholder="👤 Tên khách hàng"/></div>
      </div>
      <!-- Numpad -->
      <div class="npad-area">
        <div class="npad-modes"><button class="npad-mode on" data-mode="qty" onclick="P.setMode('qty')">SL</button><button class="npad-mode" data-mode="disc" onclick="P.setMode('disc')">% CK</button><button class="npad-mode" data-mode="price" onclick="P.setMode('price')">Giá</button></div>
        <div class="npad">
          <button class="nb" onclick="P.np('1')">1</button><button class="nb" onclick="P.np('2')">2</button><button class="nb" onclick="P.np('3')">3</button><button class="nb nb-q" onclick="P.np('+1')">+1</button>
          <button class="nb" onclick="P.np('4')">4</button><button class="nb" onclick="P.np('5')">5</button><button class="nb" onclick="P.np('6')">6</button><button class="nb nb-q" onclick="P.np('+5')">+5</button>
          <button class="nb" onclick="P.np('7')">7</button><button class="nb" onclick="P.np('8')">8</button><button class="nb" onclick="P.np('9')">9</button><button class="nb nb-q" onclick="P.np('+10')">+10</button>
          <button class="nb" onclick="P.np('.')">.</button><button class="nb" onclick="P.np('0')">0</button><button class="nb" onclick="P.np('C')">C</button><button class="nb nb-del" onclick="P.np('del')">&#9003;</button>
        </div>
      </div>
      <!-- Footer -->
      <div class="cart-ft">
        <div class="ft-row"><span>Tạm tính:</span><span id="ft-sub">0 ₫</span></div>
        <div class="ft-row"><span>Giảm giá:</span><span id="ft-disc" style="color:var(--r400)">-0 ₫</span></div>
        <div class="ft-total"><span>TỔNG TIỀN:</span><span id="ft-total">0 ₫</span></div>
        <button class="btn-pay" id="btn-pay" disabled onclick="P.goPayment()">💳 THANH TOÁN</button>
      </div>
    </div>
    <div class="prod-pnl">
      <div class="cat-tabs" id="cat-tabs"><button class="cb on" onclick="P.cat('all',this)">Tất cả</button></div>
      <div class="pgrid" id="pgrid"><div class="ploading">Đang tải sản phẩm...</div></div>
    </div>
  </div>
</div>

<!-- ════════ SCREEN 2: PAYMENT ════════ -->
<div id="s2" class="scr">
  <div class="pay-wrap">
    <div class="pay-left">
      <button class="btn-back" onclick="P.show('s1')">← Quay lại</button>
      <div class="sec-title">Phương thức thanh toán</div>
      <button class="pm on" data-m="cash" onclick="P.payM(this)"><span class="pm-icon">💵</span>Tiền mặt</button>
      <button class="pm" data-m="transfer" onclick="P.payM(this)"><span class="pm-icon">🏦</span>Ngân hàng</button>
      <button class="pm" data-m="card" onclick="P.payM(this)"><span class="pm-icon">💳</span>Thẻ</button>
      <div class="pay-sum-box">
        <div class="ps-row"><span>Mặt hàng:</span><span id="ps-cnt">0</span></div>
        <div class="ps-row"><span>Cần TT:</span><span id="ps-amt">0 ₫</span></div>
        <div class="ps-div"></div>
        <div class="ps-row" style="color:var(--g400)"><span>Tiền thừa:</span><span id="pay-change">0 ₫</span></div>
      </div>
    </div>
    <div class="pay-center">
      <div class="pay-big" id="pay-big">0 ₫</div>
      
      <!-- Quick Cash Bar -->
      <div style="display:flex; gap:6px; margin: 5px 0 15px 0;">
        <button style="background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.1); color:var(--d300); padding:6px 12px; border-radius:15px; font-size:.7rem; font-weight:600" onclick="P.pnp('+50')">50k</button>
        <button style="background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.1); color:var(--d300); padding:6px 12px; border-radius:15px; font-size:.7rem; font-weight:600" onclick="P.pnp('+100')">100k</button>
        <button style="background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.1); color:var(--d300); padding:6px 12px; border-radius:15px; font-size:.7rem; font-weight:600" onclick="P.pnp('+200')">200k</button>
        <button style="background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.1); color:var(--d300); padding:6px 12px; border-radius:15px; font-size:.7rem; font-weight:600" onclick="P.pnp('+500')">500k</button>
      </div>

      <p class="pay-hint">Chọn phương thức và xác nhận</p>
      <div class="pay-numpad">
        <button class="pnb" onclick="P.pnp('1')">1</button><button class="pnb" onclick="P.pnp('2')">2</button><button class="pnb" onclick="P.pnp('3')">3</button><button class="pnb pnb-q" onclick="P.pnp('+10')">+10k</button>
        <button class="pnb" onclick="P.pnp('4')">4</button><button class="pnb" onclick="P.pnp('5')">5</button><button class="pnb" onclick="P.pnp('6')">6</button><button class="pnb pnb-q" onclick="P.pnp('+20')">+20k</button>
        <button class="pnb" onclick="P.pnp('7')">7</button><button class="pnb" onclick="P.pnp('8')">8</button><button class="pnb" onclick="P.pnp('9')">9</button><button class="pnb pnb-q" onclick="P.pnp('+50')">+50k</button>
        <button class="pnb" onclick="P.pnp('pm')">C</button><button class="pnb" onclick="P.pnp('0')">0</button><button class="pnb" onclick="P.pnp('.')">.</button><button class="pnb pnb-d" onclick="P.pnp('del')">&#9003;</button>
      </div>
      <button class="btn-confirm" id="btn-cfm" onclick="P.confirm()">✅ XÁC NHẬN THANH TOÁN</button>
    </div>
    <div class="pay-right">
      <h4>Khách hàng</h4><div class="pr-cust" id="pr-cust">Khách vãng lai</div>
      <h4>Tóm tắt đơn hàng</h4><div id="pr-lines"></div>
    </div>
  </div>
</div>

<!-- ════════ SCREEN 3: SUCCESS ════════ -->
<div id="s3" class="scr">
  <div class="ok-wrap">
    <div class="ok-left">
      <div class="ok-check">✅</div>
      <h2>Thanh toán thành công!</h2>
      <div style="background:rgba(16,185,129,.1); border:2px dashed var(--g500); padding:10px 30px; border-radius:12px; margin:10px 0">
        <p style="font-size:.75rem; color:var(--d500); text-transform:uppercase; letter-spacing:1px; margin-bottom:4px">Mã đơn hàng</p>
        <p class="ok-order" id="ok-order" style="font-size:1.5rem; font-weight:800; color:var(--g500); margin:0">...</p>
        <div id="ok-cash-box" style="margin-top:15px; padding:10px; background:rgba(59,130,246,0.1); border-radius:8px; border:1px dashed var(--b500)">
          <p style="font-size:.7rem; color:var(--b500); text-transform:uppercase; margin:0">Tiền mặt hiện tại trong két</p>
          <p id="ok-cash" style="font-size:1.3rem; font-weight:700; color:var(--b500); margin:0">0 ₫</p>
        </div>
      </div>
      <div class="ok-acts">
        <button class="btn-print" onclick="P.printReceipt()">🖨️ In biên lai</button>
        <button id="btn-spin-lucky" class="btn-next" style="display:none; background:linear-gradient(135deg,#f59e0b,#d97706); border:none;" onclick="P.goToSpin()">🎰 Vòng quay may mắn</button>
        <button class="btn-next" onclick="P.newOrder()">➕ Đơn hàng mới</button>
      </div>
    </div>
    <div class="ok-right">
      <div class="rcpt" id="rcpt-paper">
        <div class="rcpt-center"><img src="/bhx_sales/static/src/img/logo.png" style="width:140px;margin-bottom:8px;"/><div class="rcpt-info"> contact@bachhoaxanh.vn</div></div>
        <div class="rcpt-div"></div><div class="rcpt-cashier">Thu ngân: <b>{user.name}</b></div><div class="rcpt-div"></div>
        <div id="rcpt-lines"></div><div class="rcpt-div"></div>
        <div class="rcpt-tot"><span>TỔNG CỘNG</span><span id="rcpt-total">0 ₫</span></div>
        <div class="rcpt-method" id="rcpt-meth">Tiền mặt</div>
        <div class="rcpt-ln" style="font-size:0.65rem; color:#666; margin-top:8px"><span id="rcpt-date"></span><span id="rcpt-code"></span></div>
        <div class="rcpt-div"></div>
        <div class="rcpt-foot">Cảm ơn quý khách! Hẹn gặp lại 😊</div>
      </div>
    </div>
  </div>
</div>

<!-- QR Modal -->
<div id="qr-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,.85); backdrop-filter:blur(10px); z-index:9999; flex-direction:column; align-items:center; justify-content:center; gap:20px; animation:fadeIn .3s var(--ease)">
    <div style="background:white; padding:30px; border-radius:24px; text-align:center; box-shadow:0 20px 50px rgba(0,0,0,0.5); max-width:400px; width:90%">
        <h3 style="color:#1e293b; margin-bottom:5px; font-size:1.4rem">Quét mã để thanh toán</h3>
        <p style="color:#64748b; font-size:0.9rem; margin-bottom:20px">Vui lòng không thay đổi nội dung chuyển khoản</p>
        <div id="qr-img-container" style="background:#f1f5f9; padding:15px; border-radius:16px; margin-bottom:20px; display:inline-block">
            <img id="qr-img" src="" style="width:250px; height:250px; display:block"/>
        </div>
        <div style="text-align:left; background:#f8fafc; padding:15px; border-radius:12px; border:1px solid #e2e8f0; margin-bottom:20px">
            <div style="display:flex; justify-content:space-between; margin-bottom:8px"><span style="color:#64748b; font-size:0.8rem">Số tiền:</span><b id="qr-amt" style="color:#059669; font-size:1.1rem">0 ₫</b></div>
            <div style="display:flex; justify-content:space-between"><span style="color:#64748b; font-size:0.8rem">Nội dung:</span><b id="qr-msg" style="color:#2563eb; font-size:1rem">...</b></div>
        </div>
        <div style="display:flex; gap:10px">
            <button onclick="P.cancelQR()" style="flex:1; background:#f1f5f9; color:#475569; border:none; padding:12px; border-radius:10px; font-weight:600">Huỷ bỏ</button>
            <button id="btn-check-manual" onclick="P.checkPaymentStatusManual()" style="flex:1; background:#10b981; color:white; border:none; padding:12px; border-radius:10px; font-weight:600">Đã chuyển tiền</button>
        </div>
        <div style="margin-top:15px; display:flex; align-items:center; justify-content:center; gap:8px; color:#64748b; font-size:0.8rem">
            <div class="spinner" style="width:14px; height:14px; border:2px solid #e2e8f0; border-top-color:#10b981; border-radius:50%; animation:spin 1s linear infinite"></div>
            Đang chờ hệ thống xác nhận...
        </div>
    </div>
</div>

<style>
@keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style>

</div><!-- /app -->

<script id="bhx-init" type="application/json">{{"shift_id": {shift.id}}}</script>
<script src="/bhx_sales/static/src/js/pos_logic.js?v={int(request.env.cr.now().timestamp())}"></script>
</body>
</html>'''
