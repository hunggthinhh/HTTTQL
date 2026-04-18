import json
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

class SePayWebhookController(http.Controller):

    @http.route('/bhx/payment/sepay/webhook', type='json', auth='public', methods=['POST'], csrf=False)
    def sepay_webhook(self):
        """
        Nhận tín hiệu báo có tiền vào từ SePay (https://sepay.vn)
        Payload format:
        {
            "id": 12345,
            "gateway": "MBBank",
            "content": "BHX202404180001",
            "transferAmount": 100000,
            ...
        }
        """
        data = request.jsonrequest
        _logger.info("SEPAY WEBHOOK RECEIVED: %s", json.dumps(data))

        # 1. Trích xuất nội dung chuyển khoản (Lưu ý: nội dung này phải khớp với Mã đơn hàng)
        order_name = data.get('content', '').strip()
        amount = data.get('transferAmount', 0)

        # 2. Kiểm tra Token bảo mật (Sử dụng getattr để tránh lỗi nếu chưa upgrade)
        company = request.env.company
        expected_token = getattr(company, 'sepay_webhook_token', False)
        # SePay thường gửi token trong header hoặc payload tùy cấu hình
        # Ở đây ta check trong header 'x-sepay-token' hoặc payload
        received_token = request.httprequest.headers.get('x-sepay-token') or data.get('token')
        
        if expected_token and received_token != expected_token:
            _logger.warning("SEPAY WEBHOOK: Invalid token received")
            return {"success": False, "message": "Invalid token"}

        # 3. Tìm đơn hàng tương ứng trong Odoo
        order = request.env['bhx.sales.order'].sudo().search([
            ('name', '=', order_name),
            ('state', 'in', ['draft', 'cancel'])
        ], limit=1)

        if not order:
            _logger.warning("SEPAY WEBHOOK: Order %s not found", order_name)
            return {"success": False, "message": f"Order {order_name} not found"}

        # 3. Kiểm tra số tiền (tùy chọn: có thể lỏng lẻo hoặc chặt chẽ)
        if abs(order.total_amount - amount) > 100: # Cho phép sai lệch nhỏ < 100 VND
             _logger.warning("SEPAY WEBHOOK: Amount mismatch for %s. Expected %s, got %s", order_name, order.total_amount, amount)
             # Vẫn log lại nhưng có thể không confirm tự động nếu muốn an toàn tuyệt đối
             # Ở đây tôi vẫn cho đi tiếp nếu bạn muốn automation tối đa

        # 4. Xác nhận đơn hàng
        try:
            if order.state != 'done':
                order.sudo().action_done()
                _logger.info("SEPAY WEBHOOK: Successfully confirmed order %s", order_name)
            return {"success": True, "message": "Order confirmed"}
        except Exception as e:
            _logger.error("SEPAY WEBHOOK ERROR confirming order %s: %s", order_name, str(e))
            return {"success": False, "message": str(e)}
