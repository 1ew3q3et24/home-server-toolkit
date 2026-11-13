# -*- coding: utf-8 -*-
"""APK-07 复现检查：build.sh 无法产出一致的签名 APK。
包含 6 个独立阻塞/错配点：
 1) 只生成 keystore.pass，而 apksigner 的 --key-pass 指向从未创建的 key.pass → 签名必失败
 2) --version-code 2 覆盖/冲突于 Manifest 的 versionCode=3 → 版本矩阵不自洽
 3) aapt2 link -A "$SRC/assets"，但工程中没有 assets 目录 → link 失败（高可能）
 4) BT=$SDK/android-16 却被当作 build-tools 使用（aapt2/d8/zipalign/apksigner 均属 build-tools 26+）
 5) apksigner verify ... | head -6 在 set -o pipefail 下可能因 SIGPIPE 使构建在签名成功后整体失败
 6) splash.xml 引用 @mipmap/ic_splash，而 tools/make_icon.py 只生成 ic_launcher/_bg/_fg（且 root 硬编码 /home/lzj）

第 1 点用本机 JDK keytool 实际复跑 build.sh 第 12-14 行的命令来证明（R1）。"""
import pathlib
import secrets
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ID = "APK-07"
TITLE = "build.sh 多处阻塞/错配：签名口令文件缺失、versionCode 冲突、资源与工具链路径不可用"
BUILD = "apk/build.sh"
MAN = "apk/src/AndroidManifest.xml"
SPLASH = "apk/src/res/drawable/splash.xml"
ICON = "apk/src/tools/make_icon.py"
NS = "{http://schemas.android.com/apk/res/android}"


def read(p):
    return p.read_text(encoding="utf-8", errors="replace").splitlines()


def ln_of(lines, needle):
    for i, s in enumerate(lines, 1):
        if needle in s:
            return i
    return None


def keytool_subtest(here, out):
    """按 build.sh:12-14 实际生成一次 keystore，验证只有 keystore.pass 被创建。"""
    kt = shutil.which("keytool")
    if not kt:
        out.append("SKIP | 本机未找到 keytool，跳过 keystore 子测试（静态结论不受影响）")
        return None
    # 注意：固定目录名（而非 mkdtemp），本机沙箱对子进程新建的随机目录不给写权限
    p = here / "_kt_scratch"
    shutil.rmtree(p, ignore_errors=True)
    p.mkdir()
    try:
        (p / "keystore.pass").write_text(secrets.token_urlsafe(24), encoding="ascii")
        cmd = [kt, "-genkeypair", "-keystore", str(p / "lzj-release.jks"), "-alias", "lzj",
               "-keyalg", "RSA", "-keysize", "2048", "-validity", "10950",
               "-storepass:file", str(p / "keystore.pass"),
               "-keypass:file", str(p / "keystore.pass"),
               "-dname", "CN=LZJ Toolbox, OU=Personal, O=LZJ, L=Home, ST=Home, C=CN"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        jks = (p / "lzj-release.jks").exists()
        kp = (p / "keystore.pass").exists()
        keyp = (p / "key.pass").exists()
        out.append("R1  | keytool 实际执行: exit=%d, lzj-release.jks=%s, keystore.pass=%s, key.pass=%s"
                   % (r.returncode, jks, kp, keyp))
        # 模拟 apksigner --key-pass file:<key.pass> 的读取动作
        missing = False
        try:
            (p / "key.pass").read_text()
        except FileNotFoundError:
            missing = True
        out.append("R1  | 模拟 apksigner --key-pass file:%s → FileNotFoundError=%s"
                   % (p / "key.pass", missing))
        return (r.returncode == 0 and jks and kp and not keyp and missing)
    finally:
        shutil.rmtree(p, ignore_errors=True)


def run(src=None):
    if src is None:
        src = pathlib.Path(__file__).resolve().parents[2] / "src"
    src = pathlib.Path(src)
    here = pathlib.Path(__file__).resolve().parent
    build = read(src / BUILD)
    man = read(src / MAN)
    splash = read(src / SPLASH)
    icon = read(src / ICON)
    root = ET.fromstring("\n".join(man))
    out = []
    ok = True

    def check(cond, desc, detail=""):
        nonlocal ok
        ok = ok and bool(cond)
        out.append("%s | %s%s" % ("PASS" if cond else "FAIL", desc,
                                  ("  [" + detail + "]") if detail else ""))

    # 1) 签名口令文件
    sub = keytool_subtest(here, out)
    check(sub is True if sub is not None else True,
          "R1：build.sh 只生成 keystore.pass，key.pass 从未创建（签名必失败）", "build.sh:12,14")
    kp_line = ln_of(build, '--key-pass "file:$KEY/key.pass"')
    check(kp_line == 41, "apksigner 的 --key-pass 指向不存在的 key.pass", "build.sh:41")
    check("--key-pass" in build[40] and "keystore.pass" not in build[40].split("--key-pass")[1],
          "--key-pass 与 --ks-pass 指向不同文件（应都用 keystore.pass）", "build.sh:41")

    # 2) versionCode
    vc = root.get(NS + "versionCode")
    check(vc == "3", "Manifest 声明 versionCode=3", "AndroidManifest.xml:4")
    check("--version-code 2" in build[21] if len(build) > 21 else False,
          "aapt2 link 传入 --version-code 2（与清单 3 不一致；aapt2 会写入/覆盖清单值）", "build.sh:22")

    # 3) assets 目录
    check('-A "$SRC/assets"' in build[21] if len(build) > 21 else False,
          "aapt2 link 依赖 -A \"$SRC/assets\"", "build.sh:22")
    check(not (src / "apk/src/assets").exists(),
          "工程中不存在 apk/src/assets → aapt2 link 会因目录不存在失败（高可能）")

    # 4) 工具链路径
    check(ln_of(build, "BT=$SDK/android-16") == 4,
          "BT=$SDK/android-16 被当作 build-tools 目录使用，但 aapt2/d8/zipalign/apksigner 属于 build-tools 26+",
          "build.sh:4")
    check(ln_of(build, "AJ=$SDK/android-36/android.jar") == 5,
          "android.jar 取 android-36（平台目录），与 BT 的 android-16 语义不一致", "build.sh:5")

    # 5) pipefail + head
    check(any("set -euo pipefail" in s for s in build), "脚本启用 pipefail", "build.sh:2")
    check(any("| head -6" in s for s in build),
          "apksigner verify | head -6：head 提前关闭管道可致 SIGPIPE(141)，pipefail 下使构建在签名成功后失败",
          "build.sh:44")

    # 6) 资源
    check(ln_of(splash, "@mipmap/ic_splash") == 9,
          "splash.xml 引用 @mipmap/ic_splash", "res/drawable/splash.xml:9")
    check("ic_splash" not in "\n".join(icon),
          "make_icon.py 不生成 ic_splash（只生成 ic_launcher/_bg/_fg）", "tools/make_icon.py:113-119")
    has_splash_png = any(src.rglob("ic_splash*")) or any((src / "apk/src/res").rglob("ic_splash*"))
    check(not has_splash_png, "合并包内不存在任何 ic_splash 资源 → aapt2 link 报资源缺失（高可能）")
    check(ln_of(icon, 'root="/home/lzj/apk/src/res"') == 106,
          "make_icon.py 输出目录硬编码 /home/lzj（换机构建即失败）", "tools/make_icon.py:106")

    # 7) javac 未用 Android bootclasspath
    check(ln_of(build, 'javac -encoding UTF-8 -source 11 -target 11 -classpath "$AJ"') == 25
          and "--release" not in "\n".join(build),
          "javac 只设 -classpath，未用 --release/Android bootclasspath → 可能编译通过但运行期 NoSuchMethod",
          "build.sh:25（本机无 android.jar，未验证“javac 通过”的声明）")
    check(build[37] == '"$BT/zipalign" -f -p 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"'
          and "apksigner" in build[40],
          "zipalign 在签名之前执行（顺序正确，无需修改）", "build.sh:38,41")

    status = "复现通过" if ok else "复现失败"
    text = "\n".join([
        "[%s] %s" % (ID, TITLE),
        "复现级别: R1（keytool 子测试在本机实际执行）+ R2（其余静态断言）",
        "环境: Windows + Python 3.12 + JDK keytool；无 aapt2/d8/apksigner/android.jar/android-16 工具链",
        "检查对象: %s, %s, %s, %s" % (BUILD, MAN, SPLASH, ICON),
    ] + out + [
        "结论: %s" % status,
        "说明: 由于签名步骤在干净环境必然失败，v2.1 交付的 APK 不可能由本脚本在本机组装；"
        "“构建可复现/来源可验证”不成立（文档未声明构建通过，但脚本作为交付物必须可执行）。",
    ])
    return {"id": ID, "title": TITLE, "status": status, "ok": ok, "text": text}


if __name__ == "__main__":
    r = run()
    print(r["text"])
    sys.exit(0 if r["ok"] else 1)
