from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    sepay_api_key = fields.Char(string='SePay API Key')
    sepay_bank_id = fields.Char(string='SePay Bank ID', help="Example: MB, VCB, ACB, ICB...")
    sepay_account_no = fields.Char(string='SePay Account Number')
    sepay_account_name = fields.Char(string='SePay Account Name')
    sepay_webhook_token = fields.Char(string='SePay Webhook Token', help="Dùng để xác thực tín hiệu từ SePay")
