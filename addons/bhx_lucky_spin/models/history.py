from odoo import models, fields

class LuckySpinHistory(models.Model):
    _name = 'bhx_lucky_spin.history'
    _description = 'Lịch sử Vòng Quay'
    _order = 'spin_date desc'

    customer_name = fields.Char('Tên khách hàng', required=True)
    phone = fields.Char('Số điện thoại', required=True)
    
    campaign_id = fields.Many2one('bhx_lucky_spin.campaign', string='Chiến dịch', required=True, ondelete='cascade')
    prize_id = fields.Many2one('bhx_lucky_spin.prize', string='Giải thưởng trúng', ondelete='set null')
    
    spin_date = fields.Datetime('Thời gian quay', default=fields.Datetime.now, required=True)
