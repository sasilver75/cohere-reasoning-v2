GENERATE_SOLUTION_PROMPT = """
Here's a problem:
<problem>
{problem}
</problem>

Please solve this problem step-by-step, presenting the final answer in <answer></answer> tags.
If you do not present the final answer in <answer></answer> tags, your response will be considered incorrect.
"""

VERIFY_SOLUTION_PROMPT = """
Here's a groudn-truth problem and its solution:
<problem>
{problem}
</problem>
<solution>
{solution}
</solution>

Here's a candidate solution:
<candidate_solution>
{candidate_solution}
</candidate_solution>

The candidate solution should have its final answer in <answer></answer> tags.

Given the above information, reason about whether the candidate solution is correct, comparing the 
candidate answer in <answer></answer> tags to the ground-truth solution's final answer.

Present your reasoning in <verification_reasoning></verification_reasoning> tags.

Then, determine whether the candidate solution is "Correct" or "Incorrect" in <verification_result></verification_result> tags.
"""
