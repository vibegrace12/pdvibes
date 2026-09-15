
import math
from typing import List, Dict, Any, Tuple

class ImpositionEngine:
    def __init__(self):
        # Dictionary defining standard ISO A-Series dimensions in millimeters (Width, Height)
        self.a_series_dimensions = {
            "A0": (841.0, 1189.0),
            "A1": (594.0, 841.0),
            "A2": (420.0, 594.0),
            "A3": (297.0, 420.0),
            "A4": (210.0, 297.0),
            "A5": (148.0, 210.0)
        }

    def get_sheet_dimensions(self, choice: str, custom_w: float = 0.0, custom_h: float = 0.0) -> Tuple[float, float]:
        """Returns broadsheet width and height in millimeters based on selection."""
        if choice == "Custom" or choice not in self.a_series_dimensions:
            return float(custom_w), float(custom_h)
        return self.a_series_dimensions[choice]

    def calculate_padded_page_count(self, total_pages: int, signature_size: int) -> int:
        """Calculates total required pages by filling up incomplete signature blocks with blanks."""
        remainder = total_pages % signature_size
        if remainder == 0:
            return total_pages
        return total_pages + (signature_size - remainder)

    def generate_saddle_stitch_16_map(self, total_pages: int) -> List[Dict[str, Any]]:
        """
        Generates standard booklet mapping arrays in groups of 16 pages.
        Grid Layout per signature sheet: 2 Rows x 4 Columns (Front & Back).
        """
        signature_size = 16
        working_count = self.calculate_padded_page_count(total_pages, signature_size)
        sheets = []
        
        # Calculate total number of 16-page signatures needed
        num_signatures = working_count // signature_size
        
        for sig_idx in range(num_signatures):
            # Calculate outer bounds for current saddle stitch signature block
            # Pages wrap from outermost edges toward the spine channel
            low_start = (sig_idx * (signature_size // 2)) + 1
            high_end = working_count - (sig_idx * (signature_size // 2))
            
            # Local mapping sequence tracking for a single 16-page unit block
            # 1 maps to absolute low_start, 16 maps to absolute high_end
            def get_pg(local_idx: int) -> int:
                if local_idx in:
                    # Odd local allocations build up from bottom
                    offset = (local_idx - 1) // 2
                    val = low_start + offset
                else:
                    # Even local allocations descend from top
                    offset = (local_idx // 2) - 1
                    val = high_end - offset
                return val if val <= total_pages else -1 # Return -1 for dynamic blank padding markers

            # Front Side Sheet Matrix Structuring (2 Rows x 4 Columns)
            front_sheet = {
                "side": "Front",
                "signature_index": sig_idx,
                "rows": 2,
                "cols": 4,
                # Top Row requires 180 degree rotation around geometric page bounds
                "matrix": [
                    {"page": get_pg(12), "rotate": 180},
                    {"page": get_pg(5),  "rotate": 180},
                    {"page": get_pg(8),  "rotate": 180},
                    {"page": get_pg(9),  "rotate": 180},
                    {"page": get_pg(4),  "rotate": 0},
                    {"page": get_pg(13), "rotate": 0},
                    {"page": get_pg(16), "rotate": 0},
                    {"page": get_pg(1),  "rotate": 0}
                ]
            }
            
            # Back Side Sheet Matrix Structuring (2 Rows x 4 Columns)
            back_sheet = {
                "side": "Back",
                "signature_index": sig_idx,
                "rows": 2,
                "cols": 4,
                "matrix": [
                    {"page": get_pg(10), "rotate": 180},
                    {"page": get_pg(7),  "rotate": 180},
                    {"page": get_pg(6),  "rotate": 180},
                    {"page": get_pg(11), "rotate": 180},
                    {"page": get_pg(2),  "rotate": 0},
                    {"page": get_pg(15), "rotate": 0},
                    {"page": get_pg(14), "rotate": 0},
                    {"page": get_pg(3),  "rotate": 0}
                ]
            }
            sheets.extend([front_sheet, back_sheet])
            
        return sheets

    def generate_twoup_saddle_stitch_8_map(self, total_pages: int) -> List[Dict[str, Any]]:
        """
        Generates 2-Up Split Booklet mapping arrays in groups of 8 pages.
        Grid Layout per signature sheet: 2 Rows x 2 Columns (Front & Back).
        """
        signature_size = 8
        working_count = self.calculate_padded_page_count(total_pages, signature_size)
        sheets = []
        
        num_signatures = working_count // signature_size
        
        for sig_idx in range(num_signatures):
            # Dynamic booklet calculation framework based on 32-page reference model mapping arrays
            # Mapping tracks values spanning inward from book endpoints
            k = sig_idx * 2
            
            p32 = working_count - k
            p1  = 1 + k
            p4  = 4 + k
            p29 = working_count - 3 - k
            p30 = working_count - 2 - k
            p3  = 3 + k
            p2  = 2 + k
            p31 = working_count - 1 - k

            # Verify constraints against absolute ceiling bounds to enforce correct blank generation
            def check(p: int) -> int:
                return p if p <= total_pages else -1

            front_sheet = {
                "side": "Front",
                "signature_index": sig_idx,
                "rows": 2,
                "cols": 2,
                "matrix": [
                    {"page": check(p4),  "rotate": 180}, {"page": check(p29), "rotate": 180},
                    {"page": check(p32), "rotate": 0},   {"page": check(p1),  "rotate": 0}
                ]
            }
            
            back_sheet = {
                "side": "Back",
                "signature_index": sig_idx,
                "rows": 2,
                "cols": 2,
                "matrix": [
                    {"page": check(p30), "rotate": 180}, {"page": check(p3),  "rotate": 180},
                    {"page": check(p2),  "rotate": 0},   {"page": check(p31), "rotate": 0}
                ]
            }
            sheets.extend([front_sheet, back_sheet])
            
        return sheets

    def calculate_grid_coordinates(self, 
                                   sheet_w: float, 
                                   sheet_h: float, 
                                   rows: int, 
                                   cols: int, 
                                   col_idx: int, 
                                   row_idx: int,
                                   creep_shift: float = 0.0) -> Dict[str, float]:
        """
        Computes accurate X/Y structural grid coordinate boundary offsets.
        Applies a progressive creep shift to the horizontal (X) axis near structural fold lines.
        """
        # Distribute broadsheet real estate across planned row/column structures
        cell_width = sheet_w / cols
        cell_height = sheet_h / rows
        
        # Calculate standard bounding origins
        x_start = col_idx * cell_width
        y_start = row_idx * cell_height
        
        # Determine spine proximity to calculate custom creep layout directions
        # Outer pages move outward slightly, inner pages shift inward to avoid creep trimming
        mid_column = cols / 2.0
        if (col_idx + 0.5) < mid_column:
            # Left half of broadside shifts rightward toward center margins
            x_start += creep_shift
        else:
            # Right half of broadside shifts leftward toward center margins
            x_start -= creep_shift
            
        return {
            "x": x_start,
            "y": y_start,
            "width": cell_width,
            "height": cell_height
        }

    def execute_imposition_plan(self, 
                                total_pages: int, 
                                imposition_type: str, 
                                target_sheet: str, 
                                custom_w: float = 0.0, 
                                custom_h: float = 0.0,
                                paper_thickness: float = 0.0) -> Dict[str, Any]:
        """
        Main orchestration function. Builds complete layout coordinates for the transformation engine pipeline.
        """
        sheet_w, sheet_h = self.get_sheet_dimensions(target_sheet, custom_w, custom_h)
        
        if imposition_type == "Standard Saddle-Stitch":
            sheets_data = self.generate_saddle_stitch_16_map(total_pages)
            total_sheets = len(sheets_data) // 2
        else:
            sheets_data = self.generate_twoup_saddle_stitch_8_map(total_pages)
            total_sheets = len(sheets_data) // 2

        compiled_sheets = []
        
        for sheet_data in sheets_data:
            sig_idx = sheet_data["signature_index"]
            rows = sheet_data["rows"]
            cols = sheet_data["cols"]
            matrix = sheet_data["matrix"]
            
            # Creep Math Formula: shift = (total_sheets_in_signature - current_sheet_index) * thickness
            # Inner sheets scale progress tracking downward
            current_sheet_layer = sig_idx
            creep_compensation = (total_sheets - current_sheet_layer) * paper_thickness
            
            # ... Loop initialization for each sheet layout ...
            calculated_cells = []
            
            for index, item in enumerate(matrix):
                row_idx = index // cols
                col_idx = index % cols
                
                coords = self.calculate_grid_coordinates(
                    sheet_w=sheet_w,
                    sheet_h=sheet_h,
                    rows=rows,
                    cols=cols,
                    col_idx=col_idx,
                    row_idx=row_idx,
                    creep_shift=creep_compensation
                )
                
                # 1. This appends every individual cell coordinate mapping into the grid array
                calculated_cells.append({
                    "source_page_index": item["page"],
                    "rotation": item["rotate"],
                    "target_x": coords["x"],
                    "target_y": coords["y"],
                    "target_width": coords["width"],
                    "target_height": coords["height"]
                })
                
            # 2. This appends the completed sheet configuration layout to the signature tracker list
            compiled_sheets.append({
                "side": sheet_data["side"],
                "signature_index": sig_idx,
                "broadsheet_width_mm": sheet_w,
                "broadsheet_height_mm": sheet_h,
                "layout_grid": calculated_cells
            })
            
        # 3. This final payload returns the dictionary tracking data out of the engine
        return {
            "imposition_type": imposition_type,
            "target_sheet_size": target_sheet,
            "configured_sheets": compiled_sheets
        }
