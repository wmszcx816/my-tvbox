#!/usr/bin/env python3
"""DIYP 直播源 M3U8 代理服务。

用法:
    GET /proxy?url=<目标地址>[&ref=<Referer>]

- 请求上游时附带浏览器 User-Agent 与 Referer（默认取目标地址的源 https://host/）。
- 若返回的是 M3U8，自动把其中的分片(.ts)、子播放列表、加密密钥等 URI
  重写为指向本代理的地址，避免播放器因防盗链 / 跨域而卡死。
- 非 M3U8 内容（.ts、密钥等）原样透传。
"""

import gzip
import re
import sys
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8080

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

URI_ATTR_RE = re.compile(r'URI\s*=\s*"([^"]*)"', re.IGNORECASE)
CHUNK_SIZE = 64 * 1024


def default_referer(url):
    parts = urlsplit(url)
    return "%s://%s/" % (parts.scheme, parts.netloc)


def make_proxy_url(target, referer):
    return "/proxy?" + urlencode({"url": target, "ref": referer})


def open_upstream(target, referer):
    request = Request(
        target,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": referer,
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "close",
        },
    )
    return urlopen(request, timeout=20)


def decompress(data, encoding):
    if encoding == "gzip":
        return gzip.decompress(data)
    if encoding == "deflate":
        try:
            return zlib.decompress(data)
        except zlib.error:
            return zlib.decompress(data, -zlib.MAX_WBITS)
    return data


def rewrite_playlist(text, base_url, referer):
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            lines.append(line)
        elif stripped.startswith("#"):
            if 'URI="' in stripped:
                def replace(match):
                    url = urljoin(base_url, match.group(1))
                    return 'URI="%s"' % make_proxy_url(url, referer)

                line = URI_ATTR_RE.sub(replace, line)
            lines.append(line)
        else:
            lines.append(make_proxy_url(urljoin(base_url, stripped), referer))
    return "\n".join(lines)


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        self._proxy(write_body=True)

    def do_HEAD(self):
        self._proxy(write_body=False)

    def _proxy(self, write_body):
        parts = urlsplit(self.path)
        if parts.path != "/proxy":
            self.send_error(404, "Not Found")
            return

        query = parse_qs(parts.query)
        target = (query.get("url") or [""])[0]
        if not target:
            self.send_error(400, "Missing 'url' parameter")
            return
        referer = (query.get("ref") or [""])[0] or default_referer(target)

        try:
            upstream = open_upstream(target, referer)
        except HTTPError as exc:
            self.send_error(502, "Upstream HTTP %s" % exc.code)
            return
        except (URLError, OSError) as exc:
            self.send_error(502, "Upstream error: %s" % exc)
            return

        with upstream:
            content_type = upstream.headers.get("Content-Type", "")
            encoding = upstream.headers.get("Content-Encoding", "").lower()
            head = upstream.read(1024)
            is_playlist = head.lstrip().startswith(b"#EXTM3U") or "mpegurl" in content_type.lower()

            if is_playlist:
                raw = decompress(head + upstream.read(), encoding)
                body = rewrite_playlist(
                    raw.decode("utf-8", "replace"), target, referer
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                if write_body:
                    self.wfile.write(body)
                return

            length = upstream.headers.get("Content-Length")
            self.send_response(200)
            self.send_header("Content-Type", content_type or "application/octet-stream")
            self.send_header("Access-Control-Allow-Origin", "*")
            if length is not None:
                self.send_header("Content-Length", length)
            else:
                self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            if not write_body:
                return
            if head:
                self._write_chunked(head) if length is None else self.wfile.write(head)
            while True:
                chunk = upstream.read(CHUNK_SIZE)
                if not chunk:
                    break
                self._write_chunked(chunk) if length is None else self.wfile.write(chunk)
            if length is None:
                self.wfile.write(b"0\r\n\r\n")

    def _write_chunked(self, data):
        self.wfile.write(b"%x\r\n%s\r\n" % (len(data), data))

    def log_message(self, fmt, *args):
        sys.stderr.write("[proxy] " + fmt % args + "\n")


def main():
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), ProxyHandler)
    server.daemon_threads = True
    sys.stderr.write(
        "HLS proxy listening on http://%s:%d/proxy?url=<M3U8>\n"
        % (LISTEN_HOST, LISTEN_PORT)
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
