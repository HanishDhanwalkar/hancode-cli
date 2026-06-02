# app.py
import asyncio
import json
import re
import inspect
from ollama import AsyncClient
import config

# ==========================================
# 1. DEFINE YOUR TOOLS (Unchanged)
# ==========================================
async def get_stock_price(ticker: str) -> str:
    """Retrieves the current stock price for a given ticker symbol."""
    print(f"[Tool Execution] Fetching stock price for {ticker}...")
    await asyncio.sleep(0.5)
    mock_prices = {"AAPL": "$175.00", "GOOG": "$150.00", "MSFT": "$420.00"}
    return mock_prices.get(ticker.upper(), "$100.00")

async def analyze_portfolio_risk(price: str, risk_profile: str) -> str:
    """Analyzes trading portfolio risks based on an asset's current price and user profile."""
    print(f"[Tool Execution] Analyzing risk for price {price} with profile '{risk_profile}'...")
    await asyncio.sleep(0.5)
    if risk_profile.lower() == "conservative":
        return f"Risk Level: HIGH for price {price}. Recommendation: Hold/Diversify."
    return f"Risk Level: MODERATE for price {price}. Recommendation: Buy/Accumulate."

async def get_user_risk_profile(user_id: str) -> str:
    """Retrieves the registered financial risk profile for a specific user ID."""
    print(f"[Tool Execution] Fetching risk profile for user {user_id}...")
    await asyncio.sleep(0.5)
    return "conservative"

AVAILABLE_TOOLS = {
    "get_stock_price": get_stock_price,
    "analyze_portfolio_risk": analyze_portfolio_risk,
    "get_user_risk_profile": get_user_risk_profile
}

# ==========================================
# 2. FAILSAFE PARSER FOR COLD REASONING STRINGS
# ==========================================
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
    
    # Inject system instructions to keep tool calling native
    messages = [
        {"role": "system", "content": config.SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]
    
    tools_list = list(AVAILABLE_TOOLS.values())
    continue_loop = True
    loop_count = 0
    max_loops = 6 

    print(f"\n🚀 Starting Agent Loop for prompt: '{user_prompt}'\n")

    while continue_loop and loop_count < max_loops:
        loop_count += 1
        
        response = await client.chat(
            model=config.MODEL_NAME,
            messages=messages,
            tools=tools_list,
            options=config.LLM_OPTIONS
        )
        
        # Capture raw contents
        msg_content = response.message.content
        tool_calls = response.message.tool_calls or []
        
        # --- FALLBACK SCAN ---
        # If native tool calls are empty, inspect text for accidental JSON dumps
        if not tool_calls and msg_content:
            fallback_calls = extract_fallback_tools(msg_content)
            if fallback_calls:
                print("⚠️ [Fallback Triggered] Model printed raw JSON string instead of API tools.")
                tool_calls = fallback_calls
        
        # Append the assistant response to context stack
        messages.append(response.message)
        
        if tool_calls:
            print(f"🔄 [Loop {loop_count}] Processing {len(tool_calls)} tool call(s)...")
            
            # Execute concurrently (handles both parallel items or standalone steps)
            tasks = [execute_tool(tool) for tool in tool_calls]
            tool_responses = await asyncio.gather(*tasks)
            
            for tool_resp in tool_responses:
                print(f"   ↳ Tool '{tool_resp['name']}' returned: {tool_resp['content']}")
                messages.append(tool_resp)
                
            print("⏳ Passing values back to the LLM for next evaluation cycle...")
        else:
            # Loop ends safely only when no tools are invoked either via API or raw text
            print(f"\n✨ Final Answer:\n{msg_content}\n")
            continue_loop = False

if __name__ == "__main__":
    complex_prompt = (
        "Check the stock prices for AAPL and MSFT right now. Also, pull the risk profile "
        "for user_99 and calculate the portfolio risk factor for MSFT based on that profile."
    )
    asyncio.run(run_conversation(complex_prompt))