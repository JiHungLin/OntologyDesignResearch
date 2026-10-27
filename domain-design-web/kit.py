"""找到要操作的切片 repo，以及它的工具包程式（tools/md2build.py）。
切片 repo 是工具包攤平在根目錄的 repo（例：HR-Domain-Design）；用 --repo 或環境變數 DOMAIN_REPO 指定。"""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FALLBACK_TOOLS = os.path.join(HERE, '..', 'domain-design-kit', 'tools')

_repo = None
_mb = None


def set_repo(path):
    global _repo, _mb
    _repo, _mb = os.path.realpath(path), None


def repo():
    if _repo is None:
        set_repo(os.environ.get('DOMAIN_REPO', os.getcwd()))
    return _repo


def md2build():
    """載入切片 repo 的 tools/md2build.py；切片 repo 沒有時，用本 repo 的 domain-design-kit/tools。"""
    global _mb
    if _mb is None:
        for d in (os.path.join(repo(), 'tools'), FALLBACK_TOOLS):
            p = os.path.join(d, 'md2build.py')
            if os.path.exists(p):
                spec = importlib.util.spec_from_file_location('md2build', p)
                _mb = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(_mb)
                break
        else:
            raise RuntimeError('找不到 tools/md2build.py')
    return _mb


def resolve(rel, base=None):
    """把相對路徑轉成切片 repo 裡的絕對路徑；不在 repo 裡的回傳 None。
    審查頁中的「在哪裡」常寫成相對於切片資料夾（02_entities.md:150），所以先試 base，再試 repo 根目錄。"""
    root = repo()
    for b in ([base] if base else []) + [root]:
        p = os.path.realpath(os.path.join(b, rel))
        if (p == root or p.startswith(root + os.sep)) and os.path.isfile(p):
            return p
    return None


def rel(path):
    return os.path.relpath(path, repo())


def slices():
    d = os.path.join(repo(), 'slices')
    if not os.path.isdir(d):
        return []
    return sorted(n for n in os.listdir(d) if os.path.isdir(os.path.join(d, n)) and not n.startswith('.'))
