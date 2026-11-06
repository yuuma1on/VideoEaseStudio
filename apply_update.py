"""External update worker; restores prior app if new app fails startup health check."""
import ctypes, os, shutil, subprocess, sys, time, traceback
from pathlib import Path

def wait_for_pid(pid):
    if os.name=='nt':
        SYNCHRONIZE=0x00100000
        handle=ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE,False,pid)
        if handle:
            ctypes.windll.kernel32.WaitForSingleObject(handle,60000)
            ctypes.windll.kernel32.CloseHandle(handle)
        else: time.sleep(2)
    else:
        for _ in range(600):
            try: os.kill(pid,0)
            except ProcessLookupError: break
            time.sleep(.1)

def main():
    install, staged, pid, python=Path(sys.argv[1]),Path(sys.argv[2]),int(sys.argv[3]),sys.argv[4]
    exe_mode=python.lower().endswith('.exe')
    wait_for_pid(pid)
    backup=install.parent/(install.name+'.rollback')
    marker=staged.parent/'healthy.marker'
    log=staged.parent/'update.log'
    try:
        if backup.exists(): shutil.rmtree(backup)
        shutil.copytree(install,backup,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        # Do not remove user project files or settings; update only packaged application files.
        for file in staged.rglob('*'):
            if not file.is_file(): continue
            relative=file.relative_to(staged)
            target=install/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(file,target)
        command=([python,'--update-health',str(marker)] if exe_mode else [python,str(install/'videoease.py'),'--update-health',str(marker)])
        process=subprocess.Popen(command,cwd=str(install))
        for _ in range(300):
            if marker.exists():
                shutil.rmtree(backup,ignore_errors=True)
                return
            if process.poll() is not None: break
            time.sleep(.1)
        try: process.terminate();process.wait(timeout=5)
        except Exception: pass
        raise RuntimeError('更新後の起動確認に失敗しました')
    except Exception:
        with log.open('w',encoding='utf-8') as f: traceback.print_exc(file=f)
        if backup.exists():
            for file in backup.rglob('*'):
                if file.is_file():
                    target=install/file.relative_to(backup)
                    target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(file,target)
            shutil.rmtree(backup,ignore_errors=True)
        command=([python] if exe_mode else [python,str(install/'videoease.py')])
        subprocess.Popen(command,cwd=str(install))
    finally:
        # Keep staged folder and log until next run; removing executing helper is unsafe on Windows.
        pass

if __name__=='__main__': main()
