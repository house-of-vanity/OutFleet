-- ВАРИАНТ 1: Удалить ВСЕ записи без acl_link_id
-- ОСТОРОЖНО! Это удалит все старые логи
DELETE FROM vpn_accesslog 
WHERE acl_link_id IS NULL OR acl_link_id = '';

-- ВАРИАНТ 2: Удалить записи без acl_link_id старше 30 дней
-- Более безопасный вариант
DELETE FROM vpn_accesslog 
WHERE (acl_link_id IS NULL OR acl_link_id = '') 
  AND timestamp < NOW() - INTERVAL 30 DAY;

-- ВАРИАНТ 3: Удалить записи без acl_link_id старше 7 дней
-- Еще более консервативный подход
DELETE FROM vpn_accesslog 
WHERE (acl_link_id IS NULL OR acl_link_id = '') 
  AND timestamp < NOW() - INTERVAL 7 DAY;

-- ВАРИАНТ 4: Оставить только последние 1000 записей без ссылок (для истории)
DELETE FROM vpn_accesslog 
WHERE (acl_link_id IS NULL OR acl_link_id = '') 
  AND id NOT IN (
    SELECT id FROM (
      SELECT id FROM vpn_accesslog 
      WHERE acl_link_id IS NULL OR acl_link_id = ''
      ORDER BY timestamp DESC 
      LIMIT 1000
    ) AS recent_logs
  );

-- ВАРИАНТ 5: Поэтапное удаление (для больших БД)
-- Удаляем по 10000 записей за раз
DELETE FROM vpn_accesslog 
WHERE (acl_link_id IS NULL OR acl_link_id = '') 
  AND timestamp < NOW() - INTERVAL 30 DAY
LIMIT 10000;
