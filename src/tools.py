

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
    print(f"[Tool Execution] Dividing {a} and {b}...")
    return a / b