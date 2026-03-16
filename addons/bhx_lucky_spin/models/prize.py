from odoo import models, fields, api
from odoo.exceptions import ValidationError

class LuckySpinPrize(models.Model):
    _name = 'bhx_lucky_spin.prize'
    _description = 'Giải thưởng Vòng Quay'

    name = fields.Char('Tên giải thưởng', required=True)
    campaign_id = fields.Many2one('bhx_lucky_spin.campaign', string='Chiến dịch', required=True, ondelete='cascade')
    
    probability = fields.Float('Tỉ lệ trúng (%)', required=True, default=0.0)
    total_qty = fields.Integer('Tổng số lượng', default=100)
    remaining_qty = fields.Integer('Số lượng còn lại', default=100, copy=False)
    
    image = fields.Binary('Hình ảnh', attachment=True)
    color = fields.Char('Màu sắc hiển thị', default='#007b3e', help='Mã màu hex (VD: #007b3e) dùng để hiển thị trên vòng quay frontend.')

    @api.onchange('total_qty')
    def _onchange_total_qty(self):
        self.remaining_qty = self.total_qty

    @api.constrains('probability')
    def _check_probability(self):
        for rec in self:
            if rec.probability < 0 or rec.probability > 100:
                raise ValidationError('Tỉ lệ trúng phải nằm trong khoảng từ 0% đến 100%.')

    @api.constrains('total_qty', 'remaining_qty')
    def _check_qty(self):
        for rec in self:
            if rec.remaining_qty < 0:
                raise ValidationError('Số lượng giải thưởng còn lại không được nhỏ hơn 0.')
            if rec.remaining_qty > rec.total_qty:
                raise ValidationError('Số lượng còn lại không thể lớn hơn Tổng số lượng ban đầu.')
