#!/bin/sh
# 一键把 DIYP 列表里的 127.0.0.1 替换成指定 IP。
# 用法:
#   sh switch_ip.sh                  # 默认替换为 192.168.1.9
#   sh switch_ip.sh 10.0.0.5         # 替换为其它 IP
#   sh switch_ip.sh 127.0.0.1        # 改回本机地址
#   sh switch_ip.sh 192.168.1.9 /path/to/list.txt   # 指定其它文件
set -e

DIR=$(cd "$(dirname "$0")" && pwd)
IP="${1:-192.168.1.9}"
FILE="${2:-$DIR/diyp_live.txt}"

if [ ! -f "$FILE" ]; then
    echo "找不到文件: $FILE"
    exit 1
fi

COUNT=$(grep -o "127\.0\.0\.1" "$FILE" 2>/dev/null | wc -l)
sed -i "s/127\.0\.0\.1/$IP/g" "$FILE"

echo "已把 $COUNT 处 127.0.0.1 替换为 $IP"
echo "文件: $FILE"
