from odoo import http, fields
from odoo.http import request
from markupsafe import Markup
import random
import json
from datetime import datetime

class LuckySpinController(http.Controller):

    @http.route('/lucky-spin', type='http', auth='public', website=True)
    def render_lucky_spin(self, **kw):
        now = datetime.now()
        # find the active campaign that is currently running
        campaign = request.env['bhx_lucky_spin.campaign'].sudo().search([
            ('active', '=', True),
            ('start_date', '<=', now),
            ('end_date', '>=', now)
        ], limit=1)

        prizes = []
        if campaign:
            for prize in campaign.prize_ids:
                prizes.append({
                    'id': prize.id,
                    'name': prize.name,
                    'color': prize.color,
                })

        prizes_json = Markup(json.dumps(prizes))

        return request.render('bhx_lucky_spin.lucky_spin_page', {
            'campaign': campaign,
            'prizes': prizes_json,
        })

    @http.route('/lucky-spin/play', type='json', auth='public')
    def play_lucky_spin(self, name, phone, campaign_id, **kw):
        if not name or not phone or not campaign_id:
            return {'error': 'Vui lòng nhập đầy đủ thông tin.'}

        campaign = request.env['bhx_lucky_spin.campaign'].sudo().browse(int(campaign_id))
        if not campaign or not campaign.active:
            return {'error': 'Chiến dịch không tồn tại hoặc đã kết thúc.'}

        # Lấy danh sách giải thưởng xem xét probability và remaining_qty
        prizes = campaign.prize_ids.filtered(lambda p: p.remaining_qty > 0)
        
        if not prizes:
            return {'error': 'Rất tiếc, đã hết giải thưởng!'}

        # Calculate random prize based on probability
        rand_val = random.uniform(0, 100)
        cumulative_prob = 0.0
        winning_prize = None

        for prize in prizes:
            cumulative_prob += prize.probability
            if rand_val <= cumulative_prob:
                winning_prize = prize
                break
        
        # Nếu tổng tỉ lệ < 100% và quay vào phần tỉ lệ trống thì không trúng
        if not winning_prize:
            return {'prize_id': None, 'message': 'Chúc bạn may mắn lần sau!'}
        
        # Create history record
        request.env['bhx_lucky_spin.history'].sudo().create({
            'customer_name': name,
            'phone': phone,
            'campaign_id': campaign.id,
            'prize_id': winning_prize.id,
        })

        # Giảm số lượng còn lại của giải
        winning_prize.sudo().remaining_qty -= 1

        return {
            'prize_id': winning_prize.id,
            'prize_name': winning_prize.name,
            'message': f'Chúc mừng! Bạn đã trúng {winning_prize.name}'
        }
