#!/usr/bin/env python3
# HMAC-SHA256 签名器: 密钥只从文件读取, 不出现在命令行, 也不经过网络
import sys, hmac, hashlib
def main():
    if len(sys.argv) != 3:
        sys.stderr.write("usage: hbsign.py <secret_file> <message>\n")
        sys.exit(2)
    with open(sys.argv[1], "rb") as f:
        secret = f.read().strip()
    print(hmac.new(secret, sys.argv[2].encode(), hashlib.sha256).hexdigest())
main()
