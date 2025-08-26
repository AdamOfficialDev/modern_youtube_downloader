#!/usr/bin/env python3
"""
Demo script to show the professional tab design
This creates a simple PyQt6 application to demonstrate the new tab styling
"""

import sys
import os

# Add the system PyQt6 path
sys.path.insert(0, '/usr/lib/python3/dist-packages')

try:
    from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QLabel
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QPalette, QColor
except ImportError as e:
    print(f"PyQt6 not available: {e}")
    print("This demo requires PyQt6 to be installed")
    sys.exit(1)


class ProfessionalTabsDemo(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Professional Tab Design Demo - Modern Video Downloader")
        self.setMinimumSize(900, 600)
        
        # Create tab widget
        self.tabs = QTabWidget()
        
        # Apply professional tab styling
        self.apply_professional_tab_style()
        
        # Create demo tabs
        for i, (name, content) in enumerate([
            ("Download", "Single video download interface"),
            ("Batch", "Batch download interface"),
            ("Search", "Video search interface"),
            ("History", "Download history interface"),
            ("Bot", "Telegram bot interface"),
            ("Settings", "Application settings")
        ]):
            tab = QWidget()
            layout = QVBoxLayout(tab)
            label = QLabel(f"This is the {name} tab\n\n{content}")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("font-size: 16px; color: #666;")
            layout.addWidget(label)
            self.tabs.addTab(tab, name)
        
        # Set default to Settings tab (as in original)
        self.tabs.setCurrentIndex(5)
        
        # Set as central widget
        self.setCentralWidget(self.tabs)
        
        # Apply light theme by default
        self.apply_light_theme()
    
    def apply_professional_tab_style(self):
        """Apply professional, clean and elegant tab styling"""
        professional_style = """
            QTabWidget::pane {
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                margin-top: -1px;
                background-color: #fafafa;
            }
            
            QTabBar::tab {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                            stop: 0 #f8f9fa, stop: 1 #e9ecef);
                border: 1px solid #d0d0d0;
                border-bottom-color: transparent;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                min-width: 80px;
                padding: 10px 16px;
                margin-right: 2px;
                font-weight: 500;
                font-size: 13px;
                color: #495057;
            }
            
            QTabBar::tab:selected {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                            stop: 0 #ffffff, stop: 1 #f8f9fa);
                border-color: #007bff;
                border-bottom-color: #fafafa;
                color: #007bff;
                font-weight: 600;
            }
            
            QTabBar::tab:disabled {
                color: #adb5bd;
                background: #f8f9fa;
                border-color: #dee2e6;
            }
            
            QTabBar::tab:hover:!selected {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                            stop: 0 #ffffff, stop: 1 #f1f3f4);
                border-color: #6c757d;
                color: #343a40;
            }
        """
        self.tabs.setStyleSheet(professional_style)
    
    def apply_light_theme(self):
        """Apply light theme to the window"""
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(245, 245, 245))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
        palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.white)
        self.setPalette(palette)


def main():
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    window = ProfessionalTabsDemo()
    window.show()
    
    # Create a demo info message
    print("=== Professional Tab Design Demo ===")
    print("Features:")
    print("- Clean, modern tab design with subtle gradients")
    print("- Professional color scheme")
    print("- Elegant hover effects")
    print("- Proper spacing and typography")
    print("- Tab names simplified for better UX")
    print("- Clean borders and rounded corners")
    print("\nChanges made:")
    print("- 'Single Download' → 'Download'")
    print("- 'Batch Download' → 'Batch'") 
    print("- 'Telegram Bot' → 'Bot'")
    print("- Other tabs remain the same")
    print("\nThe Settings tab content is unchanged as requested.")
    print("=====================================")
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()