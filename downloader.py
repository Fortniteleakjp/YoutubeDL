import os
import subprocess
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal
import yt_dlp

# ダウンロードと変換のスレッド
class DownloadThread(QThread):
    progress_update = pyqtSignal(int, str)
    finished_signal = pyqtSignal(list)
    log_message = pyqtSignal(str)

    def __init__(self, tasks, output_dir, to_mp3, cookies_file=None, log_file=None):
        super().__init__()
        self.tasks = tasks
        self.output_dir = output_dir
        self.to_mp3 = to_mp3
        self.cookies_file = cookies_file
        self.log_file = log_file

    def log(self, message):
        full_message = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
        if self.log_file:
            self.log_file.write(full_message + "\n")
            self.log_file.flush()
        self.log_message.emit(full_message)

    def run(self):
        results = []
        os.makedirs(self.output_dir, exist_ok=True)

        for idx, (url, filename) in enumerate(self.tasks, 1):
            try:
                def progress_hook(d):
                    if d['status'] == 'downloading':
                        percent = int(d.get('downloaded_bytes', 0) / max(d.get('total_bytes',1),1) * 100)
                        msg = f"Downloading {filename or 'video'} ({idx}/{len(self.tasks)})"
                        self.progress_update.emit(percent, msg)
                        self.log(msg)
                    elif d['status'] == 'finished':
                        msg = f"Download finished: {filename or 'video'} ({idx}/{len(self.tasks)})"
                        self.progress_update.emit(100, msg)
                        self.log(msg)

                ydl_opts = {
                    'format': 'bestvideo+bestaudio/best',
                    'outtmpl': os.path.join(self.output_dir, f"{filename}.%(ext)s") if filename else os.path.join(self.output_dir, "%(title)s.%(ext)s"),
                    'merge_output_format': 'mp4',
                    'noplaylist': True,
                    'quiet': True,
                    'progress_hooks': [progress_hook],
                }

                if self.cookies_file and os.path.exists(self.cookies_file):
                    ydl_opts['cookiefile'] = self.cookies_file

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    title = filename or info.get('title', 'output')
                    mp4_file = os.path.join(self.output_dir, f"{title}.mp4")

                mp3_file = None
                if self.to_mp3:
                    mp3_file = os.path.join(self.output_dir, f"{title}.mp3")
                    cmd = ["ffmpeg", "-i", mp4_file, "-vn", "-ab", "192k", "-ar", "44100", "-y", mp3_file]
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
                    for line in process.stdout:
                        if "time=" in line:
                            msg = f"Converting {title} to MP3 ({idx}/{len(self.tasks)})"
                            self.progress_update.emit(50, msg)
                            self.log(msg)
                    process.wait()
                    msg = f"Conversion finished: {title}"
                    self.progress_update.emit(100, msg)
                    self.log(msg)

                results.append(f"{mp4_file}" + (f"\n{mp3_file}" if mp3_file else ""))

            except Exception as e:
                err_msg = str(e)
                if "The following content is not available on this app" in err_msg:
                    err_msg += (
                        "\n\nこの動画はYouTubeのアプリ限定コンテンツです。\n"
                        "cookies.txt を使用してログイン状態を反映するとダウンロード可能になる場合があります。"
                    )
                results.append(f"URL: {url} でエラー発生: {err_msg}")
                self.log(f"ERROR: URL {url} - {err_msg}")

        self.finished_signal.emit(results)