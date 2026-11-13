-- 聊天室数据库结构 (chat)
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nickname VARCHAR(32) NOT NULL,
  email VARCHAR(190) NOT NULL,
  pass_hash VARCHAR(255) NOT NULL,
  verified TINYINT NOT NULL DEFAULT 0,
  is_admin TINYINT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL,
  last_seen DATETIME NULL,
  UNIQUE KEY uniq_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS messages (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  body VARCHAR(2000) NOT NULL,
  created_at DATETIME NOT NULL,
  KEY idx_created (created_at),
  KEY idx_user_time (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS codes (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(190) NOT NULL,
  purpose VARCHAR(16) NOT NULL,
  code_hash CHAR(64) NOT NULL,
  expires_at DATETIME NOT NULL,
  attempts TINYINT NOT NULL DEFAULT 0,
  used_at DATETIME NULL,
  created_at DATETIME NOT NULL,
  KEY idx_email (email, purpose)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS invite_codes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  code CHAR(24) NOT NULL,
  note VARCHAR(64) NULL,
  created_at DATETIME NOT NULL,
  expires_at DATETIME NOT NULL,
  used_by INT NULL,
  used_at DATETIME NULL,
  status VARCHAR(8) NOT NULL DEFAULT 'active',
  UNIQUE KEY uniq_code (code),
  KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS settings (
  k VARCHAR(32) PRIMARY KEY,
  v VARCHAR(64) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ip_actions (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  ip VARCHAR(45) NOT NULL,
  action VARCHAR(16) NOT NULL,
  day DATE NOT NULL,
  n INT NOT NULL DEFAULT 1,
  UNIQUE KEY uniq_ip_action_day (ip, action, day)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO settings (k, v) VALUES ('registration_mode', 'invite')
  ON DUPLICATE KEY UPDATE v = v;
