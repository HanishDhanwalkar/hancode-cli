import os
import re
import difflib
import operator
import logging
from datetime import datetime
from typing import Annotated, Sequence, TypedDict, List, Callable, Dict, Any
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import ToolNode
from langchain_ollama import ChatOllama

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('agent_orchestrator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# TODO:
# "User Soul": "The user is Hanish, software engineer", # TODO: load from SOUL.md
# "Coding Standards": "Best Python practices", # TODO: load from AGENTS.md

MODEL = "qwen3:8b"
# MODEL = "llama3.2"

# Unified Shared Memory (Graph State)
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next_destination: str

# Shared Knowledge Base Tool
@tool
def common_knowledge_base(query: str) -> str:
    """Query the shared knowledge base."""
    logger.info(f"[KnowledgeBase] Query received: '{query}'")
    
    knowledge = {
        "shipping policy ":  "Standard shipping takes 3-5 business days. Express takes 1-2 days. ",
        "security protocol ":  "All external API integrations must use OAuth2 protocols. "
    }
    
    query_lower = query.lower()
    for key, val in knowledge.items():
        if key in query_lower:
            logger.info(f"[KnowledgeBase] Match found for key: '{key}'")
            return f"[Knowledge Base Match]: {val} "
    
    logger.warning(f"[KnowledgeBase] No match found for query: '{query}'")
    return  "No explicit knowledge base entry found. Proceed with standard operations. "

class Agent:
    def __init__(self, name: str, system_context: str, tools: List[Callable] = None):
        self.name = f"{name}_agent"  # Standardized internal naming convention
        self.system_context = system_context
        
        logger.info(f"[Agent:{self.name}] Initializing agent with context: {system_context[:50]}...")
        
        # Every sub-agent automatically inherits the common knowledge base
        base_tools = [common_knowledge_base]
        self.tools = base_tools + (tools if tools else [])
        
        logger.info(f"[Agent:{self.name}] Loaded {len(self.tools)} tools: {[t.name if hasattr(t, 'name') else t.__name__ for t in self.tools]}")

        # Internal LLM instance bound with the agent's unique toolset
        self.llm = ChatOllama(
            model=MODEL,
            temperature=0
        ).bind_tools(self.tools)
        
        logger.info(f"[Agent:{self.name}] LLM initialized with model: llama3.2")
        
        self.valid_agent_targets = [] # Will be populated dynamically by the orchestrator

    def node_function(self, state: AgentState) -> Dict[str, Any]:
        """The actual function executed when LangGraph visits this agent node."""
        logger.info(f"[Agent:{self.name}] Node function invoked")
        logger.debug(f"[Agent:{self.name}] Current state - Messages count: {len(state['messages'])}")
        logger.debug(f"[Agent:{self.name}] Next destination: {state.get('next_destination', 'None')}")
        
        system_instruction = SystemMessage(
            content=f"{self.system_context}\\n\\nCRITICAL: If a request belongs to another team, output exactly: 'TRANSFER TO [Agent Name]_agent' (e.g., 'TRANSFER TO shipping_agent') to hand off. "
        )

        logger.debug(f"[Agent:{self.name}] System instruction prepared")
        
        # Run the agent utilizing shared memory context
        start_time = datetime.now()
        logger.info(f"[Agent:{self.name}] Invoking LLM...")
        
        response = self.llm.invoke([system_instruction] + state["messages"])
        
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"[Agent:{self.name}] LLM response received in {elapsed:.2f}s")
        logger.debug(f"[Agent:{self.name}] Response content preview: {response.content[:100]}...")

        # Default destination is this agent's tool execution node
        next_dest = f"{self.name}_tools"
        logger.debug(f"[Agent:{self.name}] Default next destination set to: {next_dest}")

        match = re.search(r"TRANSFER TO\\s+([a-zA-Z0-9_]+)", response.content, re.IGNORECASE)
        if match:
            extracted_target = match.group(1).strip().lower()
            logger.info(f"[Agent:{self.name}] Transfer request detected: '{extracted_target}'")
            
            # Perform a fast fuzzy search over the registry list
            # cutoff=0.4 allows matching 'security_protocol_agent' down to 'security_agent'
            closest_matches = difflib.get_close_matches(
                extracted_target, 
                self.valid_agent_targets, 
                n=1, 
                cutoff=0.4
            )
            
            logger.debug(f"[Agent:{self.name}] Fuzzy search results: {closest_matches}")
            
            if closest_matches:
                resolved_target = closest_matches[0]
                # Ensure we don't accidentally route an agent to transfer to itself
                if resolved_target != self.name:
                    next_dest = resolved_target
                    logger.info(f"🔮 [Fuzzy Matcher]: Resolved '{extracted_target}' to existing node '{resolved_target}'")
                else:
                    logger.warning(f"[Agent:{self.name}] Attempted self-transfer to '{resolved_target}', ignored")
            else:
                logger.warning(f"[Agent:{self.name}] No valid target found for '{extracted_target}', keeping current destination")
        else:
            logger.debug(f"[Agent:{self.name}] No transfer request detected in response")
                
        result = {
            "messages": [response],
            "next_destination": next_dest
        }
        
        logger.info(f"[Agent:{self.name}] Returning state update with next_destination: {next_dest}")
        return result

# The Agent Orchestrator Class (Main Agent Controller)
class AgentOrchestrator:
    def __init__(self, *agents: Agent, default_entry: Agent = None):
        logger.info("="*60)
        logger.info("[Orchestrator] Initializing Agent Orchestrator")
        logger.info("="*60)
        
        self.agents = list(agents)
        self.default_entry = default_entry.name if default_entry else self.agents[0].name
        
        logger.info(f"[Orchestrator] Total agents registered: {len(self.agents)}")
        logger.info(f"[Orchestrator] Agent names: {[agent.name for agent in self.agents]}")
        logger.info(f"[Orchestrator] Default entry point: {self.default_entry}")
        
        # Gather all valid agent string names
        all_agent_names = [agent.name for agent in self.agents]
        
        # Give each agent visibility into who else exists in the ecosystem
        for agent in self.agents:
            agent.valid_agent_targets = all_agent_names
            logger.info(f"[Orchestrator] Agent '{agent.name}' can see targets: {all_agent_names}")
        
        logger.info("[Orchestrator] Building graph...")
        self.graph = self._build_graph()
        logger.info("[Orchestrator] Graph built successfully")

    def _universal_router(self, state: AgentState) -> str:
        logger.debug("[Router] Universal router invoked")
        
        last_message = state["messages"][-1]
        destination = state.get("next_destination", END)
        
        logger.debug(f"[Router] Last message type: {type(last_message).__name__}")
        logger.debug(f"[Router] Current destination: {destination}")
        
        # If the model produced tool calls, those take execution precedence
        if last_message.tool_calls:
            logger.info(f"[Router] Tool calls detected: {[tc['name'] for tc in last_message.tool_calls]}")
            
            # Reconstruct the tool node name matching the current agent
            sender = state['messages'][-2].additional_kwargs.get('sender', destination.replace('_tools','')) if len(state['messages']) > 1 else destination.replace('_tools','')
            
            if not destination.endswith("_tools"):
                result = f"{sender}_tools"
            else:
                result = destination
                
            logger.info(f"[Router] Routing to tool node: {result}")
            return result
            
        if destination.endswith("_agent"):
            logger.info(f"[Router] Routing to agent node: {destination}")
            return destination
        
        logger.info(f"[Router] Routing to END")
        return END

    def _build_graph(self) -> Any:
        logger.info("[GraphBuilder] Starting graph construction")
        
        builder = StateGraph(AgentState)
        routing_map = {END: END}
        
        logger.debug(f"[GraphBuilder] Initial routing map: {routing_map}")
        
        for agent in self.agents:
            tool_node_name = f"{agent.name}_tools"
            
            logger.info(f"[GraphBuilder] Adding node: {agent.name}")
            builder.add_node(agent.name, agent.node_function)
            
            logger.info(f"[GraphBuilder] Adding tool node: {tool_node_name}")
            builder.add_node(tool_node_name, ToolNode(agent.tools))
            
            logger.info(f"[GraphBuilder] Adding edge: {tool_node_name} -> {agent.name}")
            builder.add_edge(tool_node_name, agent.name)
            
            routing_map[agent.name] = agent.name
            routing_map[tool_node_name] = tool_node_name
            
            logger.debug(f"[GraphBuilder] Updated routing map: {routing_map}")
        
        logger.info(f"[GraphBuilder] Adding START edge to: {self.default_entry}")
        builder.add_edge(START, self.default_entry)
         
        for agent in self.agents:
            logger.info(f"[GraphBuilder] Adding conditional edges for: {agent.name}")
            builder.add_conditional_edges(agent.name, self._universal_router, routing_map)
        
        logger.info("[GraphBuilder] Compiling graph...")
        compiled_graph = builder.compile()
        logger.info("[GraphBuilder] Graph compilation complete")
        
        return compiled_graph

    def run(self, prompt: str):
        logger.info("="*60)
        logger.info("[Execution] Starting orchestration run")
        logger.info("="*60)
        logger.info(f"[Execution] User prompt: {prompt}")
        logger.info(f"[Execution] Entry agent: {self.default_entry}")
        
        initial_state = {
            "messages": [HumanMessage(content=prompt)],
            "next_destination": ""
        }
        
        logger.debug(f"[Execution] Initial state prepared")
        print(f"=== Commencing Orchestration via Entry Agent: [{self.default_entry}] ===")
        
        step_count = 0
        for output in self.graph.stream(initial_state, stream_mode="updates"):
            step_count += 1
            logger.info(f"[Execution] Processing step {step_count}")
            
            for node_name, state_update in output.items():
                logger.info(f"\\n [Node Active: {node_name}]")
                logger.debug(f"[Node:{node_name}] State update keys: {list(state_update.keys())}")
                
                if "messages" in state_update:
                    last_msg = state_update["messages"][-1]
                    
                    if last_msg.content:
                        content_preview = last_msg.content[:200] + ("..." if len(last_msg.content) > 200 else "")
                        logger.info(f"[Node:{node_name}] Output: {content_preview}")
                        print(f" Output: {last_msg.content}")
                    
                    if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                        tool_names = [tc['name'] for tc in last_msg.tool_calls]
                        logger.info(f"[Node:{node_name}] Triggered Tool Calls: {tool_names}")
                        print(f" Triggered Tool Calls: {tool_names}")
                        
                        # Log tool call details
                        for tc in last_msg.tool_calls:
                            logger.debug(f"[Node:{node_name}] Tool call details: {tc}")
                
                if "next_destination" in state_update:
                    logger.info(f"[Node:{node_name}] Next destination updated to: {state_update['next_destination']}")
        
        logger.info("="*60)
        logger.info(f"[Execution] Orchestration complete after {step_count} steps")
        logger.info("="*60)

if __name__ == "__main__":
    @tool
    def calculate_shipping_cost(weight: float, destination: str) -> str:
        """Calculates shipping fees based on package weight and destination state."""
        logger.info(f"[Tool:calculate_shipping_cost] Called with weight={weight}, destination={destination}")
        result = f"Shipping cost for {weight} lbs to {destination} is $12.50 via Ground."
        logger.info(f"[Tool:calculate_shipping_cost] Result: {result}")
        return result
    
    @tool
    def verify_token(api_key: str) -> str:
        """Verifies if a developer API token is still active."""
        logger.info(f"[Tool:verify_token] Called with api_key={api_key}")
        result = f"Token '{api_key}' status verified: ACTIVE."
        logger.info(f"[Tool:verify_token] Result: {result}")
        return result

    # 1. Define independent, granular sub-agents using your target configuration syntax
    logger.info("[Setup] Creating shipping agent...")
    shipping_agent = Agent(
        name="shipping",
        system_context="You handle shipping logistics, delivery tracking, and transit costs.",
        tools=[calculate_shipping_cost]
    )

    logger.info("[Setup] Creating security agent...")
    security_agent = Agent(
        name="security",
        system_context="You handle system authentication, network protocols, and API key validations.",
        tools=[verify_token]
    )

    logger.info("[Setup] Creating orchestrator...")
    agent_main = AgentOrchestrator(shipping_agent, security_agent, default_entry=shipping_agent)

    user_query = (
        "Check company security protocol regarding keys, "
        "verify the token 'tok_abc55', and then calculate "
        "shipping fees for a 15lb box heading to Texas."
    )

    logger.info("[Setup] Configuration complete, ready to run")
    agent_main.run(user_query)
