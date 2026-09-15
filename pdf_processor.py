import os
import pikepdf
from typing import Dict, Any

class PdfProcessor:
    def __init__(self):
        pass

    def apply_imposition(self, input_pdf_path: str, output_pdf_path: str, plan: Dict[str, Any]) -> bool:
        """
        Reads the input sequential PDF and constructs a target broadsheet layout 
        using mathematical matrix transformations. All elements remain editable in CorelDRAW.
        """
        if not os.path.exists(input_pdf_path):
            raise FileNotFoundError(f"Source file not found at: {input_pdf_path}")

        # Open the source document via pikepdf to protect vector layers and color channels
        with pikepdf.Pdf.open(input_pdf_path) as src_pdf:
            total_input_pages = len(src_pdf.pages)
            
            # Create a completely blank target document container
            with pikepdf.Pdf.new() as dest_pdf:
                configured_sheets = plan.get("configured_sheets", [])
                
                for sheet in configured_sheets:
                    # 1. Convert broadsheet dimensions from millimeters to standard PostScript points (1 mm = 2.83465 points)
                    sheet_w_pts = sheet["broadsheet_width_mm"] * 2.83465
                    sheet_h_pts = sheet["broadsheet_height_mm"] * 2.83465
                    
                    # 2. Create a blank broadsheet page with the target dimensions
                    broadsheet_page = dest_pdf.add_blank_page(page_size=(sheet_w_pts, sheet_h_pts))
                    
                    # 3. Iterate through the grid layout configuration to place each page
                    for cell in sheet["layout_grid"]:
                        pg_idx = cell["source_page_index"]
                        
                        # Skip placement logic if this cell is designated as an auto-padded blank page
                        if pg_idx == -1 or pg_idx > total_input_pages:
                            continue
                            
                        # Extract the target page reference (converting 1-based prepress index to 0-based index)
                        src_page = src_pdf.pages[pg_idx - 1]
                        
                        # 4. Read source page dimensions
                        src_w = float(src_page.mediabox[2] - src_page.mediabox[0])
                        src_h = float(src_page.mediabox[3] - src_page.mediabox[1])
                        
                        # Convert cell placement boundaries to points
                        target_x = cell["target_x"] * 2.83465
                        target_y = cell["target_y"] * 2.83465
                        target_w = cell["target_width"] * 2.83465
                        target_h = cell["target_height"] * 2.83465
                        
                        # 5. Compute the scaling factor required to fit the page into the layout grid box
                        scale_x = target_w / src_w
                        scale_y = target_h / src_h
                        scale = min(scale_x, scale_y)
                        
                        # Center the scaled page inside the layout cell bounding box
                        pad_x = (target_w - (src_w * scale)) / 2.0
                        pad_y = (target_h - (src_h * scale)) / 2.0
                        final_x = target_x + pad_x
                        final_y = target_y + pad_y
                        
                        # 6. Formulate the affine transformation matrix array
                        # Base array structure template: [a, b, c, d, e, f]
                        if cell["rotation"] == 180:
                            # 180-degree rotation: scale negatively and shift back into the frame bounding box
                            a = -scale
                            b = 0.0
                            c = 0.0
                            d = -scale
                            e = final_x + (src_w * scale)
                            f = final_y + (src_h * scale)
                        else:
                            # Standard 0-degree placement orientation
                            a = scale
                            b = 0.0
                            c = 0.0
                            d = scale
                            e = final_x
                            f = final_y
                            
                        # 7. Inject the page non-destructively as a Form XObject
                        # This retains underlying vector properties, CMYK profiles, and text strings intact
                        broadsheet_page.add_underlay(src_page, pikepdf.Transformation(a, b, c, d, e, f))
                        
                # Write the assembled prepress payload down to disk safely
                dest_pdf.save(output_pdf_path)
                
        return True
