# Photo Notes Workflow

A WIRL workflow that automatically extracts useful text and information from recent photos and saves them as organized notes in Obsidian.

## ⚠️ macOS Only

**This workflow is designed exclusively for macOS users** and requires the native macOS Photos app integration through the `osxphotos` library.

## What It Does

The Photo Notes Workflow:

1. **Exports recent photos** from your macOS Photos library (last 24 hours by default)
2. **Analyzes each photo** using AI vision to classify and extract information:
   - **Casual photos**: Simply classifies the image type
   - **Product/Object photos**: Detailed descriptions including any visible text
   - **Document photos**: Extracts all text while preserving formatting
   - **Screenshots**: Extracts text content from screenshots
3. **Saves extracted notes** to an Obsidian markdown file with timestamp

## Prerequisites

### System Requirements
- **macOS** (required for Photos app integration)
- **Python 3.11+**
- **Full Disk Access** permission for Terminal/your IDE
- **Local LLM server** (Ollama with Gemma3:12b model by default)

### Required Permissions

#### Full Disk Access Setup
This workflow requires Full Disk Access to read your Photos library:

1. Open **System Preferences** → **Security & Privacy** → **Privacy**
2. Select **Full Disk Access** from the left panel
3. Click the lock icon and enter your password
4. Click the **+** button and add:
   - **Terminal** (if running from command line)
   - **Your IDE** (VS Code, Cursor, etc. if running from IDE)
   - **Python** executable (usually `/usr/bin/python3` or your virtual environment python)

#### Photos Access
The workflow will request Photos access the first time it runs. Grant permission when prompted.

## Installation

### 1. Install osxphotos

The workflow requires the `osxphotos` library for Photos app integration:

```bash
# Option 1: Install via pip (recommended)
pip install osxphotos

# Option 2: Install via homebrew
brew install osxphotos

# Verify installation
osxphotos --version
```

### 2. Install Workflow Dependencies

From the WIRL repository root:

```bash
# Install all WIRL dependencies
make workflows-setup
```

### 3. Set Up Local LLM (Ollama)

The workflow uses a local LLM for image analysis:

```bash
# Install Ollama
brew install ollama

# Start Ollama service
brew services start ollama

# Pull the required model (Gemma3:12b)
ollama pull gemma3:12b

# Verify the model is available
ollama list
```

## Usage

### Command Line

```bash
# Activate virtual environment
. .venv/bin/activate

# Run the workflow
python -m wirl_pregel_runner.pregel_runner \
  workflow_definitions/photo_notes_workflow/photo_notes_workflow.wirl \
  --functions workflow_definitions.photo_notes_workflow.photo_notes_workflow \
  --param obsidian_folder_path="/path/to/your/obsidian/vault"
```

Alternatively, if you already installed backend and runners you can use github actions to run the workflow regularly on a predefined cadence.

### Parameters

- **obsidian_folder_path**: Absolute path to your Obsidian vault directory where notes will be saved

### Example

```bash
python -m wirl_pregel_runner.pregel_runner \
  workflow_definitions/photo_notes_workflow/photo_notes_workflow.wirl \
  --functions workflow_definitions.photo_notes_workflow.photo_notes_workflow \
  --param obsidian_folder_path="/Users/yourname/Documents/ObsidianVault"
```

## Configuration

### Default Settings

The workflow is configured with these defaults in the WIRL file:

- **Export path**: `~/Exports` (temporary folder for photo exports)
- **Date range**: Last 24 hours of photos
- **AI Model**: `gemma3:12b` 
- **LLM Server**: `http://localhost:11434/v1/` (local Ollama)
- **Temperature**: `0` (deterministic responses)
- **Max iterations**: `30` photos per run

### Customizing the AI Model

To use a different model, edit the `photo_notes_workflow.wirl` file:

```wirl
node ExtractNote {
  const {
    model: "llama3.2-vision"  # Change this
    base_url: "http://localhost:11434/v1/"
    temperature: 0
  }
}
```

### Changing the Date Range

To modify how many days back to look for photos, edit the `photo_notes_workflow.wirl` file:

```wirl
node GetPhotos {
    call get_photos
    inputs {
      String obsidian_folder_path = obsidian_folder_path
    }
    const {
      export_path: "~/Exports"
      days_back: 1 # Change this
    }
    outputs {
      List<String> file_paths
    }
  }
```

## Output

The workflow creates a markdown file in your Obsidian vault:

- **Filename**: `note_from_photos_YYYY-MM-DD.md`
- **Location**: Root of your specified Obsidian folder
- **Format**: Each photo gets its own section with extracted text/information

### Example Output

```markdown
# Photo1
**Class 3 - Document Photo**

Receipt from Coffee Shop
Date: 2024-01-15
Items:
- Latte: $4.50
- Croissant: $3.25
Total: $7.75

# Photo2
**Class 4 - Screenshot**

Email from John regarding meeting:
"Hi team, let's reschedule our sync to 3 PM tomorrow..."
```

## Troubleshooting

### Common Issues

1. **"Permission denied" errors**
   - Ensure Full Disk Access is granted (see Prerequisites)
   - Try running with `sudo` if needed

2. **"osxphotos command not found"**
   - Install osxphotos: `pip install osxphotos`
   - Ensure it's in your PATH

3. **"No photos found"**
   - Check that you have photos from the last 24 hours
   - Verify Photos app permissions
   - Try running `osxphotos list --from-date $(date -v-1d +%Y-%m-%d)` manually

4. **LLM connection errors**
   - Ensure Ollama is running: `brew services list | grep ollama`
   - Check the model is available: `ollama list`
   - Verify the base_url in the workflow configuration

5. **HEIC image support issues**
   - Install pillow-heif: `pip install pillow-heif`
   - On some systems you may need: `brew install libheif`

## Limitations

- **macOS only**: Cannot run on Windows or Linux
- **Local LLM required**: Needs Ollama or compatible OpenAI-style API
- **Recent photos only**: Configured for last 24 hours by default
- **Photos app dependency**: Requires access to macOS Photos library
- **File format support**: Limited to common image formats (JPEG, PNG, HEIC)

## Development

### Running Tests

```bash
cd workflow_definitions/photo_notes_workflow
python -m pytest tests/
```

### Extending the Workflow

To modify the AI prompt or add new photo classification types, edit the `extract_note` function in `photo_notes_workflow.py`.

To change the export behavior or add filters, modify the `get_photos` function.

## Support

For issues specific to this workflow, check:

1. **osxphotos documentation**: https://github.com/RhetTbull/osxphotos
2. **Ollama setup**: https://ollama.ai/
3. **WIRL framework**: See main repository README

Remember that this workflow requires specific macOS permissions and setup - ensure all prerequisites are met before troubleshooting code issues.
