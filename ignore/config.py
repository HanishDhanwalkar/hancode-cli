# config.py

# MODEL_NAME = "llama3.2"
MODEL_NAME = "deepseek-r1:latest"


LLM_OPTIONS = {
    "temperature": 0.0,       # Keep it 0.0 for rigid tool syntax execution
    "num_predict": 1024,      # Higher token budget for multi-turn steps
    "top_p": 0.1,             # Narrow down token selection to prevent loose text formatting
}

OLLAMA_HOST = "http://localhost:11434"

# Add an explicit rule structure for local models
SYSTEM_PROMPT = (
    "You are a precise tool-calling assistant. When you need to execute a tool, "
    "you MUST use the native tool-calling feature. Never output raw JSON markdown blocks "
    "or JSON strings directly in your text content responses if a tool needs to be called."
)