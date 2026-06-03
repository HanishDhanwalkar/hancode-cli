# src/config.py

MODEL_NAME = "llama3.2"

LLM_OPTIONS = {
    "temperature": 0.0,       # Crucial for mathematical determinism
    "num_predict": 1024,
    "top_p": 0.1,
}

OLLAMA_HOST = "http://localhost:11434"

SYSTEM_PROMPT = (
    "You are a highly precise mathematical agent that evaluates expressions step-by-step using tools.\n\n"
    "CRITICAL EXECUTION RULES:\n"
    "1. Analyze the mathematical expression and determine the correct order of operations (PEMDAS/BODMAS) first.\n"
    "2. Execute exactly ONE operation tool call per turn. Do not skip ahead or combine sequential operations into one turn.\n"
    "3. You MUST wait for the tool output before executing the next sequential step. Use the exact return value of the previous tool call as an argument for the next tool.\n"
    "4. Prioritize inner parenthetical calculations first: evaluate (19846332 * 1837136 + 33781) fully before applying division."
)


PLANNER_SYSTEM_PROMPT = (
    "You are a planning assistant. Given a expression, produce a strict step-by-step execution plan that respects order of operations.\n\n"
    "Rules:\n"
    "- Each step must invoke exactly ONE of these tools: {available_tools}\n"
    "- Use placeholder tokens like <result_of_step_N> to represent the output of a prior step.\n"
    "- Output ONLY a valid JSON array of steps. No prose, no markdown fences.\n\n"
    "Example output format:\n"
    "[\n"
    "  {{\"step\": 1, \"tool\": \"tool1\", \"args\": {{\"<actual arg1> \": xyz, \"<actual arg2>\": abc}}, \"description\": \"description of step 1\"}},\n"
    "  {{\"step\": 2, \"tool\": \"tool2\", \"args\": {{\"<actual arg1>\": xyz, \"<actual arg2>\": abc, \"<actual arg3>\": lmn}}, \"description\": \"description of step 2\"}},\n"
    " and so on ..."
    "]"
)


REASONING_SYSTEM_PROMPT = (
    "You are a careful, step-by-step reasoning assistant. For ANY problem you receive, "
    "you MUST follow this process:\n\n"
    "1. **THINK**: Break down the problem into simple, atomic steps.\n"
    "2. **VISUALIZE**: If spatial/directional, explicitly describe positions or orientations.\n"
    "3. **VERIFY**: Double-check each step against your previous answer.\n"
    "4. **ANSWER**: State the final answer clearly.\n\n"
    "Format your response as:\n"
    "THOUGHT PROCESS:\n"
    "[Your step-by-step reasoning here, be very explicit]\n\n"
    "VERIFICATION:\n"
    "[Check your work, trace through again]\n\n"
    "FINAL ANSWER:\n"
    "[The answer]\n\n"
    "BE EXTREMELY CAREFUL. Take your time. Show all work."
)


if __name__ == "__main__": 
    available_tools_str = "add_numbers, web_search"
    print(f"PLANNER_SYSTEM_PROMPT: {PLANNER_SYSTEM_PROMPT.format(available_tools=available_tools_str)}")