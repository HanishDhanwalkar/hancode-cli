from langgraph.graph import StateGraph, MessagesState, START, END

def mock_llm(state: MessagesState):
    return {
        "messages": [
            {
                "role": "ai",
                "content": "Hello, how can I help you today?"
            }
        ]
    }
    
def mock_tool(state: MessagesState):
    return {
        "messages": [
            {
                "role": "tool",
                "tool_call_id": "1",
                "content": "Hello, how can I help you today?"
            }
        ]
    }
    
    
    
graph = StateGraph(MessagesState)

graph.add_node(mock_llm)
graph.add_node(mock_tool)

graph.add_edge(START, "mock_llm")
graph.add_edge("mock_llm", "mock_tool")
graph.add_edge("mock_tool", END)

graph = graph.compile()

# response = graph.invoke(
#     {
#         "messages": [
#             {
#                 "role": "user",
#                 "content": "Hello!"
#             }
#         ]
#     }
# )

stream = graph.stream_events({
    "messages": [{"role": "user", "content": "What is 42 * 17?"}],
}, version="v3")

for message in stream.messages:
    for token in message.text:
        print(token, end="", flush=True)

final_state = stream.output
print(final_state)

# print(response)