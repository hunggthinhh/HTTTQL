from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SalesShift(models.Model):
    _name = 'bhx.sales.shift'
    _description = 'Ca bán hàng'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, shift_type'

    name = fields.Char(
        string='Mã ca', required=True, copy=False,
        readonly=True, default=lambda self: _('New'), tracking=True,
    )
    date = fields.Date(string='Ngày', required=True, default=fields.Date.today, tracking=True)
    shift_type = fields.Selection([
        ('morning', 'Ca sáng (06:00 - 14:00)'),
        ('afternoon', 'Ca chiều (14:00 - 22:00)'),
        ('night', 'Ca đêm (22:00 - 06:00)'),
    ], string='Ca làm việc', required=True, default='morning', tracking=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Cửa hàng', required=True, tracking=True)
    cashier_id = fields.Many2one(
        'res.users', string='Thu ngân / Trưởng ca',
        default=lambda self: self.env.user, tracking=True,
    )
    open_time = fields.Datetime(string='Giờ mở ca')
    close_time = fields.Datetime(string='Giờ đóng ca')
    opening_cash = fields.Monetary(string='Tiền mặt đầu ca', currency_field='currency_id')
    closing_cash = fields.Monetary(string='Tiền mặt cuối ca', currency_field='currency_id')
    total_revenue = fields.Monetary(
        string='Tổng doanh thu ca', currency_field='currency_id',
        compute='_compute_revenue', store=True,
    )
    total_transactions = fields.Integer(
        string='Số giao dịch',
        compute='_compute_revenue', store=True,
    )
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    note = fields.Text(string='Ghi chú cuối ca')
    state = fields.Selection([
        ('open', 'Đang mở ca'),
        ('closed', 'Đã đóng ca'),
        ('reconciled', 'Đã đối soát'),
    ], string='Trạng thái ca', default='open', tracking=True)

    order_ids = fields.One2many('bhx.sales.order', 'shift_id', string='Đơn hàng trong ca')

    @api.depends('order_ids.total_amount', 'order_ids.state')
    def _compute_revenue(self):
        for shift in self:
            done_orders = shift.order_ids.filtered(lambda o: o.state == 'done')
            shift.total_revenue = sum(done_orders.mapped('total_amount'))
            shift.total_transactions = len(done_orders)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('bhx.sales.shift') or _('New')
            if 'open_time' not in vals:
                vals['open_time'] = fields.Datetime.now()
        return super().create(vals_list)

    def action_close_shift(self):
        self.ensure_one()
        self.write({'state': 'closed', 'close_time': fields.Datetime.now()})

    def action_reconcile(self):
        self.ensure_one()
        if self.state != 'closed':
            raise UserError(_('Chỉ có thể đối soát ca đã đóng.'))
        self.write({'state': 'reconciled'})

    def action_open_pos(self):
        self.ensure_one()
        if self.state != 'open':
            raise UserError(_('Ca đã đóng, không thể bán hàng.'))
        return {
            'type': 'ir.actions.act_url',
            'url': '/bhx/pos',
            'target': 'self',
        }


