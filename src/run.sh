#!/bin/bash
echo "Running for $(tail -1 input)"
python3 parse.py $(tail -1 input)
