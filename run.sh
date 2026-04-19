#!/bin/bash
cd "$(dirname "$0")"
export LIBVA_DRIVER_NAME=iHD
source venv/bin/activate
python3 main.py
