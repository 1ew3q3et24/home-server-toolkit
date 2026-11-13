
import shutil, time, re
p='/usr/local/sbin/failover.sh'
s=open(p,encoding='utf-8').read(); miss=[]

s2=re.sub(r'\[ -n "\$\{RAINYUN_API_KEY:-\}" \] \|\| die [^\n]*\n', '', s, count=1)
if s2==s: miss.append('RAINYUN_LINE')
s=s2
s2=re.sub(r'ID="\$\{RAINYUN_DOMAIN_ID:\?\}"; ', '', s, count=1)
if s2==s: miss.append('ID_LINE')
s=s2
s2=re.sub(r'CFG=\$\(mktemp\); chmod 600 "\$CFG"\nprintf .*?CURL=\(curl -sS --max-time 20 --config "\$CFG"\)\n', '', s, count=1, flags=re.S)
if s2==s: miss.append('DEAD_CFG')
s=s2

def rep(a,b):
    global s
    if a not in s:
        miss.append(a[:40]); return
    s=s.replace(a,b,1)

rep('''  # 安全校验: 家里 MC 仍在写世界时, 先等它停止 (最多 10 分钟), 绝不双写
  if /usr/local/sbin/home-mc-alive.sh | grep -q '^1 '; then
    log "手动接管: 家里 MC 仍在运行, 等待停止 (最多 10 分钟)"
    for i in $(seq 1 120); do
      /usr/local/sbin/home-mc-alive.sh | grep -q '^0 ' && break
      sleep 5
    done
    if /usr/local/sbin/home-mc-alive.sh | grep -q '^1 '; then
      log "手动接管取消: 家里 MC 仍未停止"
      exit 3
    fi
    log "家里 MC 已停止, 继续云端接管"
  fi''','''  # 安全校验: 家里 MC 仍在写世界时, 先等它停止 (最多 10 分钟), 绝不双写
  alive_out=$(/usr/local/sbin/home-mc-alive.sh 2>>"$LOG") || { log "ERROR 防双写检查执行失败, 拒绝切云"; exit 4; }
  case "$alive_out" in
    "1 "*)
      log "手动接管: 家里 MC 仍在运行, 等待停止 (最多 10 分钟)"
      for i in $(seq 1 120); do
        alive_out=$(/usr/local/sbin/home-mc-alive.sh 2>>"$LOG") || { log "ERROR 防双写检查执行失败, 拒绝切云"; exit 4; }
        case "$alive_out" in
          "0 "*) break;;
          "1 "*) :;;
          *) log "ERROR 防双写检查输出异常: $alive_out"; exit 4;;
        esac
        sleep 5
      done
      case "$alive_out" in
        "1 "*) log "手动接管取消: 家里 MC 仍未停止"; exit 3;;
        "0 "*) log "家里 MC 已停止, 继续云端接管";;
      esac
      ;;
    "0 "*) :;;
    *) log "ERROR 防双写检查输出异常: $alive_out"; exit 4;;
  esac''')

rep('''  systemctl start mc; wait_for_port || die "云端 MC 起不来"
  set_record mc "$CIP" || die "DNS 切换失败"''','''  systemctl start mc; wait_for_port || die "云端 MC 起不来"
  if ! set_record mc "$CIP"; then systemctl stop mc; die "DNS 切换失败, 已停云端 MC"; fi''')

rep('''  log "失联 $N/$TH: $NOTE 且外网不可达"
  [ "$N" -ge "$TH" ] || exit 0
  log "=== 开始切换: 家里 -> 云端 ==="''','''  log "失联 $N/$TH: $NOTE 且外网不可达"
  [ "$N" -ge "$TH" ] || exit 0
  alive_out=$(/usr/local/sbin/home-mc-alive.sh 2>>"$LOG") || { log "ERROR 防双写检查执行失败, 拒绝切云"; exit 4; }
  case "$alive_out" in
    "1 "*) log "家里 MC 仍在运行, 拒绝切云以免双写"; echo 0 > "$CNTF"; exit 0;;
    "0 "*) :;;
    *) log "ERROR 防双写检查输出异常: $alive_out"; exit 4;;
  esac
  log "=== 开始切换: 家里 -> 云端 ==="''')

# CGNAT branch: insert reset after the log line, without literal dollar-brace
s2=re.sub(r'(log "告警 连续[^\n]*\n)(\s*exit 0)', r'\1    echo 0 > "$CNTF"\n\2', s, count=1)
if s2==s: miss.append('CGNAT')
s=s2

rep('''if [ "$ACTION" = "force-home" ]; then
  [ -n "$TARGET" ] || die "取不到家里 IP"
  if systemctl is-active --quiet mc; then''','''if [ "$ACTION" = "force-home" ]; then
  [ -n "$TARGET" ] || die "取不到家里 IP"
  [ "$(probe "$TARGET")" = "yes" ] || die "家里 25565 不可达, 拒绝 force-home"
  if systemctl is-active --quiet mc; then''')

if miss:
    print('MISSING',miss); raise SystemExit(2)
shutil.copyfile(p,p+'.bak-bugfix-'+time.strftime('%Y%m%d-%H%M%S'))
open(p,'w',encoding='utf-8').write(s)
print('FAILOVER_PATCHED')
