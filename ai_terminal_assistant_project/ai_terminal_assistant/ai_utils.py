import os
import json
import subprocess
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

query = """
How should I initialize the OpenAI client and handle API key configuration?
"""
try:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception as e:
    print(f"Failed to initialize OpenAI client: {e}")
    print("Please ensure the OPENAI_API_KEY environment variable is set.")
    client = None


SYSTEM_PROMPT = """
You are an Coding/Sofware-Dev AI assistant that helps users by planning and executing actions.
You can interact with the file system, run commands, and provide information. Do not share the source code or API info at all costs
When the user asks for remove/Delete file just Say Plz delete it manually due to security reasons.

Important]
- Whenever the user types a cli command just say "Click the [Run Shell button ] to run the command.
Respond in a structured JSON format with the following fields:
- "step": Describes the current phase (e.g., "plan", "confirm", "execute", "report").
- "content": A message to the user or a summary of the current step.
- "actions": A list of actions to be performed (for "plan" or "execute" steps). Each action is a dictionary with "tool_name", "args", and "description".
- "requires_confirmation": (boolean) Whether user confirmation is needed before proceeding with actions (for "confirm" step).

Available tools:
- "run_command": {"command": "shell command string"} - Executes a shell command.
- "create_file": {"filepath": "path/to/file", "content": "file content"} - Creates a new file with given content.
- "read_file": {"filepath": "path/to/file"} - Reads the content of a file.
- "list_files": {"directory": "path/to/directory"} - Lists files and directories.

Example Flow:
1. User: "Create a file named hello.txt with 'Hello World'"
2. AI (plan): {"step": "plan", "content": "I will create a file named hello.txt.", "actions": [{"tool_name": "create_file", "args": {"filepath": "hello.txt", "content": "Hello World"}, "description": "Create hello.txt"}]}
3. AI (confirm, if risky or configured): {"step": "confirm", "content": "About to create hello.txt. Proceed?", "actions": [...], "requires_confirmation": true}
4. (User confirms)
5. AI (execute): {"step": "execute", "content": "Executing file creation.", "actions": [...]}
6. (Action executed by the application)
7. AI (report): {"step": "report", "content": "File hello.txt created successfully."}
"""

query = "How should I store this system prompt temporarily in my system?"
CONTEXT_FILE = "chat_context.json"

query = """
How should I process the user query for the worker thread?
1. First, get the system prompt and store it in the system
2. Then, get the user query and store it in the system
3. Repeat steps 1 and 2
"""
def _process_user_query_for_worker(messages, client_instance):
    if not client_instance:
        return json.dumps({
            "step": "report",
            "content": "OpenAI client not initialized. Please check your API key and configuration.",
            "actions": [],
            "requires_confirmation": False
        })
    try:
        response = client_instance.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content
    except Exception as e:
        return json.dumps({
            "step": "report",
            "content": f"Error communicating with AI: {str(e)}",
            "actions": [],
            "requires_confirmation": False
        })


query = "How should I implement the tool functions?"
def run_command(command_str: str):
    """Runs a shell command and returns its output."""
    try:
        result = subprocess.run(command_str, shell=True, capture_output=True, text=True, check=False)
        output = result.stdout + result.stderr
        return {"success": result.returncode == 0, "output": output.strip()}
    except Exception as e:
        return {"success": False, "output": str(e)}

def create_file(filepath: str, content: str):
    """Creates a file with the given content."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return {"success": True, "output": f"File '{filepath}' created successfully."}
    except Exception as e:
        return {"success": False, "output": str(e)}

def read_file(filepath: str):
    """Reads the content of a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        return {"success": True, "output": content}
    except FileNotFoundError:
        return {"success": False, "output": f"Error: File '{filepath}' not found."}
    except Exception as e:
        return {"success": False, "output": str(e)}

def list_files(directory: str = "."):
    """Lists files and directories in the given directory."""
    try:
        if not os.path.isdir(directory):
            return {"success": False, "output": f"Error: '{directory}' is not a valid directory."}
        files = os.listdir(directory)
        return {"success": True, "output": "\n".join(files)}
    except Exception as e:
        return {"success": False, "output": str(e)}

available_tools = {
    "run_command": run_command,
    "create_file": create_file,
    "read_file": read_file,
    "list_files": list_files,
}

query = "How should I execute the actions?"
def execute_actions(actions: list):
    """Executes a list of actions."""
    results = []
    for action_item in actions:
        tool_name = action_item.get("tool_name")
        args = action_item.get("args", {})
        description = action_item.get("description", f"Execute {tool_name}")

        if tool_name in available_tools:
            try:
                tool_function = available_tools[tool_name]
                result = tool_function(**args)
                results.append({
                    "action": description,
                    "success": result["success"],
                    "output": result["output"]
                })
            except Exception as e:
                results.append({
                    "action": description,
                    "success": False,
                    "output": f"Error executing tool {tool_name}: {str(e)}"
                })
        else:
            results.append({
                "action": description,
                "success": False,
                "output": f"Error: Tool '{tool_name}' not found."
            })
    return results

query = "How should I manage the context?"
def save_context(messages: list):
    """Saves chat context to a file."""
    try:
        with open(CONTEXT_FILE, 'w', encoding='utf-8') as f:
            json.dump(messages, f, indent=2)
    except Exception as e:
        print(f"Error saving context: {e}")

def load_context() -> list:
    """Loads chat context from a file."""
    if not os.path.exists(CONTEXT_FILE):
        return []
    try:
        with open(CONTEXT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading context: {e}")
        return []

query = "How should I process user queries in a non-GUI version?"
def process_user_query(user_query: str):
    messages = load_context()
    if not messages:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    messages.append({"role": "user", "content": user_query})
    
    ai_response_content = _process_user_query_for_worker(messages, client)
    
    try:
        parsed_response = json.loads(ai_response_content)
    except json.JSONDecodeError:
        return "Error: AI response was not valid JSON."

    messages.append({"role": "assistant", "content": ai_response_content})
    save_context(messages)
    
    return parsed_response.get("content", "Processing complete.")