#!/bin/bash
# 聊天室数据清理: 消息/上传 保留 30 天; 验证码 30 天; 过期/作废邀请码 30 天; IP 计数 7 天
mariadb chat <<'SQL'
DELETE FROM messages WHERE created_at < DATE_SUB(NOW(), INTERVAL 30 DAY);
DELETE FROM messages WHERE kind = 'image' AND file_id IS NOT NULL AND file_id NOT IN (SELECT id FROM uploads);
DELETE FROM uploads WHERE created_at < DATE_SUB(NOW(), INTERVAL 30 DAY);
DELETE FROM codes WHERE created_at < DATE_SUB(NOW(), INTERVAL 30 DAY);
DELETE FROM invite_codes WHERE created_at < DATE_SUB(NOW(), INTERVAL 30 DAY) AND status <> 'active';
DELETE FROM ip_actions WHERE day < DATE_SUB(CURDATE(), INTERVAL 7 DAY);
SQL
find /var/lib/chat-uploads -type f -mtime +30 -delete 2>/dev/null || true
echo "$(date +%Y-%m-%dT%H:%M:%S) [清理] 聊天室数据清理完成 (消息/图片/上传>30天 已删)" >> /var/log/chat.log
