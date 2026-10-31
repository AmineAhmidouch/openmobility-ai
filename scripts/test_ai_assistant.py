from ai.assistant import ask

questions = [
    "Which transport mode has the worst reporting completeness?",
    "Which RATP transport mode has the worst reporting completeness?",
    "Compare reporting completeness across all transport modes for SNCF.",
    "Which RATP transport mode has the highest missing-measurement rate among urgent alerts?",
    "Which transport modes have no urgent alerts?",
]

for question in questions:
    print("\n" + "=" * 80)
    print(f"QUESTION: {question}")
    print("-" * 80)
    print(ask(question))