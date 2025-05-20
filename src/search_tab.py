from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QProgressBar, QScrollArea, QFrame, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QImage, QPixmap
from datetime import datetime
import requests
from PIL import Image
from io import BytesIO

class SearchThread(QThread):
    video_found_signal = pyqtSignal(dict)  # Signal untuk setiap video yang ditemukan
    finished_signal = pyqtSignal(bool, str)  # Signal ketika pencarian selesai
    progress_signal = pyqtSignal(int, int)  # Signal untuk progress (current, total)
    
    def __init__(self, youtube, query):
        super().__init__()
        self.youtube = youtube
        self.query = query
        self.last_api_validation = 0
        
    def run(self):
        try:
            # Perform search
            search_request = self.youtube.search().list(
                part="snippet",
                q=self.query,
                type="video",
                maxResults=50
            )
            search_response = search_request.execute()
            
            # Get video IDs for detailed info
            video_ids = [item['id']['videoId'] for item in search_response['items']]
            
            # Get detailed video information including statistics
            videos_request = self.youtube.videos().list(
                part="snippet,statistics",
                id=','.join(video_ids)
            )
            videos_response = videos_request.execute()
            
            # Create a mapping of video details
            video_details = {}
            for item in videos_response['items']:
                video_details[item['id']] = {
                    'statistics': item['statistics'],
                    'snippet': item['snippet']
                }
            
            # Process each video
            total_videos = len(search_response['items'])
            
            for index, item in enumerate(search_response['items'], 1):
                video_id = item['id']['videoId']
                
                # Merge video details
                if video_id in video_details:
                    item['statistics'] = video_details[video_id]['statistics']
                    # Update snippet with more detailed information
                    item['snippet'].update(video_details[video_id]['snippet'])
                
                # Pre-download thumbnail
                try:
                    thumbnail_url = item['snippet']['thumbnails']['default']['url']
                    response = requests.get(thumbnail_url)
                    img = Image.open(BytesIO(response.content))
                    img = img.resize((120, 90), Image.Resampling.LANCZOS)
                    img_data = img.tobytes("raw", "RGB")
                    item['_thumbnail_data'] = img_data
                except Exception as e:
                    print(f"Error loading thumbnail: {e}")
                    item['_thumbnail_data'] = None
                
                # Add relevance index
                item['relevance_index'] = index - 1
                
                # Emit the video immediately
                self.video_found_signal.emit(item)
                
                # Update progress
                self.progress_signal.emit(index, total_videos)
                
            self.finished_signal.emit(True, f"Found {total_videos} videos")
        except Exception as e:
            print(f"Search error: {e}")
            self.finished_signal.emit(False, str(e))

class SearchTab(QWidget):
    search_requested = pyqtSignal(str)  # Signal emitted when search is requested
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.sort_ascending = False
        self.search_results = []
        self.video_widgets = []
        
        # Initialize search timer for debouncing
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._execute_search)
        
        self.search_thread = None
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Search controls
        search_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search YouTube videos...")
        self.search_input.textChanged.connect(self._debounce_search)
        search_layout.addWidget(self.search_input)
        
        # Sort controls
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Relevance", "View Count", "Date", "Title"])
        self.sort_combo.setMinimumWidth(150)  # Make dropdown wider
        self.sort_combo.currentTextChanged.connect(self.sort_results)
        search_layout.addWidget(self.sort_combo)
        
        self.sort_order_btn = QPushButton("↓")
        self.sort_order_btn.setFixedWidth(30)
        self.sort_order_btn.clicked.connect(self.toggle_sort_order)
        search_layout.addWidget(self.sort_order_btn)
        
        layout.addLayout(search_layout)
        
        # Selection controls
        selection_layout = QHBoxLayout()
        
        # Selected count label
        self.selected_count_label = QLabel("Selected: 0")
        selection_layout.addWidget(self.selected_count_label)
        
        selection_layout.addStretch()
        
        # Add to batch button
        self.add_to_batch_btn = QPushButton("Add Selected to Batch")
        self.add_to_batch_btn.clicked.connect(self.add_selected_to_batch)
        self.add_to_batch_btn.setEnabled(False)  # Initially disabled
        selection_layout.addWidget(self.add_to_batch_btn)
        
        layout.addLayout(selection_layout)
        
        # Search results area
        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.results_scroll.setWidget(self.results_widget)
        layout.addWidget(self.results_scroll)
        
        # Progress bar and status
        self.search_progress = QProgressBar()
        self.search_progress.setVisible(False)
        layout.addWidget(self.search_progress)
        
        self.status_label = QLabel()
        layout.addWidget(self.status_label)
        
    def _debounce_search(self):
        # Cancel any ongoing search
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.terminate()
            self.search_thread.wait()
            
        # Reset and start the timer
        self.search_timer.stop()
        self.search_timer.start(500)  # 500ms delay before executing search
        
    def _execute_search(self):
        # Stop the timer if it's running
        self.search_timer.stop()
        self.perform_search()
        
    def perform_search(self):
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.terminate()
            self.search_thread.wait()
        
        query = self.search_input.text().strip()
        if not query:
            return
            
        # Clear previous results first
        self.clear_results()
        
        # Show progress
        self.search_progress.setVisible(True)
        self.search_progress.setValue(0)
        self.update_search_status("Searching for videos...")
        
        # Start new search thread
        self.search_thread = SearchThread(self.parent.youtube, query)
        self.search_thread.video_found_signal.connect(self.add_video)
        self.search_thread.progress_signal.connect(self.update_search_progress)
        self.search_thread.finished_signal.connect(self.on_search_finished)
        self.search_thread.start()

    def clear_results(self, clear_search_results=True):
        """Clear all search results
        Args:
            clear_search_results (bool): If True, also clear the search_results list. 
                                       If False, only clear the widgets.
        """
        if clear_search_results:
            self.search_results = []
        
        # Clear widgets
        while self.results_layout.count() > 1:  # Keep the last stretch item
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.video_widgets = []
        
        # Reset selected count
        self.selected_count_label.setText("Selected: 0")
        self.add_to_batch_btn.setEnabled(False)
        
    def update_search_progress(self, current, total):
        """Update the search progress bar"""
        self.search_progress.setVisible(True)
        self.search_progress.setMaximum(total)
        self.search_progress.setValue(current)
        self.update_search_status(f"Loading videos... ({current}/{total})")
        
    def update_search_status(self, message, is_error=False):
        """Update the search status label"""
        color = "#dc3545" if is_error else "#1a73e8"
        self.status_label.setStyleSheet(f"QLabel {{ color: {color}; }}")
        self.status_label.setText(message)
        
    def get_sort_criteria(self):
        """Get current sort criteria"""
        return self.sort_combo.currentText(), self.sort_ascending

    def toggle_sort_order(self):
        """Toggle sort order between ascending and descending"""
        self.sort_ascending = not self.sort_ascending
        self.sort_order_btn.setText("↑" if self.sort_ascending else "↓")
        self.sort_results()
        
    def add_video(self, video_item):
        # Add to search results
        self.search_results.append(video_item)
        
        # Create and add widget
        video_widget = self.create_video_widget(video_item)
        # Insert before the stretch item
        self.results_layout.insertWidget(
            self.results_layout.count() - 1, 
            video_widget
        )
        self.video_widgets.append(video_widget)
        
        # Update status
        self.update_search_status(f"Found {len(self.search_results)} videos...")

    def on_search_finished(self, success, message):
        self.update_search_status(message, not success)
        self.search_progress.setVisible(False)

    def create_video_widget(self, video_item):
        video_frame = QFrame()
        video_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        video_layout = QHBoxLayout(video_frame)
        
        # Add checkbox
        checkbox = QCheckBox()
        video_id = video_item['id']['videoId']
        checkbox.setObjectName(f"checkbox_{video_id}")
        checkbox.setProperty("video_id", video_id)
        # Connect checkbox state change to update selected count
        checkbox.stateChanged.connect(self.update_selected_count)
        video_layout.addWidget(checkbox)
        
        # Thumbnail
        thumbnail_label = QLabel()
        thumbnail_label.setFixedSize(120, 90)
        if video_item.get('_thumbnail_data'):
            img = QImage(video_item['_thumbnail_data'], 120, 90, QImage.Format.Format_RGB888)
            thumbnail_label.setPixmap(QPixmap.fromImage(img))
        video_layout.addWidget(thumbnail_label)
        
        # Info section
        info_layout = QVBoxLayout()
        
        # Title
        title_label = QLabel(video_item['snippet']['title'])
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-weight: bold;")
        title_label.setProperty("type", "title")
        info_layout.addWidget(title_label)
        
        # Channel
        channel_label = QLabel(video_item['snippet']['channelTitle'])
        channel_label.setProperty("type", "channel")
        info_layout.addWidget(channel_label)
        
        # Additional info (views, date)
        stats_layout = QHBoxLayout()
        
        # Views
        views_count = int(video_item.get('statistics', {}).get('viewCount', 0))
        views_text = f"{views_count:,} views" if views_count > 0 else "No views"
        views_label = QLabel(views_text)
        stats_layout.addWidget(views_label)
        
        # Date
        try:
            date_str = video_item['snippet']['publishedAt']
            date_obj = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
            date_label = QLabel(date_obj.strftime("%Y-%m-%d"))
            stats_layout.addWidget(date_label)
        except:
            pass
        
        stats_layout.addStretch()
        info_layout.addLayout(stats_layout)
        
        video_layout.addLayout(info_layout)
        
        # Download button
        download_btn = QPushButton("Download")
        download_btn.clicked.connect(
            lambda: self.parent.prepare_download(f"https://www.youtube.com/watch?v={video_item['id']['videoId']}"))
        download_btn.setFixedWidth(100)
        video_layout.addWidget(download_btn)
        
        # Store video data in widget for download
        video_frame.video_data = video_item
        
        # Set initial style
        self.parent.update_video_widget_style(video_frame)
        
        return video_frame

    def update_selected_count(self):
        # Count checked checkboxes
        selected_count = 0
        for i in range(self.results_layout.count()):
            widget = self.results_layout.itemAt(i).widget()
            if widget:
                checkbox = widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    selected_count += 1
        
        # Update label and button state
        self.selected_count_label.setText(f"Selected: {selected_count}")
        self.add_to_batch_btn.setEnabled(selected_count > 0)
        
    def sort_results(self):
        if not self.search_results:
            return

        sort_by = self.sort_combo.currentText()
        sort_ascending = self.sort_ascending
        
        def get_sort_key(item):
            try:
                snippet = item.get('snippet', {})
                if sort_by == "Title":
                    return snippet.get('title', '').lower()
                elif sort_by == "View Count":
                    stats = item.get('statistics', {})
                    return int(stats.get('viewCount', '0'))
                elif sort_by == "Date":
                    return snippet.get('publishedAt', '')
                else:  # Relevance - maintain original order
                    return item.get('relevance_index', 0)
            except Exception as e:
                print(f"Error getting sort key for {sort_by}: {e}")
                if sort_by == "View Count":
                    return 0
                elif sort_by == "Title":
                    return ""
                elif sort_by == "Date":
                    return ""
                else:
                    return 0
        
        try:
            # Sort the results
            self.search_results.sort(key=get_sort_key, reverse=not sort_ascending)
            
            # Store the current scroll position
            scroll_pos = self.results_scroll.verticalScrollBar().value()
            
            # Clear current results but preserve search_results
            self.clear_results(clear_search_results=False)
            
            # Create a set to track video IDs we've already added
            added_videos = set()
            
            # Recreate widgets in sorted order
            for video_item in self.search_results:
                video_id = video_item['id']['videoId']
                if video_id not in added_videos:
                    video_widget = self.create_video_widget(video_item)
                    # Apply theme style
                    self.parent.update_video_widget_style(video_widget)
                    self.results_layout.insertWidget(
                        self.results_layout.count() - 1, 
                        video_widget
                    )
                    self.video_widgets.append(video_widget)
                    added_videos.add(video_id)
            
            # Restore scroll position
            self.results_scroll.verticalScrollBar().setValue(scroll_pos)
                
        except Exception as e:
            print(f"Error sorting results: {str(e)}")

    def add_selected_to_batch(self):
        selected_videos = []
        for i in range(self.results_layout.count()):
            widget = self.results_layout.itemAt(i).widget()
            if widget:
                checkbox = widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    # Get video ID directly from checkbox property
                    video_id = checkbox.property("video_id")
                    if video_id:
                        url = f"https://www.youtube.com/watch?v={video_id}"
                        selected_videos.append(url)
        
        if selected_videos:
            # Get current text from batch downloader's URL input
            current_text = self.parent.batch_downloader.url_input.toPlainText()
            
            # Clean up existing text and new URLs
            existing_urls = [url.strip() for url in current_text.split('\n') if url.strip()]
            all_urls = existing_urls + selected_videos
            
            # Remove duplicates while preserving order
            unique_urls = []
            seen = set()
            for url in all_urls:
                if url not in seen:
                    unique_urls.append(url)
                    seen.add(url)
            
            # Join URLs with newlines and set the text
            self.parent.batch_downloader.url_input.setPlainText('\n'.join(unique_urls))
            
            self.parent.show_styled_message_box(
                "Success",
                f"Added {len(selected_videos)} videos to batch download list",
                "info"
            )
            
            # Switch to batch downloader tab
            self.parent.tabs.setCurrentWidget(self.parent.batch_downloader)
        else:
            self.parent.show_styled_message_box(
                "No Selection",
                "Please select at least one video to add to batch download",
                "warning"
            )
