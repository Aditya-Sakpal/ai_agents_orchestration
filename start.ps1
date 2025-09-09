# start.ps1 - Windows PowerShell Script

# Activate the Poetry environment
$poetryEnvPath = & poetry env info --path
if ($poetryEnvPath) {
    & "$poetryEnvPath\Scripts\Activate"
} else {
    Write-Host "Poetry environment not found. Please run 'poetry install' first."
    exit 1
}

# Prompt the user to choose an option
Write-Host "Please choose an option:"
Write-Host "1. Streamlit (with AMA)"
Write-Host "2. Voice (with AMA)"
$choice = Read-Host "Enter your choice (1 or 2)"

switch ($choice) {
    "1" {
        Write-Host "Running Streamlit application (with AMA)..."
        streamlit run ama_main_st.py
    }
    "2" {
        Write-Host "Running Voice Integration (with AMA)..."
        python ama_main_voice.py start
    }
    default {
        Write-Host "Invalid choice. Please run the script again and choose either 1 or 2."
    }
}