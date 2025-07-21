-- Проверить количество записей без acl_link_id
SELECT COUNT(*) as total_without_link 
FROM vpn_accesslog 
WHERE acl_link_id IS NULL OR acl_link_id = '';

-- Проверить общее количество записей
SELECT COUNT(*) as total_records FROM vpn_accesslog;

-- Показать распределение по датам (последние записи без ссылок)
SELECT DATE(timestamp) as date, COUNT(*) as count 
FROM vpn_accesslog 
WHERE acl_link_id IS NULL OR acl_link_id = ''
GROUP BY DATE(timestamp) 
ORDER BY date DESC 
LIMIT 10;
