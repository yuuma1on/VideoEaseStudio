"""VideoEase Studio updater: GitHub release ZIP, SHA-256, safe staged install."""
import hashlib, json, os, shutil, subprocess, sys, tempfile, time, urllib.request, zipfile
from pathlib import Path

VERSION = '3.1.2'
CONFIG = (Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent) / 'update_config.json'
USER_AGENT = 'VideoEaseStudio-Updater/3.0'
MAX_DOWNLOAD = 350 * 1024 * 1024

def version_tuple(v):
    parts = str(v).lstrip('v').split('.')
    if not parts or len(parts)>4 or any(not p.isdigit() for p in parts):
        raise ValueError('不正なバージョン番号です')
    return tuple(map(int,parts)) + (0,)*(4-len(parts))

def repository():
    config=json.loads(CONFIG.read_text(encoding='utf-8'))
    repo=config.get('repository','')
    import re
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo) or repo=='OWNER/REPO':
        raise ValueError('update_config.json の repository に GitHub の OWNER/REPO を設定してください')
    return repo

def fetch(url, max_bytes=2_000_000):
    req=urllib.request.Request(url,headers={'User-Agent':USER_AGENT,'Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(req,timeout=20) as response:
        if response.status!=200: raise RuntimeError('HTTP '+str(response.status))
        data=response.read(max_bytes+1)
        if len(data)>max_bytes: raise ValueError('応答サイズが大きすぎます')
        return data

def check_release():
    repo=repository()
    release=json.loads(fetch(f'https://api.github.com/repos/{repo}/releases/latest'))
    tag=release['tag_name']; version=version_tuple(tag)
    if version<=version_tuple(VERSION): return None
    assets={a['name']:a['browser_download_url'] for a in release.get('assets',[])}
    name=f'VideoEaseStudio-v{tag.lstrip("v")}.zip'
    if name not in assets or name+'.sha256' not in assets:
        raise ValueError('リリースにZIPまたはSHA256ファイルがありません')
    for url in (assets[name],assets[name+'.sha256']):
        if not url.startswith(f'https://github.com/{repo}/releases/download/'):
            raise ValueError('不正なダウンロードURLです')
    return {'tag':tag,'name':name,'url':assets[name],'sha_url':assets[name+'.sha256'],'notes':release.get('body','')[:1000]}

def download(release, progress):
    folder=Path(tempfile.mkdtemp(prefix='ves-update-'))
    try:
        checksum=fetch(release['sha_url'],1024).decode('utf-8').strip().split()[0].lower()
        if len(checksum)!=64 or any(c not in '0123456789abcdef' for c in checksum):
            raise ValueError('SHA256の形式が不正です')
        archive=folder/release['name']; digest=hashlib.sha256()
        req=urllib.request.Request(release['url'],headers={'User-Agent':USER_AGENT})
        with urllib.request.urlopen(req,timeout=30) as resp, archive.open('wb') as out:
            total=int(resp.headers.get('Content-Length','0'))
            count=0
            while True:
                chunk=resp.read(1024*256)
                if not chunk: break
                count+=len(chunk)
                if count>MAX_DOWNLOAD: raise ValueError('更新ファイルが大きすぎます')
                out.write(chunk);digest.update(chunk)
                progress(int(count/total*100) if total else 0)
        if digest.hexdigest()!=checksum: raise ValueError('SHA256検証に失敗しました')
        with zipfile.ZipFile(archive) as z:
            names=z.namelist()
            if len(names)>300: raise ValueError('ファイル数が多すぎます')
            for info in z.infolist():
                path=Path(info.filename)
                if path.is_absolute() or '..' in path.parts or '\\' in info.filename or ':' in info.filename or info.file_size>MAX_DOWNLOAD:
                    raise ValueError('ZIPに危険なパスが含まれています')
                if info.external_attr >> 16 & 0o170000 == 0o120000:
                    raise ValueError('シンボリックリンクは許可されていません')
            z.extractall(folder/'extracted')
        staged=folder/'extracted'/'VideoEaseStudio'
        if getattr(sys, 'frozen', False):
            if not (staged/'VideoEaseStudio.exe').is_file():
                raise ValueError('EXE版の更新ZIPには VideoEaseStudio/VideoEaseStudio.exe が必要です')
        elif not (staged/'videoease.py').is_file() or not (staged/'updater.py').is_file():
            raise ValueError('更新パッケージの構造が正しくありません')
        return folder,staged
    except Exception:
        shutil.rmtree(folder,ignore_errors=True)
        raise

def launch_update(folder, staged):
    """Updater must run outside install folder so files can be replaced on Windows."""
    if getattr(sys, 'frozen', False):
        helper_src=Path(sys.executable).resolve().with_name('VideoEaseUpdater.exe')
        if not helper_src.is_file():
            raise FileNotFoundError('VideoEaseUpdater.exe が見つかりません。EXEと同じ場所に置いてください')
        helper=folder/'VideoEaseUpdater.exe'
        shutil.copy2(helper_src, helper)
        args=[str(helper),str(Path(sys.executable).resolve().parent),str(staged),str(os.getpid()),str(Path(sys.executable).resolve())]
        subprocess.Popen(args,creationflags=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0),close_fds=True)
        return
    helper=folder/'apply_update.py'
    shutil.copyfile(Path(__file__).with_name('apply_update.py'),helper)
    args=[sys.executable,str(helper),str(Path(__file__).resolve().parent),str(staged),str(os.getpid()),sys.executable]
    flags=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0)
    subprocess.Popen(args,creationflags=flags,close_fds=True)
