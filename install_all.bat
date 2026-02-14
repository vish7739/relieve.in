@echo off
echo Removing old packages...
pip uninstall pandas numpy -y

echo Installing numpy first...
pip install "numpy==1.24.3"

echo Installing pandas...
pip install "pandas==2.0.3"

echo Installing other packages...
pip install flask==2.3.3
pip install openpyxl==3.1.2
pip install pdfplumber==0.10.3
pip install PyMuPDF==1.23.8

echo Verifying installation...
python -c "import numpy; print('NumPy version:', numpy.__version__)"
python -c "import pandas; print('Pandas version:', pandas.__version__)"
python -c "import flask; print('Flask installed')"
python -c "import openpyxl; print('OpenPyXL installed')"

echo All packages installed successfully!
pause