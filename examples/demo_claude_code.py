"""
Demo: Using Claude Code as the LLM Agent

This demonstrates using Claude Code (the current session) as the LLM
for generating components, instead of calling an external API.

Run this:
    cd /Users/williamtalcott/projects/dj-fixi
    python examples/demo_claude_code.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dj_fixi.llm.claude_code_adapter import ClaudeCodeAgent, ask_claude


def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def demo_1_simple_table():
    """Demo 1: Generate a simple table."""
    print_section("DEMO 1: Simple Table Generation")

    prompt = "Show me all products"
    print(f"User: {prompt}\n")

    result = ask_claude(prompt)

    print(f"Claude Code: {result['response']}\n")
    print("Generated Component:")
    print(f"  Type: {result['components'][0]['component_type']}")
    print(f"\n  View Code:\n{result['components'][0]['view_code']}\n")

    print("Suggestions:")
    for suggestion in result['suggestions']:
        print(f"  • {suggestion}")


def demo_2_filtered_table():
    """Demo 2: Generate table with filters."""
    print_section("DEMO 2: Filtered Table")

    prompt = "Show me products with price > 100"
    print(f"User: {prompt}\n")

    result = ask_claude(prompt)

    print(f"Claude Code: {result['response']}\n")

    component = result['components'][0]
    print("Generated Component:")
    print(f"  Type: {component['component_type']}")
    print(f"  Model: {component['metadata']['model']}")
    print(f"  Filters: {component['metadata']['filters']}")
    print(f"\n  View Code:\n{component['view_code']}\n")


def demo_3_chart():
    """Demo 3: Generate a chart."""
    print_section("DEMO 3: Chart Generation")

    prompt = "Create a bar chart of sales by region"
    print(f"User: {prompt}\n")

    result = ask_claude(prompt)

    print(f"Claude Code: {result['response']}\n")

    component = result['components'][0]
    print("Generated Component:")
    print(f"  Type: {component['component_type']}")
    print(f"  Chart Type: {component['metadata']['chart_type']}")
    print(f"\n  View Code:\n{component['view_code']}\n")


def demo_4_conversation():
    """Demo 4: Multi-turn conversation."""
    print_section("DEMO 4: Conversation Flow")

    agent = ClaudeCodeAgent()

    # Turn 1
    prompt1 = "Show me all users"
    print(f"User: {prompt1}\n")

    result1 = agent.process_prompt(prompt1)
    print(f"Claude Code: {result1['response']}\n")
    print(f"Component: {result1['components'][0]['component_type']} for {result1['components'][0]['metadata']['model']}\n")

    # Turn 2 (build on previous)
    prompt2 = "Make it editable"
    print(f"User: {prompt2}\n")

    result2 = agent.process_prompt(prompt2)
    print(f"Claude Code: {result2['response']}\n")


def demo_5_interactive():
    """Demo 5: Interactive prompt."""
    print_section("DEMO 5: Interactive Mode")

    print("Try asking Claude Code to generate components!")
    print("Examples:")
    print("  - Show me all products")
    print("  - Create a sales chart")
    print("  - Build a customer form")
    print("  - Show me orders with status active")
    print("\nType 'quit' to exit\n")

    agent = ClaudeCodeAgent()

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye!")
                break

            result = agent.process_prompt(user_input)

            print(f"\nClaude Code: {result['response']}\n")

            if result['components']:
                component = result['components'][0]
                print(f"Generated: {component['component_type']} component")
                print(f"Model: {component['metadata'].get('model', 'N/A')}")

                # Ask if user wants to see code
                show_code = input("\nShow generated code? (y/n): ").strip().lower()
                if show_code == 'y':
                    print(f"\n{component['view_code']}\n")

            print("\nSuggestions:")
            for suggestion in result['suggestions']:
                print(f"  • {suggestion}")
            print()

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}\n")


def main():
    """Run all demos."""
    print("\n" + "🤖" * 35)
    print("Claude Code as LLM Agent - Interactive Demo")
    print("🤖" * 35)

    demos = [
        ("1", "Simple Table", demo_1_simple_table),
        ("2", "Filtered Table", demo_2_filtered_table),
        ("3", "Chart", demo_3_chart),
        ("4", "Conversation", demo_4_conversation),
        ("5", "Interactive", demo_5_interactive),
    ]

    print("\nAvailable demos:")
    for num, name, _ in demos:
        print(f"  {num}. {name}")
    print("  a. Run all (non-interactive)")
    print("  q. Quit")

    choice = input("\nSelect demo (1-5, a, or q): ").strip().lower()

    if choice == 'q':
        print("Goodbye!")
        return

    if choice == 'a':
        # Run all non-interactive demos
        for num, name, func in demos[:-1]:  # Exclude interactive
            func()
        return

    # Run specific demo
    for num, name, func in demos:
        if choice == num:
            func()
            return

    print("Invalid choice!")


if __name__ == "__main__":
    main()
