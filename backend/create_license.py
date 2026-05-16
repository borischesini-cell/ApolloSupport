import psycopg
conn = psycopg.connect('dbname=apollosupport_db user=postgres password=INGENIERIA', autocommit=True)
conn.execute("INSERT INTO licenses (license_key, client_id, max_devices, expiry_date, is_active, created_at) VALUES ('APOLLO-TEST-KEY-123', 1, 5, '2030-01-01', true, NOW());")
print('License created')
