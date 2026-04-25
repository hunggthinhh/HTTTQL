from odoo import models, fields, api, _
from odoo.exceptions import UserError

class BhxReturnWizard(models.TransientModel):
    _name = 'bhx.return.wizard'
    _description = 'Wizard chọn sản phẩm đổi/trả'

    order_id = fields.Many2one(
        'bhx.sales.order', string='Đơn hàng',
        required=True, readonly=True
    )
    note = fields.Text(string='Lý do đổi/trả')
    line_ids = fields.One2many(
        'bhx.return.wizard.line', 'wizard_id',
        string='Sản phẩm'
    )

    def action_create_return_request(self):
        """Tạo phiếu Return Request từ Wizard, mở form để nhân viên xác nhận."""
        self.ensure_one()
        lines_to_return = self.line_ids.filtered(lambda l: l.return_qty > 0)

        if not lines_to_return:
            raise UserError(_('Vui lòng nhập số lượng muốn trả cho ít nhất một sản phẩm.'))

        req = self.env['bhx.return.request'].create({
            'order_id': self.order_id.id,
            'note': self.note,
            'line_ids': [(0, 0, {
                'order_line_id': l.order_line_id.id,
                'return_qty': l.return_qty,
            }) for l in lines_to_return],
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Yêu cầu Đổi/Trả'),
            'res_model': 'bhx.return.request',
            'res_id': req.id,
            'view_mode': 'form',
            'target': 'current',
        }

class BhxReturnWizardLine(models.TransientModel):
    _name = 'bhx.return.wizard.line'
    _description = 'Dòng Wizard đổi/trả'

    wizard_id = fields.Many2one(
        'bhx.return.wizard', required=True, ondelete='cascade'
    )
    order_line_id = fields.Many2one(
        'bhx.sales.order.line', string='Dòng đơn hàng',
        required=True
    )
    product_id = fields.Many2one(
        related='order_line_id.product_id', store=True,
        string='Sản phẩm'
    )
    purchased_qty = fields.Float(
        related='order_line_id.qty',
        string='SL đã mua'
    )
    returned_qty = fields.Float(
        string='Đã trả trước đó',
        compute='_compute_qty'
    )
    available_qty = fields.Float(
        string='Có thể trả',
        compute='_compute_qty'
    )
    return_qty = fields.Float(
        string='SL muốn trả', default=0
    )

    @api.depends('order_line_id')
    def _compute_qty(self):
        for line in self:
            approved = self.env['bhx.return.request.line'].search([
                ('order_line_id', '=', line.order_line_id.id),
                ('return_id.state', '=', 'approved'),
            ])
            returned = sum(approved.mapped('return_qty'))
            line.returned_qty = returned
            line.available_qty = (line.purchased_qty or 0) - returned

    @api.constrains('return_qty')
    def _check_qty(self):
        for line in self:
            if line.return_qty < 0:
                raise UserError(_('Số lượng trả không được âm.'))
            if line.return_qty > line.available_qty:
                raise UserError(_(
                    'Sản phẩm "%s": Số lượng trả (%s) vượt quá số lượng có thể trả (%s).'
                ) % (line.product_id.name, line.return_qty, line.available_qty))
                