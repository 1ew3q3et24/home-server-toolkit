
p='/var/www/logview/ddospanel.py'
s=open(p,encoding='utf-8').read(); miss=[]
old='''                if action == "mode_on":
                    open(MODE, "w").write(str(int(time.time())))
                    set_setting("security_level", "under_attack")
                    os.makedirs(os.path.dirname(UA_UNTIL), exist_ok=True)
                    open(UA_UNTIL, "w").write(str(int(time.time()) + 7200))
                    audit("mode_on")
                else:
                    try: os.remove(MODE)
                    except Exception: pass
                    set_setting("security_level", "medium")
                    audit("mode_off")'''
new='''                import subprocess
                if action == "mode_on":
                    subprocess.run(["/usr/local/sbin/ddos-mode.sh", "on"], capture_output=True, timeout=40)
                    open(MODE, "w").write(str(int(time.time())))
                    set_setting("security_level", "under_attack")
                    audit("mode_on")
                else:
                    subprocess.run(["/usr/local/sbin/ddos-mode.sh", "off"], capture_output=True, timeout=40)
                    try: os.remove(MODE)
                    except Exception: pass
                    set_setting("security_level", "medium")
                    audit("mode_off")'''
if old not in s: miss.append('MODE_BLOCK')
else: s=s.replace(old,new,1)
if miss: print('MISSING',miss); raise SystemExit(2)
open(p,'w',encoding='utf-8').write(s)
print('PANEL_PATCHED')
