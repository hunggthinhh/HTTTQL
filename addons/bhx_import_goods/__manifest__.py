{
    'name': 'BHX Nhập Hàng',
    'version': '1.0',
    'category': 'Inventory',
    'summary': 'Quản lý nhập hàng: FMCG, Rau củ trái cây, Hàng Fresh',
    'description': """
        Module quản lý nhập hàng dành cho Bách Hóa Xanh.
        - Kiểm hàng nhập kho FMCG
        - Nhập rau củ trái cây
        - Nhập hàng Fresh (thịt, cá, hải sản...)
    """,
    'author': 'Thinh Phan',
    'depends': ['base', 'stock', 'product', 'mail', 'purchase', 'sale'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'data/demo_data.xml',
        'views/fmcg_import_views.xml',
        'views/fruit_veg_import_views.xml',
        'views/fresh_import_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
