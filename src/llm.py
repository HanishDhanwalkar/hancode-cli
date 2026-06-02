# app.py
import asyncio
import json
import re
import inspect

from ollama import AsyncClient

import src.config as config
from src.tools_registry import AVAILABLE_TOOLS


class MockToolCall:
    """Mock class matching Ollama's native response tool structure."""
    def __init__(self, name, arguments):
        self.function = MockFunction(name, arguments)

class MockFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments

def extract_fallback_tools(content: str) -> list:
    """Parses text content to extract rogue text-JSON strings emitted by the model."""
    if not content:
        return []
    
    found_tools = []
    # Search for JSON blocks/objects embedded inside the text string
    json_pattern = re.compile(r'\{[^{}]*\"name\"\s*:\s*\"[^\"]+\"[^{}]*\}')
    matches = json_pattern.findall(content)
    
    for match in matches:
        try:
            data = json.loads(match)
            if "name" in data:
                # Standardize to mirror native tool properties
                args = data.get("parameters", data.get("arguments", {}))
                found_tools.append(MockToolCall(data["name"], args))
        except Exception:
            continue
    return found_tools

# ==========================================
# 3. HELPER TO EXECUTE TOOLS CONCURRENTLY
# ==========================================
async def execute_tool(tool_call) -> dict:
    name = tool_call.function.name
    arguments = tool_call.function.arguments

    if name not in AVAILABLE_TOOLS:
        return {"role": "tool", "name": name, "content": f"Error: Tool '{name}' not found."}

    try:
        function_to_call = AVAILABLE_TOOLS[name]
        if inspect.iscoroutinefunction(function_to_call):
            result = await function_to_call(**arguments)
        else:
            result = function_to_call(**arguments)
            
        return {"role": "tool", "name": name, "content": str(result)}
    except Exception as e:
        return {"role": "tool", "name": name, "content": f"Error: {str(e)}"}

# ==========================================
# 4. CORE LOOP (WITH RECOVERY FALLBACK)
# ==========================================
async def run_conversation(user_prompt: str):
    client = AsyncClient(host=config.OLLAMA_HOST)
    
    messages = [
        {"role": "system", "content": config.SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]
    
    tools_list = list(AVAILABLE_TOOLS.values())
    loop_count = 0
    max_loops = 6 

    print(f"\n[---] Starting Agent Loop for prompt: '{user_prompt}'\n")

    while loop_count < max_loops:
        loop_count += 1
        
        response = await client.chat(
            model=config.MODEL_NAME,
            messages=messages,
            tools=tools_list,
            options=config.LLM_OPTIONS
        )
        
        msg_content = response.message.content
        native_tool_calls = response.message.tool_calls or []
        tool_calls_to_process = list(native_tool_calls)
        
        # --- FALLBACK SCAN ---
        if not tool_calls_to_process and msg_content:
            fallback_calls = extract_fallback_tools(msg_content)
            if fallback_calls:
                print(f"[Loop {loop_count}] ⚠️ Fallback triggered: Model printed raw JSON.")
                tool_calls_to_process = fallback_calls

        # --- ARTIFACT APPENDING ---
        # We must preserve the native structure for Ollama's internal context state tracking
        messages.append({
            "role": "assistant",
            "content": msg_content or "",
            "tool_calls": response.message.tool_calls if response.message.tool_calls else None
        })
        
        # --- DECISION TREE FOR LOOP TERMINATION ---
        if tool_calls_to_process:
            print(f"[Loop {loop_count}] 🔄 Model invoked {len(tool_calls_to_process)} tool call(s).")
            
            # Run tools in parallel (handles single or multiple items smoothly)
            tasks = [execute_tool(tool) for tool in tool_calls_to_process]
            tool_responses = await asyncio.gather(*tasks)
            
            # Append execution outputs to context history
            for tool_resp in tool_responses:
                print(f"   ↳ Tool '{tool_resp['name']}' returned: {tool_resp['content']}")
                messages.append(tool_resp)
                
            print("⏳ Passing values back to the LLM for the next sequential step...\n")
            # CRITICAL: We do NOT terminate here. We let the loop cycle back to the LLM.
            
        else:
            # If absolutely no tools were requested natively or via fallback text string,
            # this turn represents the true final answer state.
            print(f"\n[DONE] Final Answer Reached in {loop_count} turns:\n{msg_content}\n")
            break
    else:
        print(f"\n⚠️ [TIMEOUT] Agent reached maximum loop ceiling ({max_loops}) without a clear resolution.")

if __name__ == "__main__":
    # prompt = (
    #     "Check the stock prices for AAPL and MSFT right now. Also, pull the risk profile "
    #     "for user_99 and calculate the portfolio risk factor for MSFT based on that profile."
    # )
    
    prompt = "solve (19846332 * 1837136 + 33781) / 57342"
    asyncio.run(run_conversation(prompt))