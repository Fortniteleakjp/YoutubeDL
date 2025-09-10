import sys
import os
import subprocess
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox,
    QCheckBox, QTextEdit, QProgressBar, QDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import yt_dlp

# ログ作成
def create_logger(output_dir="logs"):
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(output_dir, f"{timestamp}.log")
    return open(log_path, "w", encoding="utf-8")

# ダウンロードと変換のスレッド
class DownloadThread(QThread):
    progress_update = pyqtSignal(int, str)
    finished_signal = pyqtSignal(list)

    def __init__(self, tasks, output_dir, to_mp3, cookies_file=None, log_file=None):
        super().__init__()
        self.tasks = tasks
        self.output_dir = output_dir
        self.to_mp3 = to_mp3
        self.cookies_file = cookies_file
        self.log_file = log_file

    def log(self, message):
        if self.log_file:
            self.log_file.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
            self.log_file.flush()

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
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
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

# メインのGUI
class YouTubeDownloader(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube MP4 & MP3 ダウンローダー (Cookies対応)")
        self.setFixedSize(700, 500)
        self.log_file = create_logger()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # 保存先
        folder_layout = QHBoxLayout()
        self.folder_entry = QLineEdit()
        browse_btn = QPushButton("参照")
        browse_btn.clicked.connect(self.browse_folder)
        folder_layout.addWidget(QLabel("保存先フォルダ:"))
        folder_layout.addWidget(self.folder_entry)
        folder_layout.addWidget(browse_btn)
        layout.addLayout(folder_layout)

        # MP3変換チェック
        self.mp3_checkbox = QCheckBox("MP3に変換する")
        layout.addWidget(self.mp3_checkbox)

        # Cookies指定
        cookies_layout = QHBoxLayout()
        self.cookies_entry = QLineEdit()
        cookies_btn = QPushButton("Cookiesファイル選択")
        cookies_btn.clicked.connect(self.browse_cookies)
        cookies_layout.addWidget(QLabel("cookies.txt:"))
        cookies_layout.addWidget(self.cookies_entry)
        cookies_layout.addWidget(cookies_btn)
        layout.addLayout(cookies_layout)

        # URL入力
        self.urls_text = QTextEdit()
        self.urls_text.setPlaceholderText(
            "URL と出力名を1行ずつ、カンマ区切りで入力\n例:\nhttps://youtube.com/xxxx,video1"
        )
        layout.addWidget(QLabel("複数URLと出力名（任意）:"))
        layout.addWidget(self.urls_text)

        # ダウンロードボタン
        download_btn = QPushButton("ダウンロード開始")
        download_btn.clicked.connect(self.start_download)
        layout.addWidget(download_btn)
        self.setLayout(layout)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "保存先フォルダを選択")
        if folder:
            self.folder_entry.setText(folder)

    def browse_cookies(self):
        file, _ = QFileDialog.getOpenFileName(self, "Cookiesファイル選択", "", "Cookiesファイル (*.txt)")
        if file:
            self.cookies_entry.setText(file)

    def start_download(self):
        output_dir = self.folder_entry.text().strip() or "downloads"
        to_mp3 = self.mp3_checkbox.isChecked()
        cookies_file = self.cookies_entry.text().strip() or None
        lines = self.urls_text.toPlainText().splitlines()

        if not lines:
            QMessageBox.critical(self, "エラー", "URLを入力してください")
            return

        tasks = []
        for line in lines:
            if not line.strip():
                continue
            parts = line.split(",", maxsplit=1)
            url = parts[0].strip()
            filename = parts[1].strip() if len(parts) > 1 else None
            tasks.append((url, filename))

        # プログレスダイアログ
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        dlg = QDialog(self)
        dlg.setWindowTitle("進捗状況")
        dlg.setLayout(QVBoxLayout())
        dlg.layout().addWidget(QLabel("処理中…"))
        dlg.layout().addWidget(self.progress_bar)
        dlg.setModal(True)
        dlg.setFixedSize(400, 100)
        self.progress_dialog = dlg

        # スレッド起動
        self.thread = DownloadThread(tasks, output_dir, to_mp3, cookies_file, self.log_file)
        self.thread.progress_update.connect(self.update_progress)
        self.thread.finished_signal.connect(self.download_finished)
        self.thread.start()

        dlg.show()

    def update_progress(self, percent, message):
        self.progress_bar.setValue(percent)
        self.progress_bar.setFormat(f"{message} - {percent}%")

    def download_finished(self, results):
        self.progress_dialog.close()
        self.log_file.write("\n=== 完了 ===\n")
        self.log_file.flush()
        QMessageBox.information(self, "完了", "\n\n".join(results))

#実行☆
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YouTubeDownloader()
    window.show()
    sys.exit(app.exec())
