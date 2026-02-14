@echo off
echo Installing Microsoft C++ Build Tools...
echo.
echo Step 1: Please download and install from:
echo https://visualstudio.microsoft.com/visual-cpp-build-tools/
echo.
echo After installation, press any key to continue...
pause

echo.
echo Installing Python packages...
python -m pip install --upgrade pip
pip install flask==2.3.3
pip install pandas==2.0.3
pip install openpyxl==3.1.2
pip install pdfplumber==0.10.3
pip install PyMuPDF==1.23.8

echo.
echo Installation complete!
echo.
echo Starting 26AS Parser Tool...
python app.py
pause