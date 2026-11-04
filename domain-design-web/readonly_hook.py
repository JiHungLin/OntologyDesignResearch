"""網頁裡的 AI（claude -p）用的 PreToolUse hook：只讀的串接指令直接放行。

claude -p 不能核准權限，允許清單又只能一個指令一個指令比對，AI 常把讀檔串成
「cd …; for f in …; do cat …; done」「grep … | head」被擋，再改用別的方法（白跑一趟，也讓人以為出錯）。
這裡把指令拆開，每一段都是只讀的指令、讀的路徑都在設計 repo（或網頁資料夾）裡，就回答 allow；
git 只放行讀的子指令（status、diff、log、show…）。
tools/run_evidence.py 雖然在 tools/ 底下，但會執行它包住的實作指令，回答 ask，一律交給人核准（approve_mcp.py）。
自己寫的 python（python3 - <<EOF、python3 -c）一定被擋，這裡直接拒絕並附上改用什麼——
挑錯、核對的子代理拿不到網頁附加的系統提示，只能從被擋的理由學到。
其他一律不表示意見，照原本的權限規則（允許清單、被擋就擋）。
"""
import json
import os
import re
import shlex
import sys

READ_ONLY = {'cd', 'ls', 'cat', 'head', 'tail', 'wc', 'grep', 'egrep', 'fgrep', 'rg', 'sed', 'awk', 'echo', 'printf',
             'sort', 'uniq', 'cut', 'tr', 'diff', 'find', 'nl', 'column', 'basename', 'dirname', 'pwd', 'true', 'test',
             '[', 'stat', 'file', 'realpath', 'readlink', 'tree', 'comm', 'paste', 'fold', 'expand', 'date',
             'rev', 'tac', 'md5sum', 'sha256sum'}
LOOP_WORDS = {'for', 'in', 'do', 'done', 'while', 'if', 'then', 'else', 'elif', 'fi', '!', '{', '}'}
SEPARATORS = {';', '&&', '||', '|', '\n', '(', ')', '&'}
GIT_READ = {'status', 'diff', 'log', 'show', 'rev-parse', 'ls-files', 'blame', 'grep', 'shortlog', 'cat-file'}
GIT_BAD = re.compile(r'^(-c|-C|--output.*|--ext-diff|-O.*|--open-files-in-pager.*|--exec-path.*)$')   # 改設定、寫檔、開外部程式
INLINE_PY = re.compile(r'\bpython3?(\s+-[A-Za-z]+)*\s+(-c\b|-(\s|$))|\bpython3?\b[^\n;|&]*<<')
PY_REASON = ('網頁裡不能跑自己寫的 python（python3 - <<EOF、python3 -c），一定會被擋。改用：讀某幾行用 Read 的 offset／limit；'
             '找字、找編號用 Grep；表格欄數、格式、引用、編號，以及 api.yaml 讀不讀得進來、$ref 指不指得到，都用 python3 -I tools/lint.py <切片>（舊版工具包沒有 API 檢查時，用 Read 看 api.yaml，有疑問寫進挑錯或審查頁）；看改了什麼用 git diff --stat、git diff <檔案>。'
             '要驗算取位、比例分攤這類數字時，在檔案裡寫出算式與步驟，標 [未執行] 交給人核對（黃金案例的預期結果本來就由人算）。'
             '能跑的 python 只有 python3 tools/*。')
EVIDENCE = re.compile(r'\brun_evidence\.py\b')
REDIRECT_OK = re.compile(r'\d?>&\d|&>\s*/dev/null')   # 2>&1、&>/dev/null：只改輸出去向，不寫檔
SED_WRITE = re.compile(r'(^|[;\d$/,\s])\s*[weW](\s|$)')   # sed 的 w（寫檔）、e（執行）指令，前面可以有位址


def _inside(p, roots):
    return any(p == r or p.startswith(r + os.sep) for r in roots)


def _where(tok, here):
    return os.path.realpath(os.path.join(here, os.path.expanduser(tok)))


def _ok_path(tok, roots, here):
    """路徑（相對的照目前資料夾算，cd 之後的 ../../ 也算得出來）要在設計 repo 或網頁資料夾裡。"""
    if tok == '/dev/null':
        return True
    if '$' in tok:   # 沒設定過的變數：算不出來，只擋 ..
        return '..' not in tok.split('/')
    return _inside(_where(tok, here), roots)


def read_only(cmd, roots):
    if re.search(r'\$\(|`|<<|>\s*[^&/]|>>|>\s*/(?!dev/null)', cmd):   # 指令替換、heredoc、寫檔（2>/dev/null 可以）
        return False
    cmd = REDIRECT_OK.sub(' ', cmd)
    cmd = cmd.replace('<(', ' ( ')   # diff <(sed …) <(sed …)：括號裡的指令照樣逐一檢查
    cmd = re.sub(r"'[|;&()]'|\"[|;&()]\"", 'SEP', cmd)   # tr '|' '\n' 的 '|' 是參數，不是管線（shlex 拆完分不出有沒有引號）
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=';&|()')
        lex.whitespace_split = True
        lex.whitespace = ' \t\r'
        toks = list(lex)
    except ValueError:
        return False
    head = True
    cur, pattern_left = None, False
    here, env = roots[0], {}   # 目前資料夾（跟著 cd 走）、設定過的變數（D=…）
    for t in toks:
        t = re.sub(r'\$\{?([A-Za-z_]\w*)\}?', lambda m: env.get(m.group(1), m.group(0)), t)
        if t in SEPARATORS or t == '\n':
            if cur == 'cd':   # 只打 cd：回到家目錄
                here = os.path.expanduser('~')
            head, cur = True, None
            continue
        if re.fullmatch(r'\d?>/dev/null', t):   # 2>/dev/null（例：done 2>/dev/null | head）
            continue
        if head:
            if t == 'for':   # for 變數 in 清單; do …：清單只檢查路徑，do 之後才是指令
                cur, head = 'for', False
                continue
            if t in LOOP_WORDS:
                continue
            if re.fullmatch(r'[A-Za-z_]\w*=.*', t):   # 變數設定（D=/repo）：之後的 $D 換成它再檢查路徑
                k, v = t.split('=', 1)
                env[k] = v
                continue
            if t == 'git':
                cur, head = 'git', False
                continue
            if t in ('python3', 'python'):   # 只放行 python3 [-I] tools/<工具>.py
                cur, head = 'py', False
                continue
            if t not in READ_ONLY:
                return False
            cur, head = t, False
            pattern_left = t in ('grep', 'egrep', 'fgrep', 'rg', 'sed', 'awk')   # 第一個非選項參數是樣式或程式，不是路徑
            continue
        if t in ('do', 'then', 'else'):
            head, cur = True, None
            continue
        if t in LOOP_WORDS:
            continue
        if cur == 'py':   # 設計 repo 的 tools/*.py（相對或絕對路徑都可以）；允許清單本來就放行 python3 tools/*
            if t in ('-I', '-B', '-u'):
                continue
            p = _where(t, here)
            if not (p.endswith('.py') and p.startswith(os.path.join(roots[0], 'tools') + os.sep)):
                return False
            cur = 'py-args'
            continue
        if cur == 'cd':
            if t.startswith('-'):
                continue
            if not _ok_path(t, roots, here):
                return False
            here, cur = _where(t, here), 'cd-done'
            continue
        if cur == 'git':   # 第一個參數是子指令
            if GIT_BAD.match(t) or t not in GIT_READ:
                return False
            cur = 'git-read'
            continue
        if cur == 'git-read' and GIT_BAD.match(t):
            return False
        if cur == 'sed' and (t.startswith('-i') or t == '--in-place' or SED_WRITE.search(t)):
            return False
        if cur == 'awk' and re.search(r'system|getline|print\s*>|printf\s*>|\|', t):
            return False
        if cur == 'find' and t in ('-exec', '-execdir', '-delete', '-ok', '-fprint', '-fprintf', '-fls'):
            return False
        if pattern_left and not t.startswith('-'):
            pattern_left = False
            if cur == 'sed' and SED_WRITE.search(t):
                return False
            continue
        if not t.startswith('-') and not _ok_path(t, roots, here):
            return False
    return True


def main():
    data = json.load(sys.stdin)
    if data.get('tool_name') != 'Bash':
        return
    cmd = (data.get('tool_input') or {}).get('command', '')
    if INLINE_PY.search(cmd):
        json.dump({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                          'permissionDecisionReason': PY_REASON}}, sys.stdout)
        return
    if EVIDENCE.search(cmd):   # 在 tools/ 底下，但會執行它包住的實作指令：一律交給人核准（docs/01 ⑥）
        json.dump({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'ask',
                                          'permissionDecisionReason': 'tools/run_evidence.py 會執行實作指令，要人逐條核准'}}, sys.stdout)
        return
    roots = [os.path.realpath(data.get('cwd') or os.getcwd()), os.path.dirname(os.path.realpath(__file__))]
    if read_only(cmd, roots):
        json.dump({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'allow',
                                          'permissionDecisionReason': '只讀的指令（流程網頁 readonly_hook）'}}, sys.stdout)


if __name__ == '__main__':
    main()
