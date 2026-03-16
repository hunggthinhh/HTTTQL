from odoo import models, fields

class ProductBatch(models.Model):
    _name = 'product.batch'
    _description = 'Product Batch'

    name = fields.Char(string="Batch Code", required=True)

    product_id = fields.Many2one(
        'product.product',
        string="Product",
        required=True
    )

    quantity = fields.Integer(string="Quantity")

    expiry_date = fields.Date(string="Expiry Date")

    status = fields.Selection(
        [
            ('available', 'Available'),
            ('expired', 'Expired'),
        ],
        default='available',
        string="Status"
    )