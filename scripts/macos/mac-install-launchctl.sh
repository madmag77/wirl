#!/bin/bash

# macOS Overmind LaunchCtl Installation Script
# This script installs overmind, generates a plist file from template, and sets up autoload

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PLIST_TEMPLATE="$REPO_ROOT/infra/macos/launchctl.plist.template"
SERVICE_NAME="com.local.wirl.overmind"
LAUNCHAGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$LAUNCHAGENTS_DIR/$SERVICE_NAME.plist"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to install overmind
install_overmind() {
    print_status "Checking if overmind is installed..."
    
    if command_exists overmind; then
        print_success "Overmind is already installed at $(which overmind)"
        return 0
    fi
    
    print_status "Overmind not found. Installing via Homebrew..."
    
    # Check if homebrew is installed
    if ! command_exists brew; then
        print_error "Homebrew is not installed. Please install Homebrew first:"
        print_error "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
    
    # Install overmind
    brew install overmind
    
    if command_exists overmind; then
        print_success "Overmind installed successfully at $(which overmind)"
    else
        print_error "Failed to install overmind"
        exit 1
    fi
}

# Function to generate plist from template
generate_plist() {
    print_status "Generating plist file from template..."
    
    if [ ! -f "$PLIST_TEMPLATE" ]; then
        print_error "Template file not found: $PLIST_TEMPLATE"
        exit 1
    fi
    
    # Get current user
    CURRENT_USER=$(whoami)
    
    # Get overmind path
    OVERMIND_PATH=$(which overmind)
    
    # Create LaunchAgents directory if it doesn't exist
    mkdir -p "$LAUNCHAGENTS_DIR"
    
    # Replace placeholders in template
    sed -e "s|{USERNAME}|$CURRENT_USER|g" \
        -e "s|{PATH TO REPO}|$REPO_ROOT|g" \
        -e "s|{PATH TO HOME FOLDER}|$HOME|g" \
        -e "s|/opt/homebrew/bin/overmind|$OVERMIND_PATH|g" \
        -e "s|/Users/artemgoncharov/bpmn-workflows|$REPO_ROOT|g" \
        "$PLIST_TEMPLATE" > "$PLIST_FILE"
    
    # Create log directory
    mkdir -p "$HOME/.local/log"
    
    print_success "Generated plist file: $PLIST_FILE"
}

# Function to install and load the service
install_and_load_service() {
    print_status "Installing and loading the service..."
    
    # Unload existing service if it exists
    if launchctl list | grep -q "$SERVICE_NAME"; then
        print_status "Unloading existing service..."
        launchctl unload "$PLIST_FILE" 2>/dev/null || true
    fi
    
    # Load the new service
    print_status "Loading service: $SERVICE_NAME"
    launchctl load "$PLIST_FILE"
    
    # Start the service
    print_status "Starting service..."
    launchctl start "$SERVICE_NAME"
    
    print_success "Service installed and loaded successfully"
}

# Function to verify installation
verify_installation() {
    print_status "Verifying installation..."
    
    # Check if service is loaded
    if launchctl list | grep -q "$SERVICE_NAME"; then
        print_success "Service is loaded in launchctl"
    else
        print_error "Service is not loaded in launchctl"
        return 1
    fi
    
    # Wait a moment for service to start
    sleep 3
    
    # Check if overmind socket exists
    SOCKET_PATH="$REPO_ROOT/.overmind.sock"
    if [ -S "$SOCKET_PATH" ]; then
        print_success "Overmind socket found: $SOCKET_PATH"
    else
        print_warning "Overmind socket not found. Service might still be starting..."
    fi
    
    # Check log files
    LOG_OUT="$HOME/.local/log/bpmn-workflows-overmind.out"
    LOG_ERR="$HOME/.local/log/bpmn-workflows-overmind.err"
    
    if [ -f "$LOG_OUT" ]; then
        print_status "Output log: $LOG_OUT"
        if [ -s "$LOG_OUT" ]; then
            print_status "Recent output log entries:"
            tail -5 "$LOG_OUT" | sed 's/^/  /'
        fi
    fi
    
    if [ -f "$LOG_ERR" ] && [ -s "$LOG_ERR" ]; then
        print_warning "Error log has content: $LOG_ERR"
        print_status "Recent error log entries:"
        tail -5 "$LOG_ERR" | sed 's/^/  /'
    fi
}

# Function to show debugging information
show_debug_info() {
    print_status "Debugging information:"
    echo "  Repository root: $REPO_ROOT"
    echo "  Plist file: $PLIST_FILE"
    echo "  Service name: $SERVICE_NAME"
    echo "  Overmind path: $(which overmind 2>/dev/null || echo 'Not found')"
    echo "  Current user: $(whoami)"
    echo ""
    print_status "To debug issues:"
    echo "  1. Check service status: launchctl list | grep $SERVICE_NAME"
    echo "  2. View logs: tail -f $HOME/.local/log/bpmn-workflows-overmind.out"
    echo "  3. View errors: tail -f $HOME/.local/log/bpmn-workflows-overmind.err"
    echo "  4. Restart service: launchctl unload '$PLIST_FILE' && launchctl load '$PLIST_FILE'"
    echo "  5. Check overmind manually: cd '$REPO_ROOT' && overmind start"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  --debug        Show debugging information and exit"
    echo "  --uninstall    Uninstall the service"
    echo ""
    echo "This script will:"
    echo "  1. Install overmind (if not present)"
    echo "  2. Generate plist from template"
    echo "  3. Install and load the LaunchAgent service"
    echo "  4. Verify the installation"
}

# Function to uninstall service
uninstall_service() {
    print_status "Uninstalling service..."
    
    if launchctl list | grep -q "$SERVICE_NAME"; then
        launchctl unload "$PLIST_FILE"
        print_success "Service unloaded"
    fi
    
    if [ -f "$PLIST_FILE" ]; then
        rm "$PLIST_FILE"
        print_success "Plist file removed"
    fi
    
    print_success "Service uninstalled successfully"
}

# Main execution
main() {
    print_status "Starting macOS Overmind LaunchCtl installation..."
    print_status "Repository: $REPO_ROOT"
    
    # Parse command line arguments
    case "${1:-}" in
        -h|--help)
            show_usage
            exit 0
            ;;
        --debug)
            show_debug_info
            exit 0
            ;;
        --uninstall)
            uninstall_service
            exit 0
            ;;
    esac
    
    # Check if we're in the right directory
    if [ ! -f "$REPO_ROOT/procfile" ]; then
        print_error "Procfile not found in repository root. Are you in the correct directory?"
        exit 1
    fi
    
    # Execute installation steps
    install_overmind
    generate_plist
    install_and_load_service
    verify_installation
    
    print_success "Installation completed successfully!"
    print_status "Your wirl services should now start automatically on system boot."
    print_status ""
    show_debug_info
}

# Run main function with all arguments
main "$@"
