#!/bin/bash

# Set Python version
echo "Setting Python version to 3.11.9..."
pyenv shell 3.11.9

# Install requirements if not already installed
echo "Installing requirements..."
pip install -r backend/requirements.txt

# Run the combined server
echo "Starting the combined server..."
python server.py