#!/usr/bin/env python3
# SH-10 等价模型：archive_cloud_world 在 `systemctl stop mc` **之前** 执行 ->
#         对正在写入的 world 目录打 tar，快照不一致（region/level.dat 可能半写）；
#         且 tar 失败被 2>/dev/null 吞掉、无 `tar tzf` 校验、无保留策略。
#
# 等价性前提：本机无法运行 mc 服务，用“后台线程持续写文件 + 同时打包”复刻
# “在写盘时对目录打 tar”的时序；tar 行为用 Python tarfile（与 GNU tar 同为
# “边读边写，长度取自文件系统当时的值”）。这是对“非一致快照”的可执行证明，
# 不依赖 bash。
import os
import shutil
import sys
import tarfile
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "..", "src"))
FAILOVER = os.path.join(SRC, "cloud", "usr", "local", "sbin", "failover.sh")


def lines(p):
    with open(p, encoding="utf-8") as f:
        return f.read().splitlines()


def live_tar_test():
    # 工作区内的临时目录（本机沙箱允许写 work/ 下）；用后即删
    tmp = os.path.join(HERE, ".tmp_sh10")
    os.makedirs(tmp, exist_ok=True)
    try:
        world = os.path.join(tmp, "world")
        os.makedirs(world)
        region = os.path.join(world, "r.0.0.mca")
        level = os.path.join(world, "level.dat")
        with open(region, "wb") as f:
            f.write(b"\0" * 4096)
        with open(level, "wb") as f:
            f.write(b"level")
        stop = {"v": False}

        def writer():
            with open(region, "ab") as f:
                while not stop["v"]:
                    f.write(b"CHUNK" * 1024)
                    f.flush()
                    time.sleep(0.0005)

        th = threading.Thread(target=writer)
        th.start()
        time.sleep(0.05)
        arc = os.path.join(tmp, "world.tar.gz")
        with tarfile.open(arc, "w:gz") as tf:      # 等价于 tar czf ... -C dir world
            tf.add(world, arcname="world")
        stop["v"] = True
        th.join()
        final = os.path.getsize(region)
        with tarfile.open(arc) as tf:
            archived = [m.size for m in tf.getmembers()
                        if m.name.endswith("r.0.0.mca")][0]
        return final, archived, arc
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    fo = lines(FAILOVER)
    ok = True
    print("== 0. 源码事实（work/src 行号）==")
    for n in (99, 100, 101, 102, 103):
        print("failover.sh:%d: %s" % (n, fo[n - 1].strip()))
    for n in (153, 237, 238):
        print("failover.sh:%d: %s" % (n, fo[n - 1].strip()))
    print()
    print("[+] 调用顺序：")
    print("    force-home : 第153行 archive_cloud_world 在 systemctl stop mc **之前**")
    print("    auto 切回  : 第237行 archive_cloud_world 在 第238行 systemctl stop mc **之前**")
    print("    => 归档对象是“仍在被 MC 写入”的 world 目录。")
    print()

    text = "\n".join(fo)
    no_verify = "tar tzf" not in text and "tar -tzf" not in text
    no_prune = ("find /data/backups" not in text) and ("rm -f /data/backups" not in text)
    swallow = "tar czf" in text and "2>/dev/null" in text
    print("== 1. 其它缺陷（静态核对）==")
    print("   tar 后是否校验归档完整性(tar tzf): %s" % ("否" if no_verify else "是"))
    print("   是否有保留/清理策略: %s" % ("否（/data/backups 会无限增长）" if no_prune else "是"))
    print("   tar 失败是否被吞: %s" % ("是（`tar ... 2>/dev/null && log`，失败时无日志无告警）"
                                        if swallow else "否"))
    ok = ok and no_verify and no_prune and swallow
    print()

    print("== 2. 可执行证明：一边写一边打包 ==")
    final, archived, _ = live_tar_test()
    print("   写入结束后 region 实际大小 = %d 字节" % final)
    print("   归档里记录的 region 大小 = %d 字节" % archived)
    print("   归档是否小于实际（快照被截断）= %s" % ("是" if archived < final else "否（本次时序未命中）"))
    ok = ok and archived < final
    print()
    print("   说明：MC 的 region 文件在 autosave/区块保存时是“先写新数据再更新头部”，")
    print("   打包时若正好写到一半，恢复出来的世界会出现 chunk 损坏/回档。")
    print("   正确做法：先 `systemctl stop mc`（或 rcon `save-off` + `save-all flush`）再 tar。")
    print()
    print("VERDICT: %s" % ("REPRODUCED" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
