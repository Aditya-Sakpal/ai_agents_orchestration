#!/bin/bash

# Activate the Poetry environment
source $(poetry env info --path)/bin/activate

# Check if --debug flag was provided as the first argument
DEBUG_MODE=0
if [ "$1" == "--debug" ]; then
    DEBUG_MODE=1
fi

# Prompt the user to choose an option
echo "Please choose an option:"
echo "1. Streamlit (with AMA)"
echo "2. Voice (with AMA)"
echo "3. API (with AMA)"
read -p "Enter your choice (1 or 2): " choice

case $choice in
    1)
        if [ $DEBUG_MODE -eq 1 ]; then
            echo "Running Streamlit application (with AMA) under debugpy"
            export PYDEVD_DISABLE_FILE_VALIDATION=1
            echo "Waiting for debugger to attach on port 5678."
            python -Xfrozen_modules=off -m debugpy --listen 5678 --wait-for-client -m streamlit run ama_main_st.py
        else
            echo "Running Streamlit application (with AMA)"
            streamlit run ama_main_st.py
        fi
        ;;
    2)
        if [ $DEBUG_MODE -eq 1 ]; then
            echo "Running Voice Integration (with AMA) under debugpy"
            export PYDEVD_DISABLE_FILE_VALIDATION=1
            echo "Waiting for debugger to attach on port 5678."
            python -Xfrozen_modules=off -m debugpy --listen 5678 --wait-for-client ama_main_voice.py start
        else
            echo "Running Voice Integration (with AMA)"
            python ama_main_voice.py start
        fi
        ;;
    3)
        if [ $DEBUG_MODE -eq 1 ]; then
            echo "Running API (with AMA) under debugpy"
            export PYDEVD_DISABLE_FILE_VALIDATION=1
            echo "Waiting for debugger to attach on port 5678."
            python -Xfrozen_modules=off -m debugpy --listen 5678 --wait-for-client ama_main_api.py start
        else
            echo "Running API (with AMA)"
            uvicorn ama_main_api:app --reload
        fi
        ;;
    *)
        echo "Invalid choice. Please run the script again and choose either 1 or 2."
        ;;
esac