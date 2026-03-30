from odoo import http
from odoo.http import request

class ExternalDashboard(http.Controller):

    @http.route('/bhx/dashboard', type='http', auth='public', website=True)
    def render_external_dashboard(self, **kwargs):
        # Lấy thông tin cảnh báo kiểm kê và kiểm soát đang chờ xử lý
        alerts = request.env['bhx.stock.alert'].sudo().search([
            ('state', 'in', ['new', 'processing']),
            ('alert_type', 'in', ['audit_required', 'control_required'])
        ])

        # Nhóm theo cửa hàng/kho
        warehouses = request.env['stock.warehouse'].sudo().search([
            ('id', 'in', alerts.mapped('warehouse_id').ids)
        ])

        dashboard_data = []
        for wh in warehouses:
            wh_alerts = alerts.filtered(lambda a: a.warehouse_id.id == wh.id)
            dashboard_data.append({
                'warehouse_name': wh.name,
                'audit_count': len(wh_alerts.filtered(lambda a: a.alert_type == 'audit_required')),
                'control_count': len(wh_alerts.filtered(lambda a: a.alert_type == 'control_required')),
                'alerts': wh_alerts
            })

        return request.render('bhx_inventory_display.external_dashboard_template', {
            'dashboard_data': dashboard_data,
            'total_alerts': len(alerts),
        })
