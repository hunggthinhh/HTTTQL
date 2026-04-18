import json
import logging
import re
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


def parse_order_name(content):
    """
    Chuyển đổi mã đơn hàng từ nội dung chuyển khoản sang tên đơn trong Odoo.
    Hỗ trợ 2 format:
      - Có dấu gạch chéo:  BH/2026/04/00177
      - Không có dấu gạch: BH20260400177
    Trả về list các tên cần thử tìm.
    """
    content = content.strip()
    candidates = [content]

    # Format không có dấu /: BH + YYYY + MM + NNNNN (tổng >= 11 ký tự)
    # VD: BH20260400177 -> BH/2026/04/00177
    m = re.search(r'(BH)(\d{4})(\d{2})(\d{5,})', content.upper())
    if m:
        prefix, year, month, seq = m.groups()
        formatted = f"{prefix}/{year}/{month}/{seq}"
        candidates.append(formatted)
        # Thêm cả dạng có leading zeros tuỳ độ dài
        candidates.append(f"{prefix}/{year}/{month}/{seq.zfill(5)}")

    # Format có dấu /: BH/2026/04/00177 — lấy thẳng nếu content đã có dạng này
    m2 = re.search(r'(BH/\d{4}/\d{2}/\d+)', content.upper())
    if m2:
        candidates.append(m2.group(1))

    # Loại trùng, giữ thứ tự
    seen = set()
    unique = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


class SePayWebhookController(http.Controller):

    @http.route('/bhx/payment/sepay/webhook', type='http', auth='none', methods=['POST'], csrf=False, save_session=False)
    def sepay_webhook(self, **kwargs):
        """
        Nhận tín hiệu báo có tiền vào từ SePay.
        Dùng auth='none' + direct DB cursor để tránh 404 trong multi-database mode.
        """
        try:
            # Xác định database
            db_name = request.httprequest.args.get('db') or request.httprequest.headers.get('X-Openerp-Database')
            if not db_name:
                from odoo.tools import config
                db_name = config.get('db_name', False)

            if not db_name:
                _logger.error("SEPAY WEBHOOK: Missing db parameter")
                return request.make_response(
                    json.dumps({"success": False, "message": "Missing db parameter"}),
                    headers=[('Content-Type', 'application/json')]
                )

            # Lấy dữ liệu thô
            raw_data = request.httprequest.data
            if not raw_data:
                return request.make_response(
                    json.dumps({"success": False, "message": "No data"}),
                    headers=[('Content-Type', 'application/json')]
                )

            data = json.loads(raw_data)
            _logger.info("SEPAY WEBHOOK RECEIVED on db=%s: %s", db_name, json.dumps(data))

            # Trích xuất nội dung chuyển khoản
            raw_content = data.get('content', '').strip()
            if not raw_content:
                return request.make_response(
                    json.dumps({"success": False, "message": "Missing content"}),
                    headers=[('Content-Type', 'application/json')]
                )

            # Lấy danh sách tên đơn hàng có thể khớp
            name_candidates = parse_order_name(raw_content)
            _logger.info("SEPAY WEBHOOK: Searching for order, candidates: %s", name_candidates)

            # Kết nối database
            from odoo.api import Environment
            from odoo import registry
            import odoo

            db_registry = registry(db_name)
            with db_registry.cursor() as cr:
                env = Environment(cr, odoo.SUPERUSER_ID, {})
                OrderModel = env['bhx.sales.order']

                # Thử tìm đơn hàng với từng candidate
                order = None
                for name in name_candidates:
                    order = OrderModel.search([
                        ('state', 'in', ['draft']),
                        ('name', '=ilike', name)
                    ], limit=1)
                    if order:
                        _logger.info("SEPAY WEBHOOK: Found order %s with candidate '%s'", order.name, name)
                        break

                if not order:
                    _logger.warning("SEPAY WEBHOOK: No order found for content='%s', tried: %s", raw_content, name_candidates)
                    return request.make_response(
                        json.dumps({"success": False, "message": f"Order not found. Tried: {name_candidates}"}),
                        headers=[('Content-Type', 'application/json')]
                    )

                # Bảo mật Token
                company = order.company_id
                expected_token = getattr(company, 'sepay_webhook_token', False)
                received_token = (
                    request.httprequest.headers.get('x-sepay-token') or
                    data.get('token')
                )
                if expected_token and received_token != expected_token:
                    _logger.warning("SEPAY WEBHOOK: Invalid token for order %s", order.name)
                    return request.make_response(
                        json.dumps({"success": False, "message": "Invalid token"}),
                        status=401,
                        headers=[('Content-Type', 'application/json')]
                    )

                # Hoàn tất đơn hàng
                if order.state != 'done':
                    order.with_context(skip_qr_wizard=True).action_done()
                    _logger.info("SEPAY WEBHOOK: Order %s confirmed successfully!", order.name)

            return request.make_response(
                json.dumps({"success": True, "message": "OK"}),
                headers=[('Content-Type', 'application/json')]
            )

        except Exception as e:
            _logger.error("SEPAY WEBHOOK CRASH: %s", str(e), exc_info=True)
            return request.make_response(
                json.dumps({"success": False, "message": str(e)}),
                status=500,
                headers=[('Content-Type', 'application/json')]
            )
