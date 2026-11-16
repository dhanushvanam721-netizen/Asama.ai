import subprocess
import json
import sys
from openai import OpenAI

client = OpenAI()

# ==========================================
# 1. ALLOW-LISTED SYSTEM COMMANDS (Security)
# ==========================================
ALLOWED_COMMANDS = {
    "get_cpu_info": ["lscpu"],
    "get_memory_info": ["free", "-h"],
    "get_storage_info": ["lsblk", "-o", "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT"],
    "get_pci_devices": ["lspci"],
    "get_system_info": ["uname", "-a"]
}

def execute_command(tool_name: str) -> str:
    if tool_name not in ALLOWED_COMMANDS:
        return json.dumps({"error": "Command not allowed for security reasons."})
    try:
        res = subprocess.run(ALLOWED_COMMANDS[tool_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        if res.returncode != 0:
            return json.dumps({"error": res.stderr.strip()})
        return json.dumps({"output": res.stdout.strip()})
    except Exception as e:
        return json.dumps({"error": str(e)})

# ==========================================
# 2. LLM TOOL DEFINITIONS
# ==========================================
tools = [
    {"type": "function", "function": {"name": "get_cpu_info", "description": "Get CPU details", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_memory_info", "description": "Get RAM and swap usage", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_storage_info", "description": "Get disk and partition info", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_pci_devices", "description": "Get hardware devices (GPU, controllers)", "parameters": {"type": "object", "properties": {}}}}
]

available_tools = {
    "get_cpu_info": execute_command,
    "get_memory_info": execute_command,
    "get_storage_info": execute_command,
    "get_pci_devices": execute_command
}


# ==========================================
# 3. INTERACTIVE ASSISTANT LOOP
# ==========================================
def run_assistant():
    print("=== Linux Hardware Q&A Assistant ===")
    print("Type your questions (e.g., 'How much RAM do I have?' or 'What GPU is installed?'). Type 'exit' to quit.\n")
    
    messages = [{"role": "system", "content": "You are a Linux hardware assistant. Never guess specs; always call tools. Say 'I don't know' if data is unavailable."}]

    while True:
        try:
            user_input = input("User: ")
            if user_input.strip().lower() in ["exit", "quit"]: break
            if not user_input.strip(): continue

            messages.append({"role": "user", "content": user_input})
            response = client.chat.completions.create(model="gpt-4o", messages=messages, tools=tools, tool_choice="auto")
            msg = response.choices[0].message
            messages.append(msg)

            if msg.tool_calls:
                for call in msg.tool_calls:
                    fname = call.function.name
                    print(f"[Executing system diagnostic: {fname}...] ")
                    output = available_tools[fname](fname)
                    messages.append({"tool_call_id": call.id, "role": "tool", "name": fname, "content": output})

                final_res = client.chat.completions.create(model="gpt-4o", messages=messages)
                print(f"Assistant: {final_res.choices[0].message.content}\n")
            else:
                print(f"Assistant: {msg.content}\n")
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    run_assistant()