COMPLETION_PROMPT_USER = """
{problem}

Please solve this problem step-by-step, boxing the final answer.
"""

COMPLETION_PROMPT_ASSISTANT = """
Certainly. Here is the step-by-step reasoning and final answer to the problem:

{prefix}
"""

RAW_COMPLETION_TEMPLATE = """<BOS_TOKEN><|START_OF_TURN_TOKEN|><|SYSTEM_TOKEN|><|END_OF_TURN_TOKEN|><|START_OF_TURN_TOKEN|><|USER_TOKEN|>{user_turn}<|END_OF_TURN_TOKEN|><|START_OF_TURN_TOKEN|><|CHATBOT_TOKEN|>{assistant_turn}"""

VERIFY_SOLUTION_PROMPT = """
Here's a ground-truth problem and its solution:
<problem>
{problem}
</problem>
<solution>
{solution}
</solution>

Here's a candidate solution that may or may not be correct:
<candidate_solution>
{candidate_solution}
</candidate_solution>

The candidate solution _should_ have boxed (e.g. using the \\boxed{{...}} command) the answers to both explicitly stated subproblems and the final answer.

Given the above information, reason about whether the candidate solution is correct, where correctness is defined as producing a correct final answer.

First, reason about whether the solution is correct in <verification_reasoning></verification_reasoning> tags, specifically indicating the step and manner in which the reasoning may have gone wrong, if it did.
If the correct answer is produced, but not boxed, that should still be considered as a Correct solution.

Then, determine whether the candidate solution is either "Correct" or "Incorrect" in <verification_result></verification_result> tags.
"""
