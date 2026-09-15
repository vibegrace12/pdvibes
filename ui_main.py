import sys
import os
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QComboBox, QGroupBox, QTextEdit, 
                             QPushButton, QFileDialog, QDoubleSpinBox, QProgressBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QFont

# Core Prepress Module Pipeline Imports
import pikepdf  
from imposition_engine import ImpositionEngine
from pdf_processor import PdfProcessor


class ImpositionWorker(QThread):
    """
    Dedicated worker thread to run imposition rendering calculations
    without freezing or blocking the responsive PyQt graphical user interface loop.
    """
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(int)

    def __init__(self, plan_data, input_file, output_file):
        super().__init__()
        self.plan_data = plan_data
        self.input_file = input_file
        self.output_file = output_file

        def run(self):
        try:
            self.progress.emit(10)
            engine = ImpositionEngine()
            processor = PdfProcessor()
            
            if not self.input_file or not os.path.exists(self.input_file):
                raise FileNotFoundError("Target source input file path could not be resolved.")
                
            # 1. Open the file to scan its physical length parameters
            with pikepdf.Pdf.open(self.input_file) as temp_pdf:
                actual_page_count = len(temp_pdf.pages)
                
            self.progress.emit(30)
            
            # 2. Generate the dynamic layout maps based on the true input file length
            calculated_plan = engine.execute_imposition_plan(
                total_pages=actual_page_count,
                imposition_type=self.plan_data["imposition_type"],
                target_sheet=self.plan_data["target_sheet"],
                custom_w=self.plan_data["custom_w"],
                custom_h=self.plan_data["custom_h"],
                paper_thickness=self.plan_data["paper_thickness"]
            )
            
            self.progress.emit(60)
            
            # 3. Run the processing engine to build the output file
            processor.apply_imposition(self.input_file, self.output_file, calculated_plan)
            
            self.progress.emit(100)
            self.finished.emit(True, f"Success! Document imposed seamlessly.\nSaved to: {self.output_file}")
        except Exception as e:
            self.finished.emit(False, f"Prepress Pipeline Failure: {str(e)}")


class PreviewCanvas(QWidget):
    """
    Custom vector rendering canvas widget visualizing calculated sheet grids, 
    spine positions, layout orientations, and custom page sequencing.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sheet_data = None
        self.current_side_index = 0
        self.setMinimumSize(400, 300)
        self.setStyleSheet("background-color: #1e1e1e; border: 1px solid #4f4f4f;")

    def update_preview(self, compiled_plan_payload):
        if compiled_plan_payload and compiled_plan_payload.get("configured_sheets"):
            self.sheet_data = compiled_plan_payload["configured_sheets"]
            self.current_side_index = 0
        else:
            self.sheet_data = None
        self.update()

    def set_side(self, index):
        if self.sheet_data and 0 <= index < len(self.sheet_data):
            self.current_side_index = index
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if not self.sheet_data or self.current_side_index >= len(self.sheet_data):
            # Fallback text draw when no data mapping context is active
            painter.setPen(QColor("#7a7a7a"))
            painter.setFont(QFont("Arial", 11, QFont.Weight.Medium))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No active layout preview plan loaded.")
            return

        current_sheet = self.sheet_data[self.current_side_index]
        layout_grid = current_sheet["layout_grid"]
        
        # Calculate dynamic canvas scaling limits to ensure proportional presentation mappings
        canvas_w = self.width() - 40
        canvas_h = self.height() - 40
        sheet_w = current_sheet["broadsheet_width_mm"]
        sheet_h = current_sheet["broadsheet_height_mm"]
        
        scale_x = canvas_w / sheet_w
        scale_y = canvas_h / sheet_h
        scale = min(scale_x, scale_y)
        
        # Center target drawing bounds onto components
        offset_x = (self.width() - (sheet_w * scale)) / 2
        offset_y = (self.height() - (sheet_h * scale)) / 2

        # Render background broadsheet structural border limits
        painter.setBrush(QColor("#fcfcfc"))
        painter.setPen(QPen(QColor("#2d82b7"), 2, Qt.PenStyle.SolidLine))
        sheet_rect = QRectF(offset_x, offset_y, sheet_w * scale, sheet_h * scale)
        painter.drawRect(sheet_rect)

        # Draw grid items
        for cell in layout_grid:
            cell_x = offset_x + (cell["target_x"] * scale)
            cell_y = offset_y + (cell["target_y"] * scale)
            cell_w = cell["target_width"] * scale
            cell_h = cell["target_height"] * scale
            
            cell_rect = QRectF(cell_x, cell_y, cell_w, cell_h)
            
            # Draw standard matrix page boundary rules
            painter.setBrush(QColor("#e8f1f5"))
            painter.setPen(QPen(QColor("#4f4f4f"), 1, Qt.PenStyle.SolidLine))
            painter.drawRect(cell_rect)
            
            # Print page routing identifiers inside cells
            page_num = cell["source_page_index"]
            display_text = f"Page {page_num}" if page_num != -1 else "[Blank]"
            
            painter.setPen(QColor("#1e1e1e") if page_num != -1 else QColor("#993333"))
            font = QFont("Arial", 9, QFont.Weight.Bold)
            painter.setFont(font)
            
            # Draw visual head orientation layout arrows indicating folding directions
            arrow_txt = "↑ HEAD ↑" if cell["rotation"] == 0 else "↓ HEAD ↓ (180°)"
            
            painter.drawText(cell_rect.adjusted(4, 4, -4, -cell_h/2), 
                             Qt.AlignmentFlag.AlignCenter, display_text)
            painter.setFont(QFont("Arial", 7, QFont.Weight.Light))
            painter.drawText(cell_rect.adjusted(4, cell_h/2, -4, -4), 
                             Qt.AlignmentFlag.AlignCenter, arrow_txt)


class PdvibeMainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.engine = ImpositionEngine()
        self.selected_input_pdf = ""
        self.init_ui()

    def init_ui(self):
        # Configure layout styling rules to resemble dark prepress utilities
        self.setStyleSheet("""
            QWidget { background-color: #3c3f41; color: #ffffff; font-family: 'Segoe UI', Arial, sans-serif; }
            QGroupBox { font-weight: bold; border: 1px solid #555555; margin-top: 12px; padding-top: 8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 3px; }
            QComboBox, QDoubleSpinBox { background-color: #2b2b2b; color: #ffffff; border: 1px solid #555555; padding: 4px; border-radius: 3px; }
            QPushButton { background-color: #4b4b4b; color: #ffffff; border: 1px solid #646464; padding: 6px 12px; border-radius: 3px; font-weight: bold; }
            QPushButton:hover { background-color: #5b5b5b; border-color: #2d82b7; }
            QPushButton:pressed { background-color: #2d82b7; }
            QTextEdit { background-color: #2b2b2b; color: #a9b7c6; font-family: monospace; border: 1px solid #555555; border-radius: 3px; }
        """)
        
        main_layout = QHBoxLayout()
        self.setLayout(main_layout)
        
        # ------------------------------------------------------------------
        # LEFT SIDE LAYOUT PANEL: Settings & File Selection Configurations
        # ------------------------------------------------------------------
        left_panel = QVBoxLayout()
        
        # Group 1: Source File I/O Management Controls
        io_group = QGroupBox("File Management")
        io_layout = QVBoxLayout()
        self.btn_select_file = QPushButton("📁 Load Sequential Source PDF")
        self.btn_select_file.clicked.connect(self.handle_file_selection)
        self.lbl_file_status = QLabel("No document target loaded.")
        self.lbl_file_status.setWordWrap(True)
        io_layout.addWidget(self.btn_select_file)
        io_layout.addWidget(self.lbl_file_status)
        io_group.setLayout(io_layout)
        left_panel.addWidget(io_group)

        # Group 2: Core Scheme Controls
        config_group = QGroupBox("Imposition Specifications")
        config_layout = QVBoxLayout()
        
        # Row: Imposition Type Selection State Dropdown
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Imposition Type:"))
        self.combo_type = QComboBox()
        self.combo_type.addItems(["Standard Saddle-Stitch", "2-Up Multi-Signature Saddle-Stitch"])
        self.combo_type.currentIndexChanged.connect(self.sync_signature_dropdown)
        type_layout.addWidget(self.combo_type)
        config_layout.addLayout(type_layout)

        # Row: Signature Size Specification Selector Selection Dropdown
        sig_layout = QHBoxLayout()
        sig_layout.addWidget(QLabel("Signature Size:"))
        self.combo_sig = QComboBox()
        self.combo_sig.currentIndexChanged.connect(self.trigger_plan_calculation)
        sig_layout.addWidget(self.combo_sig)
        config_layout.addLayout(sig_layout)
        
        # Row: Broadside Base Target Framework Matrix Selector
        sheet_layout = QHBoxLayout()
        sheet_layout.addWidget(QLabel("Target Sheet Size:"))
        self.combo_sheet = QComboBox()
        self.combo_sheet.addItems(["A0", "A1", "A2", "A3", "A4", "A5", "Custom"])
        self.combo_sheet.setCurrentText("A2")
        self.combo_sheet.currentIndexChanged.connect(self.toggle_custom_dimension_visibility)
        sheet_layout.addWidget(self.combo_sheet)
		        config_layout.addLayout(sheet_layout)

        # Row: Custom Layout Geometric Boundaries Entry Form Container
        self.custom_dims_widget = QWidget()
        custom_layout = QHBoxLayout()
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.addWidget(QLabel("W (mm):"))
        self.spin_custom_w = QDoubleSpinBox()
        self.spin_custom_w.setRange(10.0, 5000.0)
        self.spin_custom_w.setValue(594.0)
        self.spin_custom_w.valueChanged.connect(self.trigger_plan_calculation)
        custom_layout.addWidget(self.spin_custom_w)
        
        custom_layout.addWidget(QLabel("H (mm):"))
        self.spin_custom_h = QDoubleSpinBox()
        self.spin_custom_h.setRange(10.0, 5000.0)
        self.spin_custom_h.setValue(420.0)
        self.spin_custom_h.valueChanged.connect(self.trigger_plan_calculation)
        custom_layout.addWidget(self.spin_custom_h)
        self.custom_dims_widget.setLayout(custom_layout)
        self.custom_dims_widget.setVisible(False)
        config_layout.addWidget(self.custom_dims_widget)

        # Row: Paper Thickness Shift Control Field Input Elements (Creep)
        creep_layout = QHBoxLayout()
        creep_label = QLabel("Paper Creep (mm):")
        creep_label.setToolTip("Adjusts structural inner margins per page to balance paper fold stack build up thickness.")
        creep_layout.addWidget(creep_label)
        self.spin_creep = QDoubleSpinBox()
        self.spin_creep.setRange(0.00, 10.00)
        self.spin_creep.setSingleStep(0.05)
        self.spin_creep.setDecimals(3)
        self.spin_creep.valueChanged.connect(self.trigger_plan_calculation)
        creep_layout.addWidget(self.spin_creep)
        config_layout.addLayout(creep_layout)

        config_group.setLayout(config_layout)
        left_panel.addWidget(config_group)

        # Group 3: Technical Routing Execution Console log readout
        console_group = QGroupBox("System Prepress Console Output")
        console_layout = QVBoxLayout()
        self.txt_console = QTextEdit()
        self.txt_console.setReadOnly(True)
        console_layout.addWidget(self.txt_console)
        console_group.setLayout(console_layout)
        left_panel.addWidget(console_group)
        
        # Core Command Controls
        self.btn_execute = QPushButton("⚡ Execute Imposition Engine Plan")
        self.btn_execute.setStyleSheet("background-color: #2d82b7; color: white; padding: 10px; font-size: 13px;")
        self.btn_execute.clicked.connect(self.run_imposition_pipeline)
        left_panel.addWidget(self.btn_execute)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        left_panel.addWidget(self.progress_bar)

        main_layout.addLayout(left_panel, stretch=2)
		
		        # ------------------------------------------------------------------
        # RIGHT SIDE LAYOUT PANEL: Live Dynamic Vector Print Preview Area
        # ------------------------------------------------------------------
        right_panel = QVBoxLayout()
        preview_group = QGroupBox("Interactive Live Print Sheet Layout Preview Canvas")
        preview_layout = QVBoxLayout()
        
        # View side toggle switcher elements
        toggle_layout = QHBoxLayout()
        toggle_layout.addWidget(QLabel("Select Active Sheet View:"))
        self.combo_preview_side = QComboBox()
        self.combo_preview_side.currentIndexChanged.connect(self.handle_preview_side_change)
        toggle_layout.addWidget(self.combo_preview_side)
        preview_layout.addLayout(toggle_layout)
        
        # Incorporate visual graph canvas mapping components
        self.canvas = PreviewCanvas()
        preview_layout.addWidget(self.canvas)
        preview_group.setLayout(preview_layout)
        
        # CORRECTED: Nest the preview group in the right panel layout properly
        right_panel.addWidget(preview_group)
        main_layout.addLayout(right_panel, stretch=3)
        
        # Initialize selection behaviors
        self.sync_signature_dropdown()

    def sync_signature_dropdown(self):
        """Maintains dynamic contextual coupling values between choices."""
        self.combo_sig.blockSignals(True)
        self.combo_sig.clear()
        selected_type = self.combo_type.currentText()
        if selected_type == "Standard Saddle-Stitch":
            self.combo_sig.addItem("16-Page Signature (2x4 Grid)", 16)
            self.combo_sig.addItem("8-Page Signature (2x2 Grid)", 8)
            self.combo_sig.addItem("4-Page Signature (1x2 Grid)", 4)
        else:
            self.combo_sig.addItem("8-Page Signature (2x2 Grid)", 8)
            self.combo_sig.addItem("4-Page Signature (1x2 Grid)", 4)
        self.combo_sig.blockSignals(False)
        self.trigger_plan_calculation()

    def toggle_custom_dimension_visibility(self):
        """Displays or hides millimeter values based on selection."""
        is_custom = (self.combo_sheet.currentText() == "Custom")
        self.custom_dims_widget.setVisible(is_custom)
        self.trigger_plan_calculation()

    def handle_file_selection(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Document Stream File", "", "PDF Files (*.pdf)")
        if file_path:
            self.selected_input_pdf = file_path
            self.lbl_file_status.setText(f"Active Source: {os.path.basename(file_path)}")
            self.log_message(f"[LOADED] File target established: {file_path}")
            self.trigger_plan_calculation()

    def trigger_plan_calculation(self):
        """Extracts current configuration inputs and re-computes mapping geometries."""
        simulated_base_count = 32
        imposition_type = self.combo_type.currentText()
        target_sheet = self.combo_sheet.currentText()
        custom_w = self.spin_custom_w.value()
        custom_h = self.spin_custom_h.value()
        paper_thickness = self.spin_creep.value()
        
        plan = self.engine.execute_imposition_plan(
            total_pages=simulated_base_count,
            imposition_type=imposition_type,
            target_sheet=target_sheet,
            custom_w=custom_w,
            custom_h=custom_h,
            paper_thickness=paper_thickness
        )
        
        self.combo_preview_side.blockSignals(True)
        current_selection = self.combo_preview_side.currentText()
        self.combo_preview_side.clear()
        
        for idx, sheet in enumerate(plan["configured_sheets"]):
            label = f"Sig {sheet['signature_index'] + 1} - {sheet['side']}"
            self.combo_preview_side.addItem(label, idx)
            
        index = self.combo_preview_side.findText(current_selection)
        if index >= 0:
            self.combo_preview_side.setCurrentIndex(index)
        else:
            self.combo_preview_side.setCurrentIndex(0)
        self.combo_preview_side.blockSignals(False)
        
        self.canvas.update_preview(plan)
        self.canvas.set_side(self.combo_preview_side.currentData() or 0)
        self.log_message(f"[PLAN MATRIX RECALCULATED] Style: {imposition_type} | Target Framework: {target_sheet} | Creep Offset Applied: {paper_thickness}mm")

    def handle_preview_side_change(self):
        data_idx = self.combo_preview_side.currentData()
        if data_idx is not None:
            self.canvas.set_side(data_idx)

    def log_message(self, message):
        self.txt_console.append(message)

    def run_imposition_pipeline(self):
        """Assembles variables and provisions thread pipelines safely."""
        if not self.selected_input_pdf:
            self.log_message("[ERROR] Cannot execute imposition layout plan: No input file selected.")
            return
            
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Imposed Production Copy", "", "PDF Files (*.pdf)")
        if not save_path:
            return
            
        self.btn_execute.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        
        imposition_type = self.combo_type.currentText()
        target_sheet = self.combo_sheet.currentText()
        
        plan_data = {
            "imposition_type": imposition_type,
            "target_sheet": target_sheet,
            "custom_w": self.spin_custom_w.value(),
            "custom_h": self.spin_custom_h.value(),
            "paper_thickness": self.spin_creep.value()
        }
        
        self.log_message(f"[STARTING WORKER ENGINE] Imposing vector streams to: {save_path}")
        self.worker = ImpositionWorker(plan_data, self.selected_input_pdf, save_path)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self.handle_pipeline_completion)
        self.worker.start()

    def handle_pipeline_completion(self, success, text):
        self.btn_execute.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.log_message(text)
        if success:
            self.log_message("[PIPELINE FINISHED] CorelDRAW compatible vector output generation complete.")

# CORRECTED: Standard double-underscore module wrapper evaluation block
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PdvibeMainWindow()
    window.setWindowTitle("pdvibe — Prepress Production Imposition Software Canvas Suite")
    window.resize(1150, 700)
    window.show()
    sys.exit(app.exec())

