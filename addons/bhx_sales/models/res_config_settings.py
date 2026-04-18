from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sepay_api_key = fields.Char(related='company_id.sepay_api_key', readonly=False, string="SePay API Key")
    sepay_bank_id = fields.Char(related='company_id.sepay_bank_id', readonly=False, string="Ngân hàng (Bank ID)")
    sepay_account_no = fields.Char(related='company_id.sepay_account_no', readonly=False, string="Số tài khoản")
    sepay_account_name = fields.Char(related='company_id.sepay_account_name', readonly=False, string="Tên chủ tài khoản")
    sepay_webhook_token = fields.Char(related='company_id.sepay_webhook_token', readonly=False, string="Mã xác thực Webhook")
