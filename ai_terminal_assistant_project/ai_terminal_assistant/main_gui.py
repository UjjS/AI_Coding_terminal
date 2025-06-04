import sys
import threading
import queue
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QSplitter, QLabel, QFrame,
    QProgressBar, QMessageBox # QTabWidget, QFileDialog were imported but QFileDialog only one used
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt # QTimer was imported but not used
from PyQt6.QtGui import QTextCursor # QFont, QPalette, QColor were imported but not used

from ai_utils import (
    SYSTEM_PROMPT, save_context, load_context, _process_user_query_for_worker, execute_actions,client,run_command,read_file
)
# QFileDialog is part of QtWidgets, so it's already imported.
from PyQt6.QtWidgets import QFileDialog

import os
import json

class AIWorkerThread(QThread):
    """Separate thread for AI processing to keep GUI responsive"""
    output_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(str)
    confirmation_signal = pyqtSignal(str, list)
    finished_signal = pyqtSignal()

    def __init__(self, query, resume=False):
        super().__init__()
        self.query = query
        self.resume = resume
        # self.confirmed = False # This wasn't used
        self.confirmation_queue = queue.Queue()

    def run(self):
        try:
            result = self.process_query_with_gui()
            self.output_signal.emit(str(result)) # Ensure result is a string
        except Exception as e:
            self.output_signal.emit(f"❌ Error in AIWorkerThread: {str(e)}")
        finally:
            self.finished_signal.emit()

    def process_query_with_gui(self):
        # Uses the refactored AI logic from ai_utils
        global client, SYSTEM_PROMPT, save_context, load_context, _process_user_query_for_worker, execute_actions

        if self.resume:
            messages = load_context()
            if not messages: # If context is empty or couldn't load
                # Provide a default starting point for resume if context is empty
                # Or emit an error message
                self.progress_signal.emit("Context is empty or couldn't be loaded. Starting new session with resume query if provided.")
                messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                if self.query: # If a query was provided with resume, use it.
                    messages.append({"role": "user", "content": self.query})
                else: # If no query and empty context, this might be an issue.
                     messages.append({"role": "user", "content": "Resume the previous conversation or task."})

            elif self.query : # If there's a query along with resume, append it.
                 messages.append({"role": "user", "content": self.query})
        else:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": self.query}
            ]

        while True:
            # Use the helper from ai_utils
            ai_response_str = _process_user_query_for_worker(messages, client)

            if ai_response_str is None: # Handle case where client might be None
                return "❌ Error: AI client is not available."

            messages.append({"role": "assistant", "content": ai_response_str}) # Save the raw JSON string
            save_context(messages)

            try:
                parsed = json.loads(ai_response_str)
            except json.JSONDecodeError:
                self.progress_signal.emit(f"⚠️ AI response (not valid JSON): {ai_response_str}")
                return "⚠️ Error: AI response is not valid JSON. Check console for raw AI output."

            step = parsed.get("step")
            content_text = parsed.get("content", "")
            actions = parsed.get("actions", [])
            requires_confirmation = parsed.get("requires_confirmation", False)

            self.progress_signal.emit(f"📋 {step.upper() if step else 'AI'}: {content_text}")

            if step == "plan":
                if actions:
                    action_text = "\nPlanned actions:\n"
                    for i, action in enumerate(actions, 1):
                        action_text += f"  {i}. {action.get('description', action.get('tool_name', 'Unknown action'))}\n"
                    self.progress_signal.emit(action_text)
                # Continue to next AI interaction implicitly by continuing the loop
                # The AI should now generate a "confirm" or "execute" step
                messages.append({"role": "user", "content": "User acknowledges plan. Proceed to confirmation or execution."})
                continue # Get next step from AI

            elif step == "confirm" and requires_confirmation:
                self.confirmation_signal.emit(content_text, actions)
                try:
                    confirmed_by_user = self.confirmation_queue.get(timeout=120)  # 120 second timeout
                    if confirmed_by_user:
                        self.progress_signal.emit("✅ User confirmed.")
                        messages.append({"role": "user", "content": "User confirmed. Proceed with execution."})
                        # The AI should now respond with an "execute" step
                        continue # Get next step from AI (which should be execute)
                    else:
                        self.progress_signal.emit("❌ Action cancelled by user.")
                        messages.append({"role": "user", "content": "User cancelled. Abort actions."})
                        # The AI should respond with a "report" step indicating cancellation
                        continue # Get next step from AI
                except queue.Empty:
                    return "❌ Confirmation timeout. Please try again."

            elif step == "execute":
                if actions:
                    self.progress_signal.emit("🚀 Executing actions...")
                    # Use execute_actions from ai_utils
                    results = execute_actions(actions) # execute_actions is from ai_utils

                    for result in results:
                        status = "✅" if result["success"] else "❌"
                        self.progress_signal.emit(f"{status} {result['action']}")
                        if "output" in result and result["output"] and result["output"].strip():
                            output_preview = result['output'][:200] + ('...' if len(result['output']) > 200 else '')
                            self.progress_signal.emit(f"   Output: {output_preview}")

                    execution_summary = {
                        "step": "execution_feedback", # Inform AI about execution results
                        "content": "Actions have been executed.",
                        "results": results
                    }
                    messages.append({"role": "user", "content": json.dumps(execution_summary)})
                    # The AI should now respond with a "report" step
                    continue # Get next step from AI
                else:
                    self.progress_signal.emit("No actions to execute for this step.")
                    messages.append({"role": "user", "content": "No actions were specified for execution. What's next?"})
                    continue # Get next step from AI

            elif step == "report":
                return f"✅ Task finished: {content_text}"
            
            else: # Unknown step or simple message
                self.progress_signal.emit(f"ℹ️ AI: {content_text}")
                # If there are actions without a clear step, decide how to handle.
                # For now, assume it's informational and we wait for next user query unless it's a report.
                if actions: # If there are actions in an unknown step, maybe they are follow-ups?
                     self.progress_signal.emit("Received actions in an unspecified step. Awaiting further instruction or explicit 'execute' command from AI.")
                # To prevent an infinite loop if the AI doesn't give a recognized step:
                # You might want to return here or send a specific message to the AI.
                # For now, let's assume a report or an implicit end if no other step is clear.
                return f"ℹ️ AI Update: {content_text}"


    def confirm_action(self, confirmed):
        self.confirmation_queue.put(confirmed)

class FileExplorer(QWidget):
    """Simple file explorer widget"""
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.file_list = QTextEdit()
        self.file_list.setReadOnly(True)
        # self.file_list.setMaximumHeight(200) # Let splitter handle sizing
        self.layout.addWidget(QLabel("📁 File Explorer (.):")) # Specify current dir
        self.layout.addWidget(self.file_list)

        self.refresh_button = QPushButton("🔄 Refresh")
        self.refresh_button.clicked.connect(self.refresh_files)
        self.layout.addWidget(self.refresh_button)

        self.refresh_files()

    def refresh_files(self):
        try:
            # Using the imported list_files from ai_utils for consistency,
            # but os.listdir is also fine here.
            # For simplicity, stick to os.listdir for direct display.
            files_and_dirs = os.listdir(".") # Target current directory
            display_list = []
            for item in sorted(files_and_dirs):
                if os.path.isdir(item):
                    display_list.append(f"📁 {item}/")
                else:
                    display_list.append(f"📄 {item}")
            self.file_list.setText("\n".join(display_list))
        except Exception as e:
            self.file_list.setText(f"Error refreshing files: {e}")


class TerminalAssistant(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🚀 AI Terminal Assistant v2.0")
        self.setGeometry(100, 100, 1400, 900)

        # Set dark theme (Simplified from original for brevity, assuming it works)
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; color: #ffffff; }
            QTextEdit { background-color: #2d2d2d; color: #ffffff; border: 1px solid #404040; font-family: 'Consolas', 'Monaco', monospace; font-size: 13px; padding: 10px; }
            QLineEdit { background-color: #2d2d2d; color: #ffffff; border: 2px solid #404040; border-radius: 5px; padding: 8px; font-family: 'Consolas', 'Monaco', monospace; font-size: 13px; }
            QLineEdit:focus { border-color: #007acc; }
            QPushButton { background-color: #007acc; color: white; border: none; padding: 8px 15px; border-radius: 4px; font-weight: bold; font-size: 12px;}
            QPushButton:hover { background-color: #005a9e; }
            QPushButton:pressed { background-color: #004578; }
            QLabel { color: #ffffff; font-weight: bold; font-size: 12px; }
            QProgressBar { border: 1px solid #404040; text-align: center; background-color: #2d2d2d; border-radius: 4px; color: #FFF;}
            QProgressBar::chunk { background-color: #007acc; border-radius: 4px; }
            QSplitter::handle { background-color: #404040; }
            QSplitter::handle:horizontal { width: 1px; }
            QSplitter::handle:vertical { height: 1px; }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        central_widget_layout = QVBoxLayout()
        central_widget_layout.addWidget(main_splitter)
        central_widget.setLayout(central_widget_layout)

        self.file_explorer = FileExplorer()
        # self.file_explorer.setMaximumWidth(300) # Let splitter handle sizing
        main_splitter.addWidget(self.file_explorer)

        terminal_widget = QWidget()
        terminal_layout = QVBoxLayout()
        terminal_widget.setLayout(terminal_layout)
        main_splitter.addWidget(terminal_widget)
        
        main_splitter.setSizes([300, 1100]) # Initial sizes for explorer and terminal

        header = QLabel("🤖 AI Terminal Assistant")
        header.setStyleSheet("font-size: 20px; padding: 10px; color: #007acc; font-weight: bold; text-align: center;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        terminal_layout.addWidget(header)

        self.output_console = QTextEdit()
        self.output_console.setReadOnly(True)
        terminal_layout.addWidget(self.output_console)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Processing...")
        terminal_layout.addWidget(self.progress_bar)

        input_frame = QFrame()
        input_layout = QVBoxLayout()
        input_frame.setLayout(input_layout)

        input_row = QHBoxLayout()
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("🚀 Ask AI: 'create a python script for http server', 'run git status', 'explain this error log'...")
        self.command_input.returnPressed.connect(self.process_ai_query)
        
        input_prompt_label = QLabel("➤")
        input_prompt_label.setStyleSheet("font-size: 16px; color: #007acc; padding-right: 5px;")
        input_row.addWidget(input_prompt_label)
        input_row.addWidget(self.command_input)
        input_layout.addLayout(input_row)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        self.ai_btn = QPushButton("🤖 Ask AI")
        self.ai_btn.clicked.connect(self.process_ai_query)
        button_row.addWidget(self.ai_btn)

        self.shell_btn = QPushButton("💻 Run Shell")
        self.shell_btn.clicked.connect(self.run_shell_command)
        button_row.addWidget(self.shell_btn)

        self.file_btn = QPushButton("📄 Open File") # Changed icon for clarity
        self.file_btn.clicked.connect(self.open_file_dialog) # Renamed method
        button_row.addWidget(self.file_btn)

        self.clear_btn = QPushButton("🗑️ Clear")
        self.clear_btn.clicked.connect(self.clear_console)
        button_row.addWidget(self.clear_btn)

        self.resume_btn = QPushButton("♻️ Resume AI")
        self.resume_btn.clicked.connect(self.resume_session)
        button_row.addWidget(self.resume_btn)
        
        button_row.addStretch() # Pushes buttons to the left

        input_layout.addLayout(button_row)
        terminal_layout.addWidget(input_frame)

        self.status_label = QLabel("✅ Ready")
        self.status_label.setStyleSheet("color: #00cc00; padding: 5px; font-size:11px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        terminal_layout.addWidget(self.status_label)

        self.current_thread = None
        self.append_output("🚀 AI Terminal Assistant Ready!")
        self.append_output("💡 Type your query or command above. Examples:")
        self.append_output("   - 'create a file named demo.txt with content Hello AI'")
        self.append_output("   - 'list all python files in current directory'")
        self.append_output("   - 'what is the capital of France?'")
        self.command_input.setFocus()

    def append_output(self, text: str):
        self.output_console.append(text)
        self.output_console.verticalScrollBar().setValue(self.output_console.verticalScrollBar().maximum())


    def set_status(self, text: str, color: str ="#00cc00"):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; padding: 5px; font-size:11px;")

    def _start_ai_thread(self, query: str, resume_mode: bool = False):
        if self.current_thread and self.current_thread.isRunning():
            self.append_output("⚠️ AI is already processing. Please wait...")
            return

        self.append_output(f"\n{'♻️ Resuming AI with query' if resume_mode and query else ('♻️ Resuming AI session' if resume_mode else '🔍 Query')}: {query if query else '(Continuing previous context)'}")
        self.command_input.clear()
        self.set_status("🤖 AI Processing...", "#ffaa00")

        self.current_thread = AIWorkerThread(query, resume=resume_mode)
        self.current_thread.output_signal.connect(self.handle_ai_output)
        self.current_thread.progress_signal.connect(self.append_output) # Progress directly to console
        self.current_thread.confirmation_signal.connect(self.show_confirmation_dialog) # Renamed method
        self.current_thread.finished_signal.connect(self.on_ai_finished)
        self.current_thread.start()

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0) # Indeterminate progress
        self.progress_bar.setFormat("🤖 AI Thinking...")


    def process_ai_query(self):
        query = self.command_input.text().strip()
        if not query:
            # self.append_output("⚠️ Please enter a query.")
            QMessageBox.warning(self, "Input Error", "Please enter a query for the AI.")
            return
        self._start_ai_thread(query, resume_mode=False)

    def handle_ai_output(self, text: str):
        """Handles the final output from the AI thread."""
        self.append_output(text)
        # Potentially parse final AI output if it's structured, or just display

    def show_confirmation_dialog(self, message: str, actions: list):
        action_descriptions = "\n".join([f"• {action.get('description', action.get('tool_name','Unknown Action'))}" for action in actions])
        full_message = f"{message}\n\nProposed actions:\n{action_descriptions}\n\nDo you want to proceed?"

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("🛡️ Confirm Actions")
        msg_box.setText(full_message)
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
        
        # Apply dark theme styling to QMessageBox (basic example)
        msg_box.setStyleSheet("""
            QMessageBox { background-color: #2d2d2d; color: white; }
            QPushButton { background-color: #007acc; color: white; padding: 5px 10px; border-radius: 3px; }
            QPushButton:hover { background-color: #005a9e; }
        """)


        result = msg_box.exec()
        confirmed = (result == QMessageBox.StandardButton.Yes)

        if self.current_thread:
            self.current_thread.confirm_action(confirmed)
            if confirmed:
                self.append_output("👍 User confirmed. AI will proceed.")
            else:
                self.append_output("👎 User declined. AI will be notified.")


    def on_ai_finished(self):
        self.progress_bar.setVisible(False)
        self.progress_bar.setFormat("Processing...") # Reset format
        self.set_status("✅ Ready", "#00cc00")
        self.file_explorer.refresh_files()
        self.command_input.setFocus()


    def run_shell_command(self):
        command = self.command_input.text().strip()
        if not command:
            # self.append_output("⚠️ Please enter a command.")
            QMessageBox.warning(self, "Input Error", "Please enter a shell command to run.")
            return

        self.append_output(f"\n💻 Running Shell: {command}")
        self.command_input.clear()
        self.set_status("⚙️ Running command...", "#ffcc00") # Yellow for running

        # To avoid blocking GUI, consider a QThread for shell commands too if they can be long.
        # For simplicity here, keeping it direct.
        try:
            # Use run_command from ai_utils
            result = run_command(command) # This is from ai_utils
            if result["success"]:
                self.append_output(f"✅ Command output:\n{result['output']}")
            else:
                self.append_output(f"❌ Command error:\n{result['output']}")
        except Exception as e:
            self.append_output(f"💥 Critical Shell Error: {e}")
        finally:
            self.set_status("✅ Ready", "#00cc00")
            self.file_explorer.refresh_files()
            self.command_input.setFocus()


    def open_file_dialog(self): # Renamed from open_file
        file_path, _ = QFileDialog.getOpenFileName(self, "Open File", ".", "All Files (*.*)")
        if file_path:
            try:
                # Use read_file from ai_utils
                result = read_file(file_path) # This is from ai_utils
                if result["success"]:
                    self.append_output(f"\n📄 Content of: {file_path}\n" + "─" * 60)
                    self.output_console.append(result["output"]) # Use append to preserve formatting better for raw text
                    self.append_output("─" * 60 + f"\nEnd of {file_path}")
                else:
                    self.append_output(f"❌ Error reading file '{file_path}': {result['output']}")
            except Exception as e:
                self.append_output(f"💥 Critical File Read Error: {e}")

    def clear_console(self):
        self.output_console.clear()
        self.append_output("✨ Console cleared. Ready for new tasks!")
        self.set_status("✅ Ready")

    def resume_session(self):
        if not os.path.exists(load_context.CONTEXT_FILE if hasattr(load_context, 'CONTEXT_FILE') else "chat_context.json"):
            QMessageBox.information(self, "Resume Info", "No previous session context (chat_context.json) found to resume.")
            return

        query = self.command_input.text().strip() # Allow adding a new query while resuming
        if query:
             self.append_output(f"♻️ Resuming session with additional query: {query}")
        else:
            self.append_output("♻️ Resuming previous AI session from context...")

        self._start_ai_thread(query, resume_mode=True)

# Entry point function for the package
def run_assistant():
    app = QApplication(sys.argv)
    app.setApplicationName("AITerminalAssistant")
    app.setApplicationVersion("2.0") # Corresponds to your class name

    # Apply a global style for the app if desired, or keep it in TerminalAssistant
    # app.setStyle("Fusion") # Example: try Fusion style

    window = TerminalAssistant()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    # This allows running the GUI directly for development
    # (e.g., python -m ai_terminal_assistant.main_gui)
    run_assistant()