# Note that you have to double up all instances of { } in the prompt to allow you to only inject {problem}
GENERATE_SOLUTION_PROMPT = """
Here's a problem:
<problem>
{problem}
</problem>

Please solve this problem step-by-step. Do not include additional html tags in your response.

<example>
<example_problem>
In $\triangle ABC$, the lengths of the sides opposite to angles $A$, $B$, and $C$ are $a$, $b$, and $c$ respectively. Given that $\cos \frac{{C}}{{2}} = \frac{{\sqrt{{5}}}}{{3}}$ and $a \cos B + b \cos A = 2$, find the maximum area of $\triangle ABC$.
Since $\cos \frac{{C}}{{2}} = \frac{{\sqrt{{5}}}}{{3}}$, we have $\cos C = 2\cos^2 \frac{{C}}{{2}} - 1 = 2 \left(\frac{{\sqrt{{5}}}}{{3}}\right)^2 - 1 = \frac{{1}}{{9}}$.
</example_problem>

<example_solution>
Step 1: Using the cosine law, we have $a \cos B + b \cos A = 2$ can be written as $a \frac{{a^2 + c^2 - b^2}}{{2ac}} + b \frac{{c^2 + b^2 - a^2}}{{2bc}} = 2$

Step 2: Simplifying the equation, we obtain $c = 2$.

Step 3: Now, we have $4 = a^2 + b^2 - 2ab \cos C \geq 2ab - 2ab \frac{{1}}{{9}} = \frac{{16}}{{9}}ab$, which implies $ab \leq \frac{{9}}{{4}}$. The equality holds when $a = b = \frac{{3}}{{2}}$.

Step 4: Using the sine law, we have $\sin C = \sqrt{{1 - \cos^2 C}} = \sqrt{{1 - \left(\frac{{1}}{{9}}\right)^2}} = \frac{{4\sqrt{{5}}}}{{9}}$.

Step 5: The area of $\triangle ABC$ is given by $S = \frac{{1}}{{2}}ab \sin C \leq \frac{{1}}{{2}} \cdot \frac{{9}}{{4}} \cdot \frac{{4\sqrt{{5}}}}{{9}} = \boxed{{\frac{{\sqrt{{5}}}}{{2}}}}$.

Step 6: Therefore, the maximum area of $\triangle ABC$ is $\boxed{{\frac{{\sqrt{{5}}}}{{2}}}}$.
</example_solution>
</example>

It is critical that, like in the example above, you box the answer to subproblems that are explicitly stated in the problem, and that you box your final answer.
Use newline characters between steps.
"""

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

Finally, inside <verification_prefix></verification_prefix> tags:
    - If the candidate solution is "Incorrect", explicitly restate (It is absolutely critical that  you do not modifying the specific wording, structure, or intent of the candidate solution) the candidate solution UP TO AND INCLUDING the first incorrect step.You should include the "Step" prefixes for each step in the candidate solution.
    - Otherwise, if the candidate solution is "Correct", populate the inside of <verification_prefix></verification_prefix> with "N/A"
"""
