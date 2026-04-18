{
    'name': 'BHX Bán Hàng',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Quản lý bán hàng tại quầy, ca làm việc và doanh thu',
    'description': """
        Module bán hàng dành cho Bách Hóa Xanh.
        - Quản lý ca bán hàng (mở ca / đóng ca)
        - Ghi nhận doanh thu theo ca / ngày
        - Quản lý chương trình khuyến mãi
        - Báo cáo doanh thu nhanh
    """,
    'author': 'Thinh Phan',
    'depends': ['base', 'product', 'mail', 'stock', 'bhx_import_goods'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'data/demo_data.xml',
        'views/sales_shift_views.xml',
        'views/sales_order_views.xml',
        'views/promotion_views.xml',
        'views/bhx_pos_templates.xml',
        'views/res_config_settings_views.xml',
        'views/payment_qr_wizard_views.xml',
        'views/menu.xml',

    ],
    # 'assets': {
    #     'web.assets_frontend': [
    #         'bhx_sales/static/src/css/pos_style.css',
    #         'bhx_sales/static/src/js/pos_logic.js',
    #     ],
    # },

    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
