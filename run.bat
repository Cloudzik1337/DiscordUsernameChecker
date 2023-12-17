@echo off

echo Installing requirements

pip install -r requirements.txt

cls

echo Assuming successful installation, starting cloud_checker.py in 2 seconds

timeout /t 2

py cloud_checker.py