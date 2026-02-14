@echo off
echo Uninstalling old packages...
pip uninstall pandas -y
pip uninstall numpy -y

echo Installing compatible versions...
pip install "numpy<2.0" --force-reinstall
pip install "pandas==2.0.3" --force-reinstall
pip install "openpyxl==3.1.2" --force-reinstall

echo Verifying installation...
python -c "import pandas; print('Pandas version:', pandas.__version__)"
python -c "import numpy; print('NumPy version:', numpy.__version__)"

echo Done!
pause