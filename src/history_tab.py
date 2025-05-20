from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QFrame, QLineEdit, 
                           QLabel, QComboBox, QTreeWidget, QPushButton,
                           QTreeWidgetItem, QFileDialog, QDialog,
                           QProgressBar, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
import os
from datetime import datetime, timedelta

class ExportThread(QThread):
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, history_data, file_path):
        super().__init__()
        self.history_data = history_data
        self.file_path = file_path
    
    def run(self):
        try:
            with open(self.file_path, 'w', newline='', encoding='utf-8') as file:
                # Write header
                file.write("Title,Date,Format,Output Directory,Status\n")
                
                # Write data
                for item in self.history_data:
                    file.write(f"{item.get('title', 'N/A')},{item.get('date', 'N/A')},"
                             f"{item.get('format', 'N/A')},{item.get('output_dir', 'N/A')},"
                             f"{item.get('status', 'Completed')}\n")
                             
            self.finished_signal.emit(True, "History exported successfully!")
        except Exception as e:
            self.finished_signal.emit(False, f"Error exporting history: {str(e)}")

class HistoryWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.download_history = []
        self.setup_ui()
        self.update_history_display()  # Memastikan history langsung ditampilkan saat inisialisasi
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Search and filter section
        filter_frame = QFrame()
        filter_layout = QHBoxLayout(filter_frame)
        
        self.history_search = QLineEdit()
        self.history_search.setPlaceholderText("Search in history...")
        self.history_search.textChanged.connect(self.filter_history)
        
        date_label = QLabel("Filter by date:")
        self.date_filter = QComboBox()
        self.date_filter.addItems(["All Time", "Today", "This Week", "This Month", "This Year"])
        self.date_filter.currentTextChanged.connect(self.filter_history)
        
        filter_layout.addWidget(self.history_search)
        filter_layout.addWidget(date_label)
        filter_layout.addWidget(self.date_filter)
        
        layout.addWidget(filter_frame)
        
        # History tree
        self.history_tree = QTreeWidget()
        self.history_tree.setHeaderLabels(["Title", "Date", "Format", "Output Directory", "Status"])
        self.history_tree.setColumnWidth(0, 300)  # Title
        self.history_tree.setColumnWidth(1, 150)  # Date
        self.history_tree.setColumnWidth(2, 150)  # Format
        self.history_tree.setColumnWidth(3, 200)  # Output Directory
        
        # Control buttons
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        
        export_button = QPushButton("Export to CSV")
        export_button.clicked.connect(self.export_history)
        clear_button = QPushButton("Clear History")
        clear_button.clicked.connect(self.clear_history)
        
        button_layout.addWidget(export_button)
        button_layout.addStretch()
        button_layout.addWidget(clear_button)
        
        layout.addWidget(self.history_tree)
        layout.addWidget(button_frame)
        
        # Load history
        # self.update_history_display()
    
    def filter_history(self):
        self.history_tree.clear()
        search_text = self.history_search.text().lower()
        date_filter = self.date_filter.currentText()
        
        current_date = datetime.now()
        
        for item in self.download_history:
            # Check if item matches search text
            title_match = search_text in item.get('title', '').lower()
            format_match = search_text in item.get('format', '').lower()
            if not (title_match or format_match) and search_text:
                continue
            
            # Check if item matches date filter
            date_str = item.get('date', '')
            if date_str and date_str != 'N/A':
                try:
                    item_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    if date_filter != "All Time":
                        if date_filter == "Today":
                            if item_date.date() != current_date.date():
                                continue
                        elif date_filter == "This Week":
                            week_ago = current_date - timedelta(days=7)
                            if item_date.date() < week_ago.date():
                                continue
                        elif date_filter == "This Month":
                            month_ago = current_date - timedelta(days=30)
                            if item_date.date() < month_ago.date():
                                continue
                        elif date_filter == "This Year":
                            if item_date.year != current_date.year:
                                continue
                except ValueError:
                    # If date parsing fails, only show if filter is "All Time"
                    if date_filter != "All Time":
                        continue
            elif date_filter != "All Time":
                continue
            
            tree_item = QTreeWidgetItem([
                item.get('title', 'N/A'),
                item.get('date', 'N/A'),
                item.get('format', 'N/A'),
                item.get('output_dir', 'N/A'),
                item.get('status', 'Completed')
            ])
            self.history_tree.addTopLevelItem(tree_item)
    
    def export_history(self):
        # Ask user for save location
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export History",
            os.path.expanduser("~/Downloads/download_history.csv"),
            "CSV Files (*.csv)"
        )
        
        if not file_path:
            return
            
        # Create and show progress dialog
        progress_dialog = QDialog(self)
        progress_dialog.setWindowTitle("Exporting History")
        progress_dialog.setFixedSize(300, 100)
        layout = QVBoxLayout(progress_dialog)
        
        label = QLabel("Exporting download history...\nPlease wait...")
        layout.addWidget(label)
        
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 0)  # Indeterminate progress
        layout.addWidget(progress_bar)
        
        # Create and start export thread
        self.export_thread = ExportThread(self.download_history, file_path)
        self.export_thread.finished_signal.connect(
            lambda success, msg: self._handle_export_finished(success, msg, progress_dialog)
        )
        self.export_thread.start()
        
        # Show progress dialog
        progress_dialog.exec()
    
    def _handle_export_finished(self, success, message, dialog):
        dialog.close()
        if success:
            QMessageBox.information(
                self,
                "Export History",
                message,
                QMessageBox.StandardButton.Ok
            )
        else:
            QMessageBox.warning(
                self,
                "Export History",
                message,
                QMessageBox.StandardButton.Ok
            )

    def clear_history(self):
        reply = QMessageBox.question(
            self,
            "Clear History",
            "Are you sure you want to clear download history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.download_history = []
            self.save_history()
            self.update_history_display()
    
    def update_history_display(self):
        self.history_tree.clear()
        if not self.download_history:  # Jika history kosong
            return  # Tidak perlu melakukan apa-apa jika tidak ada data
            
        for item in self.download_history:
            tree_item = QTreeWidgetItem([
                item.get('title', 'N/A'),
                item.get('date', 'N/A'),
                item.get('format', 'N/A'),
                item.get('output_dir', 'N/A'),
                item.get('status', 'Completed')
            ])
            self.history_tree.addTopLevelItem(tree_item)
            
    def save_history(self):
        # This method should be implemented in the main class
        if self.parent:
            self.parent.save_history()
            
    def set_download_history(self, history, update_display_only=False):
        """Update the download history from parent"""
        self.download_history = history
        if update_display_only:
            self.update_history_display()
        else:
            self.save_history()
