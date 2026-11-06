import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import subprocess, shutil, json, os, threading, queue, tempfile, copy, sys
import updater
from pathlib import Path

APP='VideoEase Studio'
VERSION=updater.VERSION
FFMPEG=shutil.which('ffmpeg') or 'ffmpeg'
FFPROBE=shutil.which('ffprobe') or 'ffprobe'
FFPLAY=shutil.which('ffplay')

def probe(path):
    try:
        p=subprocess.run([FFPROBE,'-v','error','-show_entries','format=duration:stream=codec_type','-of','json',path],capture_output=True,text=True,check=True)
        j=json.loads(p.stdout); return float(j['format'].get('duration',0)),any(s.get('codec_type')=='audio' for s in j.get('streams',[]))
    except Exception as e: raise RuntimeError(f'動画情報を読み取れません: {path}\n{e}')

class Studio:
    def __init__(self,root):
        self.root=root;root.title(APP+'  |  Windows動画編集');root.geometry('1180x760');root.minsize(850,600)
        self.clips=[];self.project=None;self.busy=False;self.events=queue.Queue();self.mode=tk.StringVar(value='簡単');self.undo_stack=[];self.redo_stack=[];self.drag_from=None
        self.res=tk.StringVar(value='1920x1080');self.fps=tk.StringVar(value='30');self.volume=tk.DoubleVar(value=100)
        self.status=tk.StringVar(value='動画を追加して編集を始めましょう');self.progress=tk.DoubleVar(value=0)
        self.build();root.bind_all("<Control-Shift-U>",lambda e:self.check_updates());root.after(150,self.poll);root.after(30000,self.autosave);root.after(1800,self.check_updates_silent)
        root.bind('<Control-z>',lambda e:self.undo());root.bind('<Control-y>',lambda e:self.redo());root.bind('<Control-s>',lambda e:self.save_project());root.bind('<Control-o>',lambda e:self.open_project());root.bind('<Control-n>',lambda e:self.new());root.bind('<Delete>',lambda e:self.delete())
        root.protocol('WM_DELETE_WINDOW',self.close)
    def build(self):
        self.root.configure(bg='#101722'); style=ttk.Style();style.theme_use('clam')
        style.configure('TFrame',background='#101722');style.configure('TLabel',background='#101722',foreground='#dce6f5',font=('Segoe UI',10))
        style.configure('TButton',font=('Segoe UI',10),padding=8)
        style.configure('TCombobox',padding=5)
        style.configure('Treeview',background='#1c293b',fieldbackground='#1c293b',foreground='white',rowheight=32,font=('Segoe UI',10))
        style.map('Treeview',background=[('selected','#315f9c')])
        header=ttk.Frame(self.root);header.pack(fill='x',padx=18,pady=14)
        ttk.Label(header,text=f'▶  VideoEase Studio v{VERSION}',font=('Segoe UI',20,'bold')).pack(side='left')
        ttk.Label(header,text='編集モード:').pack(side='left',padx=(20,5))
        mode_box=ttk.Combobox(header,textvariable=self.mode,values=['簡単','プロ'],width=7,state='readonly');mode_box.pack(side='left');mode_box.bind('<<ComboboxSelected>>',lambda e:self.update_mode())
        for text,cmd in [('更新確認',self.check_updates),('新規',self.new),('開く',self.open_project),('保存',self.save_project),('動画を追加 ＋',self.add)]:
            ttk.Button(header,text=text,command=cmd).pack(side='right',padx=4)
        bar=ttk.Frame(self.root);bar.pack(fill='x',padx=18,pady=(0,12));self.bar=bar
        for text,cmd in [('▶ プレビュー',self.preview),('✂ 選択クリップを分割',self.split),('時間を調整',self.trim),('↑ 上へ',lambda:self.move(-1)),('↓ 下へ',lambda:self.move(1)),('削除',self.delete)]:
            ttk.Button(bar,text=text,command=cmd).pack(side='left',padx=3)
        self.probar=ttk.Frame(self.root)
        for text,cmd in [('↶ 元に戻す',self.undo),('↷ やり直し',self.redo),('速度変更',self.change_speed),('フェード設定',self.change_fades),('クリップ複製',self.duplicate)]:ttk.Button(self.probar,text=text,command=cmd).pack(side='left',padx=4)
        body=ttk.Frame(self.root);self.body=body;body.pack(fill='both',expand=True,padx=18)
        left=ttk.Frame(body);left.pack(side='left',fill='both',expand=True)
        ttk.Label(left,text='タイムライン（上から順番に再生）',font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(0,8))
        self.tree=ttk.Treeview(left,columns=('name','start','end','duration'),show='headings',selectmode='browse')
        for key,title,width in [('name','ファイル名',300),('start','開始 (秒)',90),('end','終了 (秒)',90),('duration','使用時間',90)]:
            self.tree.heading(key,text=title);self.tree.column(key,width=width,anchor='w' if key=='name' else 'center')
        self.tree.pack(fill='both',expand=True);self.tree.bind('<Double-1>',lambda e:self.trim());self.tree.bind('<ButtonPress-1>',self.drag_start);self.tree.bind('<ButtonRelease-1>',self.drag_end)
        right=ttk.Frame(body,width=285);right.pack(side='right',fill='y',padx=(16,0));right.pack_propagate(False)
        ttk.Label(right,text='書き出し設定',font=('Segoe UI',13,'bold')).pack(anchor='w',pady=(0,12))
        ttk.Label(right,text='解像度').pack(anchor='w')
        ttk.Combobox(right,textvariable=self.res,values=['1280x720','1920x1080','2560x1440','3840x2160'],state='readonly').pack(fill='x',pady=(3,12))
        ttk.Label(right,text='フレームレート').pack(anchor='w')
        ttk.Combobox(right,textvariable=self.fps,values=['24','30','60'],state='readonly').pack(fill='x',pady=(3,12))
        ttk.Label(right,text='音量（%）').pack(anchor='w')
        ttk.Scale(right,from_=0,to=200,variable=self.volume).pack(fill='x',pady=(3,12))
        ttk.Label(right,text='クリップは指定範囲だけを使用。\n画面比率を維持して黒帯で調整。\n音声なしの動画も混在できます。',wraplength=260).pack(anchor='w',pady=(6,18))
        ttk.Button(right,text='MP4を書き出す',command=self.export).pack(fill='x',ipady=12)
        ttk.Label(right,text='対応: MP4 / MOV / MKV / WEBMなど\n保存形式: H.264 + AAC',wraplength=260).pack(anchor='w',pady=14)
        bottom=ttk.Frame(self.root);bottom.pack(fill='x',padx=18,pady=15)
        ttk.Progressbar(bottom,variable=self.progress,maximum=100).pack(fill='x',pady=(0,7))
        ttk.Label(bottom,textvariable=self.status).pack(anchor='w');self.update_mode()
    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i,c in enumerate(self.clips):self.tree.insert('','end',iid=str(i),values=(Path(c['path']).name,f"{c['start']:.2f}",f"{c['end']:.2f}",f"{(c['end']-c['start'])/c.get('speed',1):.2f}"))
        self.status.set(f'{len(self.clips)}クリップ | 合計 {sum((c["end"]-c["start"])/c.get('speed',1) for c in self.clips):.1f} 秒')
    def selected(self):
        s=self.tree.selection();return int(s[0]) if s else None
    def add(self):
        paths=filedialog.askopenfilenames(title='動画を追加',filetypes=[('動画','*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.ts'),('すべて','*.*')])
        for path in paths:
            try:
                duration,audio=probe(path)
                if duration<=0:raise ValueError('長さが0秒です')
                self.snapshot();self.clips.append(dict(path=path,start=0.,end=duration,audio=audio,speed=1.,fade_in=0.,fade_out=0.))
            except Exception as e:messagebox.showerror('読み込みエラー',str(e))
        self.refresh()
    def trim(self):
        i=self.selected()
        if i is None:return messagebox.showinfo('選択','クリップを選択してください')
        c=self.clips[i];duration,_=probe(c['path'])
        a=simpledialog.askfloat('開始位置','開始秒数',initialvalue=c['start'],minvalue=0,maxvalue=duration,parent=self.root)
        if a is None:return
        b=simpledialog.askfloat('終了位置','終了秒数',initialvalue=c['end'],minvalue=0,maxvalue=duration,parent=self.root)
        if b is None:return
        if b-a<0.1:return messagebox.showerror('範囲エラー','終了は開始より0.1秒以上後にしてください')
        self.snapshot();c.update(start=a,end=b);self.refresh();self.tree.selection_set(str(i))
    def split(self):
        i=self.selected()
        if i is None:return messagebox.showinfo('選択','クリップを選択してください')
        c=self.clips[i];at=simpledialog.askfloat('分割','元動画の何秒地点で分割しますか？',initialvalue=(c['start']+c['end'])/2,parent=self.root)
        if at is None:return
        if not c['start']+.1<at<c['end']-.1:return messagebox.showerror('範囲エラー','クリップの内側を指定してください')
        self.snapshot();old=c['end'];c['end']=at;self.clips.insert(i+1,dict(c,start=at,end=old));self.refresh()
    def move(self,delta):
        i=self.selected()
        if i is None or not 0<=i+delta<len(self.clips):return
        self.snapshot();self.clips[i],self.clips[i+delta]=self.clips[i+delta],self.clips[i];self.refresh();self.tree.selection_set(str(i+delta))
    def delete(self):
        i=self.selected()
        if i is not None:self.snapshot();self.clips.pop(i);self.refresh()
    def preview(self):
        i=self.selected()
        if i is None:return messagebox.showinfo('選択','プレビューするクリップを選択してください')
        c=self.clips[i]
        if FFPLAY:subprocess.Popen([FFPLAY,'-autoexit','-ss',str(c['start']),'-t',str(c['end']-c['start']),c['path']],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        else:os.startfile(c['path']) if os.name=='nt' else messagebox.showinfo('FFplay','FFmpegに付属するffplayをインストールしてください')
    def new(self):
        if self.clips and not messagebox.askyesno('新規','現在の編集内容を破棄しますか？'):return
        self.snapshot();self.clips=[];self.project=None;self.refresh()
    def save_project(self):
        path=self.project or filedialog.asksaveasfilename(defaultextension='.ves.json',filetypes=[('VideoEaseプロジェクト','*.ves.json')])
        if not path:return
        with open(path,'w',encoding='utf-8') as f:json.dump(dict(clips=self.clips,res=self.res.get(),fps=self.fps.get(),volume=self.volume.get(),mode=self.mode.get()),f,ensure_ascii=False,indent=2)
        self.project=path;self.status.set('プロジェクトを保存しました: '+path)
    def open_project(self):
        path=filedialog.askopenfilename(filetypes=[('VideoEaseプロジェクト','*.ves.json'),('JSON','*.json')])
        if not path:return
        try:
            with open(path,encoding='utf-8') as f:j=json.load(f)
            missing=[c['path'] for c in j['clips'] if not os.path.isfile(c['path'])]
            if missing:raise FileNotFoundError('元動画が見つかりません:\n'+'\n'.join(missing[:5]))
            self.snapshot();self.clips=j['clips'];self.mode.set(j.get('mode','簡単'));self.update_mode();self.res.set(j.get('res','1920x1080'));self.fps.set(j.get('fps','30'));self.volume.set(j.get('volume',100));self.project=path;self.refresh()
        except Exception as e:messagebox.showerror('読み込みエラー',str(e))
    def export(self):
        if self.busy:return
        if not self.clips:return messagebox.showinfo('クリップなし','動画を追加してください')
        if not shutil.which(FFMPEG):return messagebox.showerror('FFmpegが必要','FFmpegをインストールし、PATHに追加してください')
        output=filedialog.asksaveasfilename(defaultextension='.mp4',filetypes=[('MP4動画','*.mp4')])
        if not output:return
        self.busy=True;self.progress.set(0);self.status.set('書き出しを開始しています…')
        clips=[dict(c) for c in self.clips];w,h=map(int,self.res.get().split('x'));fps=int(self.fps.get());vol=self.volume.get()/100
        threading.Thread(target=self.render,args=(clips,w,h,fps,vol,output),daemon=True).start()
    def render(self,clips,w,h,fps,vol,output):
        try:
            with tempfile.TemporaryDirectory(prefix='videoease_') as tmp:
                segments=[];total=len(clips)
                for i,c in enumerate(clips):
                    seg=os.path.join(tmp,f'{i:04}.mp4');dur=c['end']-c['start'];speed=float(c.get('speed',1.))
                    cmd=[FFMPEG,'-y','-hide_banner','-loglevel','error','-ss',str(c['start']),'-i',c['path']]
                    if not c.get('audio',False):cmd+=['-f','lavfi','-i','anullsrc=channel_layout=stereo:sample_rate=48000']
                    cmd+=['-t',str(dur),'-map','0:v:0','-map','0:a:0' if c.get('audio',False) else '1:a:0',
                          '-vf',f'setpts=(PTS-STARTPTS)/{speed},scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}',
                          '-af',self.audio_filter(c,vol,dur/speed), '-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-c:a','aac','-ar','48000','-ac','2','-b:a','192k','-t',str(dur/speed),seg]
                    p=subprocess.run(cmd,capture_output=True,text=True)
                    if p.returncode:raise RuntimeError(f'クリップ {i+1} の変換に失敗:\n{p.stderr[-1200:]}')
                    segments.append(seg);self.events.put(('progress',round((i+1)/total*90),f'変換中 {i+1}/{total}'))
                concat=os.path.join(tmp,'list.txt')
                with open(concat,'w',encoding='utf-8') as f:
                    for seg in segments:f.write("file '"+seg.replace("'","'\\''")+"'\n")
                p=subprocess.run([FFMPEG,'-y','-hide_banner','-loglevel','error','-f','concat','-safe','0','-i',concat,'-c','copy','-movflags','+faststart',output],capture_output=True,text=True)
                if p.returncode:raise RuntimeError(p.stderr[-1200:])
            self.events.put(('done',output))
        except Exception as e:self.events.put(('error',str(e)))
    def audio_filter(self,c,vol,duration):
        speed=float(c.get('speed',1));filters=[f'atempo={speed}',f'volume={vol}']
        fade_in=min(float(c.get('fade_in',0)),duration)
        fade_out=min(float(c.get('fade_out',0)),duration)
        if fade_in>0:filters.append(f'afade=t=in:st=0:d={fade_in}')
        if fade_out>0:filters.append(f'afade=t=out:st={max(0,duration-fade_out)}:d={fade_out}')
        return ','.join(filters)
    def snapshot(self):
        self.undo_stack.append(copy.deepcopy(self.clips));self.undo_stack=self.undo_stack[-60:];self.redo_stack.clear()
    def undo(self):
        if not self.undo_stack:return
        self.redo_stack.append(copy.deepcopy(self.clips));self.clips=self.undo_stack.pop();self.refresh()
    def redo(self):
        if not self.redo_stack:return
        self.undo_stack.append(copy.deepcopy(self.clips));self.clips=self.redo_stack.pop();self.refresh()
    def update_mode(self):
        if self.mode.get()=='プロ':self.probar.pack(fill='x',padx=18,pady=(0,10),before=self.body)
        else:self.probar.pack_forget()
        self.status.set('プロモード: 詳細編集機能を利用できます' if self.mode.get()=='プロ' else '簡単モード: 基本操作だけを表示しています')
    def change_speed(self):
        i=self.selected()
        if i is None:return messagebox.showinfo('選択','クリップを選択してください')
        value=simpledialog.askfloat('再生速度','倍率（0.25～4.0）',initialvalue=self.clips[i].get('speed',1),minvalue=.25,maxvalue=4,parent=self.root)
        if value is not None:self.snapshot();self.clips[i]['speed']=value;self.refresh()
    def change_fades(self):
        i=self.selected()
        if i is None:return messagebox.showinfo('選択','クリップを選択してください')
        c=self.clips[i];duration=(c['end']-c['start'])/c.get('speed',1)
        fi=simpledialog.askfloat('フェードイン','フェードイン秒数',initialvalue=c.get('fade_in',0),minvalue=0,maxvalue=duration,parent=self.root)
        if fi is None:return
        fo=simpledialog.askfloat('フェードアウト','フェードアウト秒数',initialvalue=c.get('fade_out',0),minvalue=0,maxvalue=duration,parent=self.root)
        if fo is not None:self.snapshot();c['fade_in']=fi;c['fade_out']=fo;self.refresh()
    def duplicate(self):
        i=self.selected()
        if i is not None:self.snapshot();self.clips.insert(i+1,copy.deepcopy(self.clips[i]));self.refresh();self.tree.selection_set(str(i+1))
    def drag_start(self,event):
        item=self.tree.identify_row(event.y);self.drag_from=int(item) if item else None
    def drag_end(self,event):
        target=self.tree.identify_row(event.y)
        if self.drag_from is None or not target:return
        i=self.drag_from;j=int(target);self.drag_from=None
        if i==j:return
        self.snapshot();clip=self.clips.pop(i);self.clips.insert(j,clip);self.refresh();self.tree.selection_set(str(j))
    def autosave_now(self):
        if self.clips:
            folder=Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'VideoEaseStudio'
            folder.mkdir(parents=True,exist_ok=True)
            (folder/'autosave.ves.json').write_text(json.dumps(dict(clips=self.clips,res=self.res.get(),fps=self.fps.get(),volume=self.volume.get(),mode=self.mode.get()),ensure_ascii=False,indent=2),encoding='utf8')
    def autosave(self):
        if self.clips and not self.busy:
            try:
                folder=Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'VideoEaseStudio';folder.mkdir(parents=True,exist_ok=True)
                (folder/'autosave.ves.json').write_text(json.dumps(dict(clips=self.clips,res=self.res.get(),fps=self.fps.get(),volume=self.volume.get(),mode=self.mode.get()),ensure_ascii=False,indent=2),encoding='utf8')
            except OSError:pass
        self.root.after(30000,self.autosave)
    def check_updates_silent(self):
        self.check_updates(silent=True)
    def check_updates(self, silent=False):
        if getattr(self,'updating',False): return
        self.updating=True
        if not silent: self.status.set('最新版を確認しています…')
        def worker():
            try: self.events.put(('update_check',updater.check_release(),silent))
            except Exception as e: self.events.put(('update_check_error',str(e),silent))
        threading.Thread(target=worker,daemon=True).start()
    def start_update(self,release):
        if self.busy:
            return messagebox.showwarning('更新できません','動画の書き出しが終わってから更新してください')
        self.status.set('アップデートをダウンロード中…')
        self.updating=True
        def worker():
            try:
                folder,staged=updater.download(release,lambda n:self.events.put(('update_progress',n)))
                self.events.put(('update_ready',folder,staged))
            except Exception as e:self.events.put(('update_error',str(e)))
        threading.Thread(target=worker,daemon=True).start()
    def poll(self):
        try:
            while True:
                ev=self.events.get_nowait()
                if ev[0]=='update_check':
                    self.updating=False
                    release=ev[1]
                    if release:
                        if messagebox.askyesno('アップデート',f"新しいバージョン {release['tag']} が見つかりました。\n\n更新して再起動しますか？"):
                            self.start_update(release)
                    elif not ev[2]: messagebox.showinfo('更新確認','最新版です。')
                elif ev[0]=='update_check_error':
                    self.updating=False
                    if not ev[2]: messagebox.showerror('更新確認',ev[1])
                elif ev[0]=='update_progress':
                    self.progress.set(ev[1]);self.status.set(f'更新をダウンロード中: {ev[1]}%')
                elif ev[0]=='update_error':
                    self.updating=False;messagebox.showerror('更新失敗',ev[1])
                elif ev[0]=='update_ready':
                    self.updating=False
                    if self.busy:
                        messagebox.showwarning('更新保留','書き出し中なので更新できません。後で更新確認してください。')
                    else:
                        try:
                            self.autosave_now()
                            updater.launch_update(ev[1],ev[2])
                            self.root.destroy()
                            return
                        except Exception as e:messagebox.showerror('更新失敗',str(e))
                elif ev[0]=='progress':self.progress.set(ev[1]);self.status.set(ev[2])
                elif ev[0]=='done':self.busy=False;self.progress.set(100);self.status.set('書き出し完了: '+ev[1]);messagebox.showinfo('完了','動画を書き出しました！\n'+ev[1])
                elif ev[0]=='error':self.busy=False;self.status.set('書き出しに失敗しました');messagebox.showerror('書き出しエラー',ev[1])
        except queue.Empty:pass
        self.root.after(150,self.poll)
    def close(self):
        if self.busy and not messagebox.askyesno('確認','書き出し中です。終了しますか？'):return
        self.root.destroy()

if __name__=='__main__':
    root=tk.Tk();Studio(root)
    if '--update-health' in sys.argv:
        try:
            marker=Path(sys.argv[sys.argv.index('--update-health')+1])
            root.after(600,lambda:marker.write_text('ok',encoding='utf-8'))
        except (IndexError,ValueError): pass
    root.mainloop()
