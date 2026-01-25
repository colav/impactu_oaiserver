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
import logging

logging.basicConfig(level=logging.INFO)


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
        proxy_url = f'http://127.0.0.1:{self.server.server_port}/oai'
        try:
            # force Host and X-Forwarded-Host to the proxy address so the backend
            # constructs base URLs using the proxy endpoint (validator may send the
            # original host in the Host header when calling the proxy)
            incoming_host = f'127.0.0.1:{self.server.server_port}'
            headers = {'Host': incoming_host, 'X-Forwarded-Host': incoming_host}
            logging.info(f"proxy forward: target_url={target_url} headers={headers}")
            req = urllib.request.Request(target_url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read()
                # try to parse XML and rewrite the <request> element to the proxy URL
                try:
                    root = ET.fromstring(body)
                    # rewrite request and baseURL to point to the proxy
                    req_el = root.find('.//{http://www.openarchives.org/OAI/2.0/}request')
                    if req_el is None:
                        req_el = root.find('.//request')
                    if req_el is not None:
                        logging.info(f"found <request> before rewrite: {req_el.text}")
                        req_el.text = proxy_url
                        logging.info(f"rewrote <request> to: {proxy_url}")
                    base_el = root.find('.//{http://www.openarchives.org/OAI/2.0/}baseURL')
                    if base_el is None:
                        base_el = root.find('.//baseURL')
                    if base_el is not None:
                        logging.info(f"found <baseURL> before rewrite: {base_el.text}")
                        base_el.text = proxy_url
                        logging.info(f"rewrote <baseURL> to: {proxy_url}")
                    # also replace any literal occurrences of the backend base URL string
                    try:
                        body_text = body.decode('utf-8')
                        if 'http://localhost:8000/oai' in body_text:
                            logging.info('literal backend base URL found in body; replacing')
                        body_text = body_text.replace('http://localhost:8000/oai', proxy_url)
                        body = body_text.encode('utf-8')
                    except Exception:
                        body = ET.tostring(root, encoding='utf-8')
                except Exception:
                    # not XML or parse failure -- leave body unchanged
                    pass
                except Exception:
                    # not XML or parse failure -- leave body unchanged
                    pass

                self.send_response(resp.getcode())
                # copy headers, but adjust content-length
                for k, v in resp.getheaders():
                    if k.lower() in ('transfer-encoding', 'content-length'):
                        continue
                    self.send_header(k, v)
                self.send_header('Content-Length', str(len(body)))
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
            incoming_host = self.headers.get('Host') or f'127.0.0.1:{self.server.server_port}'
            headers = {'Host': incoming_host, 'X-Forwarded-Host': incoming_host}
            req = urllib.request.Request(target_url, headers=headers)
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
                    proxy_url = f'http://127.0.0.1:{self.server.server_port}/oai'
                    oai = ET.Element('{http://www.openarchives.org/OAI/2.0/}OAI-PMH')
                    rd = ET.SubElement(oai, '{http://www.openarchives.org/OAI/2.0/}responseDate')
                    rd.text = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
                    reqel = ET.SubElement(oai, '{http://www.openarchives.org/OAI/2.0/}request')
                    reqel.text = proxy_url
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
