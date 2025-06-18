#!/usr/bin/env python3
"""
ECG PDF Format Validator and Sorter

This script validates a folder of PDF files to check if they contain properly formatted ECGs.
Valid PDFs are copied to format-specific subfolders within the 'Correct' folder,
while invalid ones go to an 'Incorrect' folder.
"""

import os
import shutil
import argparse
from pathlib import Path
import fitz  # PyMuPDF
import re
from collections import Counter

# Define the expected formats
FORMAT1_TITLES = {
    "I": 1,
    "II": 1,
    "III": 1,
    "V1": 2,  # V1 appears twice (once in standard leads and once for rhythm strip)
    "V2": 1,
    "V3": 1,
    "V4": 1,
    "V5": 1,
    "V6": 1,
    "aVR": 1,
    "aVL": 1,
    "aVF": 1
}

FORMAT2_TITLES = {
    "I": 1,
    "II": 2,
    "III": 1,
    "V1": 2,
    "V2": 1,
    "V3": 1,
    "V4": 1,
    "V5": 2,
    "V6": 1,
    "aVR": 1,
    "aVL": 1,
    "aVF": 1
}

# Collect all formats in a dictionary for easy lookup and iteration
ECG_FORMATS = {
    "format1": FORMAT1_TITLES,
    "format2": FORMAT2_TITLES
}

def extract_text_from_first_page(pdf_path):
    """
    Extract text from the first page of a PDF using PyMuPDF's dictionary-based extraction
    which preserves more structural information and handles text better.
    """
    if not os.path.exists(pdf_path):
        print(f"Error: File not found - {pdf_path}")
        return ""
    
    try:
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            print("PDF has no pages")
            doc.close()
            return ""
            
        # Get the first page
        page = doc[0]
        
        # Use dictionary extraction for better text representation
        text_dict = page.get_text("dict")
        
        # Extract all text, preserving some structure
        all_text = ""
        for block in text_dict["blocks"]:
            if block["type"] == 0:  # Text block
                for line in block["lines"]:
                    line_text = ""
                    for span in line["spans"]:
                        line_text += span["text"]
                    all_text += line_text + "\n"
        
        doc.close()
        return all_text
        
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return ""

def check_graph_titles(text, expected_titles):
    """
    Check if the text contains the expected ECG graph titles for a specific format.
    
    Args:
        text (str): The extracted text from the PDF
        expected_titles (dict): The dictionary of expected titles and their counts
        
    Returns:
        dict: Results with validation status and diagnostics
    """
    # Collection for actual counts and diagnostics
    actual_counts = Counter()
    diagnostics = {
        "missing_titles": [],
        "unexpected_counts": {},
        "found_titles": []
    }
    
    # Process text to handle variations
    # Normalize text: uppercase, clean spaces
    processed_text = text.upper()
    
    # Count occurrences with more robust patterns
    for title, expected_count in expected_titles.items():
        title_upper = title.upper()
        
        # Different regex patterns to try:
        patterns = [
            rf'\b{re.escape(title_upper)}\b',  # Standard word boundary
            rf'{re.escape(title_upper)}(?=\s|$|:)',  # Followed by space, end or colon
            rf'(?<=\s|^){re.escape(title_upper)}(?=\s|$|:)',  # Preceded by space or start, followed by space, end or colon
        ]
        
        # Try each pattern
        found = False
        for pattern in patterns:
            matches = re.findall(pattern, processed_text)
            if matches:
                count = len(matches)
                actual_counts[title] = count
                found = True
                break
        
        if not found:
            actual_counts[title] = 0
    
    # Analyze results
    for title, expected_count in expected_titles.items():
        actual_count = actual_counts[title]
        
        if actual_count == 0:
            diagnostics["missing_titles"].append(title)
        elif actual_count != expected_count:
            diagnostics["unexpected_counts"][title] = {
                "expected": expected_count,
                "actual": actual_count
            }
        else:
            diagnostics["found_titles"].append(title)
    
    # Determine if validation passed
    is_valid = (len(diagnostics["missing_titles"]) == 0 and 
                len(diagnostics["unexpected_counts"]) == 0)
    
    return {
        "is_valid": is_valid,
        "actual_counts": dict(actual_counts),
        "expected_counts": expected_titles,
        "diagnostics": diagnostics
    }

def check_all_formats(text):
    """
    Check the text against all defined ECG formats.
    
    Args:
        text (str): The extracted text from the PDF
        
    Returns:
        tuple: (matching_format, validation_results) where matching_format is 
               the name of the matching format or None if no match was found
    """
    matching_format = None
    matching_results = None
    
    for format_name, format_titles in ECG_FORMATS.items():
        results = check_graph_titles(text, format_titles)
        if results["is_valid"]:
            # If we already found a matching format, we have an ambiguity
            if matching_format is not None:
                print(f"Warning: PDF matches multiple formats: {matching_format} and {format_name}")
                return None, None  # Ambiguous format match
            matching_format = format_name
            matching_results = results
    
    return matching_format, matching_results

def validate_ecg_format(pdf_path, verbose=False):
    """
    Validate if a PDF's first page contains the expected ECG graph titles
    for any of the supported formats.
    
    Args:
        pdf_path (str): Path to the PDF file
        verbose (bool): If True, prints detailed diagnostic information
        
    Returns:
        tuple: (matching_format, validation_results) where matching_format is 
               the name of the matching format or None if no match was found
    """
    text = extract_text_from_first_page(pdf_path)
    matching_format, results = check_all_formats(text)
    
    if verbose:
        print(f"\nECG Format Validation Results for: {os.path.basename(pdf_path)}")
        if matching_format:
            print(f"Valid ECG format detected: {matching_format}")
            print(f"Found {len(results['diagnostics']['found_titles'])} correctly matched titles")
        else:
            print("No valid ECG format detected")
            
            # Try each format to show diagnostics
            for format_name, format_titles in ECG_FORMATS.items():
                format_results = check_graph_titles(text, format_titles)
                print(f"\nFormat '{format_name}' validation:")
                
                if format_results['diagnostics']['missing_titles']:
                    print(f"  Missing titles: {', '.join(format_results['diagnostics']['missing_titles'])}")
                
                if format_results['diagnostics']['unexpected_counts']:
                    print("  Unexpected counts:")
                    for title, counts in format_results['diagnostics']['unexpected_counts'].items():
                        print(f"    {title}: expected {counts['expected']}, found {counts['actual']}")
    
    return matching_format, results

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Validate and sort ECG PDF files')
    parser.add_argument('input_folder', help='Folder containing PDF files to process')
    parser.add_argument('--output', '-o', help='Output folder (defaults to script directory)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Print detailed validation results')
    args = parser.parse_args()
    
    # Validate input folder
    input_path = Path(args.input_folder)
    if not input_path.exists() or not input_path.is_dir():
        print(f"Error: Input folder does not exist: {args.input_folder}")
        return 1
    
    # Set up output folder
    if args.output:
        output_path = Path(args.output)
    else:
        # Default to script's directory
        output_path = Path(os.path.dirname(os.path.abspath(__file__)))
    
    # Create output folders with format-specific subfolders
    correct_path = output_path / "Correct"
    incorrect_path = output_path / "Incorrect"
    
    correct_path.mkdir(parents=True, exist_ok=True)
    incorrect_path.mkdir(parents=True, exist_ok=True)
    
    # Create format-specific subfolders
    format_paths = {}
    for format_name in ECG_FORMATS.keys():
        format_path = correct_path / format_name
        format_path.mkdir(exist_ok=True)
        format_paths[format_name] = format_path
    
    print(f"Output folders created:")
    print(f"  Invalid ECGs: {incorrect_path}")
    for format_name, format_path in format_paths.items():
        print(f"  Valid ECGs ({format_name}): {format_path}")
    
    # Get all PDF files in the input folder
    pdf_files = [f for f in input_path.iterdir() if f.is_file() and f.suffix.lower() == '.pdf']
    
    # Statistics
    stats = {
        'total': len(pdf_files),
        'correct': 0,
        'incorrect': 0
    }
    
    # Format-specific stats
    format_stats = {format_name: 0 for format_name in ECG_FORMATS.keys()}
    
    # Process each PDF file
    print(f"\nProcessing {stats['total']} PDF files...")
    
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"[{i}/{stats['total']}] Validating: {pdf_file.name}")
        
        try:
            # Validate the PDF
            matching_format, _ = validate_ecg_format(str(pdf_file), verbose=args.verbose)
            
            # Copy to appropriate folder
            if matching_format:
                stats['correct'] += 1
                format_stats[matching_format] += 1
                dest = format_paths[matching_format] / pdf_file.name
                print(f"✅ Valid ECG ({matching_format}): Copying to {dest}")
                shutil.copy2(pdf_file, dest)
            else:
                stats['incorrect'] += 1
                dest = incorrect_path / pdf_file.name
                print(f"❌ Invalid ECG: Copying to {dest}")
                shutil.copy2(pdf_file, dest)
        except Exception as e:
            stats['incorrect'] += 1
            dest = incorrect_path / pdf_file.name
            print(f"❌ Error validating {pdf_file.name}: {str(e)}")
            print(f"  Treating as invalid and copying to {dest}")
            try:
                shutil.copy2(pdf_file, dest)
            except Exception as copy_err:
                print(f"  Error copying file: {str(copy_err)}")
    
    # Print summary
    print("\n" + "="*50)
    print("ECG Validation Summary:")
    print(f"Total PDFs processed: {stats['total']}")
    if stats['total'] > 0:
        print(f"Valid ECGs: {stats['correct']} ({stats['correct']/stats['total']*100:.1f}%)")
        
        # Explicitly print counts for each format
        format1_count = format_stats.get('format1', 0)
        format2_count = format_stats.get('format2', 0)
        print(f"  - Format 1 ECGs: {format1_count} ({format1_count/stats['total']*100:.1f}% of total)")
        print(f"  - Format 2 ECGs: {format2_count} ({format2_count/stats['total']*100:.1f}% of total)")
        
        print(f"Invalid ECGs: {stats['incorrect']} ({stats['incorrect']/stats['total']*100:.1f}%)")
    else:
        print("No PDF files found to process.")

    print(f"Invalid ECGs saved to: {incorrect_path}")
    for format_name, format_path in format_paths.items():
        print(f"{format_name} ECGs saved to: {format_path}")
    
    return 0

if __name__ == "__main__":
    exit(main())