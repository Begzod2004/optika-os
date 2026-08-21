-- Optika OS: filiallar bo'yicha izolyatsiya migratsiyasi + demo ma'lumotlarni tozalash.
-- ISHLATISH TARTIBI (server) — TARTIB MUHIM:
--   1) cd /opt/optika-os && docker compose -p optika -f docker-compose.prod.yml stop backend
--      (backend TO'XTATILADI: wipe paytida yozuvlar kirmasin, eski kod qayta seed qilmasin)
--   2) bash scripts/backup.sh                    (majburiy backup!)
--   3) docker exec -i optika-postgres-1 psql -U optika -d optika -v ON_ERROR_STOP=1 < scripts/migrate-branches.sql
--   4) Yangi kod rsync qilinadi va backend+frontend build/up: shundan keyingina backend qayta ishga tushadi.
-- Saqlanadi: users, branches, user_branches, audit_logs, backup_records.

BEGIN;

-- 1) branch_id ustunlari (8 ta jadval)
ALTER TABLE customers      ADD COLUMN IF NOT EXISTS branch_id INTEGER REFERENCES branches(id);
ALTER TABLE products       ADD COLUMN IF NOT EXISTS branch_id INTEGER REFERENCES branches(id);
ALTER TABLE orders         ADD COLUMN IF NOT EXISTS branch_id INTEGER REFERENCES branches(id);
ALTER TABLE sales          ADD COLUMN IF NOT EXISTS branch_id INTEGER REFERENCES branches(id);
ALTER TABLE repair_orders  ADD COLUMN IF NOT EXISTS branch_id INTEGER REFERENCES branches(id);
ALTER TABLE optical_cases  ADD COLUMN IF NOT EXISTS branch_id INTEGER REFERENCES branches(id);
ALTER TABLE cash_shifts    ADD COLUMN IF NOT EXISTS branch_id INTEGER REFERENCES branches(id);
ALTER TABLE expenses       ADD COLUMN IF NOT EXISTS branch_id INTEGER REFERENCES branches(id);

CREATE INDEX IF NOT EXISTS ix_customers_branch_id     ON customers(branch_id);
CREATE INDEX IF NOT EXISTS ix_products_branch_id      ON products(branch_id);
CREATE INDEX IF NOT EXISTS ix_orders_branch_id        ON orders(branch_id);
CREATE INDEX IF NOT EXISTS ix_sales_branch_id         ON sales(branch_id);
CREATE INDEX IF NOT EXISTS ix_repair_orders_branch_id ON repair_orders(branch_id);
CREATE INDEX IF NOT EXISTS ix_optical_cases_branch_id ON optical_cases(branch_id);
CREATE INDEX IF NOT EXISTS ix_cash_shifts_branch_id   ON cash_shifts(branch_id);
CREATE INDEX IF NOT EXISTS ix_expenses_branch_id      ON expenses(branch_id);

-- 2) Telefon unikalligi: global -> filial darajasida
ALTER TABLE customers DROP CONSTRAINT IF EXISTS customers_phone_key;
ALTER TABLE customers DROP CONSTRAINT IF EXISTS uq_customers_branch_phone;
DROP INDEX IF EXISTS ix_customers_phone;
DROP INDEX IF EXISTS uq_customers_branch_phone;
CREATE INDEX ix_customers_phone ON customers(phone);
CREATE UNIQUE INDEX uq_customers_branch_phone ON customers(branch_id, phone);
-- Izoh: branch_id IS NULL qatorlar orasida PG unikallikni tekshirmaydi;
-- ilova darajasidagi 409 tekshiruvi buni qoplaydi.

-- 3) Demo/sinov ma'lumotlarini tozalash (FK-xavfsiz tartibda)
DELETE FROM telegram_links;
DELETE FROM telegram_subscribers;
DELETE FROM eye_exams;
DELETE FROM centrations;
DELETE FROM lens_configurations;
DELETE FROM lab_jobs;
DELETE FROM optical_cases;
DELETE FROM sale_returns;
DELETE FROM sale_items;
DELETE FROM sales;
DELETE FROM orders;
DELETE FROM repair_orders;
DELETE FROM prescriptions;
DELETE FROM customer_payments;
DELETE FROM purchase_items;
DELETE FROM purchases;
DELETE FROM supplier_payments;
DELETE FROM suppliers;
DELETE FROM stock_movements;
DELETE FROM products;
DELETE FROM expenses;
DELETE FROM cash_movements;
DELETE FROM cash_shifts;
DELETE FROM customers;

-- 4) Id ketma-ketliklarini 1 dan boshlash
SELECT setval(pg_get_serial_sequence(t, 'id'), 1, false)
FROM unnest(ARRAY['customers','customer_payments','products','stock_movements','prescriptions',
  'suppliers','supplier_payments','purchases','purchase_items','cash_shifts','cash_movements',
  'expenses','orders','sales','sale_items','sale_returns','repair_orders','telegram_subscribers',
  'telegram_links','optical_cases','eye_exams','centrations','lens_configurations','lab_jobs']) AS t;

COMMIT;
