"""
AML Transaction Intelligence - Interactive Model Analysis
==========================================================
Compare Base Model vs Fine-tuned Model responses side-by-side.
Analyze model confidence and reasoning quality.

Usage:
    python scripts/interactive_analysis.py
    python scripts/interactive_analysis.py --model_path ./models/aml-expert
"""

import os
import json
import argparse
import time
from datetime import datetime
from typing import Optional, Dict, Any

import requests

# Configuration
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
BASE_MODEL = "llama3.1"
FINE_TUNED_MODEL = "aml-expert"  # Custom model name after loading adapter

# Test scenarios for analysis
TEST_SCENARIOS = [
    {
        "id": 1,
        "name": "Structuring Pattern",
        "description": "Classic cash structuring below CTR threshold",
        "input": "Account holder made 8 cash deposits of $9,800 each over 5 days at different ATM locations, totaling $78,400."
    },
    {
        "id": 2,
        "name": "Fan-Out Pattern",
        "description": "Rapid fund dispersion to multiple accounts",
        "input": "Business account received $450,000 wire and within 2 hours sent 15 transfers of ~$30,000 each to different entities in 8 countries."
    },
    {
        "id": 3,
        "name": "Trade-Based ML",
        "description": "Invoice discrepancy indicating over-invoicing",
        "input": "Import company paid $1.2M for electronics from Hong Kong supplier. Customs declaration shows goods valued at $180,000."
    },
    {
        "id": 4,
        "name": "Legitimate Business",
        "description": "Normal business operations (should be LOW risk)",
        "input": "Restaurant receives daily card payment settlements averaging $3,500 with seasonal variation. Pattern consistent for 2 years."
    },
    {
        "id": 5,
        "name": "Money Mule",
        "description": "Aggregation pattern suggesting mule account",
        "input": "College student account received 34 Venmo transfers from different people totaling $12,000 in 48 hours, then wired $11,500 to an overseas account."
    },
]

# System prompt for AML analysis
SYSTEM_PROMPT = """You are an expert AML (Anti-Money Laundering) analyst with deep knowledge of:
- FATF (Financial Action Task Force) Recommendations
- BSA (Bank Secrecy Act) requirements
- SAR (Suspicious Activity Report) filing criteria
- Money laundering typologies and red flags

Analyze the given transaction pattern and provide:
1. Risk Assessment (CRITICAL/HIGH/MEDIUM/LOW)
2. Identified Patterns
3. FATF Red Flags Triggered
4. Recommended Actions

Be specific and cite relevant regulations."""


def call_ollama(model: str, prompt: str, system: str = SYSTEM_PROMPT) -> Dict[str, Any]:
    """Call Ollama API and return response with timing."""
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"Analyze this transaction for potential money laundering:\n\n{prompt}"}
                ],
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                }
            },
            timeout=120
        )
        response.raise_for_status()
        data = response.json()
        
        return {
            "success": True,
            "response": data["message"]["content"],
            "latency_ms": int((time.time() - start_time) * 1000),
            "model": model,
            "eval_count": data.get("eval_count", 0),
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": str(e),
            "latency_ms": int((time.time() - start_time) * 1000),
            "model": model,
        }


def check_model_availability(model: str) -> bool:
    """Check if a model is available in Ollama."""
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        if response.status_code == 200:
            models = [m["name"] for m in response.json().get("models", [])]
            return model in models or f"{model}:latest" in models
    except:
        pass
    return False


def print_header(text: str, char: str = "="):
    """Print a styled header."""
    print(f"\n{char * 70}")
    print(f" {text}")
    print(f"{char * 70}")


def print_response(result: Dict[str, Any], label: str):
    """Print a model response with styling."""
    print(f"\n{'─' * 35}")
    print(f"│ {label}")
    print(f"│ Model: {result['model']} | Latency: {result['latency_ms']}ms")
    print(f"{'─' * 35}")
    
    if result["success"]:
        # Indent the response
        lines = result["response"].split("\n")
        for line in lines:
            print(f"  {line}")
    else:
        print(f"  ERROR: {result['error']}")


def run_comparison(scenario: Dict[str, Any], base_model: str, expert_model: Optional[str] = None):
    """Run a side-by-side comparison of models."""
    print_header(f"Scenario {scenario['id']}: {scenario['name']}")
    print(f"Description: {scenario['description']}")
    print(f"\nInput: {scenario['input']}")
    
    # Get base model response
    print("\n⏳ Generating base model response...")
    base_result = call_ollama(base_model, scenario["input"])
    print_response(base_result, "🔵 BASE MODEL (Standard)")
    
    # Get expert model response if available
    if expert_model and check_model_availability(expert_model):
        print("\n⏳ Generating expert model response...")
        expert_result = call_ollama(expert_model, scenario["input"])
        print_response(expert_result, "🟢 EXPERT MODEL (Fine-tuned)")
        
        # Comparison summary
        print(f"\n{'─' * 35}")
        print("│ COMPARISON SUMMARY")
        print(f"{'─' * 35}")
        print(f"  Base Model Latency:   {base_result['latency_ms']}ms")
        print(f"  Expert Model Latency: {expert_result['latency_ms']}ms")
        latency_diff = base_result['latency_ms'] - expert_result['latency_ms']
        if latency_diff > 0:
            print(f"  Expert is {latency_diff}ms faster ⚡")
        else:
            print(f"  Base is {-latency_diff}ms faster")
    else:
        print(f"\n⚠️  Expert model '{expert_model}' not available.")
        print("   Run fine-tuning first: python scripts/fine_tune_unsloth.py")


def interactive_mode(base_model: str, expert_model: Optional[str] = None):
    """Run interactive analysis mode."""
    print_header("AML TRANSACTION INTELLIGENCE - INTERACTIVE ANALYSIS")
    print(f"Base Model: {base_model}")
    print(f"Expert Model: {expert_model or 'Not configured'}")
    print(f"Ollama URL: {OLLAMA_URL}")
    
    # Check model availability
    if not check_model_availability(base_model):
        print(f"\n❌ Error: Base model '{base_model}' not found in Ollama.")
        print(f"   Pull it with: ollama pull {base_model}")
        return
    
    expert_available = expert_model and check_model_availability(expert_model)
    if expert_model and not expert_available:
        print(f"\n⚠️  Warning: Expert model '{expert_model}' not found.")
        print("   Will use base model only.")
    
    while True:
        print_header("MAIN MENU", "─")
        print("1. Run all test scenarios")
        print("2. Run specific scenario")
        print("3. Enter custom transaction")
        print("4. Model info")
        print("5. Exit")
        
        choice = input("\nSelect option (1-5): ").strip()
        
        if choice == "1":
            for scenario in TEST_SCENARIOS:
                run_comparison(scenario, base_model, expert_model if expert_available else None)
                input("\nPress Enter to continue...")
        
        elif choice == "2":
            print("\nAvailable scenarios:")
            for s in TEST_SCENARIOS:
                print(f"  {s['id']}. {s['name']}: {s['description']}")
            
            try:
                scenario_id = int(input("\nEnter scenario ID: ").strip())
                scenario = next((s for s in TEST_SCENARIOS if s['id'] == scenario_id), None)
                if scenario:
                    run_comparison(scenario, base_model, expert_model if expert_available else None)
                else:
                    print("Invalid scenario ID.")
            except ValueError:
                print("Please enter a valid number.")
        
        elif choice == "3":
            print("\nEnter your custom transaction description:")
            print("(Press Enter twice when done)")
            lines = []
            while True:
                line = input()
                if line:
                    lines.append(line)
                else:
                    break
            
            if lines:
                custom_input = " ".join(lines)
                custom_scenario = {
                    "id": 0,
                    "name": "Custom Analysis",
                    "description": "User-provided transaction",
                    "input": custom_input
                }
                run_comparison(custom_scenario, base_model, expert_model if expert_available else None)
        
        elif choice == "4":
            print_header("MODEL INFORMATION", "─")
            try:
                response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    print(f"\nAvailable models ({len(models)}):")
                    for m in models:
                        status = "✓" if m["name"] in [base_model, expert_model, f"{base_model}:latest", f"{expert_model}:latest"] else " "
                        size_gb = m.get("size", 0) / (1024**3)
                        print(f"  [{status}] {m['name']} ({size_gb:.1f} GB)")
                else:
                    print("Failed to get model list")
            except Exception as e:
                print(f"Error: {e}")
        
        elif choice == "5":
            print("\nGoodbye! 👋")
            break
        
        else:
            print("Invalid option. Please try again.")


def main():
    parser = argparse.ArgumentParser(description="Interactive AML Model Analysis")
    parser.add_argument("--base_model", type=str, default=BASE_MODEL,
                        help=f"Base model name (default: {BASE_MODEL})")
    parser.add_argument("--expert_model", type=str, default=FINE_TUNED_MODEL,
                        help=f"Fine-tuned expert model name (default: {FINE_TUNED_MODEL})")
    parser.add_argument("--ollama_url", type=str, default=OLLAMA_URL,
                        help=f"Ollama API URL (default: {OLLAMA_URL})")
    parser.add_argument("--scenario", type=int, default=0,
                        help="Run specific scenario (0 for interactive mode)")
    
    args = parser.parse_args()
    
    # Update global OLLAMA_URL if provided
    if args.ollama_url != OLLAMA_URL:
        globals()['OLLAMA_URL'] = args.ollama_url
    
    if args.scenario > 0:
        scenario = next((s for s in TEST_SCENARIOS if s['id'] == args.scenario), None)
        if scenario:
            run_comparison(scenario, args.base_model, args.expert_model)
        else:
            print(f"Scenario {args.scenario} not found.")
    else:
        interactive_mode(args.base_model, args.expert_model)


if __name__ == "__main__":
    main()
