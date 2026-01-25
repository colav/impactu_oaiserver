#!/usr/bin/env python3
"""Simple proxy that restricts ListSets to a single setSpec and forwards other requests.

Usage: proxy_single_set.py --target ENDPOINT --set SETSPEC --port PORT
"""
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode
import urllib.request
import sys
import xml.etree.ElementTree as ET
from datetime import datetime


class ProxyHandler(BaseHTTPRequestHandler):
    target = None
    setspec = None

    def do_GET(self):
        qs = urlparse(self.path).query
        if 'verb=ListSets' in qs or 'verb=ListSets' in self.path:
            self.handle_listsets()
            return
        # forward other requests
        self.forward_request()

    def forward_request(self):
        # avoid duplicating the /oai path if target already contains it
        if self.target.endswith('/oai') and self.path.startswith('/oai'):
            base = self.target[:-4]
        else:
            base = self.target.rstrip('/')
        target_url = base + self.path
        try:
            req = urllib.request.Request(target_url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read()
                self.send_response(resp.getcode())
                for k, v in resp.getheaders():
                    if k.lower() == 'transfer-encoding':
                        continue
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)
        except Exception as e:
            self.send_error(502, 'Bad Gateway: %s' % e)

    def handle_listsets(self):
        # fetch original ListSets
        if self.target.endswith('/oai') and self.path.startswith('/oai'):
            base = self.target[:-4]
        else:
            base = self.target.rstrip('/')
        target_url = base + self.path
        try:
            req = urllib.request.Request(target_url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read()
                # parse and extract the set matching setspec
                try:
                    root = ET.fromstring(body)
                    ns = {'oai': 'http://www.openarchives.org/OAI/2.0/'}
                    found = None
                    for s in root.findall('.//{http://www.openarchives.org/OAI/2.0/}set'):
                        spec = s.find('{http://www.openarchives.org/OAI/2.0/}setSpec')
                        if spec is not None and spec.text == self.setspec:
                            found = s
                            break
                    # build a minimal ListSets response
                    oai = ET.Element('{http://www.openarchives.org/OAI/2.0/}OAI-PMH')
                    rd = ET.SubElement(oai, '{http://www.openarchives.org/OAI/2.0/}responseDate')
                    rd.text = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
                    reqel = ET.SubElement(oai, '{http://www.openarchives.org/OAI/2.0/}request')
                    reqel.text = self.target
                    lists = ET.SubElement(oai, '{http://www.openarchives.org/OAI/2.0/}ListSets')
                    if found is not None:
                        lists.append(found)
                    out = ET.tostring(oai, encoding='utf-8')
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/xml; charset=utf-8')
                    self.send_header('Content-Length', str(len(out)))
                    self.end_headers()
                    self.wfile.write(out)
                    return
                except Exception:
                    # fallback: return original body
                    self.send_response(resp.getcode())
                    self.send_header('Content-Type', resp.getheader('Content-Type') or 'text/xml')
                    self.end_headers()
                    self.wfile.write(body)
                    return
        except Exception as e:
            self.send_error(502, 'Bad Gateway: %s' % e)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--target', required=True)
    p.add_argument('--set', required=True, dest='setspec')
    p.add_argument('--port', type=int, required=True)
    args = p.parse_args()

    ProxyHandler.target = args.target
    ProxyHandler.setspec = args.setspec

    server = HTTPServer(('127.0.0.1', args.port), ProxyHandler)
    print(f'Proxy for set "{args.setspec}" -> {args.target} listening on 127.0.0.1:{args.port}', file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == '__main__':
    main()
