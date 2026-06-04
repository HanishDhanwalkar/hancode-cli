import asyncio
import json
import re
import inspect

from ollama import AsyncClient

# import src.config as config
# from src.tools_registry import AVAILABLE_TOOLS
# from src.context_manager import ContextAwareClient, MessageCompressor

# For .ipynb
import config as config
from tools_registry import AVAILABLE_TOOLS
from context_manager import ContextAwareClient, MessageCompressor


# ==========================================
# 1. MOCK STRUCTURES
# ==========================================

class MockToolCall:
    """Mock class matching Ollama's native response tool structure."""

    def __init__(self, name, arguments):
        self.function = MockFunction(name, arguments)


class MockFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


# ==========================================
# 2. FALLBACK TOOL EXTRACTOR
# ==========================================

def extract_fallback_tools(content: str) -> list:
    """Parses text content to extract rogue text-JSON strings emitted by the model."""
    if not content:
        return []

    found_tools = []
    json_pattern = re.compile(r'\{[^{}]*\"name\"\s*:\s*\"[^\"]+\"[^{}]*\}')
    matches = json_pattern.findall(content)

    for match in matches:
        try:
            data = json.loads(match)
            if "name" in data:
                args = data.get("parameters", data.get("arguments", {}))
                found_tools.append(MockToolCall(data["name"], args))
        except Exception:
            continue
    return found_tools


# ==========================================
# 3. TOOL EXECUTOR
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


VALID_TOOLS = set(AVAILABLE_TOOLS.keys())


def get_tools_with_signatures() -> str:
    """Returns a string description of tools and their exact parameters."""
    descriptions = []
    for name, func in AVAILABLE_TOOLS.items():
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        descriptions.append(f"- {name}({', '.join(params)})")
    return "\n".join(descriptions)


def validate_plan(plan: list[dict]) -> bool:
    """
    Rejects plans where every step uses zeroed-out args (hallucinated filler)
    or references tool names that don't exist in AVAILABLE_TOOLS.
    """
    for step in plan:
        if step.get("tool") not in VALID_TOOLS:
            print(f"[PLANNER] ❌ Invalid tool in plan: '{step.get('tool')}'")
            return False

    # Tool specific guidelines/ restrictions
    for step in plan:
        if step.get("tool") == "web_search_ddg":
            if "args" not in step:
                step["args"] = {}
            step["args"]["max_results"] = min(
                int(step["args"].get("max_results", 3)), 3)

    # Detect all-zero filler plans: every numeric arg across all steps is 0
    numeric_args = []
    for step in plan:
        for val in step.get("args", {}).values():
            if isinstance(val, (int, float)):
                numeric_args.append(val)

    if numeric_args and all(v == 0 for v in numeric_args):
        print("[PLANNER] ❌ Plan rejected: all numeric args are 0 (hallucinated filler).")
        return False

    return True


# ==========================================
# 4. PLANNING PHASE
# ==========================================

async def plan_execution(client: AsyncClient, user_prompt: str) -> list[dict]:
    """
    Calls the LLM in planner mode to produce a structured JSON execution plan.
    Returns a list of step dicts, or an empty list on failure.
    """
    print("[PLANNER] 🧠 Generating draft execution plan...\n")

    planner_messages = [
        {"role": "system", "content": config.PLANNER_SYSTEM_PROMPT.format(
            available_tools=get_tools_with_signatures())},
        {"role": "user", "content": f"Expression to evaluate: {user_prompt}"}
    ]

    response = await client.chat(
        model=config.MODEL_NAME,
        messages=planner_messages,
        options={**config.LLM_OPTIONS, "temperature": 0.0}
    )

    raw = response.message.content or ""
    raw = re.sub(r"\x60{3}(?:json)?", "", raw).strip().rstrip("\x60").strip()
    
    if raw.startswith("<think>"):
        raw = raw.split("</think>")[1].strip()
    
    plan = json.loads(raw)
    if plan and validate_plan(plan):
        print(f"[PLANNER] 📝 Draft Plan with {len(plan)} step(s) created:")
        for step in plan:
            print(f"   Step {step.get('step')}: {step.get('description')} "
                  f"→ {step.get('tool')}({step.get('args')})")
        print()
        return plan

    print(f"[PLANNER] ⚠️  Could not parse draft plan. Raw output:\n{plan}\n")
    return []


# ==========================================
# 4.5 PLAN REVIEW & ENHANCEMENT PHASE (Robust)
# ==========================================
async def review_and_enhance_plan(client: AsyncClient, user_prompt: str, draft_plan: list[dict]) -> list[dict]:
    """
    An independent reviewer turn (no conversation context shared) that audits, corrects,
    and refines the generated draft execution plan for mathematical and logical consistency.
    """
    print("[REVIEWER] 🔍 Initiating isolated plan auditing loop...\n")

    # Define the Reviewer's System Guidelines
    reviewer_system_prompt = (
        "You are an expert Planning Auditor and Optimizer. Your task is to review a draft step-by-step execution plan "
        "designed to satisfy a user request. You must ensure the plan is logical, sequentially correct, avoids redundancies, "
        "and maps parameter dependencies correctly using step placeholder tags (e.g. <result_of_step_N>).\n\n"
        "Strict Review Constraints:\n"
        "- The only allowed tools and their exact callable signatures are:\n"
        "{available_tools}\n"
        "- Check for and ELIMINATE redundant filler steps (e.g., adding 0, multiplying/dividing by 1, or creating intermediate placeholder steps that perform no useful work).\n"
        "- Double-check the user's mathematical intent against the tool selection! If they ask to 'multiply' or 'product', ensure you use 'multiply_numbers' and NOT 'add_numbers'. If they ask to 'add' or 'sum', use 'add_numbers'.\n"
        "- Verify that placeholder tokens correctly point to a prior step's outputs.\n"
        "- Ensure math operations follow standard precedence rules.\n"
        "- Minimize the total number of steps. If a plan can be resolved in 3 clean steps instead of 5 bloated steps, modify and consolidate it.\n"
        "- Output ONLY the final validated valid JSON array of steps. Absolutely no conversational filler, markdown code fences, or headers."
    )

    review_user_message = (
        f"Original User Request: '{user_prompt}'\n\n"
        f"Draft Plan to audit:\n{json.dumps(draft_plan, indent=2)}\n\n"
        f"Analyze the draft plan, apply any corrections or enhancements, and output the audited plan JSON:"
    )

    reviewer_messages = [
        {"role": "system", "content": reviewer_system_prompt.format(
            available_tools=get_tools_with_signatures())},
        {"role": "user", "content": review_user_message}
    ]

    try:
        # Execute turning call (using clean, independent client execution)
        response = await client.chat(
            model=config.MODEL_NAME,
            messages=reviewer_messages,
            options={**config.LLM_OPTIONS, "temperature": 0.0}
        )

        raw = response.message.content or ""

        # Use our robust array parser to extract JSON list regardless of surrounding conversational preamble
        raw = re.sub(r"\x60{3}(?:json)?", "", raw).strip().rstrip("\x60").strip()

        plan = json.loads(raw)

        if plan and validate_plan(plan):
            print(
                f"[REVIEWER] ✅ Plan audit complete! Enhanced plan contains {len(plan)} step(s):")
            for step in plan:
                print(f"   Step {step.get('step')}: {step.get('description')} "
                      f"→ {step.get('tool')}({step.get('args')})")
            print()
            return plan
        else:
            print(
                "[REVIEWER] ⚠️ Reviewed plan parsed but failed structural validation. Falling back to draft plan.")
    except Exception as e:
        print(
            f"[REVIEWER] ❌ Review phase failed due to parse error: {str(e)}. Falling back to draft plan.")

    return draft_plan


# ==========================================
# 5. PLAN-GUIDED EXECUTION
# ==========================================

async def execute_plan(async_client: AsyncClient, plan: list[dict], user_prompt: str):
    """
    Executes a pre-built plan step-by-step, substituting <result_of_step_N>
    placeholders with real tool outputs as they become available.
    Uses ContextAwareClient to manage token limits.
    """
    step_results: dict[int, float | int | str] = {}

    # Use context-aware wrapper
    client = ContextAwareClient(async_client)
    client.add_system_prompt(config.SYSTEM_PROMPT)
    client.add_message("user", user_prompt)

    print("[EXECUTOR] 🚀 Starting plan-guided execution...\n")

    for step_def in plan:
        step_num = step_def["step"]
        tool_name = step_def["tool"]
        raw_args = step_def.get("args", {})
        description = step_def.get("description", "")

        if tool_name == "web_search_ddg" and "max_results" in raw_args:
            try:
                requested_count = int(raw_args["max_results"])
                raw_args["max_results"] = min(requested_count, 3)
            except (ValueError, TypeError):
                raw_args["max_results"] = 3

        resolved_args = {}
        for key, val in raw_args.items():
            if isinstance(val, str) and val.startswith("<result_of_step_"):
                ref_step = int(re.search(r"\d+", val).group())
                resolved_val = step_results.get(ref_step)
                if resolved_val is None:
                    print(
                        f"[EXECUTOR] ❌ Step {step_num} references step {ref_step} but that result is missing. Aborting."
                    )
                    return
                resolved_args[key] = resolved_val
            else:
                resolved_args[key] = val

        print(f"[EXECUTOR] Step {step_num}: {description}")
        print(f"           → Calling {tool_name}({resolved_args})")

        mock_call = MockToolCall(tool_name, resolved_args)
        tool_resp = await execute_tool(mock_call)
        raw_result = tool_resp["content"]
        print(f"           ← Raw Result: {raw_result}")

        if tool_name == "web_search_ddg":
            print(f"[EXECUTOR] 🔍 Extracting numeric values from raw web results...")
            extraction_prompt = (
                f"You were asked: {description}. Here are raw search results (JSON): {raw_result}. "
                f"Extract the single liner answer or if possible numerical integer or float that best answers the query. "
                f"Reply in very short answer in plain text. Do NOT add any extra markdown, code formatting, or text."
            )

            async def attempt_extraction(prompt_str: str) -> tuple[bool, any]:
                extract_resp = await async_client.chat(
                    model=config.MODEL_NAME,
                    messages=[{"role": "user", "content": prompt_str}],
                    options={**config.LLM_OPTIONS, "temperature": 0.0}
                )
                text_out = (extract_resp.message.content or "").strip()

                return True, text_out

            success, extracted_val = await attempt_extraction(extraction_prompt)

            if not success:
                print(
                    f"[EXECUTOR] ⚠️ Extraction failed. Retrying with a stricter constraint format..."
                )

            if success and extracted_val is not None:
                print(
                    f"           🎯 Extracted chosen numeric outcome: {extracted_val}"
                )
                raw_result = str(extracted_val)
                # Register context telemetry trail
                client.add_message("tool", tool_resp["content"])
                client.add_message(
                    "assistant", f"search_results -> chosen_count: {extracted_val}")
            else:
                print(
                    f"[EXECUTOR] ❌ Extraction fallback aborted or returned null. Ending execution loop."
                    )
                return

        # Show context usage
        info = client.get_info()
        print(f"           📊 Context: {info['estimated_tokens']}/{info['context_limit']} tokens "
              f"({info['utilization_percent']:.1f}%)\n")

        # Store numeric result for subsequent steps
        try:
            if "." in raw_result:
                step_results[step_num] = float(raw_result)
            else:
                step_results[step_num] = int(raw_result)
        except (ValueError, TypeError):
            step_results[step_num] = raw_result

        # Keep conversation context in sync
        if tool_name != "web_search_ddg":
            client.add_message(
                "assistant",
                f"Executing step {step_num}: {description}",
                tool_calls=[
                    {
                        "function": {
                            "name": tool_name,
                            "arguments": resolved_args
                        }
                    },
                ]
            )
            client.add_message("tool", tool_resp["content"])

    print("[EXECUTOR] 🛡️ Running confirmation check on gathered workflow dependencies...")
    verification_summary = f"Review the execution chain step parameters evaluated so far: {json.dumps(step_results)}. Confirm if all intermediate values map logically before presenting final calculations."

    await async_client.chat(
        model=config.MODEL_NAME,
        messages=[{"role": "user", "content": verification_summary}],
        options={**config.LLM_OPTIONS, "temperature": 0.0}
    )

    final_msg = "All steps are complete. Provide the final answer."
    client.add_message("user", final_msg)

    final_response, was_compressed = await client.chat(
        model=config.MODEL_NAME,
        options=config.LLM_OPTIONS
    )

    if was_compressed:
        print("[EXECUTOR] ⚠️  Context was compressed during final answer phase")

    final_answer = final_response.message.content or ""
    print(f"[DONE] ✅ Final Answer:\n{final_answer}\n")


# ==========================================
# 6. FALLBACK: UNGUIDED AGENTIC LOOP
# ==========================================

async def run_unguided_loop(client: AsyncClient, user_prompt: str):
    """
    Original agentic loop used when planning fails. The model drives tool
    selection itself, with a fallback JSON scanner for rogue text output.
    """
    messages = [
        {"role": "system", "content": config.SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    tools_list = list(AVAILABLE_TOOLS.values())
    loop_count = 0
    max_loops = 6

    print("[FALLBACK] 🔁 Running unguided agentic loop...\n")

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

        if not tool_calls_to_process and msg_content:
            fallback_calls = extract_fallback_tools(msg_content)
            if fallback_calls:
                print(
                    f"[Loop {loop_count}] ⚠️ Fallback triggered: Model printed raw JSON.")
                tool_calls_to_process = fallback_calls

        messages.append({
            "role": "assistant",
            "content": msg_content or "",
            "tool_calls": response.message.tool_calls if response.message.tool_calls else None
        })

        if tool_calls_to_process:
            print(
                f"[Loop {loop_count}] 🔄 Model invoked {len(tool_calls_to_process)} tool call(s).")
            tasks = [execute_tool(tc) for tc in tool_calls_to_process]
            tool_responses = await asyncio.gather(*tasks)

            for tool_resp in tool_responses:
                print(
                    f"   ↳ Tool '{tool_resp['name']}' returned: {tool_resp['content']}")
                messages.append(tool_resp)

            print("⏳ Passing values back to LLM...\n")
        else:
            print(
                f"\n[DONE] Final Answer Reached in {loop_count} turns:\n{msg_content}\n")
            break
    else:
        print(
            f"\n⚠️ [TIMEOUT] Agent reached max loops ({max_loops}) without resolution.")


# ==========================================
# 7. MAIN ENTRY POINT
# ==========================================

async def run_conversation(user_prompt: str):
    client = AsyncClient(host=config.OLLAMA_HOST)

    print(f"\n[---] Starting Agent for prompt: '{user_prompt}'\n")

    # --- PHASE 1: DRAFT PLAN ---
    draft_plan = await plan_execution(client, user_prompt)

    # --- PHASE 2: REVIEW & ENHANCE (NEW) ---
    plan = []
    if draft_plan:
        plan = await review_and_enhance_plan(client, user_prompt, draft_plan)

    # --- PHASE 3: EXECUTE ---
    if plan:
        await execute_plan(client, plan, user_prompt)
    else:
        print(
            "[---] Planning/Auditing failed completely. Falling back to unguided agentic loop.\n")
        await run_unguided_loop(client, user_prompt)


if __name__ == "__main__":
    prompt = "Calculate number of times RCB won in IPL and multiply that number with number of times MI won"
    asyncio.run(run_conversation(prompt))
