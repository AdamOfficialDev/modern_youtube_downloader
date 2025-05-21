from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QFrame, QLineEdit,
                           QLabel, QComboBox, QTreeWidget, QPushButton,
                           QTreeWidgetItem, QFileDialog, QDialog,
                           QProgressBar, QMessageBox, QMenu, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
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
                file.write("Title,Date,Format,Output Directory,Status,URL\n")

                # Write data
                for item in self.history_data:
                    file.write(f"{item.get('title', 'N/A')},{item.get('date', 'N/A')},"
                             f"{item.get('format', 'N/A')},{item.get('output_dir', 'N/A')},"
                             f"{item.get('status', 'Completed')},{item.get('url', 'N/A')}\n")

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
        self.history_tree.setHeaderLabels(["Title", "Date", "Format", "Output Directory", "Status", "URL"])
        self.history_tree.setColumnWidth(0, 250)  # Title
        self.history_tree.setColumnWidth(1, 150)  # Date
        self.history_tree.setColumnWidth(2, 120)  # Format
        self.history_tree.setColumnWidth(3, 180)  # Output Directory
        self.history_tree.setColumnWidth(4, 100)  # Status
        self.history_tree.setColumnWidth(5, 250)  # URL
        self.history_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_tree.customContextMenuRequested.connect(self.show_context_menu)
        # Connect double-click to open URL
        self.history_tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        # Enable multiple selection
        self.history_tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)

        # Control buttons
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)

        export_button = QPushButton("Export to CSV")
        export_button.clicked.connect(self.export_history)
        clear_button = QPushButton("Clear History")
        clear_button.clicked.connect(self.clear_history)
        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.clicked.connect(self.delete_selected_items)
        self.delete_button.setEnabled(False)  # Disable initially until selection is made

        # Connect selection changed signal
        self.history_tree.itemSelectionChanged.connect(self.on_selection_changed)

        button_layout.addWidget(export_button)
        button_layout.addStretch()
        button_layout.addWidget(self.delete_button)
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
            url_match = search_text in item.get('url', '').lower()
            if not (title_match or format_match or url_match) and search_text:
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
                item.get('status', 'Completed'),
                item.get('url', 'N/A')
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
            # Clear local history list
            self.download_history = []

            # If we have a parent, update its history list directly
            if self.parent and hasattr(self.parent, 'download_history'):
                self.parent.download_history = []

            # Save the empty history to file
            self.save_history()

            # Update the display
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
                item.get('status', 'Completed'),
                item.get('url', 'N/A')
            ])

            # Set tooltip for URL column to show full URL on hover
            url = item.get('url', 'N/A')
            if url and url != 'N/A':
                tree_item.setToolTip(5, f"Double-click to open: {url}")

            self.history_tree.addTopLevelItem(tree_item)

    def on_item_double_clicked(self, item, column):
        """Handle double-click on history item to open URL"""
        # Get the URL from column 5 (URL column)
        url = item.text(5)

        # Only try to open valid URLs
        if url and url != "N/A":
            try:
                # Use QDesktopServices to open the URL in the default browser
                from PyQt6.QtGui import QDesktopServices
                from PyQt6.QtCore import QUrl
                QDesktopServices.openUrl(QUrl(url))
            except Exception as e:
                # Show error message if URL can't be opened
                QMessageBox.warning(
                    self,
                    "Error Opening URL",
                    f"Could not open URL: {str(e)}",
                    QMessageBox.StandardButton.Ok
                )

    def save_history(self):
        # This method should be implemented in the main class
        if self.parent and hasattr(self.parent, 'save_history'):
            # Make sure parent's download_history is synchronized with ours
            if hasattr(self.parent, 'download_history'):
                self.parent.download_history = self.download_history

            # Call parent's save_history method
            self.parent.save_history()

    def set_download_history(self, history, update_display_only=False):
        """Update the download history from parent"""
        self.download_history = history
        if update_display_only:
            self.update_history_display()
        else:
            self.save_history()

    def show_context_menu(self, position):
        """Show context menu for history items"""
        menu = QMenu()

        # Get selected items
        selected_items = self.history_tree.selectedItems()

        # Create actions
        if selected_items:
            # If items are selected, show delete option
            if len(selected_items) == 1:
                delete_text = "Delete Selected Item"

                # Add Copy URL option for single selection
                copy_url_action = menu.addAction("Copy URL")

                # Get the URL from the selected item (column 5 is URL)
                selected_url = selected_items[0].text(5)
                if selected_url == "N/A":
                    copy_url_action.setEnabled(False)
            else:
                delete_text = f"Delete {len(selected_items)} Selected Items"

            delete_action = menu.addAction(delete_text)
            menu.addSeparator()

        # Always show these options
        select_all_action = menu.addAction("Select All")

        # Only add deselect if items are selected
        if selected_items:
            deselect_action = menu.addAction("Deselect All")

        # Execute menu
        action = menu.exec(self.history_tree.mapToGlobal(position))

        # Handle actions
        if selected_items and action == delete_action:
            self.delete_selected_items()
        elif action == select_all_action:
            self.history_tree.selectAll()
        elif selected_items and action == deselect_action:
            self.history_tree.clearSelection()
        elif len(selected_items) == 1 and action == copy_url_action and selected_url != "N/A":
            # Copy URL to clipboard
            clipboard = QApplication.clipboard()
            clipboard.setText(selected_url)
            # Show a brief status message
            self.parent.status_label.setText("URL copied to clipboard")
            # Reset status message after 3 seconds
            QTimer.singleShot(3000, lambda: self.parent.status_label.setText(""))

    def on_selection_changed(self):
        """Update delete button based on selection"""
        selected_items = self.history_tree.selectedItems()
        count = len(selected_items)

        if count == 0:
            self.delete_button.setText("Delete Selected")
            self.delete_button.setEnabled(False)
        elif count == 1:
            self.delete_button.setText("Delete Selected Item")
            self.delete_button.setEnabled(True)
        else:
            self.delete_button.setText(f"Delete {count} Selected Items")
            self.delete_button.setEnabled(True)

    def delete_selected_items(self):
        """Delete selected history items"""
        selected_items = self.history_tree.selectedItems()

        if not selected_items:
            return

        # Create appropriate message based on count
        count = len(selected_items)
        if count == 1:
            message = "Are you sure you want to delete the selected item?"
        else:
            message = f"Are you sure you want to delete {count} selected items?"

        reply = QMessageBox.question(
            self,
            "Delete History Items",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Get the indices of selected items
            items_to_delete = []

            # Debug information
            print(f"Selected items: {len(selected_items)}")
            print(f"History items: {len(self.download_history)}")

            # Get all displayed items in the tree
            all_items = []
            for i in range(self.history_tree.topLevelItemCount()):
                all_items.append(self.history_tree.topLevelItem(i))

            # For each selected item, find its index in the tree
            for item in selected_items:
                # Find the index of this item in the tree
                for i, tree_item in enumerate(all_items):
                    if tree_item is item:  # Compare object identity
                        # If we found the item, add its index to the delete list
                        if i < len(self.download_history):
                            items_to_delete.append(i)
                            print(f"Adding index {i} to delete list")
                        break

            # Delete items from highest index to lowest to avoid index shifting
            for index in sorted(items_to_delete, reverse=True):
                if 0 <= index < len(self.download_history):
                    del self.download_history[index]

            # Save changes and update display
            self.save_history()
            self.update_history_display()
