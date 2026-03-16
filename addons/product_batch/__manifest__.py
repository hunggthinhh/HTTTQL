{
    'name': 'Product Batch',
    'version': '1.0',
    'summary': 'Manage product batches',
    'author': 'Thinh',
    'license': 'LGPL-3',
    'depends': ['base', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_batch_views.xml',
    ],
    'installable': True,
    'application': True,
}