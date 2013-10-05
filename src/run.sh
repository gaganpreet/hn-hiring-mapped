#!/bin/bash
echo "Checking latest HN hiring link..."
python3 get_latest.py
echo "Running for $(tail -1 input)"
python3 parse.py $(tail -1 input)
