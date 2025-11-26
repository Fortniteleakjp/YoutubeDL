import os
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox, QGroupBox,
    QCheckBox, QTextEdit, QProgressBar, QDialog
)

from downloader import DownloadThread

# ログ作成
def create_logger(output_dir="logs"):
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(output_dir, f"{timestamp}.log")
    return open(log_path, "w", encoding="utf-8")

# メインのGUI
class YouTubeDownloader(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube MP4 & MP3 ダウンローダー (Cookies対応)")
        self.resize(700, 600)
        self.log_file = create_logger()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # 保存先
        settings_group = QGroupBox("基本設定")
        settings_layout = QVBoxLayout()

        folder_layout = QHBoxLayout()
        self.folder_entry = QLineEdit()
        browse_btn = QPushButton("参照")
        browse_btn.clicked.connect(self.browse_folder)
        folder_layout.addWidget(QLabel("保存先フォルダ:"))
        folder_layout.addWidget(self.folder_entry)
        folder_layout.addWidget(browse_btn)
        settings_layout.addLayout(folder_layout)

        # MP3変換チェック
        self.mp3_checkbox = QCheckBox("MP3に変換する")
        settings_layout.addWidget(self.mp3_checkbox)
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Cookies指定
        advanced_group = QGroupBox("詳細設定")
        advanced_layout = QVBoxLayout()
        cookies_layout = QHBoxLayout()
        self.cookies_entry = QLineEdit()
        cookies_btn = QPushButton("Cookiesファイル選択")
        cookies_btn.clicked.connect(self.browse_cookies)
        cookies_layout.addWidget(QLabel("cookies.txt:"))
        cookies_layout.addWidget(self.cookies_entry)
        cookies_layout.addWidget(cookies_btn)
        advanced_layout.addLayout(cookies_layout)
        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)

        # URL入力
        urls_group = QGroupBox("ダウンロードリスト")
        urls_layout = QVBoxLayout()
        self.urls_text = QTextEdit()
        self.urls_text.setPlaceholderText(
            "URL と出力名を1行ずつ、カンマ区切りで入力\n例:\nhttps://youtube.com/xxxx,video1"
        )
        urls_layout.addWidget(self.urls_text)
        urls_group.setLayout(urls_layout)
        layout.addWidget(urls_group, 1) # Stretch factor

        # ダウンロードボタン
        self.download_btn = QPushButton("ダウンロード開始")
        self.download_btn.clicked.connect(self.start_download)
        layout.addWidget(self.download_btn)

        # 進捗とログ
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

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

        if not any(line.strip() for line in lines):
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

        self.download_btn.setEnabled(False)
        self.log_output.clear()
        self.progress_bar.setValue(0)

        # スレッド起動
        self.thread = DownloadThread(tasks, output_dir, to_mp3, cookies_file, self.log_file)
        self.thread.progress_update.connect(self.update_progress)
        self.thread.finished_signal.connect(self.download_finished)
        self.thread.log_message.connect(self.append_log)
        self.thread.start()

    def append_log(self, message):
        self.log_output.append(message)

    def update_progress(self, percent, message):
        self.progress_bar.setValue(percent)
        self.progress_bar.setFormat(f"{message} - {percent}%")

    def download_finished(self, results):
        self.download_btn.setEnabled(True)
        self.progress_bar.setFormat("完了")
        self.log_file.write("\n=== 完了 ===\n")
        self.log_file.flush()
        self.append_log("\n=== 完了 ===")
        for result in results:
            self.append_log(result)
        QMessageBox.information(self, "完了", "すべての処理が完了しました。詳細はログを確認してください。")