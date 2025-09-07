# Wirl VSCode Extension

This folder contains a minimal Visual Studio Code extension that provides syntax highlighting for `.wirl` files.

## Install Locally

1. Ensure you have Node.js installed.
2. From this folder run:

```bash
npm install
npx vsce package
```

3. In VS Code press `Ctrl+Shift+P` and choose **Extensions: Install from VSIX...**
   then select the generated `.vsix` file.

After installation, files with the `.wirl` extension will be highlighted automatically.
