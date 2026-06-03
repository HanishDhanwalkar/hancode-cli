
import json
import requests
import asyncio
from typing import Any

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

async def add_numbers(a: Any, b: Any) -> float:
    """Returns the sum of two numbers."""
    if not isinstance(a, float):
        a = float(a)
    if not isinstance(b, float):
        b = float(b)
    
    print(f"[Tool Execution] Adding {a} and {b}...")
    return a + b

async def multiply_numbers(a: Any, b: Any) -> float:
    """Returns the product of two numbers."""
    if not isinstance(a, float):
        a = float(a)
    if not isinstance(b, float):
        b = float(b)
        
    print(f"[Tool Execution] Multiplying {a} and {b}...")
    
    return a * b

async def substract_numbers(a: Any, b: Any) -> float:
    """Returns the difference between two numbers."""
    if not isinstance(a, float):
        a = float(a)
    if not isinstance(b, float):
        b = float(b)
    print(f"[Tool Execution] Substracting {a} and {b}...")
    return a - b

async def divide_numbers(a: Any, b: Any) -> float:
    """Returns the quotient of two numbers."""
    if not isinstance(a, float):
        a = float(a)
    if not isinstance(b, float):
        b = float(b)
        if b == 0:
            return ZeroDivisionError
    print(f"[Tool Execution] Dividing {a} and {b}...")
    return a / b

async def web_search_ddg(query:str, max_results: int=3):
    from ddgs import DDGS
    with DDGS() as ddgs:
        results = ddgs.text(query=query, max_results=max_results)
        
        tool_result = []
        for result in results:
            tool_result.append(
                {
                    "title": result["title"],
                    "body": result["body"],
                }
            )
            
        return list(results)



async def get_webpage_content(url: str):
    # TODO: 1. Compress the web content
    # 2. Truncate / Rerank -> Keeps only the top ~500 tokens relevant to the query
    
    # # Method #1
    # from ddgs import DDGS

    # page = DDGS().extract(url)
    # return page["content"]

    # Method #2
    response = requests.get(f"https://r.jina.ai/{url}")
    return response.text  # Returns clean, highly compressed markdown

    

if __name__ == "__main__":
    
    results = []
    async def test_web_search_ddgs():
        # query = "Today's date?"
        query = "Who ?"
        
        m_res = 2
        results = await web_search_ddg(query, m_res)
        print(results)
        # await get_webpage_content(results[0]['href'])
        
    asyncio.run(test_web_search_ddgs())
