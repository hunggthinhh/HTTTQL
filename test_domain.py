import odoo
print("TEST SCRIPT STARTED")
def test():
    env = odoo.api.Environment(odoo.registry('Odoo').cursor(), 1, {})
    domain1 = [
        ('state', 'in', ['new', 'processing']),
        '|',
        ('alert_type', 'in', ['audit_required', 'control_required']),
        '&', ('days_to_expiry', '<', 30), '|', ('expiry_date', '!=', False), ('alert_type', 'in', ['near_expiry', 'expired'])
    ]
    alerts = env['bhx.stock.alert'].search([])
    print(f"Total alerts in DB: {len(alerts)}")
    for a in alerts:
        print(f"ID: {a.id} TYPE: {a.alert_type} EXPIRY: {a.expiry_date} DAYS: {a.days_to_expiry} STATE: {a.state}")
    
    print("\n--- DOMAIN FILTERED ---")
    fil_alerts = env['bhx.stock.alert'].search(domain1)
    for a in fil_alerts:
        print(f"MATCH: ID: {a.id} TYPE: {a.alert_type}")
test()
print("TEST SCRIPT ENDED")
