
// ================= 2026-10-05 追加2: 群主兜底校验 =================
function owner_count(): int {
  try { return (int)db()->query('SELECT COUNT(*) FROM users WHERE role = 3')->fetchColumn(); }
  catch (Throwable $e) { return -1; }
}

// 有用户却没有任何群主 -> 记录并拒绝; 空库(首次注册)放行
function owner_guard(): void {
  $n = owner_count();
  if ($n < 0) return;
  if ($n === 0) {
    try { $total = (int)db()->query('SELECT COUNT(*) FROM users')->fetchColumn(); } catch (Throwable $e) { return; }
    if ($total === 0) return;
    chat_log('群主缺失', '没有任何群主账号, 已阻止访问; ip=' . client_ip() . ' uri=' . ($_SERVER['REQUEST_URI'] ?? ''));
    log_mod(null, null, 'owner_missing', 'blocked ' . ($_SERVER['REQUEST_URI'] ?? ''));
    fail('系统异常: 当前没有任何群主账号, 已暂停服务 (请联系管理员恢复)', 503);
  }
  if ($n > 1) {
    chat_log('群主异常', '检测到 ' . $n . ' 个群主账号; ip=' . client_ip());
    log_mod(null, null, 'owner_multi', 'count=' . $n);
  }
}
