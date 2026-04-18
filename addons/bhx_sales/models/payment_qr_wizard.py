from odoo import models, fields, api, _
from odoo.exceptions import UserError

class BHXPaymentQRWizard(models.TransientModel):
    _name = 'bhx.payment.qr.wizard'
    _description = 'Wizard hiển thị mã QR thanh toán'

    order_id = fields.Many2one('bhx.sales.order', string='Đơn hàng', readonly=True)
    order_name = fields.Char(string='Mã đơn hàng', readonly=True)
    amount = fields.Float(string='Số tiền', readonly=True)
    qr_url = fields.Char(string='QR URL', readonly=True)
    qr_html = fields.Html(compute='_compute_qr_html', string='Mã QR')
    state = fields.Selection(related='order_id.state', string='Trạng thái đơn hàng', readonly=True)

    @api.depends('qr_url', 'amount', 'order_name')
    def _compute_qr_html(self):
        for rec in self:
            if rec.qr_url:
                rec.qr_html = f'''
                    <div style="text-align: center; background: white; padding: 20px; border-radius: 15px;">
                        <img src="{rec.qr_url}" style="width: 250px; height: 250px; display: block; margin: 0 auto;"/>
                        <div style="margin-top: 15px; font-weight: bold; color: #10b981; font-size: 1.2rem;">
                            {rec.amount:,.0f} VND
                        </div>
                        <div style="color: #64748b; margin-top: 5px;">
                            Nội dung: <span style="color: #2563eb; font-weight: bold;">{rec.order_name}</span>
                        </div>
                    </div>
                '''
            else:
                rec.qr_html = False

    def action_check_payment(self):
        """Kiểm tra xem đơn hàng đã được thanh toán (qua webhook) chưa"""
        self.ensure_one()
        if self.order_id.state == 'done':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Thành công'),
                    'message': _('Đơn hàng đã được thanh toán!'),
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }
        else:
            raise UserError(_('Đơn hàng chưa được thanh toán hoặc hệ thống chưa nhận được tín hiệu. Vui lòng kiểm tra lại sau giây lát.'))

    def action_confirm_manually(self):
        """Xác nhận thủ công nếu webhook gặp sự cố (Chỉ dành cho quản lý/thu ngân tin tưởng)"""
        self.ensure_one()
        self.order_id.action_done()
        return {'type': 'ir.actions.act_window_close'}
