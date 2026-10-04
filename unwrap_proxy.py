#!/usr/bin/env python3
"""把 DIYP 列表里被本地代理包裹的链接还原为原始直链。

默认读取 diyp_live_lan.txt，输出 diyp_live_direct.txt（不套任何代理）。
用法: python3 unwrap_proxy.py [输入文件] [输出文件]
"""

import re
import sys
from urllib.parse import unquote

# 匹配 http(s)://<host>:8080/proxy?url=<编码后的原始链接>[&ref=...]
PROXY_RE = re.compile(
    r'https?://[^/\s"#]+:8080/proxy\?url=([^&\s#]+)(?:&ref=[^&\s#]+)?'
)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "diyp_live_lan.txt"
    dst = sys.argv[2] if len(sys.argv) > 2 else "diyp_live_direct.txt"

    count = 0

    def replace(match):
        nonlocal count
        count += 1
        return unquote(match.group(1))

    with open(src, encoding="utf-8") as fin:
        lines = [PROXY_RE.sub(replace, line) for line in fin]

    with open(dst, "w", encoding="utf-8") as fout:
        fout.writelines(lines)

    print("输入:", src)
    print("输出:", dst)
    print("还原链接数:", count)


if __name__ == "__main__":
    main()
