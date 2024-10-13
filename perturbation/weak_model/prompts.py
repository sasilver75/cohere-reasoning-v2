# Note that you have to double up all instances of { } in the prompt to avoid allow you to only inject {problem}
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

<answer>
\frac{{\sqrt{{5}}}}{{2}}
</answer>
</example_solution>
</example>

It is import that you present the final answer in <answer></answer> tags.
"""

VERIFY_SOLUTION_PROMPT = """
Here's a ground-truth problem and its solution:
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
