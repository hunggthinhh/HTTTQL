from odoo import models, fields, api
from odoo.exceptions import ValidationError

class LuckySpinCampaign(models.Model):
    _name = 'bhx_lucky_spin.campaign'
    _description = 'Chiến dịch Vòng Quay Trúng Thưởng'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc'

    name = fields.Char('Tên chiến dịch', required=True, tracking=True)
    start_date = fields.Datetime('Thời gian bắt đầu', required=True, tracking=True)
    end_date = fields.Datetime('Thời gian kết thúc', required=True, tracking=True)
    active = fields.Boolean('Hoạt động', default=True, tracking=True)
    description = fields.Text('Mô tả')

    prize_ids = fields.One2many('bhx_lucky_spin.prize', 'campaign_id', string='Danh sách Giải thưởng')
    history_ids = fields.One2many('bhx_lucky_spin.history', 'campaign_id', string='Lịch sử quay')

    total_spins = fields.Integer('Tổng số lượt quay', compute='_compute_spins_count')

    @api.depends('history_ids')
    def _compute_spins_count(self):
        for rec in self:
            rec.total_spins = len(rec.history_ids)

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.start_date > rec.end_date:
                raise ValidationError('Thời gian kết thúc phải lớn hơn hoặc bằng thời gian bắt đầu.')
    
    @api.constrains('prize_ids')
    def _check_probabilities_total(self):
        for rec in self:
            total_prob = sum(rec.prize_ids.mapped('probability'))
            if total_prob > 100.0001:  # Allow slight float variations
                raise ValidationError('Tổng Tỉ lệ trúng của các giải thưởng không được vượt quá 100%.')
