#!/bin/bash
# Launchpad Mapper - Start Script

cd "$(dirname "$0")"

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not installed."
    exit 1
fi

# Check for virtual environment, create if missing
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Checking dependencies..."
pip install -q -r requirements.txt

# Run the server
echo ""
echo "Starting Launchpad Mapper..."
echo "Open http://localhost:5000 in your browser"
echo ""
python server.py
