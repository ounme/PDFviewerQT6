
import sys
import json
from PyQt6.QtWidgets import QVBoxLayout, QMessageBox, QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem, QWidget, QListWidgetItem, QListWidget, QGraphicsView, QGraphicsScene, QHBoxLayout, QPushButton, QFileDialog
from PyQt6.QtGui import QColor, QImage, QPixmap, QAction, qGray, qRgb, qRed, qGreen, qBlue, QVector4D
from PyQt6.QtCore import Qt
from collections import OrderedDict
import time
import fitz  # PyMuPDF
from qtoggle import QToggle
import numpy as np

from concurrent.futures import ThreadPoolExecutor



class PDFReader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_page = 0  # Current page of the PDF
        self.current_file = ""  # Currently open PDF file
        self.zoom_factor = 1.0  # Page scale
        self.last_page = -1  # Last page of the PDF (default -1 to indicate pages are not yet loaded)
        self.history_file = 'history.json'   # File for storing history
        self.history = OrderedDict()  # History of opened documents (maintaining order)
        self.dark_pdf_enabled = False   # Flag to track the state of PDF inversion mode
        self.initUI()

    def initUI(self):
        """Initialize the user interface."""
        self.setWindowTitle('PDF Reader')  # Set window title
        self.load_pdf_action = QAction("Open PDF", self)
        self.load_pdf_action.triggered.connect(self.openFile)
        self.menuBar().addAction(self.load_pdf_action)

        layout = QHBoxLayout()  # Horizontal layout
        
        layout.setSpacing(0)   # Set spacing between elements to  0 pixels
        layout.setContentsMargins(0,0,0,0)
        
        centralWidget = QWidget()   # Central widget to hold the layout
        centralWidget.setLayout(layout)  # Set layout to central widget

        self.sideWidget = QWidget()
        sideLayout = QVBoxLayout(self.sideWidget)

        self.dark_mode_toggle = QToggle(self)
        self.dark_mode_toggle.setText(" Dark Mode")
        self.dark_mode_toggle.toggled.connect(self.toggleDarkMode)   # Connect signal to slot for theme toggle
        sideLayout.addWidget(self.dark_mode_toggle)

        self.dark_PDF_toggle = QToggle(self)
        self.dark_PDF_toggle.setText(" Dark PDF")
        self.dark_PDF_toggle.toggled.connect(self.toggleDarkPDF) # Connect signal to slot for PDF inversion toggle
        sideLayout.addWidget(self.dark_PDF_toggle)

        self.treeWidget = QTreeWidget()  # Use QTreeWidget to display table of contents
        self.treeWidget.setHeaderLabel('Contents')   # Set header for QTreeWidget
        self.header = self.treeWidget.header()

        self.treeWidget.itemClicked.connect(self.onTreeItemClicked)  # Connect itemClicked signal to handler



        self.graphicsView = QGraphicsView()  # Use QGraphicsView to display PDF pages

        
        layout.addWidget(self.sideWidget, 10)
        layout.addWidget(self.graphicsView, 70)  # QGraphicsView takes 70% of the window width
        layout.addWidget(self.treeWidget, 20)  # QTreeWidget takes 20% of the window width

        self.setCentralWidget(centralWidget)  # Set central widget in the main window
        self.setMinimumSize(800, 600)  # Set minimum window size

        self.loadHistory()  # Load history on startup

        if self.history:
            last_opened_file = list(self.history.keys())[-1]  # Get the last opened file from history
            last_page = self.history[last_opened_file]  # Get the page where the last document was stopped
            self.openFile(last_opened_file, last_page)  # Open the last document on startup

    def toggleDarkMode(self, checked):
        # Logic to toggle between dark mode and light mode
        if checked:
            # Enable dark mode
            self.graphicsView.setBackgroundBrush(Qt.GlobalColor.darkGray)   # Set black background
            self.treeWidget.setStyleSheet("QTreeWidget { background-color: #333; color: #FFF; border: 0px solid;}")  # Modify table of contents styles
            
            
            self.sideWidget.setStyleSheet("background-color: #333;")  # Set background color
            self.dark_mode_toggle._text_color = QColor("#FFF")   # Set white button text color
            self.dark_PDF_toggle._text_color = QColor("#FFF")

            self.header.setStyleSheet("QHeaderView::section { background-color: #333; color: #FFF; }")  # Set styles for QTreeWidget header
            self.dark_mode_toggle.setText(" Light Mode")

        else:
            # Enable light mode
            self.graphicsView.setBackgroundBrush(Qt.GlobalColor.gray)  # Set gray background
            self.treeWidget.setStyleSheet("QTreeWidget { background-color: #FFF; color: #000;  border: 0px solid;}")   # Modify table of contents styles
            self.sideWidget.setStyleSheet("background-color: #FFF;")
            self.dark_mode_toggle._text_color = QColor("#000")
            self.dark_PDF_toggle._text_color = QColor("#000")
            # Устанавливаем стили для заголовка QTreeWidget
            self.header.setStyleSheet("QHeaderView::section { background-color: #FFF; color: #000; }")  # Set styles for QTreeWidget header
            self.dark_mode_toggle.setText(" Dark Mode")

    def toggleDarkPDF(self, checked):
        """Toggle logic for PDF inversion mode."""
        self.dark_pdf_enabled = not self.dark_pdf_enabled

        if self.dark_pdf_enabled:
            self.applyDarkPDF()  # Apply PDF inversion mode
        else:
            self.applyLightPDF()   # Disable PDF inversion mode

    def applyDarkPDF(self):
        """Apply inversion effect to the current PDF page."""
        if self.current_file:
            self.showInvertedPage()  # Display page with inversion effect
        else:
            QMessageBox.warning(self, "Warning", "No PDF file is opened.")

    def applyLightPDF(self):
        """Disable inversion effect for the current PDF page."""
        if self.current_file:
            self.showPage()  # Display page without inversion effect
        else:
            QMessageBox.warning(self, "Warning", "No PDF file is opened.")

    def applyWidgetStyleSheet(self, widget, styleSheet):
        """Apply CSS style to a widget and its child elements"""
        widget.setStyleSheet(styleSheet)  # Apply style to the current widget
        for child in widget.findChildren(QWidget):  # Recursively apply style to child elements
            child.setStyleSheet(styleSheet)

    def openFile(self, filePath=None, page=0):
        """Open a PDF file."""
        if not filePath:
            filePath, _ = QFileDialog.getOpenFileName(self, "Open PDF File", "", "PDF Files (*.pdf)")

        if filePath:
            self.current_file = filePath  # Set the current open file
            if filePath in self.history:
                self.current_page = self.history[filePath]['page']   # Load page from history
                self.history[filePath]['last_opened'] = time.time()  # Update last opened time
            else:
                self.history[filePath] = {'page': page, 'last_opened': time.time()}   # Add new document to history
            self.saveHistory()  # Save history
            
            try:
                self.doc = fitz.open(filePath)  # Open the selected PDF file
                self.last_page = len(self.doc) - 1  # Update last_page value to index of last page
                self.current_page = self.history[filePath]['page']  # Set current page from history
                self.showPage()  # Display the PDF page as per history
                self.showContents()  # Display table of contents
            except Exception as e:
                print(f"Error opening file: {e}")

    def showPage(self):
        """Display the current PDF page."""
        page = self.doc.load_page(self.current_page)  # Load the current PDF page
        pixmap = page.get_pixmap(matrix=fitz.Matrix(self.zoom_factor, self.zoom_factor)) # Get the pixmap of the PDF page
        img = QImage(pixmap.samples, pixmap.width, pixmap.height, pixmap.stride, QImage.Format.Format_RGB888) # Create QImage from the pixmap

        # Create QGraphicsScene and add the image to it
        scene = QGraphicsScene()
        scene.addPixmap(QPixmap.fromImage(img))

        # Set the QGraphicsScene to QGraphicsView
        self.graphicsView.setScene(scene)

        # Set drag mode
        self.graphicsView.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)


    def showInvertedPage(self):
        """Display the current PDF page with inversion effect."""
        if self.current_file:
            page = self.doc.load_page(self.current_page)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(self.zoom_factor, self.zoom_factor))

            # Create image from pixmap and invert its colors
            img = QImage(pixmap.samples, pixmap.width, pixmap.height, pixmap.stride, QImage.Format.Format_RGB888)
            inverted_img = self.invertImage(img)

            # Create QGraphicsScene and add the inverted image to it
            scene = QGraphicsScene()
            scene.addPixmap(QPixmap.fromImage(inverted_img))

            # Set the QGraphicsScene to QGraphicsView
            self.graphicsView.setScene(scene)

            # Set drag mode
            self.graphicsView.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def invertImage(self, img):
        """Invert the colors of an image using two threads."""
        if img.format() != QImage.Format.Format_RGB32:
            img = img.convertToFormat(QImage.Format.Format_RGB32)

        width = img.width()
        height = img.height()
        img_bytes = img.bits().asarray(width * height * 4)  # Get image bytes

        # Convert bytes to numpy array
        arr = bytearray(img_bytes)
        arr = np.array(arr, dtype=np.uint8).reshape(height, width, 4)

        # Split array into two halves for parallel processing
        half_height = height // 2
        top_half = arr[:half_height]
        bottom_half = arr[half_height:]

        # Function to invert colors in half of the image
        def invert_half_image(image_data):
            image_data[:, :, 0:3] = 255 - image_data[:, :, 0:3]
            return image_data

        # Use ThreadPoolExecutor to run two threads
        with ThreadPoolExecutor() as executor:
            # Invert top and bottom halves of the image in parallel
            inverted_top_half = executor.submit(invert_half_image, top_half.copy())
            inverted_bottom_half = executor.submit(invert_half_image, bottom_half.copy())

            # Get inversion results from threads
            top_half = inverted_top_half.result()
            bottom_half = inverted_bottom_half.result()

        # Assemble the full inverted image
        arr[:half_height] = top_half
        arr[half_height:] = bottom_half

        # Create a new QImage from the numpy array
        inverted_img = QImage(arr.data, width, height, width * 4, QImage.Format.Format_RGBA8888)

        return inverted_img

    def loadHistory(self):
        try:
            with open(self.history_file, 'r') as f:
                history_list = json.load(f)
                self.history = OrderedDict()
                for item in history_list:
                    self.history[item['file_path']] = {'page': item['page'], 'last_opened': item['last_opened']}
        except FileNotFoundError:
            self.saveHistory()  # If file not found, create a new one

    def saveHistory(self):
        history_list = []
        for path, info in self.history.items():
            history_list.append({'file_path': path, 'page': info['page'], 'last_opened': info['last_opened']})

        with open(self.history_file, 'w') as f:
            json.dump(history_list, f)

    def closeEvent(self, event):
        if self.current_file:  # Check if current file is set
            self.history[self.current_file] = {
                'page': self.current_page,
                'last_opened': time.time()
            }  # Save full details of the current document
            self.saveHistory()  # Save history before closing
        event.accept()
        
    def showContents(self):
        """Displays the table of contents of the PDF."""
        toc = self.doc.get_toc()  # Get the table of contents
        if toc:
            self.treeWidget.clear()  # Clear the QTreeWidget
            self.addContentsEntry(toc)  # Add the table of contents entries

    def addContentsEntry(self, entries):
        """Adds table of contents entries to QTreeWidget with nested structure without recursion."""
        stack = []  # Stack to keep track of parent items at different levels

        for entry in entries:
            level, title, page_num = entry
            item = QTreeWidgetItem([title])  # Create QTreeWidgetItem with title name
            item.setData(0, Qt.ItemDataRole.UserRole, page_num)  # Set page number into item's user data

            if not stack or level==1 :
                # If stack is empty, add current item as top-level
                self.treeWidget.addTopLevelItem(item)
            else:
                # Otherwise determine parent item based on current level
                while stack and stack[-1][0] >= level:
                    stack.pop()  # Pop elements from stack until finding suitable parent

                if stack:
                    parent_item = stack[-1][1]
                    parent_item.addChild(item)  # Add current item as child to found parent

            # Add current item to stack for use as parent on subsequent levels
            stack.append((level, item))

        # Clear stack after processing all items
        stack.clear()



    def findSubEntries(self, entry, sub_level):
        """Find sub-entries for the current level."""
        toc = self.doc.get_toc()
        sub_entries = []
        i = toc.index(entry) + 1
        while i < len(toc):
            if toc[i][0] == sub_level:
                sub_entries.append(toc[i])
                i += 1
            else:
                break
        return sub_entries
    
    def onTreeItemClicked(self, item, column):
        """Handler for clicking on a table of contents item."""
        page_num = item.data(0, Qt.ItemDataRole.UserRole)  # Get page number from item's user data
        if page_num is not None:
            self.current_page = page_num - 1  # Set current page (subtracting 1 for zero-based indexing)
            self.showPage()  # Display the selected PDF page.

    def onContentsClicked(self, item):
        """Обрабатывает нажатие на элемент оглавления."""
        page_num = item.data(Qt.ItemDataRole.UserRole)  # Get page number from user data
        self.current_page = page_num - 1  # Set current page
        self.showPage()  # Display the selected page
        
        # Set scroll position to top upon navigation
        self.graphicsView.verticalScrollBar().setValue(0)

    def wheelEvent(self, event):
        """Handle mouse wheel scroll event for zooming and page flipping."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:  # If Ctrl key is pressed
            delta = event.angleDelta().y() / 120  # Get mouse wheel delta value
            self.zoom_factor += delta * 0.1  # Adjust page scale based on delta
            if self.zoom_factor < 0.1:  # Limit minimum scale
                self.zoom_factor = 0.1
            if self.dark_pdf_enabled:
                self.showInvertedPage()  # Display page with inversion upon scale change
            else:
                self.showPage() # Display page without inversion upon scale change
        else:  # If Ctrl key is not pressed
            if event.angleDelta().y() > 0:  # If mouse wheel is scrolled up
                self.prevPage()   # Go to previous page
            else:  # If mouse wheel is scrolled down
                self.nextPage()  # Go to next page

    def prevPage(self):
        """Go to the previous PDF page."""
        if self.current_page > 0:  # If current page is not the first one
            self.current_page -= 1  # Go to previous page
            if self.dark_pdf_enabled:
                self.showInvertedPage()  # Display previous page with inversion
            else:
                self.showPage()  # Display previous page without inversion
            # Set scroll position to bottom upon going to previous page
            self.graphicsView.verticalScrollBar().setValue(self.graphicsView.verticalScrollBar().maximum())


    def nextPage(self):
        """Go to the next PDF page."""
        if self.current_page < len(self.doc) - 1:  # If current page is not the last one
            self.current_page += 1  # Go to next page
            if self.dark_pdf_enabled:
                self.showInvertedPage()  # Display next page with inversion
            else:
                self.showPage() # Display next page without inversion
            # Set scroll position to top upon going to next page
            self.graphicsView.verticalScrollBar().setValue(0)

def main():
    app = QApplication(sys.argv)
    ex = PDFReader()
    ex.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
