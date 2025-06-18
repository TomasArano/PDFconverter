import os  # file and directory ha
import fitz  # PyMuPDF
import re  # regex 
import argparse  # command line arguments
import shutil  # file operations

def censor_pdf(pdf_path, coordinates_dict, output_dir=None, include_info=True):
    """
    Redact text in a PDF file based on coordinates with horizontal mirroring applied.
    Extracts gender and age information before redaction and adds it back on top.
    Also removes title from PDF metadata.
    
    Args:
        pdf_path (str): Path to the PDF file
        coordinates_dict (dict): Dictionary where keys are page numbers (ignored)
            and values are lists of coordinate tuples (x1, y1, x2, y2)
            representing the areas to redact
        output_dir (str, optional): Directory to save the output file
        include_info (bool): Whether to include gender and age info in the output (default: True)
    
    Returns:
        str: Path to the redacted PDF file, or None if processing failed
    """
    # Generate output filename
    base_name = os.path.basename(pdf_path)
    base_name_no_ext, ext = os.path.splitext(base_name)
    
    if output_dir:
        # Make sure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{base_name_no_ext}_censored{ext}")
    else:
        dir_name = os.path.dirname(pdf_path)
        output_path = os.path.join(dir_name, f"{base_name_no_ext}_censored{ext}")
    
    # Open the PDF file
    doc = fitz.open(pdf_path)
    
    try:
        # Check if the document has at least one page
        if len(doc) == 0:
            print("Error: The PDF file has no pages.")
            return None
        
        # Get the first page
        page = doc[0]
        
        # Check if PDF is scanned (has no extractable text)
        page_text = page.get_text().strip()
        if not page_text:
            print("Error: PDF appears to be scanned (no extractable text found).")
            return None
        
        # Flag to track if we need to create a single-page document
        is_multi_page = len(doc) > 1
        
        # Get page dimensions for coordinate transformation
        page_width = page.rect.width
        page_height = page.rect.height
        #print(f"Page dimensions: {page_width} x {page_height}")
        
        # Collect all rectangles from all pages in the coordinates dictionary
        all_rectangles = []
        for page_num, rect_list in coordinates_dict.items():
            all_rectangles.extend(rect_list)
        
        # Dictionary to store extracted information for each rectangle
        extracted_info = {}
        
        # First pass: Extract text from each rectangle before redaction
        for i, rect in enumerate(all_rectangles):
            #print(f"Processing rectangle: {rect}")
            if len(rect) != 4:
                #print(f"Warning: Invalid rectangle format {rect}. Skipping.")
                continue
            
            # Extract coordinates
            x1, y1, x2, y2 = rect
            
            # Apply horizontal mirroring transformation
            y1_transformed, y2_transformed = page_width - y2, page_width - y1
            
            # Create a rectangle from the transformed coordinates
            redact_rect = fitz.Rect(x1, y1_transformed, x2, y2_transformed)
            
            # Extract text from the rectangle area
            text = page.get_text("text", clip=redact_rect)
            #print(f"Extracted text: {text}")
            
            # Extract gender information
            gender = None
            if "Masculino" in text:
                gender = "Masculino"
            elif "Femenino" in text:
                gender = "Femenino"
                
            # Extract age information using regex
            age = None
            age_match = re.search(r'\((\d+) años\)', text)
            if age_match:
                age = f"({age_match.group(1)} años)"
                
            if gender or age:
                extracted_info[i] = {
                    "rect": redact_rect,
                    "gender": gender,
                    "age": age
                }
                #print(f"Found information: Gender={gender}, Age={age}")
        if not extracted_info:
            #print(f"Error: Could not extract gender or age information from {os.path.basename(pdf_path)}")
            return None
            
        # If this is a multi-page document, create a new document with just the first page
        if is_multi_page:
            print(f"PDF has {len(doc)} pages. Extracting only the first page...")
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=0, to_page=0)
            doc.close()
            doc = new_doc
            page = doc[0]  # Get the page from the new document
        
        # Second pass: Apply redactions
        for i, rect in enumerate(all_rectangles):
            if len(rect) != 4:
                continue
                
            # Extract coordinates
            x1, y1, x2, y2 = rect
            
            # Apply horizontal mirroring transformation
            y1_transformed, y2_transformed = page_width - y2, page_width - y1
            
            # Create a rectangle from the transformed coordinates
            redact_rect = fitz.Rect(x1, y1_transformed, x2, y2_transformed)
            #print(f"Redacting rectangle: {redact_rect}")
            
            # Add a redaction annotation with black fill
            annot = page.add_redact_annot(redact_rect, fill=(0, 0, 0))
            
        # Apply all redactions on this page
        page.apply_redactions()
        
        # Third pass: Add extracted information back on top of redacted areas (if include_info is True)
        if include_info:
            for i, info in extracted_info.items():
                rect = info["rect"]
                text_items = []
                
                if info["gender"]:
                    text_items.append(info["gender"])
                if info["age"]:
                    text_items.append(info["age"])
                    
                if text_items:
                    text = " ".join(text_items)
                    
                    # Position text in the middle of the redaction box
                    text_point = fitz.Point(90, 784)
                    
                    page.insert_text(
                        text_point,
                        text,
                        fontsize=10,
                        color=(1, 1, 1),  # White text
                        rotate=90
                    )
                    #print(f"Added text '{text}' on top of redacted area")
    
        # Save the redacted PDF 
        doc.save(output_path, garbage=4, deflate=True)
        
        if is_multi_page:
            print(f"Redacted first page of multi-page PDF saved as: {output_path}")
        else:
            print(f"Redacted PDF saved as: {output_path}")
        
        return output_path
        
    finally:
        # Always close the document
        doc.close()


def process_pdf_folder(folder_path, coordinates_dict, output_dir=None, include_info=True):
    """
    Process all PDF files in a folder, applying censorship to each one.
    
    Args:
        folder_path (str): Path to the folder containing PDF files
        coordinates_dict (dict): Dictionary of coordinates for redaction
        output_dir (str, optional): Custom output directory
        include_info (bool): Whether to include gender/age info in output (default: True)
        
    Returns:
        list: List of paths to the redacted PDF files
    """
    # Create output directory
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(folder_path), "Censored PDFs")
    os.makedirs(output_dir, exist_ok=True)
    
    # Create failed files directory
    failed_dir = os.path.join(output_dir, "Failed")
    
    # List to store paths of processed files
    processed_files = []
    # List to store names of failed files with reasons
    failed_files = []
    
    # Check if folder exists
    if not os.path.exists(folder_path):
        print(f"Error: Folder '{folder_path}' does not exist.")
        return processed_files
    
    # Process each PDF file in the folder
    for file_name in os.listdir(folder_path):
        if file_name.lower().endswith('.pdf'):
            pdf_path = os.path.join(folder_path, file_name)
            try:
                #print(f"Processing file: {file_name}")
                output_path = censor_pdf(pdf_path, coordinates_dict, output_dir, include_info)
                if output_path:
                    processed_files.append(output_path)
                else:
                    # If censor_pdf returns None, it means processing failed
                    failed_files.append(file_name)
                    # Copy failed file to Failed folder
                    os.makedirs(failed_dir, exist_ok=True)
                    failed_file_path = os.path.join(failed_dir, file_name)
                    shutil.copy2(pdf_path, failed_file_path)
            except Exception as e:
                print(f"Error processing {file_name}: {str(e)}")
                failed_files.append(file_name)
                # Copy failed file to Failed folder
                os.makedirs(failed_dir, exist_ok=True)
                failed_file_path = os.path.join(failed_dir, file_name)
                shutil.copy2(pdf_path, failed_file_path)
    
    print(f"Processed {len(processed_files)} PDF files. Saved to: {output_dir}")
    
    # Print list of failed files if any
    if failed_files:
        print(f"Failed to process {len(failed_files)} files (copied to {failed_dir}):")
        for failed_file in failed_files:
            print(f"  - {failed_file}")
    
    return processed_files


# Example usage
if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Censor PDF files.')
    
    # Input options group
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--folder', '-f', help='Path to the folder containing PDF files to censor')
    input_group.add_argument('--file', help='Path to a single PDF file to censor')
    
    # Output directory option (optional)
    parser.add_argument('--output', '-o', help='Custom output directory for censored PDFs')
    
    # Add option to control whether gender/age info is included
    parser.add_argument('--no-info', action='store_true',
                       help='Do not include gender and age information in the censored PDFs')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Determine whether to include info (default is True unless --no-info is specified)
    include_info = not args.no_info
    
    # Default coordinates
    coordinates = { 
        0: [(39.2821, 7.81606, 95.3558, 107.861)],
        1: [(21.7321, 7.99649, 37.7421, 268.27)],
        2: [(568.015, 688.962, 584.025, 767.536)]
    }
    
    # Process based on input type
    if args.folder:
        output_dir = args.output if args.output else None
        folder_path = args.folder
        processed_files = process_pdf_folder(folder_path, coordinates, output_dir, include_info)
    elif args.file:
        output_dir = args.output if args.output else None
        redacted_pdf = censor_pdf(args.file, coordinates, output_dir, include_info)
