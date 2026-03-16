{
    'name': 'Bách Hóa Xanh Lucky Spin',
    'version': '1.0',
    'category': 'Marketing',
    'summary': 'Vòng Quay Trúng Thưởng (Lucky Spin) for Bách Hóa Xanh',
    'description': """
        Module Vòng Quay Trúng Thưởng theo phong cách Bách Hóa Xanh.
        Cho phép tạo chiến dịch, cài đặt giải thưởng, tỷ lệ trúng, và lưu trữ lịch sử người quay.
    """,
    'author': 'Thinh Phan',
    'depends': ['base', 'web', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/history_views.xml',
        'views/campaign_views.xml',
        'views/prize_views.xml',
        'views/menu.xml',
        'views/lucky_spin_templates.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
