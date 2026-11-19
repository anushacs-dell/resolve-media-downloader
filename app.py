import os
import sys
import requests

if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DOWNLOAD_DIR = os.path.expanduser("~/Movies/YT_Import_Downloads")

from resolve_integration import import_to_media_bin
from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from downloader import (
    VIDEO_QUALITIES,
    detect_platform_label,
    download_media,
    estimate_size_label,
    format_duration,
    get_video_info,
    is_direct_image_url,
)


IVORY_STYLE_SHEET = """
QWidget#centralWindow {
    background-color: #F6F2EA;
    color: #1E1B18;
    font-family: -apple-system, "Segoe UI", "Helvetica Neue", sans-serif;
    font-size: 13px;
}

QFrame#card {
    background-color: #FCFBF8;
    border: 1px solid #E6DFD3;
    border-radius: 14px;
}

QFrame#thumbBox {
    background-color: #EFEAE0;
    border: 1px solid #E2DBD0;
    border-radius: 10px;
}

QLabel#brandBadge {
    background-color: #C85A32;
    color: #FFFFFF;
    border-radius: 10px;
    font-size: 18px;
    font-weight: 700;
}

QLabel#heading {
    font-family: "Georgia", "Times New Roman", serif;
    font-size: 24px;
    font-weight: 700;
    color: #1A1714;
}

QLabel#subheading {
    color: #6F675E;
    font-size: 13px;
}

QLabel#sectionLabel {
    color: #7A7167;
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.6px;
}

QLabel#sourcePill {
    background-color: #FCECE5;
    color: #B84A24;
    border: 1px solid #EBC5B6;
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}

QLabel#previewTitle {
    font-family: "Georgia", "Times New Roman", serif;
    font-size: 15px;
    font-weight: 700;
    color: #1E1B18;
}

QLabel#metaText {
    color: #6F675E;
    font-size: 12px;
}

QLineEdit, QComboBox {
    background-color: #F4EFE6;
    border: 1px solid #DFD7C8;
    border-radius: 10px;
    padding: 8px 12px;
    color: #1E1B18;
    selection-background-color: #C85A32;
    selection-color: #FFFFFF;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #C85A32;
    background-color: #FFFFFF;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #FCFBF8;
    color: #1E1B18;
    border: 1px solid #DFD7C8;
    selection-background-color: #FCECE5;
    selection-color: #B84A24;
}

QPushButton {
    background-color: #FCFBF8;
    border: 1px solid #DDD4C5;
    border-radius: 10px;
    padding: 8px 16px;
    color: #1E1B18;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #F1ECE2;
    border-color: #CFC4B2;
}

QPushButton:disabled {
    color: #A69E94;
    background-color: #F5F1E9;
}

QFrame#segContainer {
    background-color: #EFEAE0;
    border: 1px solid #E2DBD0;
    border-radius: 10px;
    padding: 3px;
}

QPushButton#segButton {
    background-color: transparent;
    border: none;
    border-radius: 7px;
    padding: 6px 14px;
    color: #6A6259;
    font-weight: 600;
}

QPushButton#segButton:hover {
    color: #1E1B18;
}

QPushButton#segButton:checked {
    background-color: #1E1B18;
    color: #FCFBF8;
}

QPushButton#primaryButton {
    background-color: #C85A32;
    border: none;
    border-radius: 10px;
    padding: 9px 22px;
    color: #FFFFFF;
    font-weight: 700;
}

QPushButton#primaryButton:hover {
    background-color: #B44B26;
}

QPushButton#primaryButton:disabled {
    background-color: #DFB7A7;
    color: #FFF9F6;
}

QProgressBar {
    background-color: #ECE6DA;
    border: none;
    border-radius: 5px;
    text-align: right;
    color: #6F675E;
    font-size: 11px;
    height: 10px;
}

QProgressBar::chunk {
    background-color: #C85A32;
    border-radius: 5px;
}
"""


class MetadataWorker(QObject):
    loaded = Signal(str, dict)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            info = get_video_info(self.url)
            self.loaded.emit(self.url, info)
        except Exception:
            self.loaded.emit(self.url, {})


class DownloadWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(str, str)
    error = Signal(str)

    def __init__(self, url, output_path, media_type, quality):
        super().__init__()
        self.url = url
        self.output_path = output_path
        self.media_type = media_type
        self.quality = quality

    def run(self):
        try:
            downloaded_file = download_media(
                self.url,
                self.output_path,
                self.media_type,
                self.quality,
                self.handle_progress,
            )
            self.finished.emit(downloaded_file, self.media_type)
        except Exception as error:
            self.error.emit(str(error))

    def handle_progress(self, data):
        if data["status"] == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            downloaded = data.get("downloaded_bytes", 0)
            speed = data.get("speed")
            eta = data.get("eta")

            pct = int(downloaded / total * 100) if total else 0
            speed_str = f"{speed / (1024 * 1024):.1f} MB/s" if speed else ""
            eta_str = f"{int(eta) // 60}:{int(eta) % 60:02d} left" if eta else ""
            parts = [f"{pct}%"]
            if speed_str:
                parts.append(speed_str)
            if eta_str:
                parts.append(eta_str)

            self.progress.emit(pct, " · ".join(parts))

        elif data["status"] == "finished":
            self.progress.emit(100, "100% · Done")


def make_card():
    frame = QFrame()
    frame.setObjectName("card")
    return frame


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("centralWindow")
        self.setWindowTitle("Media Downloader for DaVinci Resolve")
        self.resize(740, 680)
        self.setStyleSheet(IVORY_STYLE_SHEET)

        self.download_thread = None
        self.download_worker = None
        self.meta_thread = None
        self.meta_worker = None
        self.current_metadata = {}
        self.selected_media_type = "video"

        self.meta_timer = QTimer(self)
        self.meta_timer.setSingleShot(True)
        self.meta_timer.setInterval(450)
        self.meta_timer.timeout.connect(self.fetch_url_metadata)

        self.build_ui()
        self.connect_signals()
        self.refresh_quality_options(preserve_selection=False)

    # ---------------------------------------------------------- UI build

    def build_ui(self):
        root = QVBoxLayout()
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)

        # Header
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        #badge = QLabel("↓")
        #badge.setObjectName("brandBadge")
        #badge.setFixedSize(42, 42)
        #badge.setAlignment(Qt.AlignCenter)
        logo_path = os.path.join(BASE_DIR, "logo1.png")  
        badge = QLabel()
        badge.setObjectName("brandBadge")
        badge.setFixedSize(48, 48)
        badge.setAlignment(Qt.AlignCenter)

        pixmap = QPixmap(logo_path)
        if not pixmap.isNull():
            badge.setPixmap(
                pixmap.scaled(
                    45,
                    45,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
        else:
            badge.setText("↓")


        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        heading = QLabel("Media Downloader")
        heading.setObjectName("heading")
        subheading = QLabel("This is done by Anusha for Pixelflix")
        subheading.setObjectName("subheading")
        title_col.addWidget(heading)
        title_col.addWidget(subheading)
        

        header_row.addWidget(badge)
        header_row.addLayout(title_col)
        header_row.addStretch()
        root.addLayout(header_row)


        # URL card
        url_card = make_card()
        url_layout = QHBoxLayout(url_card)
        url_layout.setContentsMargins(14, 12, 14, 12)
        url_layout.setSpacing(10)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://youtube.com/watch?v=sample")

        self.paste_button = QPushButton("Paste")
        self.paste_button.setFixedWidth(84)

        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.paste_button)
        root.addWidget(url_card)

        # Preview card (title + duration only, no channel name)
        preview_card = make_card()
        preview_layout = QHBoxLayout(preview_card)
        preview_layout.setContentsMargins(14, 12, 14, 12)
        preview_layout.setSpacing(14)

        self.thumb_box = QFrame()
        self.thumb_box.setObjectName("thumbBox")
        self.thumb_box.setFixedSize(112, 68)
        thumb_inner = QVBoxLayout(self.thumb_box)
        thumb_inner.setContentsMargins(0, 0, 0, 0)
        self.thumb_label = QLabel("▶")
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setStyleSheet("color: #7A7167; font-size: 16px; background: transparent;")
        thumb_inner.addWidget(self.thumb_label)

        preview_text_col = QVBoxLayout()
        preview_text_col.setSpacing(4)

        top_badge_row = QHBoxLayout()
        self.source_pill = QLabel("URL preview")
        self.source_pill.setObjectName("sourcePill")
        top_badge_row.addWidget(self.source_pill)
        top_badge_row.addStretch()

        self.preview_title = QLabel("Sample video title goes here")
        self.preview_title.setObjectName("previewTitle")
        self.preview_title.setWordWrap(True)

        self.duration_label = QLabel("12:34")
        self.duration_label.setObjectName("metaText")

        preview_text_col.addLayout(top_badge_row)
        preview_text_col.addWidget(self.preview_title)
        preview_text_col.addWidget(self.duration_label)

        preview_layout.addWidget(self.thumb_box)
        preview_layout.addLayout(preview_text_col, stretch=1)
        root.addWidget(preview_card)

        # Options + Output card
        options_card = make_card()
        options_layout = QVBoxLayout(options_card)
        options_layout.setContentsMargins(16, 14, 16, 14)
        options_layout.setSpacing(14)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(16)

        type_col = QVBoxLayout()
        type_col.setSpacing(6)
        type_label = QLabel("DOWNLOAD TYPE")
        type_label.setObjectName("sectionLabel")

        seg_frame = QFrame()
        seg_frame.setObjectName("segContainer")
        seg_layout = QHBoxLayout(seg_frame)
        seg_layout.setContentsMargins(2, 2, 2, 2)
        seg_layout.setSpacing(2)

        self.type_group = QButtonGroup(self)
        self.type_group.setExclusive(True)

        self.video_btn = QPushButton("Video")
        self.video_btn.setObjectName("segButton")
        self.video_btn.setCheckable(True)
        self.video_btn.setChecked(True)

        self.audio_btn = QPushButton("Audio (MP3)")
        self.audio_btn.setObjectName("segButton")
        self.audio_btn.setCheckable(True)

        self.image_btn = QPushButton("Image")
        self.image_btn.setObjectName("segButton")
        self.image_btn.setCheckable(True)

        self.type_group.addButton(self.video_btn)
        self.type_group.addButton(self.audio_btn)
        self.type_group.addButton(self.image_btn)

        seg_layout.addWidget(self.video_btn)
        seg_layout.addWidget(self.audio_btn)
        seg_layout.addWidget(self.image_btn)

        type_col.addWidget(type_label)
        type_col.addWidget(seg_frame)

        quality_col = QVBoxLayout()
        quality_col.setSpacing(6)
        self.quality_label = QLabel("VIDEO QUALITY")
        self.quality_label.setObjectName("sectionLabel")

        self.quality_combo = QComboBox()
        self.quality_combo.setMinimumWidth(210)

        quality_col.addWidget(self.quality_label)
        quality_col.addWidget(self.quality_combo)

        controls_row.addLayout(type_col)
        controls_row.addStretch()
        controls_row.addLayout(quality_col)

        output_col = QVBoxLayout()
        output_col.setSpacing(6)
        output_label = QLabel("OUTPUT FOLDER")
        output_label.setObjectName("sectionLabel")

        output_row = QHBoxLayout()
        output_row.setSpacing(10)

        self.output_input = QLineEdit()
        self.output_input.setText(DOWNLOAD_DIR)

        self.browse_button = QPushButton("Browse")
        self.browse_button.setFixedWidth(96)

        output_row.addWidget(self.output_input)
        output_row.addWidget(self.browse_button)

        output_col.addWidget(output_label)
        output_col.addLayout(output_row)

        options_layout.addLayout(controls_row)
        options_layout.addLayout(output_col)
        root.addWidget(options_card)

        # Compact Download button row (less wide than full card width)
        action_row = QHBoxLayout()
        action_row.addStretch()

        self.download_button = QPushButton("Download")
        self.download_button.setObjectName("primaryButton")
        self.download_button.setFixedSize(200, 40)
        action_row.addWidget(self.download_button)
        action_row.addStretch()
        root.addLayout(action_row)

        # Progress card (no Reveal in Finder or Import to Resolve buttons)
        progress_card = make_card()
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setContentsMargins(16, 14, 16, 14)
        progress_layout.setSpacing(8)

        progress_top = QHBoxLayout()
        self.progress_title = QLabel("Sample video title goes here")
        self.progress_title.setStyleSheet("font-weight: 700; color: #1E1B18;")
        self.progress_stats = QLabel("Ready")
        self.progress_stats.setObjectName("metaText")

        progress_top.addWidget(self.progress_title)
        progress_top.addStretch()
        progress_top.addWidget(self.progress_stats)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("metaText")

        progress_layout.addLayout(progress_top)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label)

        root.addWidget(progress_card)
        root.addStretch()
        self.setLayout(root)

    def connect_signals(self):
        self.paste_button.clicked.connect(self.paste_from_clipboard)
        self.browse_button.clicked.connect(self.browse_output)
        self.download_button.clicked.connect(self.start_download)

        self.video_btn.clicked.connect(lambda: self.on_type_selected("video"))
        self.audio_btn.clicked.connect(lambda: self.on_type_selected("audio"))
        self.image_btn.clicked.connect(lambda: self.on_type_selected("image"))

        self.quality_combo.currentIndexChanged.connect(self.on_quality_changed)
        self.url_input.textChanged.connect(self.on_url_changed)

    # ---------------------------------------------------------- URL & options

    def paste_from_clipboard(self):
        clipboard_text = QApplication.clipboard().text().strip()
        if clipboard_text:
            self.url_input.setText(clipboard_text)

    def on_url_changed(self, text):
        url = text.strip()
        self.current_metadata = {}

        if not url:
            self.source_pill.setText("URL preview")
            self.preview_title.setText("Sample video title goes here")
            self.progress_title.setText("Sample video title goes here")
            self.duration_label.setText("12:34")
            self.reset_thumbnail()
            self.refresh_quality_options(preserve_selection=False)
            return

        self.source_pill.setText(detect_platform_label(url))

        if is_direct_image_url(url):
            self.selected_media_type = "image"
            self.image_btn.setChecked(True)
            name = os.path.basename(url.split("?")[0]) or "Sample image title"
            self.preview_title.setText(name)
            self.progress_title.setText(name)
            self.duration_label.setText("Image")
            self.refresh_quality_options(preserve_selection=False)
        else:
            if self.selected_media_type == "image":
                self.selected_media_type = "video"
                self.video_btn.setChecked(True)
            self.refresh_quality_options(preserve_selection=True)

        self.meta_timer.start()

    def fetch_url_metadata(self):
        url = self.url_input.text().strip()
        if not url:
            return

        self.meta_thread = QThread()
        self.meta_worker = MetadataWorker(url)
        self.meta_worker.moveToThread(self.meta_thread)
        self.meta_thread.started.connect(self.meta_worker.run)
        self.meta_worker.loaded.connect(self.on_metadata_loaded)
        self.meta_worker.loaded.connect(self.meta_thread.quit)
        self.meta_thread.start()

    def on_metadata_loaded(self, url, info):
        if self.url_input.text().strip() != url or not info:
            return

        self.current_metadata = info
        title = info.get("title") or "Sample video title goes here"
        self.preview_title.setText(title)
        self.progress_title.setText(title)

        dur_str = format_duration(info.get("duration", 0))
        if dur_str:
            self.duration_label.setText(dur_str)
        elif self.selected_media_type == "image":
            self.duration_label.setText("Image")
        else:
            self.duration_label.setText("")

        thumb_url = info.get("thumbnail")
        if thumb_url:
            self.load_thumbnail(thumb_url)

        self.refresh_quality_options(preserve_selection=True)

    def load_thumbnail(self, thumb_url):
        try:
            resp = requests.get(thumb_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
            resp.raise_for_status()
            px = QPixmap()
            if px.loadFromData(resp.content):
                scaled = px.scaled(
                    self.thumb_box.width() - 4,
                    self.thumb_box.height() - 4,
                    Qt.KeepAspectRatioByExpanding,
                    Qt.SmoothTransformation,
                )
                self.thumb_label.setPixmap(scaled)
                self.thumb_label.setText("")
        except Exception:
            pass

    def reset_thumbnail(self):
        self.thumb_label.setPixmap(QPixmap())
        self.thumb_label.setText("▶")

    def on_type_selected(self, media_type):
        self.selected_media_type = media_type
        self.refresh_quality_options(preserve_selection=False)

    def refresh_quality_options(self, preserve_selection=True):
        url = self.url_input.text().strip()
        prev_base = self.quality_combo.currentData() if preserve_selection else None

        self.quality_combo.blockSignals(True)
        self.quality_combo.clear()

        if self.selected_media_type == "video":
            self.quality_label.setText("VIDEO QUALITY")
            for q in VIDEO_QUALITIES:
                mb_text = estimate_size_label("video", q, self.current_metadata, url)
                self.quality_combo.addItem(f"{q} · {mb_text}", userData=q)
            self.quality_combo.setEnabled(True)

            target_idx = 0
            if prev_base:
                for i in range(self.quality_combo.count()):
                    if self.quality_combo.itemData(i) == prev_base:
                        target_idx = i
                        break
            self.quality_combo.setCurrentIndex(target_idx)

        elif self.selected_media_type == "audio":
            self.quality_label.setText("AUDIO FORMAT")
            mb_text = estimate_size_label("audio", "MP3 (192 kbps)", self.current_metadata, url)
            self.quality_combo.addItem(f"MP3 (192 kbps) · {mb_text}", userData="MP3 (192 kbps)")
            self.quality_combo.setEnabled(False)

        else:  # image
            self.quality_label.setText("IMAGE QUALITY")
            mb_text = estimate_size_label("image", "Original", self.current_metadata, url)
            self.quality_combo.addItem(f"Original · {mb_text}", userData="Original")
            self.quality_combo.setEnabled(False)

        self.quality_combo.blockSignals(False)

    def on_quality_changed(self):
        # Keep MB figures updated if metadata arrives later
        url = self.url_input.text().strip()
        if self.selected_media_type == "video" and url:
            self.refresh_quality_options(preserve_selection=True)

    def browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_input.setText(folder)

    # --------------------------------------------------------- download

    def start_download(self):
        url = self.url_input.text().strip()
        output_path = self.output_input.text().strip()

        if not url:
            QMessageBox.warning(self, "Missing URL", "Please enter a media URL.")
            return

        if not output_path:
            QMessageBox.warning(self, "Missing Output Folder", "Please select an output folder.")
            return

        os.makedirs(output_path, exist_ok=True)

        media_type = self.selected_media_type
        quality = self.quality_combo.currentData() or "Best"

        self.download_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_stats.setText("0%")
        self.status_label.setText("Starting download...")

        self.download_thread = QThread()
        self.download_worker = DownloadWorker(url, output_path, media_type, quality)
        self.download_worker.moveToThread(self.download_thread)

        self.download_thread.started.connect(self.download_worker.run)
        self.download_worker.progress.connect(self.on_download_progress)
        self.download_worker.finished.connect(self.download_finished)
        self.download_worker.error.connect(self.download_error)
        self.download_worker.finished.connect(self.download_thread.quit)
        self.download_worker.error.connect(self.download_thread.quit)
        self.download_thread.finished.connect(self.cleanup_download_thread)

        self.download_thread.start()

    def on_download_progress(self, pct, stats_text):
        self.progress_bar.setValue(pct)
        self.progress_stats.setText(stats_text)

    def download_finished(self, downloaded_file, media_type):
        self.progress_bar.setValue(100)
        self.progress_stats.setText("100%")

        bin_names = {
            "image": "Images",
            "audio": "Audio",
            "video": "Video",
        }
        bin_name = bin_names.get(media_type, "Media")

        self.status_label.setText(
            f"Download completed. Importing into Resolve {bin_name} bin..."
        )

        try:
            import_to_media_bin(downloaded_file, media_type)
            self.status_label.setText(
                f"Downloaded and added to Resolve {bin_name} bin."
            )
            QMessageBox.information(
                self,
                "Download Complete",
                f"The media was downloaded and added to the Resolve {bin_name} bin.",
            )
        except Exception as error:
            self.status_label.setText("Downloaded, but Resolve import failed.")
            QMessageBox.warning(
                self,
                "Resolve Import",
                "The download completed, but the media could not be added to the "
                f"Resolve {bin_name} bin.\n\n{error}\n\nDownloaded file:\n{downloaded_file}",
            )

    def download_error(self, message):
        self.status_label.setText("Download failed.")
        QMessageBox.critical(self, "Download Error", message)

    def cleanup_download_thread(self):
        self.download_button.setEnabled(True)
        if self.download_worker:
            self.download_worker.deleteLater()
        if self.download_thread:
            self.download_thread.deleteLater()
        self.download_worker = None
        self.download_thread = None


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()