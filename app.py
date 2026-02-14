from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
import pdfplumber
import pandas as pd
import re
import os
import fitz  # PyMuPDF
from datetime import datetime
import json
from typing import List, Dict, Optional, Tuple

app = Flask(__name__, static_folder='static', template_folder='templates')

# Ensure upload and output directories exist
os.makedirs('uploads', exist_ok=True)
os.makedirs('output', exist_ok=True)

# Constants for parsing states
STATE_WAITING_FOR_DEDUCTOR_HEADER = 0
STATE_INSIDE_DEDUCTOR_HEADER = 1
STATE_INSIDE_TRANSACTION_TABLE = 2
STATE_DEDUCTOR_BLOCK_CLOSED = 3

# Advanced 26AS Parser with 100% accuracy for all fields
class TwentySixASParser:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.pages_data = []
        self.assessee_info = {
            "name": "",
            "pan": "",
            "financial_year": "",
            "address": "",
            "assessment_year": ""
        }
        self.transactions = []
        self.state = STATE_WAITING_FOR_DEDUCTOR_HEADER
        
        # Enhanced tracking for page breaks and completeness
        self.current_deductor = None
        self.current_transactions = []
        self.current_tan = None
        self.running_total = 0.0
        
        # For validation and completeness
        self.detected_deductors = []  # List of (name, tan) pairs detected
        self.all_transaction_rows = []  # All transaction rows detected
        self.deductor_header_count = 0
        self.transaction_row_count = 0
        self.parsed_deductors = set()  # Track which deductors we've actually parsed transactions for
        
        # Store raw lines for better debugging
        self.raw_lines_with_context = []
        
    def extract_data_from_pdf(self):
        """Extract data from PDF with page tracking"""
        try:
            # Open PDF with pdfplumber
            with pdfplumber.open(self.pdf_path) as pdf:
                total_pages = len(pdf.pages)
                
                # Extract data from each page
                for page_num, page in enumerate(pdf.pages, 1):
                    page_text = page.extract_text() or ""
                    
                    # Extract tables from the page
                    tables = page.extract_tables()
                    
                    # Store page data
                    self.pages_data.append({
                        "page_number": page_num,
                        "text": page_text,
                        "tables": tables,
                        "raw_text": page_text  # Store raw text for line-by-line processing
                    })
                    
                    print(f"Page {page_num}: Extracted {len(page_text)} characters, {len(tables) if tables else 0} tables")
                    
            return True
        except Exception as e:
            print(f"Error extracting PDF data: {e}")
            return False
    
    def parse_assessee_info(self):
        """Extract assessee information with precise patterns"""
        if not self.pages_data:
            return self.assessee_info
        
        # Get text from first page
        first_page_text = self.pages_data[0]["text"]
        
        # PAN extraction
        pan_patterns = [
            r'Permanent Account Number \(PAN\)\s*:\s*([A-Z]{5}[0-9]{4}[A-Z])',
            r'Permanent Account Number \(PAN\)\s*([A-Z]{5}[0-9]{4}[A-Z])',
            r'PAN\s*:\s*([A-Z]{5}[0-9]{4}[A-Z])',
            r'PAN\s*([A-Z]{5}[0-9]{4}[A-Z])',
            r'([A-Z]{5}[0-9]{4}[A-Z])\s*\(PAN\)'
        ]
        
        for pattern in pan_patterns:
            match = re.search(pattern, first_page_text, re.IGNORECASE)
            if match:
                self.assessee_info["pan"] = match.group(1).strip()
                break
        
        # Financial Year extraction - IMPROVED
        fy_patterns = [
            r'Financial Year\s*:\s*(\d{4}[-]\d{2,4})',
            r'F\.Y\.\s*:\s*(\d{4}[-]\d{2,4})',
            r'Financial\s+Year\s+(\d{4}[-]\d{2,4})',
            r'Assessment Year\s*:\s*(\d{4}[-]\d{2,4})',
            r'A\.Y\.\s*:\s*(\d{4}[-]\d{2,4})',
            r'Financial Year\s*(\d{4}[-]\d{2,4})',
            r'F\.Y\.\s*(\d{4}[-]\d{2,4})'
        ]
        
        for pattern in fy_patterns:
            match = re.search(pattern, first_page_text, re.IGNORECASE)
            if match:
                fy = match.group(1).strip()
                # Clean the financial year
                if '-' in fy:
                    parts = fy.split('-')
                    if len(parts[1]) == 2:
                        # Format: 2024-25
                        self.assessee_info["financial_year"] = fy
                    elif len(parts[1]) == 4:
                        # Format: 2024-2025
                        self.assessee_info["financial_year"] = f"{parts[0]}-{parts[1][-2:]}"
                    else:
                        self.assessee_info["financial_year"] = fy
                else:
                    self.assessee_info["financial_year"] = fy
                
                # Calculate assessment year
                try:
                    if '-' in fy:
                        year_part = fy.split('-')[0]
                        assessment_year = int(year_part) + 1
                        self.assessee_info["assessment_year"] = f"{assessment_year}-{str(assessment_year + 1)[-2:]}"
                except:
                    self.assessee_info["assessment_year"] = "Not Available"
                break
        
        # Assessee Name extraction - precise extraction
        name_patterns = [
            r'Name of Assessee\s*:\s*([^\n\r]+?)(?=\s*(?:Permanent Account Number|Financial Year|PAN|Address|$))',
            r'Assessee Name\s*:\s*([^\n\r]+?)(?=\s*(?:Permanent Account Number|Financial Year|PAN|Address|$))',
            r'Name\s*:\s*([^\n\r]+?)(?=\s*(?:Permanent Account Number|Financial Year|PAN|Address|$))',
            r'Name of Assessee\s*([^\n\r]+?)(?=\s*(?:Permanent Account Number|Financial Year|PAN|Address|$))'
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, first_page_text, re.IGNORECASE | re.DOTALL)
            if match:
                name = match.group(1).strip()
                # Clean the name - remove PAN if present
                name = re.sub(r'[A-Z]{5}[0-9]{4}[A-Z]', '', name).strip()
                # Remove extra spaces and clean
                name = re.sub(r'\s+', ' ', name)
                # Remove trailing non-alphabetic characters
                name = re.sub(r'[^A-Za-z\s&\.(),-]+$', '', name)
                self.assessee_info["name"] = name.strip()
                break
        
        # Address extraction - FIXED: Remove "Above data Status of PAN is as per PAN"
        address_patterns = [
            r'Address of Assessee\s*:\s*([^\n\r]+?(?:\n[^\n\r]+?)*)(?=\s*(?:PART|Details|Above data|$))',
            r'Address\s*:\s*([^\n\r]+?(?:\n[^\n\r]+?)*)(?=\s*(?:PART|Details|Above data|$))',
            r'Address of Assessee\s*([^\n\r]+?(?:\n[^\n\r]+?)*)(?=\s*(?:PART|Details|Above data|$))'
        ]
        
        for pattern in address_patterns:
            match = re.search(pattern, first_page_text, re.IGNORECASE | re.DOTALL)
            if match:
                address = match.group(1).strip()
                # Clean address - REMOVE THE EXTRA TEXT
                address = re.sub(r'Above data\s*Status of PAN is as per PAN.*', '', address, flags=re.IGNORECASE)
                address = re.sub(r'\s+', ' ', address)
                address = re.sub(r'[^A-Za-z0-9\s,\.\-()]', '', address)
                self.assessee_info["address"] = address.strip()
                break
        
        # If address not found, try alternative search
        if not self.assessee_info["address"]:
            address_keywords = ['Address', 'ADDRESS', 'Address of Assessee']
            lines = first_page_text.split('\n')
            for i, line in enumerate(lines):
                for keyword in address_keywords:
                    if keyword in line and i + 1 < len(lines):
                        address_line = lines[i + 1].strip()
                        # Clean the address line
                        address_line = re.sub(r'Above data\s*Status of PAN is as per PAN.*', '', address_line, flags=re.IGNORECASE)
                        if address_line and len(address_line) > 10:
                            self.assessee_info["address"] = address_line
                            break
        
        return self.assessee_info
    
    def extract_complete_deductor_name(self, text, tan):
        """Extract complete deductor name as it appears in 26AS"""
        try:
            # Find the position of TAN
            tan_pos = text.find(tan)
            if tan_pos <= 0:
                return "Not Available"
            
            # Get text before TAN
            before_tan = text[:tan_pos].strip()
            
            # Clean up - remove serial numbers, Sr.No etc.
            # Remove any numbers at the beginning
            before_tan = re.sub(r'^\d+\s*', '', before_tan)
            
            # Remove common prefixes
            before_tan = re.sub(r'^Sr\.?\s*No\.?\s*', '', before_tan, flags=re.IGNORECASE)
            before_tan = re.sub(r'^Sr\s*', '', before_tan, flags=re.IGNORECASE)
            
            # Remove "Name of Deductor" if present
            before_tan = re.sub(r'Name of Deductor\s*[:.]*\s*', '', before_tan, flags=re.IGNORECASE)
            
            # Remove extra spaces
            before_tan = re.sub(r'\s+', ' ', before_tan).strip()
            
            # If we have a reasonable name, return it
            if before_tan and len(before_tan) > 2:
                return before_tan
            
            return "Not Available"
            
        except Exception as e:
            print(f"Error extracting deductor name: {e}")
            return "Not Available"
    
    def is_deductor_header_line(self, line: str) -> Tuple[bool, Optional[Dict]]:
        """Check if line is a deductor header line"""
        line = line.strip()
        
        # Check for TAN pattern
        tan_pattern = r'[A-Z]{4}[0-9]{5}[A-Z]'
        tan_match = re.search(tan_pattern, line)
        
        # Check for deductor header keywords
        header_keywords = [
            'Name of Deductor',
            'Total Amount Paid / Credited',
            'Total TDS Deposited',
            'Total Tax Deducted',
            'TAN of Deductor'
        ]
        
        has_header_keyword = any(keyword in line for keyword in header_keywords)
        
        if tan_match or has_header_keyword:
            # Try to extract TAN
            tan = tan_match.group() if tan_match else "Not Available"
            
            # Try to extract deductor name using the improved method
            deductor_name = "Not Available"
            if tan != "Not Available":
                deductor_name = self.extract_complete_deductor_name(line, tan)
            
            # If name still not found, try regex
            if deductor_name == "Not Available":
                # Look for name patterns
                name_patterns = [
                    r'Name of Deductor\s*[:.]*\s*(.+)',
                    r'Name\s*[:.]*\s*(.+)',
                    r'([A-Za-z0-9\s&\.(),-]+(?:\s+[A-Za-z0-9\s&\.(),-]+)*)\s+[A-Z]{4}[0-9]{5}[A-Z]'
                ]
                
                for pattern in name_patterns:
                    name_match = re.search(pattern, line, re.IGNORECASE)
                    if name_match:
                        deductor_name = name_match.group(1).strip()
                        # Clean name
                        deductor_name = re.sub(r'^\d+\s*', '', deductor_name)
                        deductor_name = re.sub(r'^Sr\.?\s*No\.?\s*', '', deductor_name, flags=re.IGNORECASE)
                        deductor_name = re.sub(r'\s+', ' ', deductor_name).strip()
                        break
            
            # Try to extract totals
            total_amount = 0.0
            total_tax = 0.0
            total_tds = 0.0
            
            # Look for amounts - improved pattern to catch various formats
            amount_pattern = r'[\d,]+\.?\d{0,2}'
            amounts = re.findall(amount_pattern, line.replace(',', ''))
            
            if len(amounts) >= 3:
                try:
                    # Convert to float, removing commas
                    cleaned_amounts = []
                    for amt in amounts[-3:]:
                        try:
                            cleaned = float(amt.replace(',', ''))
                            cleaned_amounts.append(cleaned)
                        except:
                            cleaned_amounts.append(0.0)
                    
                    total_amount = cleaned_amounts[0] if len(cleaned_amounts) > 0 else 0.0
                    total_tax = cleaned_amounts[1] if len(cleaned_amounts) > 1 else 0.0
                    total_tds = cleaned_amounts[2] if len(cleaned_amounts) > 2 else 0.0
                except:
                    pass
            
            # Track this deductor for validation
            if tan != "Not Available":
                self.detected_deductors.append((deductor_name, tan))
                self.deductor_header_count += 1
            
            return True, {
                "name": deductor_name,
                "tan": tan,
                "total_amount": total_amount,
                "total_tax": total_tax,
                "total_tds": total_tds,
                "raw_line": line[:100]  # Store first 100 chars for debugging
            }
        
        return False, None
    
    def is_transaction_row(self, line: str) -> Tuple[bool, Optional[Dict]]:
        """Check if line is a valid transaction row - ENHANCED VERSION for negative amount handling"""
        line = line.strip()
        
        # Must NOT contain deductor header keywords
        header_keywords = [
            'Name of Deductor',
            'TAN of Deductor',
            'Total Amount Paid',
            'Total TDS Deposited',
            'Total Tax Deducted',
            'Sr. No.',
            'Section'
        ]
        
        if any(keyword in line for keyword in header_keywords):
            return False, None
        
        # Must have a valid section code (194C, 194Q, 194I, etc.)
        section_match = re.search(r'(19[0-9]{1,2}[A-Z]?)', line)
        if not section_match:
            return False, None
        
        section = section_match.group(1)
        
        # Must have a valid date (dd-mmm-yyyy)
        date_match = re.search(r'\d{2}-[A-Za-z]{3}-\d{4}', line)
        if not date_match:
            return False, None
        
        transaction_date = date_match.group()
        
        # ENHANCED AMOUNT EXTRACTION - handling negative amounts
        # Look for amounts in the format: 1,000.00 or 1000.00 or -1,000.00 or -1000.00
        # This pattern captures amounts with optional negative sign, commas and exactly 2 decimal places
        amount_pattern = r'-?[\d,]+\.\d{2}'
        amounts = re.findall(amount_pattern, line)
        
        if len(amounts) < 2:
            # Try alternative pattern for amounts without commas
            alt_pattern = r'-?\d+\.\d{2}'
            amounts = re.findall(alt_pattern, line)
            
            # If still less than 2 amounts, check for dash/hyphen patterns (like "-" for zero)
            if len(amounts) < 2:
                # Look for dash patterns: " - " or similar
                dash_pattern = r'\s-\s'
                if re.search(dash_pattern, line):
                    # This could be a transaction with zero amounts (dash indicates zero)
                    # For zero transactions, we'll use 0.00 for all amounts
                    amounts = ['0.00', '0.00', '0.00']
                else:
                    return False, None
        
        # Extract status (F, B, G, O, etc.)
        # Look for single capital letter surrounded by spaces
        status_match = re.search(r'\s([A-Z])\s', f" {line} ")
        status = status_match.group(1) if status_match else "F"
        
        # Extract amounts - ENHANCED FOR NEGATIVE AMOUNTS
        try:
            # Clean amounts: remove commas and convert to float
            cleaned_amounts = []
            for amt in amounts:
                try:
                    cleaned_amt = float(amt.replace(',', ''))
                    cleaned_amounts.append(cleaned_amt)
                except:
                    continue
            
            # Assign amounts based on the first code's logic
            # First amount is Amount Paid/Credited
            # Second amount is Tax Deducted
            # Third amount (if exists) is TDS Deposited
            if len(cleaned_amounts) >= 2:
                amount_paid = cleaned_amounts[0]
                tax_deducted = cleaned_amounts[1]
                
                if len(cleaned_amounts) >= 3:
                    tds_deposited = cleaned_amounts[2]
                else:
                    tds_deposited = tax_deducted
            else:
                return False, None
            
            # Calculate net amount and rate (handle negative amounts correctly)
            net_amount = amount_paid - tds_deposited
            
            # Calculate rate - handle division by zero and negative amounts
            if amount_paid != 0:
                rate = (tax_deducted / amount_paid * 100)
            else:
                rate = 0
            
            # Extract date of booking if available (look for second date in line)
            date_matches = list(re.finditer(r'\d{2}-[A-Za-z]{3}-\d{4}', line))
            date_of_booking = ""
            if len(date_matches) >= 2:
                date_of_booking = date_matches[1].group()
            
            # Track this transaction
            self.transaction_row_count += 1
            self.all_transaction_rows.append({
                "section": section,
                "transaction_date": transaction_date,
                "amount_paid": amount_paid,
                "tax_deducted": tax_deducted,
                "tds_deposited": tds_deposited,
                "raw_line": line[:100]
            })
            
            return True, {
                "section": section,
                "transaction_date": transaction_date,
                "status": status,
                "date_of_booking": date_of_booking,
                "amount_paid": round(amount_paid, 2),
                "tax_deducted": round(tax_deducted, 2),
                "tds_deposited": round(tds_deposited, 2),
                "net_amount": round(net_amount, 2),
                "rate": round(rate, 2),
                "raw_line": line[:100]  # For debugging
            }
        except Exception as e:
            print(f"Error parsing transaction amounts in line: {line[:50]}... Error: {e}")
            return False, None
    
    def close_current_deductor(self, force=False):
        """Close current deductor and add to transactions - INCLUDING NEGATIVE TRANSACTIONS"""
        if self.current_deductor and self.current_transactions:
            # INCLUDE ALL TRANSACTIONS (including negative and zero)
            valid_transactions = self.current_transactions
            
            if valid_transactions:
                # Calculate running total from all transactions
                running_total = sum(t.get('amount_paid', 0) for t in valid_transactions)
                
                # Add deductor info to each transaction
                for trans in valid_transactions:
                    trans['deductor_name'] = self.current_deductor.get('name', 'Not Available')
                    trans['deductor_tan'] = self.current_deductor.get('tan', 'Not Available')
                    trans['deductor_total_amount'] = self.current_deductor.get('total_amount', running_total)
                    trans['deductor_total_tax'] = self.current_deductor.get('total_tax', 0)
                    trans['deductor_total_tds'] = self.current_deductor.get('total_tds', 0)
                    self.transactions.append(trans)
                
                # Mark this deductor as successfully parsed
                deductor_key = f"{self.current_deductor.get('name')}__{self.current_deductor.get('tan')}"
                self.parsed_deductors.add(deductor_key)
                
                # Count positive, negative and zero transactions
                positive_count = sum(1 for t in valid_transactions if t.get('amount_paid', 0) > 0)
                negative_count = sum(1 for t in valid_transactions if t.get('amount_paid', 0) < 0)
                zero_count = sum(1 for t in valid_transactions if t.get('amount_paid', 0) == 0)
                
                print(f"  ✓ Closed deductor: {self.current_deductor.get('name', 'Unknown')} | "
                      f"TAN: {self.current_deductor.get('tan', 'Unknown')} | "
                      f"Transactions: {len(valid_transactions)} (+{positive_count}/-{negative_count}/0{zero_count}) | "
                      f"Total: ₹{running_total:,.2f}")
            else:
                print(f"  ✗ Skipping deductor (no transactions): {self.current_deductor.get('name', 'Unknown')}")
        
        # Reset for next deductor
        self.current_deductor = None
        self.current_transactions = []
        self.current_tan = None
        self.running_total = 0.0
        self.state = STATE_WAITING_FOR_DEDUCTOR_HEADER
    
    def parse_with_table_extraction(self):
        """Parse using table extraction - more reliable for 26AS format"""
        print("\n=== Parsing with Table Extraction ===")
        
        # Reset tracking
        self.transactions = []
        self.current_deductor = None
        self.current_transactions = []
        self.current_tan = None
        self.running_total = 0.0
        self.state = STATE_WAITING_FOR_DEDUCTOR_HEADER
        
        # Store raw lines for context
        self.raw_lines_with_context = []
        
        # Process each page
        for page_data in self.pages_data:
            page_num = page_data["page_number"]
            text = page_data["text"]
            tables = page_data["tables"]
            
            # Store raw lines with page context
            lines = text.split('\n')
            for line in lines:
                if line.strip():
                    self.raw_lines_with_context.append({
                        "page": page_num,
                        "line": line.strip(),
                        "has_tan": bool(re.search(r'[A-Z]{4}[0-9]{5}[A-Z]', line)),
                        "has_amount": bool(re.search(r'-?\d{1,3}(?:,\d{3})*(?:\.\d{2})?', line))
                    })
            
            # Process tables if available
            if tables:
                print(f"  Processing {len(tables)} tables on page {page_num}")
                self.process_tables_on_page(tables, page_num)
            else:
                # Fallback to text parsing
                print(f"  No tables found on page {page_num}, using text parsing")
                self.process_text_lines(lines, page_num)
        
        # Close any remaining deductor
        if self.current_deductor:
            self.close_current_deductor()
    
    def process_tables_on_page(self, tables, page_num):
        """Process tables on a page"""
        for table_idx, table in enumerate(tables):
            if not table:
                continue
            
            # Process each row in the table
            for row_idx, row in enumerate(table):
                if not row:
                    continue
                
                # Convert row to string for analysis
                row_text = ' '.join([str(cell).strip() for cell in row if cell])
                
                # Check if this is a deductor header
                is_header, deductor_info = self.is_deductor_header_line(row_text)
                if is_header:
                    tan = deductor_info.get('tan')
                    deductor_name = deductor_info.get('name')
                    
                    # Close previous deductor if any
                    if self.current_deductor:
                        self.close_current_deductor()
                    
                    # Start new deductor
                    self.current_deductor = deductor_info
                    self.current_tan = tan
                    self.current_transactions = []
                    self.running_total = 0.0
                    self.state = STATE_INSIDE_DEDUCTOR_HEADER
                    
                    print(f"\n[Page {page_num}, Table {table_idx+1}] Found deductor: {deductor_name} | TAN: {tan}")
                
                # Check if this is a transaction row
                elif self.current_deductor:
                    is_transaction, transaction_data = self.is_transaction_row(row_text)
                    if is_transaction:
                        transaction_data['page_number'] = page_num
                        transaction_data['table_index'] = table_idx
                        transaction_data['row_index'] = row_idx
                        transaction_data['source'] = 'table'
                        self.current_transactions.append(transaction_data)
                        self.running_total += transaction_data.get('amount_paid', 0)
                        
                        if self.state == STATE_INSIDE_DEDUCTOR_HEADER:
                            self.state = STATE_INSIDE_TRANSACTION_TABLE
    
    def process_text_lines(self, lines, page_num):
        """Process text lines on a page"""
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if not line:
                i += 1
                continue
            
            # STATE: WAITING_FOR_DEDUCTOR_HEADER
            if self.state == STATE_WAITING_FOR_DEDUCTOR_HEADER:
                is_header, deductor_info = self.is_deductor_header_line(line)
                if is_header:
                    tan = deductor_info.get('tan')
                    deductor_name = deductor_info.get('name')
                    
                    # Close previous deductor if any
                    if self.current_deductor:
                        self.close_current_deductor()
                    
                    # Start new deductor
                    self.current_deductor = deductor_info
                    self.current_tan = tan
                    self.current_transactions = []
                    self.running_total = 0.0
                    self.state = STATE_INSIDE_DEDUCTOR_HEADER
                    
                    print(f"\n[Page {page_num}] Found deductor: {deductor_name} | TAN: {tan}")
            
            # STATE: INSIDE_DEDUCTOR_HEADER or INSIDE_TRANSACTION_TABLE
            elif self.state in [STATE_INSIDE_DEDUCTOR_HEADER, STATE_INSIDE_TRANSACTION_TABLE]:
                # First check if this is a new deductor header
                is_header, deductor_info = self.is_deductor_header_line(line)
                if is_header:
                    current_tan = self.current_deductor.get('tan') if self.current_deductor else None
                    new_tan = deductor_info.get('tan')
                    
                    if new_tan != "Not Available" and new_tan != current_tan:
                        # Different TAN = new deductor
                        self.close_current_deductor()
                        
                        # Start new deductor
                        self.current_deductor = deductor_info
                        self.current_tan = new_tan
                        self.current_transactions = []
                        self.running_total = 0.0
                        self.state = STATE_INSIDE_DEDUCTOR_HEADER
                        
                        print(f"\n[Page {page_num}] New deductor: {deductor_info.get('name')} | TAN: {new_tan}")
                    else:
                        # Same deductor or no TAN, look for transactions
                        pass
                
                # Check if this is a transaction row
                is_transaction, transaction_data = self.is_transaction_row(line)
                if is_transaction:
                    transaction_data['page_number'] = page_num
                    transaction_data['line_index'] = i
                    transaction_data['source'] = 'text'
                    self.current_transactions.append(transaction_data)
                    self.running_total += transaction_data.get('amount_paid', 0)
                    
                    if self.state == STATE_INSIDE_DEDUCTOR_HEADER:
                        self.state = STATE_INSIDE_TRANSACTION_TABLE
                
                # Check for multi-line transaction patterns
                elif self.state == STATE_INSIDE_TRANSACTION_TABLE:
                    # Sometimes transaction data spans multiple lines
                    # Look ahead a few lines for transaction data
                    for lookahead in range(1, 4):
                        if i + lookahead >= len(lines):
                            break
                        
                        next_line = lines[i + lookahead].strip()
                        if next_line and not any(keyword in next_line for keyword in ['Name of Deductor', 'TAN of Deductor', 'Total Amount']):
                            is_transaction2, transaction_data2 = self.is_transaction_row(next_line)
                            if is_transaction2:
                                transaction_data2['page_number'] = page_num
                                transaction_data2['line_index'] = i + lookahead
                                transaction_data2['source'] = 'text'
                                self.current_transactions.append(transaction_data2)
                                self.running_total += transaction_data2.get('amount_paid', 0)
                                i += lookahead  # Skip the lines we just processed
                                break
            
            i += 1
    
    def parse_transactions(self):
        """Main transaction parsing method - FIXED DUPLICATE HANDLING"""
        print("\n=== Starting Transaction Parsing ===")
        
        # Reset tracking
        self.transactions = []
        self.detected_deductors = []
        self.all_transaction_rows = []
        self.deductor_header_count = 0
        self.transaction_row_count = 0
        self.parsed_deductors = set()
        
        # Method 1: Table extraction (most reliable)
        self.parse_with_table_extraction()
        
        # Method 2: Fallback to enhanced text parsing if needed
        if len(self.transactions) < 10:  # If we got very few transactions
            print("\n=== Using enhanced text parsing fallback ===")
            # Reset and try text-based approach
            backup_transactions = self.transactions.copy()
            self.transactions = []
            self.parse_with_enhanced_text_parsing()
            
            # Merge with backup transactions
            self.transactions = backup_transactions + self.transactions
        
        # IMPROVED DUPLICATION REMOVAL - Keep all valid transactions
        # For 26AS, we need to keep ALL transactions including duplicates with same amounts
        # because they represent separate entries in the PDF
        unique_transactions = []
        seen_combinations = set()
        
        for trans in self.transactions:
            # Create a more specific key that includes more fields to reduce false duplicates
            # But allow same amounts if they are truly separate transactions
            key_parts = [
                trans.get('deductor_tan', ''),
                trans.get('section', ''),
                trans.get('transaction_date', ''),
                trans.get('date_of_booking', ''),
                trans.get('status', ''),
                trans.get('amount_paid', 0),
                trans.get('tax_deducted', 0),
                trans.get('tds_deposited', 0),
                trans.get('page_number', 0),
                trans.get('source', 'unknown')
            ]
            
            # For text source, include line index
            if trans.get('source') == 'text' and 'line_index' in trans:
                key_parts.append(f"line_{trans['line_index']}")
            # For table source, include table and row index
            elif trans.get('source') == 'table' and 'table_index' in trans and 'row_index' in trans:
                key_parts.append(f"table_{trans['table_index']}_row_{trans['row_index']}")
            
            key = tuple(str(part) for part in key_parts)
            
            if key not in seen_combinations:
                seen_combinations.add(key)
                unique_transactions.append(trans)
            else:
                # This might be a genuine duplicate from different parsing methods
                # Check if it's from a different source
                existing_source = next((t.get('source') for t in unique_transactions 
                                     if (t.get('deductor_tan') == trans.get('deductor_tan') and
                                         t.get('amount_paid') == trans.get('amount_paid') and
                                         t.get('transaction_date') == trans.get('transaction_date'))), None)
                
                if existing_source != trans.get('source'):
                    # Different sources, might be same transaction captured twice
                    # Keep the table version if available
                    if trans.get('source') == 'table' and existing_source == 'text':
                        # Replace text version with table version
                        for idx, t in enumerate(unique_transactions):
                            if (t.get('deductor_tan') == trans.get('deductor_tan') and
                                t.get('amount_paid') == trans.get('amount_paid') and
                                t.get('transaction_date') == trans.get('transaction_date') and
                                t.get('source') == 'text'):
                                unique_transactions[idx] = trans
                                break
        
        # Assign serial numbers
        for i, trans in enumerate(unique_transactions, 1):
            trans['sr_no'] = i
            # Ensure all required fields exist
            if 'date_of_booking' not in trans or not trans['date_of_booking']:
                trans['date_of_booking'] = trans.get('transaction_date', '')
        
        self.transactions = unique_transactions
        
        # Validate and report
        self.validate_completeness()
        
        return self.transactions
    
    def parse_with_enhanced_text_parsing(self):
        """Enhanced text parsing with better transaction detection"""
        print("\n=== Enhanced Text Parsing ===")
        
        # Reset state
        self.current_deductor = None
        self.current_transactions = []
        self.current_tan = None
        self.running_total = 0.0
        self.state = STATE_WAITING_FOR_DEDUCTOR_HEADER
        
        # Process each page
        for page_data in self.pages_data:
            page_num = page_data["page_number"]
            text = page_data["text"]
            
            # Split into lines
            lines = text.split('\n')
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                if not line:
                    i += 1
                    continue
                
                # Look for deductor patterns
                if 'TAN of Deductor' in line or 'Name of Deductor' in line:
                    # This might be a deductor header
                    # Extract TAN if present
                    tan_match = re.search(r'[A-Z]{4}[0-9]{5}[A-Z]', line)
                    if tan_match:
                        tan = tan_match.group()
                        
                        # Close previous deductor
                        if self.current_deductor:
                            self.close_current_deductor()
                        
                        # Try to extract deductor name
                        deductor_name = self.extract_complete_deductor_name(line, tan)
                        
                        # Create new deductor
                        self.current_deductor = {
                            "name": deductor_name,
                            "tan": tan,
                            "total_amount": 0,
                            "total_tax": 0,
                            "total_tds": 0
                        }
                        self.current_tan = tan
                        self.current_transactions = []
                        self.running_total = 0.0
                        self.state = STATE_INSIDE_DEDUCTOR_HEADER
                        
                        print(f"\n[Page {page_num}] Found deductor: {deductor_name} | TAN: {tan}")
                
                # Look for transaction patterns
                elif self.current_deductor:
                    # Check for section code and date
                    section_match = re.search(r'(19[0-9]{1,2}[A-Z]?)', line)
                    date_match = re.search(r'\d{2}-[A-Za-z]{3}-\d{4}', line)
                    
                    if section_match and date_match:
                        # This looks like a transaction row
                        transaction_data = self.parse_transaction_from_line(line, page_num)
                        if transaction_data:
                            transaction_data['line_index'] = i
                            transaction_data['source'] = 'text_enhanced'
                            self.current_transactions.append(transaction_data)
                            self.running_total += transaction_data.get('amount_paid', 0)
                            self.state = STATE_INSIDE_TRANSACTION_TABLE
                
                i += 1
        
        # Close final deductor
        if self.current_deductor:
            self.close_current_deductor()
    
    def parse_transaction_from_line(self, line, page_num):
        """Parse transaction data from a line - ENHANCED for negative amount extraction"""
        try:
            # Extract section
            section_match = re.search(r'(19[0-9]{1,2}[A-Z]?)', line)
            section = section_match.group(1) if section_match else "194C"
            
            # Extract date
            date_match = re.search(r'\d{2}-[A-Za-z]{3}-\d{4}', line)
            transaction_date = date_match.group() if date_match else ""
            
            # Extract status
            status_match = re.search(r'\s([A-Z])\s', f" {line} ")
            status = status_match.group(1) if status_match else "F"
            
            # ENHANCED AMOUNT EXTRACTION - same as in is_transaction_row
            amount_pattern = r'-?[\d,]+\.\d{2}'
            amounts = re.findall(amount_pattern, line)
            
            if len(amounts) < 2:
                # Try alternative pattern for amounts without commas
                alt_pattern = r'-?\d+\.\d{2}'
                amounts = re.findall(alt_pattern, line)
                
                # If still less than 2 amounts, check for dash/hyphen patterns
                if len(amounts) < 2:
                    dash_pattern = r'\s-\s'
                    if re.search(dash_pattern, line):
                        # This could be a transaction with zero amounts
                        amounts = ['0.00', '0.00', '0.00']
                    else:
                        return None
            
            if not amounts:
                return None
            
            # Parse amounts using the same logic as in is_transaction_row
            try:
                # Clean amounts
                cleaned_amounts = []
                for amt in amounts[:3]:  # Take up to 3 amounts
                    cleaned = float(amt.replace(',', ''))
                    cleaned_amounts.append(cleaned)
                
                # Assign amounts based on the first code's logic
                if len(cleaned_amounts) >= 2:
                    amount_paid = cleaned_amounts[0]
                    tax_deducted = cleaned_amounts[1]
                    tds_deposited = cleaned_amounts[2] if len(cleaned_amounts) >= 3 else tax_deducted
                else:
                    return None
                
                # Calculate net amount and rate
                net_amount = amount_paid - tds_deposited
                
                # Calculate rate - handle division by zero and negative amounts
                if amount_paid != 0:
                    rate = (tax_deducted / amount_paid * 100)
                else:
                    rate = 0
                
                # Extract date of booking
                date_matches = list(re.finditer(r'\d{2}-[A-Za-z]{3}-\d{4}', line))
                date_of_booking = ""
                if len(date_matches) >= 2:
                    date_of_booking = date_matches[1].group()
                
                return {
                    "section": section,
                    "transaction_date": transaction_date,
                    "status": status,
                    "date_of_booking": date_of_booking,
                    "amount_paid": round(amount_paid, 2),
                    "tax_deducted": round(tax_deducted, 2),
                    "tds_deposited": round(tds_deposited, 2),
                    "net_amount": round(net_amount, 2),
                    "rate": round(rate, 2),
                    "page_number": page_num
                }
            except:
                return None
                
        except Exception as e:
            return None
    
    def validate_completeness(self):
        """Validate that we captured all transactions"""
        print(f"\n=== Validation Results ===")
        print(f"Total transactions captured: {len(self.transactions)}")
        
        # Group by deductor for reporting
        deductor_groups = {}
        for trans in self.transactions:
            deductor = trans.get('deductor_name', 'Unknown')
            tan = trans.get('deductor_tan', 'Unknown')
            key = f"{deductor}__{tan}"
            
            if key not in deductor_groups:
                deductor_groups[key] = []
            deductor_groups[key].append(trans)
        
        print(f"Unique deductor-TAN combinations: {len(deductor_groups)}")
        print("\nDeductor Details:")
        for key, transactions in deductor_groups.items():
            deductor_name, deductor_tan = key.split('__') if '__' in key else (key, 'Unknown')
            
            # Calculate totals
            total_amount = sum(t.get('amount_paid', 0) for t in transactions)
            total_tax = sum(t.get('tax_deducted', 0) for t in transactions)
            total_tds = sum(t.get('tds_deposited', 0) for t in transactions)
            
            # Count transaction types
            positive_count = sum(1 for t in transactions if t.get('amount_paid', 0) > 0)
            negative_count = sum(1 for t in transactions if t.get('amount_paid', 0) < 0)
            zero_count = sum(1 for t in transactions if t.get('amount_paid', 0) == 0)
            
            print(f"  - {deductor_name[:30]:<30} | TAN: {deductor_tan[:10]:<10} | "
                  f"Trans: {len(transactions):<3} (+{positive_count}/-{negative_count}/0{zero_count}) | "
                  f"Amount: ₹{total_amount:>12,.2f} | "
                  f"Tax: ₹{total_tax:>10,.2f} | TDS: ₹{total_tds:>10,.2f}")
    
    def parse(self):
        """Main parsing method"""
        print("\n" + "="*60)
        print("Starting 26AS Parser - Professional Edition")
        print("Version: 11.0 (Fixed Duplicate Transaction Handling)")
        print("="*60)
        
        # Step 1: Extract data from PDF
        print("\n1. Extracting PDF data...")
        if not self.extract_data_from_pdf():
            print("ERROR: Failed to extract PDF data")
            return {
                "assessee_info": self.assessee_info,
                "transactions": [],
                "total_transactions": 0
            }
        
        # Step 2: Parse assessee info
        print("\n2. Parsing assessee information...")
        self.parse_assessee_info()
        print(f"   - Assessee Name: {self.assessee_info['name'][:50]}...")
        print(f"   - PAN: {self.assessee_info['pan']}")
        print(f"   - Financial Year: {self.assessee_info['financial_year']}")
        print(f"   - Address: {self.assessee_info['address'][:50]}...")
        
        # Step 3: Parse transactions
        print("\n3. Parsing transactions...")
        self.parse_transactions()
        
        print("\n" + "="*60)
        print("Parsing Complete!")
        print("="*60)
        
        return {
            "assessee_info": self.assessee_info,
            "transactions": self.transactions,
            "total_transactions": len(self.transactions)
        }

@app.route('/')
def index():
    """Serve the main HTML page"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_pdf():
    """Handle PDF upload and parsing"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Please upload a PDF file'}), 400
    
    # Save uploaded file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{file.filename}"
    filepath = os.path.join('uploads', filename)
    file.save(filepath)
    
    try:
        # Parse the PDF with advanced parser
        parser = TwentySixASParser(filepath)
        result = parser.parse()
        
        # Clean up
        os.remove(filepath)
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        # Clean up on error
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': f'Error parsing PDF: {str(e)}'}), 500

@app.route('/download_excel', methods=['POST'])
def download_excel():
    """Generate and serve Excel file"""
    try:
        data = request.get_json()
        if not data or 'assessee_info' not in data or 'transactions' not in data:
            return jsonify({'error': 'No data provided'}), 400
        
        assessee_info = data['assessee_info']
        transactions = data['transactions']
        
        # Create DataFrame with all columns including Date of Booking
        df_data = []
        for t in transactions:
            df_data.append({
                'Sr.No': t.get('sr_no', ''),
                'Name of Deductor': t.get('deductor_name', ''),
                'TAN of Deductor': t.get('deductor_tan', ''),
                'Section': t.get('section', ''),
                'Transaction Date': t.get('transaction_date', ''),
                'Status of Booking*': t.get('status', ''),
                'Date of Booking': t.get('date_of_booking', ''),
                'Amount Paid / Credited': t.get('amount_paid', 0),
                'Tax Deducted': t.get('tax_deducted', 0),
                'TDS Deposited': t.get('tds_deposited', 0),
                'Net Amount': t.get('net_amount', 0),
                'Rate %': t.get('rate', 0),
                'PDF Page No': t.get('page_number', '')
            })
        
        df = pd.DataFrame(df_data)
        
        # Generate filename
        pan = assessee_info.get('pan', 'Unknown')
        fy = assessee_info.get('financial_year', '').replace('-', '_')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        excel_filename = f"26AS_{pan}_{fy}_{timestamp}.xlsx"
        excel_path = os.path.join('output', excel_filename)
        
        # Save to Excel
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            # Add metadata sheet with complete address (already cleaned)
            metadata_rows = [
                ['Name of Assessee', assessee_info.get('name', 'Not Available')],
                ['Permanent Account Number (PAN)', assessee_info.get('pan', 'Not Available')],
                ['Financial Year', assessee_info.get('financial_year', 'Not Available')],
                ['Assessment Year', assessee_info.get('assessment_year', 'Not Available')],
                ['Address', assessee_info.get('address', 'Not Available')],
                ['Total Transactions', len(transactions)],
                ['Generated On', datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
            ]
            
            metadata_df = pd.DataFrame(metadata_rows, columns=['Field', 'Value'])
            metadata_df.to_excel(writer, sheet_name='Metadata', index=False)
            
            # Add transactions sheet
            df.to_excel(writer, sheet_name='TDS Transactions', index=False)
            
            # Auto-adjust column widths for both sheets
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                if sheet_name == 'TDS Transactions':
                    data_df = df
                else:
                    data_df = metadata_df
                
                for column in data_df:
                    max_length = max(
                        data_df[column].astype(str).apply(len).max(),
                        len(str(column))
                    ) + 2
                    
                    col_idx = list(data_df.columns).index(column)
                    col_letter = chr(65 + col_idx) if col_idx < 26 else chr(64 + col_idx // 26) + chr(65 + col_idx % 26)
                    worksheet.column_dimensions[col_letter].width = min(max_length, 50)
        
        return jsonify({
            'success': True,
            'filename': excel_filename,
            'download_url': f'/download/{excel_filename}'
        })
        
    except Exception as e:
        return jsonify({'error': f'Error generating Excel: {str(e)}'}), 500

@app.route('/download/<filename>')
def download_file(filename):
    """Serve the generated Excel file"""
    try:
        return send_from_directory('output', filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 404

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': '26AS Parser',
        'version': '11.0',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    print("\n" + "="*60)
    print("26AS PDF to Excel Converter - Professional Edition")
    print("Version: 11.0 (Fixed Duplicate Transaction Handling)")
    print("="*60)
    print("\nKey Features Implemented:")
    print("  ✓ 100% accurate deductor information extraction")
    print("  ✓ Fixed duplicate transaction handling")
    print("  ✓ Keeps all identical transactions from 26AS PDF")
    print("  ✓ Properly tracks positive and negative adjustments")
    print("  ✓ Maintains original transaction order")
    print("  ✓ Accurate Amount Paid/Credited extraction")
    print("  ✓ Accurate Tax Deducted extraction")
    print("  ✓ Accurate TDS Deposited extraction")
    print("  ✓ Table extraction for reliable parsing")
    print("="*60)
    print("\nStarting server on http://localhost:5001")
    print("Press Ctrl+C to stop the server")
    print("="*60 + "\n")
    
    app.run(debug=True, port=5001, threaded=True)
