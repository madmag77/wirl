# Photo Notes Workflow

A WIRL workflow that automatically extracts useful text and information from recent photos and saves them as organized notes in Obsidian.

## ⚠️ macOS Only

**This workflow is designed exclusively for macOS users** and requires macOS Shortcuts app for photo export automation.

## What It Does

The Photo Notes Workflow:

1. **Automatically exports recent photos** using macOS Shortcuts (scheduled daily at 5 AM)
2. **Reads exported photos** from a designated folder (~/Exports by default)
3. **Analyzes each photo** using AI vision to classify and extract information:
   - **Casual photos**: Simply classifies the image type
   - **Product/Object photos**: Detailed descriptions including any visible text
   - **Document photos**: Extracts all text while preserving formatting
   - **Screenshots**: Extracts text content from screenshots
4. **Saves extracted notes** to an Obsidian markdown file with timestamp

## Prerequisites

### System Requirements
- **macOS** (required for Shortcuts app integration)
- **Python 3.11+**
- **Local LLM server** (Ollama with Gemma3:12b model by default)

### Required Permissions

#### Shortcuts App Permissions
The Shortcuts automation requires Photos access:

1. Open **System Settings** → **Privacy & Security** → **Photos**
2. Enable **Shortcuts** in the list
3. If Shortcuts isn't listed, run the shortcut once manually to trigger the permission prompt

#### Advanced Shortcuts Settings
Enable automation capabilities in Shortcuts:

1. Open **Shortcuts** app
2. Go to **Settings** (gear icon in top-right)
3. Click **Advanced** tab
4. Enable all checkboxes:
   - ✅ **Allow Running Scripts**
   - ✅ **Allow Sharing Large Amounts of Data**
   - ✅ **Allow Deleting Without Confirmation**
   - ✅ **Allow Deleting Large Amounts of Data**

## Installation

### 1. Create Shortcuts Automation

Create a Shortcuts automation to export photos daily:

1. **Open Shortcuts app**
2. **Create new shortcut** named "Export daily photos"
3. **Add the following actions in order:**
   - **Get Contents of** → Select "Exports" folder (create ~/Exports folder first)
   - **Delete** → "Folder Contents" (clears previous exports)
   - **Find Photos** where "Date Taken is in the last 1 day"
   - **Save Photos** to "Exports" folder
   - **Stop and Output** → "Do Nothing"

4. **Test the shortcut** manually first to ensure it works

### 2. Set Up Daily Automation

Set up the shortcut to run automatically at 5 AM daily:

1. **Copy the launchd plist file:**
   ```bash
   cp workflow_definitions/photo_notes_workflow/infra/com.local.daily-photo-export.plist ~/Library/LaunchAgents/
   ```

2. **Load the automation:**
   ```bash
   launchctl load ~/Library/LaunchAgents/com.local.daily-photo-export.plist
   ```

3. **Test the automation immediately (optional):**
   ```bash
   launchctl start com.local.daily-photo-export
   ```

4. **Check automation status:**
   ```bash
   launchctl list | grep daily-photo-export
   ```

### 3. Install Workflow Dependencies

From the WIRL repository root:

```bash
# Install all WIRL dependencies
make workflows-setup
```

### 4. Set Up Local LLM (Ollama)

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

The workflow is configured with these defaults:

- **Export path**: `~/Exports` (folder where Shortcuts saves photos)
- **Shortcuts schedule**: Daily at 5:00 AM
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

### Changing the Export Schedule

To modify when photos are exported, edit the plist file before loading:

```xml
<key>StartCalendarInterval</key>
<dict>
    <key>Hour</key>
    <integer>5</integer>  <!-- Change this (0-23) -->
    <key>Minute</key>
    <integer>0</integer>  <!-- Change this (0-59) -->
</dict>
```

### Changing the Export Path

To use a different export folder, edit the `photo_notes_workflow.wirl` file:

```wirl
node GetPhotos {
    call get_photos
    inputs {
      String obsidian_folder_path = obsidian_folder_path
    }
    const {
      export_path: "~/MyCustomExports"  # Change this
    }
    outputs {
      List<String> file_paths
    }
  }
```

**Note:** Also update your Shortcuts automation to save to the same folder.

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

1. **Shortcuts automation not working**
   - Check Shortcuts permissions in System Settings → Privacy & Security → Photos
   - Ensure Advanced settings are enabled in Shortcuts app
   - Test the shortcut manually first
   - Check launchd status: `launchctl list | grep daily-photo-export`

2. **"No photos found" in workflow**
   - Verify Shortcuts exported photos to ~/Exports folder
   - Check that photos exist: `ls -la ~/Exports/`
   - Test Shortcuts automation: `launchctl start com.local.daily-photo-export`

3. **Launchd automation issues**
   - Check if plist is loaded: `launchctl list | grep daily-photo-export`
   - View logs: `log show --predicate 'subsystem == "com.apple.launchd"' --info --last 1h | grep daily-photo-export`
   - Reload if needed: `launchctl unload ~/Library/LaunchAgents/com.local.daily-photo-export.plist && launchctl load ~/Library/LaunchAgents/com.local.daily-photo-export.plist`

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
- **Shortcuts dependency**: Requires macOS Shortcuts app for photo export
- **Daily schedule**: Configured to export photos once per day at 5 AM
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

1. **macOS Shortcuts documentation**: https://support.apple.com/guide/shortcuts-mac/
2. **Ollama setup**: https://ollama.ai/
3. **WIRL framework**: See main repository README

Remember that this workflow requires specific macOS Shortcuts permissions and launchd setup - ensure all prerequisites are met before troubleshooting code issues.
