"""
Save agent conversation logs to a file
"""
from agent import generate_report_with_autogen_multiagent
from datetime import datetime
import sys

# Redirect output to file
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = f"agent_conversation_log_{timestamp}.txt"

# Open file for writing
with open(log_file, 'w', encoding='utf-8') as f:
    # Save original stdout
    original_stdout = sys.stdout
    
    # Redirect stdout to file
    sys.stdout = f
    
    print("="*80)
    print("MICROSOFT AUTOGEN AGENT CONVERSATION LOG")
    print(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
    print("="*80)
    print()
    
    query = "Analyze sales performance and marketing effectiveness"
    print(f"QUERY: {query}")
    print("\n" + "="*80)
    print("MULTI-AGENT CONVERSATION")
    print("="*80 + "\n")
    
    # Generate report (all agent conversations will be captured)
    report = generate_report_with_autogen_multiagent(query, "combined", n_results=8)
    
    print("\n" + "="*80)
    print("FINAL REPORT")
    print("="*80)
    print(report)
    
    print("\n" + "="*80)
    print("END OF CONVERSATION LOG")
    print("="*80)
    
    # Restore stdout
    sys.stdout = original_stdout

print(f"\n✓ Agent conversation log saved to: {log_file}")
print(f"\nOpen {log_file} to see:")
print("  • Complete conversation between agents")
print("  • User Proxy → Data Analyst")
print("  • Data Analyst → Response")
print("  • User Proxy → Report Writer")
print("  • Report Writer → Final Report")

