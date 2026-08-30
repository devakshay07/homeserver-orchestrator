#!/bin/bash
set -e
echo "Updating HomeServer..."
git pull origin main
source venv/bin/activate
pip install -r requirements.txt --upgrade
echo "Update complete. Please restart the service."
