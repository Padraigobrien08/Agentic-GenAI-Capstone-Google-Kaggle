# agents/injection_runner.py

from typing import List, Dict

from agents.injection_tester import InjectionTestGenerator
from agents.injection_simulator import InjectionSimulator
from agents.orchestrator import QaOrchestrator


class InjectionTestRunner:
    """
    Orchestrates an end-to-end prompt injection test.

    1. Generate adversarial user prompts.
    2. Simulate agent responses.
    3. Evaluate each synthetic trace using Agent QA Mentor.
    4. Return structured results.
    """

    def __init__(self):
        """Initialize the test runner with generator, simulator, and QA orchestrator."""
        self.generator = InjectionTestGenerator()
        self.simulator = InjectionSimulator()
        self.qa = QaOrchestrator()

    def run(self, system_prompt: str, num_tests: int = 5) -> List[Dict]:
        """
        Run a complete prompt injection test suite.

        Args:
            system_prompt: The system prompt to test against
            num_tests: Number of adversarial prompts to generate and test (default: 5)

        Returns:
            List of dictionaries, each containing:
            - user_prompt: The adversarial user prompt
            - issues: List of issue codes detected by the judge
            - overall_score: Overall quality score (0-5)
            - rationale: Judge's rationale for the scores
        """
        tests = self.generator.generate_tests(system_prompt, num_tests)

        results = []

        for user_prompt in tests:
            trace = self.simulator.simulate(system_prompt, user_prompt)
            report = self.qa.run_analysis(trace)

            results.append({
                "user_prompt": user_prompt,
                "issues": report.judgment.issues,
                "overall_score": report.overall_score,
                "rationale": report.judgment.rationale,
            })

        return results

