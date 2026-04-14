{
    'name': 'BHX Tồn Kho & Trưng Bày',
    'version': '1.0',
    'category': 'Inventory',
    'summary': 'Quản lý tồn kho, vị trí trưng bày và cảnh báo hàng tồn',
    'description': """
        Module quản lý tồn kho & trưng bày dành cho Bách Hóa Xanh.
        - Quản lý vị trí trưng bày theo quầy / kệ / tủ lạnh
        - Theo dõi tồn kho theo lô, HSD
        - Cảnh báo hàng sắp hết / sắp hết hạn
        - Điều chỉnh tồn kho nội bộ
    """,
    'author': 'Thinh Phan',
    'depends': ['base', 'stock', 'product', 'mail', 'bhx_import_goods', 'bhx_audit_control'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'data/dashboard_data.xml',
        'data/cron_data.xml',
        'views/dashboard_template.xml',
        'views/display_location_views.xml',
        'views/stock_alert_views.xml',
        'views/replenishment_views.xml',
        'views/stock_adjustment_views.xml',
        'views/dashboard_views.xml',
        'views/audit_control_inherit_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
