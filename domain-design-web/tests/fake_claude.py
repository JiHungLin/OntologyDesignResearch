#!/usr/bin/env python3
"""假的 claude：照 stream-json 格式印出幾個事件，測試背景執行與事件紀錄用。"""
import json
import sys

msg = sys.argv[sys.argv.index('-p') + 1]
for ev in ({'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'name': 'Read', 'input': {'file_path': 'slices/PLAN.md'}}]}},
           {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': '收到：' + msg[:20]}]}},
           {'type': 'result', 'is_error': False, 'result': '問題：要先做哪條？\nA（建議）：demo → 先建立共用核心\nB：return-order → 先做退貨',
            'permission_denials': []}):
    print(json.dumps(ev, ensure_ascii=False), flush=True)
