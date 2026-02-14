// Global variables
let selectedFile = null;
let extractedData = {
    assessee: {
        name: '',
        pan: '',
        financialYear: '',
        address: '',
        assessmentYear: ''
    },
    transactions: [],
    processingStats: {
        startTime: 0,
        endTime: 0,
        pageCount: 0
    }
};

// PDF.js variables
let pdfDocument = null;
let currentPage = 1;
let totalPages = 0;

// User data storage
let userData = {
    totalFilesProcessed: 0,
    todayFilesProcessed: 0,
    lastResetDate: new Date().toDateString()
};

// DOM elements
const uploadArea = document.getElementById('uploadArea');
const browseButton = document.getElementById('browseButton');
const fileInput = document.getElementById('fileInput');
const fileCountEl = document.getElementById('fileCount');
const summaryFileCount = document.getElementById('summaryFileCount');
const summaryTransactionCount = document.getElementById('summaryTransactionCount');
const parseBtn = document.getElementById('parseBtn');
const resetBtn = document.getElementById('resetBtn');
const downloadBtn = document.getElementById('downloadBtn');
const progressBar = document.getElementById('progressBar');
const progressFill = document.getElementById('progressFill');
const pdfViewer = document.getElementById('pdfViewer');
const pdfInfo = document.getElementById('pdfInfo');
const pdfControls = document.getElementById('pdfControls');
const prevPageBtn = document.getElementById('prevPage');
const nextPageBtn = document.getElementById('nextPage');
const pageInfo = document.getElementById('pageInfo');
const excelTable = document.getElementById('excelTable');
const excelBody = document.getElementById('excelBody');
const excelInfo = document.getElementById('excelInfo');
const excelRowInfo = document.getElementById('excelRowInfo');
const previewTabs = document.querySelectorAll('.preview-tab');
const tabPanes = document.querySelectorAll('.tab-pane');
const infoTabs = document.querySelectorAll('.info-tab');
const tabPanesInfo = document.querySelectorAll('.tab-pane-info');
const reportModal = document.getElementById('reportModal');
const closeModal = document.getElementById('closeModal');
const closeModalBtn = document.getElementById('closeModalBtn');
const confirmDownload = document.getElementById('confirmDownload');
const modalPageCount = document.getElementById('modalPageCount');
const modalTransactionCount = document.getElementById('modalTransactionCount');
const modalTime = document.getElementById('modalTime');
const modalFileSize = document.getElementById('modalFileSize');
const totalFilesCounter = document.getElementById('totalFilesCounter');
const todayFilesCounter = document.getElementById('todayFilesCounter');
const currentDate = document.getElementById('currentDate');
const transactionCounter = document.getElementById('transactionCounter');
const counterValue = document.getElementById('counterValue');
const assesseeInfo = document.getElementById('assesseeInfo');
const assesseeName = document.getElementById('assesseeName');
const assesseePAN = document.getElementById('assesseePAN');
const assesseeFY = document.getElementById('assesseeFY');
const assesseeGrid = document.getElementById('assesseeGrid');
const statsContainer = document.getElementById('statsContainer');

// Initialize
function init() {
    loadUserData();
    setupEventListeners();
    updateCurrentDate();
    setupScrollListener();
}

// Load user data from localStorage
function loadUserData() {
    const savedData = localStorage.getItem('twentySixASToolData');
    if (savedData) {
        userData = JSON.parse(savedData);
        
        // Check if it's a new day
        const today = new Date().toDateString();
        if (userData.lastResetDate !== today) {
            userData.todayFilesProcessed = 0;
            userData.lastResetDate = today;
            saveUserData();
        }
    }
    
    updateStatisticsCounters();
}

// Save user data to localStorage
function saveUserData() {
    localStorage.setItem('twentySixASToolData', JSON.stringify(userData));
    updateStatisticsCounters();
}

// Update statistics counters
function updateStatisticsCounters() {
    totalFilesCounter.textContent = userData.totalFilesProcessed.toLocaleString();
    todayFilesCounter.textContent = userData.todayFilesProcessed.toLocaleString();
}

// Update current date display
function updateCurrentDate() {
    const now = new Date();
    const options = { 
        day: 'numeric', 
        month: 'long', 
        year: 'numeric',
        weekday: 'long'
    };
    currentDate.textContent = now.toLocaleDateString('en-IN', options);
}

// Setup scroll listener for stats container
function setupScrollListener() {
    let lastScrollTop = 0;
    
    window.addEventListener('scroll', function() {
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        
        // Show stats when scrolling down, hide when at top
        if (scrollTop > 100 && scrollTop > lastScrollTop) {
            statsContainer.classList.add('visible');
        } else if (scrollTop <= 100) {
            statsContainer.classList.remove('visible');
        }
        
        lastScrollTop = scrollTop;
    });
}

// Setup event listeners
function setupEventListeners() {
    // Browse button click event
    browseButton.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        fileInput.click();
    });
    
    // Upload area click
    uploadArea.addEventListener('click', function(e) {
        if (e.target.closest('#browseButton')) {
            return;
        }
        fileInput.click();
    });
    
    // Drag and drop functionality
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('drag-over');
    });
    
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('drag-over');
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');
        
        if (e.dataTransfer.files.length) {
            handleFile(e.dataTransfer.files[0]);
        }
    });
    
    // File input change event
    fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });
    
    // Parse button click
    parseBtn.addEventListener('click', parsePDF);
    
    // Reset button click
    resetBtn.addEventListener('click', resetTool);
    
    // Download button click
    downloadBtn.addEventListener('click', showDownloadModal);
    
    // Modal events
    closeModal.addEventListener('click', () => {
        reportModal.style.display = 'none';
    });
    
    closeModalBtn.addEventListener('click', () => {
        reportModal.style.display = 'none';
    });
    
    confirmDownload.addEventListener('click', downloadExcelFile);
    
    // PDF page navigation
    prevPageBtn.addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            renderPDFPage(currentPage);
        }
    });
    
    nextPageBtn.addEventListener('click', () => {
        if (currentPage < totalPages) {
            currentPage++;
            renderPDFPage(currentPage);
        }
    });
    
    // Preview tabs
    previewTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabId = tab.getAttribute('data-tab');
            
            // Update active tab
            previewTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            // Show corresponding tab pane
            tabPanes.forEach(pane => {
                pane.classList.remove('active');
                if (pane.id === `${tabId}-preview`) {
                    pane.classList.add('active');
                }
            });
        });
    });
    
    // Info tabs
    infoTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabId = tab.getAttribute('data-tab');
            
            // Update active tab
            infoTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            // Show corresponding tab pane
            tabPanesInfo.forEach(pane => {
                pane.classList.remove('active');
                if (pane.id === `${tabId}-tab`) {
                    pane.classList.add('active');
                }
            });
        });
    });
}

// Handle file selection
function handleFile(file) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        showNotification('Please select a PDF file.', 'error');
        return;
    }
    
    selectedFile = file;
    updateFileCount();
    
    // Reset extracted data
    extractedData = {
        assessee: {
            name: '',
            pan: '',
            financialYear: '',
            address: '',
            assessmentYear: ''
        },
        transactions: [],
        processingStats: {
            startTime: 0,
            endTime: 0,
            pageCount: 0
        }
    };
    
    // Update UI
    parseBtn.disabled = false;
    previewTabs[0].click(); // Switch to PDF preview
    
    // Load and display PDF
    loadPDF(file);
    
    // Show file info
    pdfInfo.textContent = `File: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
}

// Load PDF with PDF.js
async function loadPDF(file) {
    try {
        const arrayBuffer = await file.arrayBuffer();
        
        // Initialize PDF.js
        pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
        
        const loadingTask = pdfjsLib.getDocument({ data: arrayBuffer });
        pdfDocument = await loadingTask.promise;
        
        // Store page count
        totalPages = pdfDocument.numPages;
        extractedData.processingStats.pageCount = totalPages;
        
        // Show PDF controls
        pdfControls.style.display = 'flex';
        
        // Reset to first page
        currentPage = 1;
        renderPDFPage(1);
        
    } catch (error) {
        console.error('Error loading PDF:', error);
        showNotification('Error loading PDF file. Please ensure it\'s a valid 26AS PDF.', 'error');
        
        pdfViewer.innerHTML = `
            <div style="text-align: center; padding: 4rem; color: var(--text-light);">
                <i class="fas fa-exclamation-triangle" style="font-size: 4rem; margin-bottom: 1.5rem; display: block; color: var(--warning-orange);"></i>
                <h3 style="margin-bottom: 0.8rem; color: var(--primary-blue);">Error Loading PDF</h3>
                <p>Please ensure you've uploaded a valid 26AS PDF file from TRACES.</p>
            </div>
        `;
    }
}

// Render PDF page
async function renderPDFPage(pageNumber) {
    try {
        const page = await pdfDocument.getPage(pageNumber);
        const viewport = page.getViewport({ scale: 1.2 });
        
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        canvas.height = viewport.height;
        canvas.width = viewport.width;
        canvas.className = 'pdf-canvas-container';
        
        pdfViewer.innerHTML = '';
        pdfViewer.appendChild(canvas);
        
        await page.render({
            canvasContext: context,
            viewport: viewport
        }).promise;
        
        // Update page info
        pageInfo.textContent = `Page ${pageNumber} of ${totalPages}`;
        
        // Update button states
        prevPageBtn.disabled = pageNumber <= 1;
        nextPageBtn.disabled = pageNumber >= totalPages;
        
    } catch (error) {
        console.error('Error rendering PDF page:', error);
        showNotification('Error rendering PDF page.', 'error');
    }
}

// Update file count display
function updateFileCount() {
    fileCountEl.textContent = selectedFile ? '1' : '0';
    summaryFileCount.textContent = selectedFile ? '1' : '0';
}

// Parse PDF and extract data using Python backend
async function parsePDF() {
    if (!selectedFile) {
        showNotification('Please select a 26AS PDF file first.', 'error');
        return;
    }
    
    extractedData.processingStats.startTime = Date.now();
    
    // Update UI for processing
    parseBtn.innerHTML = '<div class="loading"></div> Parsing 26AS PDF...';
    parseBtn.disabled = true;
    downloadBtn.disabled = true;
    progressBar.style.display = 'block';
    progressFill.style.width = '0%';
    
    try {
        const formData = new FormData();
        formData.append('file', selectedFile);
        
        // Show progress
        progressFill.style.width = '30%';
        
        // Send to Python backend for parsing
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        
        progressFill.style.width = '70%';
        
        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }
        
        const result = await response.json();
        
        progressFill.style.width = '100%';
        
        if (result.success) {
            // Store extracted data
            extractedData.assessee = result.data.assessee_info;
            extractedData.transactions = result.data.transactions;
            extractedData.processingStats.endTime = Date.now();
            
            // Update UI
            updateSummary();
            updateExcelPreview();
            updateAssesseeInfo();
            
            // Show transaction counter
            transactionCounter.style.display = 'flex';
            counterValue.textContent = extractedData.transactions.length;
            
            // Enable download button
            downloadBtn.disabled = false;
            
            // Switch to Excel preview
            previewTabs[1].click();
            
            // Show success notification
            showNotification(`Successfully parsed ${extractedData.transactions.length} transactions from 26AS PDF`, 'success');
            
        } else {
            throw new Error(result.error || 'Unknown error from server');
        }
        
    } catch (error) {
        console.error('Error parsing PDF:', error);
        showNotification('Error parsing PDF: ' + error.message, 'error');
    } finally {
        // Reset UI
        parseBtn.innerHTML = '<i class="fas fa-cogs"></i> Parse 26AS PDF';
        parseBtn.disabled = false;
        progressBar.style.display = 'none';
        progressFill.style.width = '0%';
    }
}

// Update summary cards
function updateSummary() {
    summaryTransactionCount.textContent = extractedData.transactions.length;
}

// Update assessee information display - FIXED FOR FINANCIAL YEAR
function updateAssesseeInfo() {
    if (extractedData.assessee && 
        (extractedData.assessee.name || 
         extractedData.assessee.pan || 
         extractedData.assessee.financialYear || 
         extractedData.assessee.financial_year)) {
        
        assesseeInfo.classList.add('visible');
        
        // Use financial_year if available (from new parser), otherwise use financialYear
        const financialYear = extractedData.assessee.financial_year || 
                             extractedData.assessee.financialYear || 
                             "Not Available";
        
        assesseeName.textContent = extractedData.assessee.name || "Not Available";
        assesseePAN.textContent = extractedData.assessee.pan || "Not Available";
        assesseeFY.textContent = financialYear;
    }
}

// Update Excel preview table - Show 50 transactions by default
function updateExcelPreview() {
    if (extractedData.transactions.length === 0) {
        excelBody.innerHTML = `
            <tr>
                <td colspan="13" style="text-align: center; padding: 4rem; color: var(--text-light);">
                    <i class="fas fa-file-excel" style="font-size: 3rem; margin-bottom: 1rem; display: block;"></i>
                    <h3 style="margin-bottom: 0.5rem; color: var(--primary-blue);">No Data to Display</h3>
                    <p>Parse 26AS PDF to see the extracted Excel data here</p>
                </td>
            </tr>
        `;
        excelInfo.textContent = 'No data parsed';
        excelRowInfo.textContent = 'Showing 0 rows';
        return;
    }
    
    // Update table header to include all columns
    document.getElementById('excelHeader').innerHTML = `
        <th>Sr.No</th>
        <th>Name of Deductor</th>
        <th>TAN of Deductor</th>
        <th>Section</th>
        <th>Transaction Date</th>
        <th>Status of Booking*</th>
        <th>Date of Booking</th>
        <th>Amount Paid / Credited</th>
        <th>Tax Deducted</th>
        <th>TDS Deposited</th>
        <th>Net Amount</th>
        <th>Rate %</th>
        <th>PDF Page No</th>
    `;
    
    // Update table body
    excelBody.innerHTML = '';
    
    // Show only first 50 rows for performance with scroll option
    const rowsToShow = extractedData.transactions.slice(0, 50);
    
    rowsToShow.forEach((transaction) => {
        const row = document.createElement('tr');
        
        // Format amounts with commas
        const formatAmount = (amt) => {
            if (!amt && amt !== 0) return '0.00';
            return parseFloat(amt).toLocaleString('en-IN', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        };
        
        row.innerHTML = `
            <td>${transaction.sr_no || ''}</td>
            <td>${transaction.deductor_name || 'Not Available'}</td>
            <td>${transaction.deductor_tan || ''}</td>
            <td>${transaction.section || ''}</td>
            <td>${transaction.transaction_date || ''}</td>
            <td>${transaction.status || 'F'}</td>
            <td>${transaction.date_of_booking || ''}</td>
            <td style="text-align: right;">₹${formatAmount(transaction.amount_paid)}</td>
            <td style="text-align: right;">₹${formatAmount(transaction.tax_deducted)}</td>
            <td style="text-align: right;">₹${formatAmount(transaction.tds_deposited)}</td>
            <td style="text-align: right;">₹${formatAmount(transaction.net_amount)}</td>
            <td style="text-align: right;">${parseFloat(transaction.rate || 0).toFixed(2)}%</td>
            <td style="text-align: center;">${transaction.page_number || ''}</td>
        `;
        
        excelBody.appendChild(row);
    });
    
    // Add info row with "Show All" button if we're showing limited data
    if (extractedData.transactions.length > 50) {
        const infoRow = document.createElement('tr');
        infoRow.innerHTML = `
            <td colspan="13" style="text-align: center; padding: 1rem; background: var(--light-blue); color: var(--primary-blue); font-weight: 600;">
                <i class="fas fa-info-circle"></i> 
                Showing first 50 of ${extractedData.transactions.length} transactions. 
                <button onclick="showAllTransactions()" style="margin-left: 10px; padding: 5px 15px; background: var(--accent-blue); color: white; border: none; border-radius: 4px; cursor: pointer;">
                    Show All
                </button>
                <br><small>Full data will be included in the downloaded file</small>
            </td>
        `;
        excelBody.appendChild(infoRow);
    }
    
    excelInfo.textContent = `Extracted ${extractedData.transactions.length} transactions from 26AS PDF`;
    excelRowInfo.textContent = `Showing ${Math.min(50, extractedData.transactions.length)} rows`;
}

// Function to show all transactions (optional)
function showAllTransactions() {
    if (!extractedData.transactions.length) return;
    
    // Clear and show all
    excelBody.innerHTML = '';
    
    extractedData.transactions.forEach((transaction) => {
        const row = document.createElement('tr');
        
        const formatAmount = (amt) => {
            if (!amt && amt !== 0) return '0.00';
            return parseFloat(amt).toLocaleString('en-IN', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        };
        
        row.innerHTML = `
            <td>${transaction.sr_no || ''}</td>
            <td>${transaction.deductor_name || 'Not Available'}</td>
            <td>${transaction.deductor_tan || ''}</td>
            <td>${transaction.section || ''}</td>
            <td>${transaction.transaction_date || ''}</td>
            <td>${transaction.status || 'F'}</td>
            <td>${transaction.date_of_booking || ''}</td>
            <td style="text-align: right;">₹${formatAmount(transaction.amount_paid)}</td>
            <td style="text-align: right;">₹${formatAmount(transaction.tax_deducted)}</td>
            <td style="text-align: right;">₹${formatAmount(transaction.tds_deposited)}</td>
            <td style="text-align: right;">₹${formatAmount(transaction.net_amount)}</td>
            <td style="text-align: right;">${parseFloat(transaction.rate || 0).toFixed(2)}%</td>
            <td style="text-align: center;">${transaction.page_number || ''}</td>
        `;
        
        excelBody.appendChild(row);
    });
    
    excelRowInfo.textContent = `Showing all ${extractedData.transactions.length} rows`;
}

// Show download modal
function showDownloadModal() {
    if (extractedData.transactions.length === 0) {
        showNotification('No data to download. Please parse a 26AS PDF first.', 'error');
        return;
    }
    
    // Update modal with current data
    modalPageCount.textContent = extractedData.processingStats.pageCount || 1;
    modalTransactionCount.textContent = extractedData.transactions.length;
    
    const processingTime = ((extractedData.processingStats.endTime - extractedData.processingStats.startTime) / 1000).toFixed(2);
    modalTime.textContent = `${processingTime}s`;
    
    // Estimate file size
    const estimatedSizeKB = Math.round((extractedData.transactions.length * 13 * 15) / 1024);
    modalFileSize.textContent = `${estimatedSizeKB} KB`;
    
    // Show modal
    reportModal.style.display = 'flex';
}

// Download Excel file via Python backend
async function downloadExcelFile() {
    if (extractedData.transactions.length === 0) {
        showNotification('No data to download.', 'error');
        return;
    }
    
    try {
        confirmDownload.innerHTML = '<div class="loading"></div> Generating Excel...';
        confirmDownload.disabled = true;
        
        // Prepare data for backend
        const downloadData = {
            assessee_info: extractedData.assessee,
            transactions: extractedData.transactions
        };
        
        // Send request to backend
        const response = await fetch('/download_excel', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(downloadData)
        });
        
        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            // Download the file
            const downloadUrl = result.download_url;
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = result.filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            
            // Update statistics
            userData.totalFilesProcessed++;
            userData.todayFilesProcessed++;
            saveUserData();
            
            // Close modal and show notification
            reportModal.style.display = 'none';
            showNotification('Excel file downloaded successfully!', 'success');
            
        } else {
            throw new Error(result.error || 'Failed to generate Excel file');
        }
        
    } catch (error) {
        console.error('Error downloading file:', error);
        showNotification('Error generating Excel file: ' + error.message, 'error');
    } finally {
        confirmDownload.innerHTML = '<i class="fas fa-download"></i> Download Excel File';
        confirmDownload.disabled = false;
    }
}

// Reset tool
function resetTool() {
    selectedFile = null;
    pdfDocument = null;
    currentPage = 1;
    totalPages = 0;
    
    extractedData = {
        assessee: {
            name: '',
            pan: '',
            financialYear: '',
            address: '',
            assessmentYear: ''
        },
        transactions: [],
        processingStats: {
            startTime: 0,
            endTime: 0,
            pageCount: 0
        }
    };
    
    // Reset UI
    updateFileCount();
    summaryTransactionCount.textContent = '0';
    
    parseBtn.disabled = true;
    downloadBtn.disabled = true;
    progressBar.style.display = 'none';
    
    transactionCounter.style.display = 'none';
    counterValue.textContent = '0';
    assesseeInfo.classList.remove('visible');
    pdfControls.style.display = 'none';
    
    // Reset previews
    pdfViewer.innerHTML = `
        <div style="text-align: center; padding: 4rem; color: var(--text-light);">
            <i class="fas fa-file-pdf" style="font-size: 4rem; margin-bottom: 1.5rem; display: block; color: var(--border-blue);"></i>
            <h3 style="margin-bottom: 0.8rem; color: var(--primary-blue);">No PDF to Display</h3>
            <p>Upload a 26AS PDF file to see the preview here</p>
        </div>
    `;
    
    pdfInfo.textContent = 'No PDF loaded. Upload a 26AS PDF to see preview.';
    
    // Reset Excel table header
    document.getElementById('excelHeader').innerHTML = `
        <th>Sr.No</th>
        <th>Name of Deductor</th>
        <th>TAN of Deductor</th>
        <th>Section</th>
        <th>Transaction Date</th>
        <th>Status of Booking*</th>
        <th>Amount Paid / Credited</th>
        <th>Tax Deducted</th>
        <th>TDS Deposited</th>
        <th>Net Amount</th>
        <th>Rate %</th>
    `;
    
    updateExcelPreview();
    
    // Reset file input
    fileInput.value = '';
    
    // Switch to PDF preview
    previewTabs[0].click();
    
    showNotification('Tool has been reset successfully.', 'success');
}

// Show notification
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        color: white;
        font-weight: 600;
        z-index: 9999;
        display: flex;
        align-items: center;
        gap: 0.8rem;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        animation: slideIn 0.3s ease;
        max-width: 400px;
    `;
    
    // Set color based on type
    if (type === 'success') {
        notification.style.background = 'var(--success-green)';
    } else if (type === 'error') {
        notification.style.background = 'var(--error-red)';
    } else {
        notification.style.background = 'var(--accent-blue)';
    }
    
    // Add icon based on type
    let icon = 'info-circle';
    if (type === 'success') icon = 'check-circle';
    if (type === 'error') icon = 'exclamation-circle';
    
    notification.innerHTML = `
        <i class="fas fa-${icon}"></i>
        <span>${message}</span>
    `;
    
    document.body.appendChild(notification);
    
    // Remove notification after 5 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 5000);
    
    // Add CSS for animations if not already added
    if (!document.querySelector('#notification-styles')) {
        const style = document.createElement('style');
        style.id = 'notification-styles';
        style.textContent = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    init();
});