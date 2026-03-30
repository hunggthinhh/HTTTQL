{
    'name': 'BHX Kiểm Kê & Kiểm Soát Hàng Hoá',
    'version': '1.0',
    'category': 'Inventory',
    'summary': 'Kiểm kê định kỳ, kiểm soát hàng hoá, xử lý hàng lỗi/hết hạn',
    'description': """
        Module kiểm kê & kiểm soát hàng hoá dành cho Bách Hóa Xanh.
        - Lập kế hoạch & thực hiện kiểm kê định kỳ
        - Kiểm soát hàng sắp hết hạn / đã hết hạn
        - Lập phiếu xử lý hàng lỗi, huỷ hàng
        - Kiểm tra hàng trưng bày theo tiêu chuẩn
    """,
    'author': 'Thinh Phan',
    'depends': ['base', 'stock', 'product', 'mail', 'bhx_import_goods'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'data/demo_data.xml',
        'views/inventory_count_views.xml',
        'views/goods_control_views.xml',
        'views/disposal_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
