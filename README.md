# AI Terminal Assistant 🚀

An AI-powered terminal assistant with a PyQt6 GUI, providing an interactive experience similar to tools like Warp or GitHub Copilot CLI, but with a visual interface for AI interactions, file management, and command execution.

## Features ✨

* **AI-Powered Queries**: Ask the AI to perform tasks, write code, explain concepts, etc.
* **Shell Command Execution**: Run shell commands directly from the interface.
* **File Explorer**: Basic built-in file explorer for the current directory.
* **Action Confirmation**: AI can request confirmation for potentially sensitive actions.
* **Dark Theme**: Modern, comfortable dark theme UI.
* **Session Resume**: Ability to resume previous AI conversations (loads from `chat_context.json`).
* **JSON-based AI Interaction**: Structured communication with the AI model.

## Prerequisites

* Python 3.8+
* An OpenAI API key (set as an environment variable `OPENAI_API_KEY`)

## Installation 📦

1.  **Clone the repository (if you're distributing source):**
    ```bash
    git clone [https://github.com/yourusername/ai-terminal-assistant-project.git](https://github.com/yourusername/ai-terminal-assistant-project.git)
    cd ai-terminal-assistant-project
    ```
    Or, if you build a wheel file, you can distribute that directly.

2.  **Install using pip:**
    From the project root directory (`ai_terminal_assistant_project`):
    ```bash
    pip install .
    ```
    This will install the package and its dependencies.

    For development, you might want to install in editable mode:
    ```bash
    pip install -e .
    ```

## Usage 🚀

After installation, you can run the assistant from your terminal:

```bash
ai-terminal-assistant
```
# AI Terminal Assistant

This project provides an AI-powered terminal assistant with a GUI interface.

## Installation

### Option 1: Run from Source
1. Install dependencies:
```bash
pip install -r ai_terminal_assistant/requirements.txt
```

# Using Wheel package
```bash
pip install dist/ai_terminal_assistant-2.0.0-py3-none-any.whl


# OR using Tarball
pip install dist/ai_terminal_assistant-2.0.0.tar.gz

# Then run from terminal
ai-assistant

```
## Install from here 
[Download the .tar.z file](ai_terminal_assistant_project/dist/ai_terminal_assistant-2.0.0.tar.gz)
