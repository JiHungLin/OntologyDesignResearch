"""下載公開來源的原文並轉成純文字，給網頁裡的 AI 用（claude -p 不能核准權限，不能自己寫 python 或 for 迴圈處理）。

用法（在設計 repo 根目錄執行）：
    python3 <本檔> <網址> [檔名]

原文存到 .domain-web/tmp/<檔名>（已被 .gitignore 排除），HTML 轉成文字（連結寫成「文字 <網址>」）、
PDF 用 pdftotext 轉，存成同名的 .txt，最後印出兩個路徑。文字照原文，不摘要；摘錄進 inputs/research/ 由 AI 照規範做。
"""
import html.parser
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'
BLOCK = {'p', 'div', 'br', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table', 'section', 'article', 'dd', 'dt', 'pre'}


class Text(html.parser.HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.out, self.skip, self.href = base, [], 0, None

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self.skip += 1
        elif tag in BLOCK:
            self.out.append('\n')
        elif tag in ('td', 'th'):
            self.out.append(' | ')
        elif tag == 'a':
            h = dict(attrs).get('href')
            self.href = urllib.parse.urljoin(self.base, h) if h and not h.startswith(('javascript:', '#')) else None

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'):
            self.skip = max(0, self.skip - 1)
        elif tag == 'a' and self.href:
            self.out.append(f' <{self.href}>')
            self.href = None
        elif tag in BLOCK:
            self.out.append('\n')

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)

    def text(self):
        t = re.sub(r'[ \t\r\f\v]+', ' ', ''.join(self.out))
        return re.sub(r'\n\s*\n+', '\n\n', '\n'.join(l.strip() for l in t.split('\n'))).strip() + '\n'


def main():
    if len(sys.argv) < 2 or not sys.argv[1].startswith(('http://', 'https://')):
        sys.exit('用法：python3 fetch_text.py <http(s) 網址> [檔名]')
    url = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 else re.sub(r'[^\w.-]+', '_', urllib.parse.urlparse(url).netloc + urllib.parse.urlparse(url).path).strip('_') or 'page'
    name = os.path.basename(name)
    d = os.path.join('.domain-web', 'tmp')
    os.makedirs(d, exist_ok=True)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=40) as r:
            data, ctype, final = r.read(), r.headers.get('Content-Type', ''), r.geturl()
    except Exception as e:
        sys.exit(f'下載失敗：{url}\n{type(e).__name__}: {e}')
    is_pdf = 'pdf' in ctype or data[:4] == b'%PDF'
    if is_pdf and not name.endswith('.pdf'):
        name += '.pdf'
    elif not is_pdf and not re.search(r'\.\w{2,5}$', name):
        name += '.html'
    raw = os.path.join(d, name)
    with open(raw, 'wb') as f:
        f.write(data)
    txt = re.sub(r'\.\w{2,5}$', '', raw) + '.txt'
    if is_pdf:
        if not shutil.which('pdftotext'):
            sys.exit(f'已下載 {raw}，但這台沒有 pdftotext，不能轉文字；請使用者打開這個 PDF')
        subprocess.run(['pdftotext', '-layout', raw, txt], check=True)
    else:
        m = re.search(rb'charset=["\']?([\w-]+)', data[:4000]) or re.search(r'charset=([\w-]+)', ctype)
        enc = (m.group(1).decode() if isinstance(m.group(1), bytes) else m.group(1)) if m else 'utf-8'
        p = Text(final)
        p.feed(data.decode(enc, errors='replace'))
        with open(txt, 'w', encoding='utf-8') as f:
            f.write(f'來源：{final}\n\n' + p.text())
    print(f'原文：{raw}\n文字：{txt}（{os.path.getsize(txt)} bytes）')


if __name__ == '__main__':
    main()
