SET NAMES utf8mb4;
ALTER TABLE users ADD COLUMN IF NOT EXISTS role TINYINT NOT NULL DEFAULT 0;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS deleted TINYINT NOT NULL DEFAULT 0;
UPDATE users SET role = 3 WHERE id = 1;
UPDATE users SET role = 2 WHERE is_admin = 1 AND id <> 1 AND role = 0;
CREATE TABLE IF NOT EXISTS keywords (
  id INT AUTO_INCREMENT PRIMARY KEY,
  word VARCHAR(64) NOT NULL,
  created_at DATETIME NOT NULL,
  UNIQUE KEY uniq_word (word)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS bans (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  type VARCHAR(8) NOT NULL,
  by_id INT NULL,
  reason VARCHAR(128) NULL,
  created_at DATETIME NOT NULL,
  UNIQUE KEY uniq_user_type (user_id, type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT IGNORE INTO keywords (word, created_at) VALUES
 ('加微信', NOW()), ('加QQ', NOW()), ('代刷', NOW()), ('刷单', NOW()),
 ('赌博', NOW()), ('博彩', NOW()), ('色情', NOW()), ('办证', NOW()), ('发票', NOW());
