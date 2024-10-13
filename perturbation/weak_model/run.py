import asyncio
import os
import re
from collections import namedtuple

import pandas as pd
import prompts
from cohere import AsyncClientV2
from dotenv import load_dotenv
from tqdm.asyncio import tqdm as atqdm

load_dotenv()
co = AsyncClientV2(api_key=os.getenv("COHERE_API_KEY"))

ProcessResult = namedtuple("ProcessResult", ["candidate_solution", "verification_trace", "verification_prefix", "audit"])

# solution_model_name = (
#     "command"  # Instruction-following conversational model that performs language tasks with high quality (4k ctx)
# )
# solution_model_name = "command-light"  # Smaller, faster version of command; almost as capable (4k ctx)
solution_model_name = "command-r-03-2024"  # Instruction-following conversational model (128k ctx)

verifier_model_name = "command-r-plus-08-2024"  # Most capable as of 10/12/2024


async def generate_candidate_solution(problem: str, index: int) -> str:
    try:
        response = await asyncio.wait_for(
            co.chat(
                model=solution_model_name,
                messages=[{"role": "user", "content": prompts.GENERATE_SOLUTION_PROMPT.format(problem=problem)}],
                temperature=0.6,
            ),
            timeout=45,
        )
    except asyncio.TimeoutError as e:
        print(f"Timeout occurred when generating candidate solution for row {index}: {e}")
        raise e
    return response.message.content[0].text


def extract_verification_data(verification_response: str) -> tuple[bool, str, str]:
    """
    Given a verification response, return whether the verifiation response indicates that the candidate solution was correct.
    Given that we're looking for af ailed response, return True if an error is encountered
    """
    verification_pattern = r"<verification_result>(.*?)</verification_result>"
    match = re.search(verification_pattern, verification_response, re.DOTALL)
    if not match:
        print(f"Could not parse verification result for {verification_response}")
    verified = match.group(1).strip().lower() == "correct" if match else True  # Default to True if no match is found (indicating an error)

    verification_reasoning_pattern = r"<verification_reasoning>(.*?)</verification_reasoning>"
    match = re.search(verification_reasoning_pattern, verification_response, re.DOTALL)
    if not match:
        print(f"Could not parse verification reasoning for {verification_response}")
    verification_reasoning = match.group(1).strip() if match else "(FAILED TO MATCH VERIFICATION REASONING)"

    verification_prefix_pattern = r"<verification_prefix>(.*?)</verification_prefix>"
    match = re.search(verification_prefix_pattern, verification_response, re.DOTALL)
    if not match:
        print(f"Could not parse verification prefix for {verification_response}")
    verification_prefix = match.group(1).strip() if match else ""

    return verified, verification_reasoning, verification_prefix


async def verify_solution(problem: str, solution: str, candidate_solution: str, index: int) -> tuple[bool, str, str]:
    """
    Return whether a candidate_solution is correct, given a ground-truth problem and its solution
    Given that we're looking for a failed response, return True if an error is encountered.
    """
    try:
        response = await asyncio.wait_for(
            co.chat(
                model=solution_model_name,
                messages=[
                    {
                        "role": "user",
                        "content": prompts.VERIFY_SOLUTION_PROMPT.format(
                            problem=problem, solution=solution, candidate_solution=candidate_solution
                        ),
                    },
                ],
                temperature=0,  # Don't want any creativity on this, just an accurate True or False
            ),
            timeout=45,
        )
    except asyncio.TimeoutError as e:
        print(f"Timeout occurred when verifying solution for row {index}: {e}")
        return True, "(TIMEOUT)", ""  # Default to True if an error is encountered

    # Extract the verification result from the response
    return extract_verification_data(response.message.content[0].text)


async def process_row(df: pd.DataFrame, index: int) -> ProcessResult:
    row = df.iloc[index]
    problem = row["problem"]
    solution = row["solution"]
    index = row["index"]

    failed_attempts = []
    failed_attempts_verification_reasoning = []

    found_failure = False
    while not found_failure:
        # Generate the candidate solution
        candidate_solution = await generate_candidate_solution(problem, index)
        if not candidate_solution:  # Empty string indicates a timeout
            continue

        # Verify the candidate solution
        verified_correct, verification_trace, verification_prefix = await verify_solution(problem, solution, candidate_solution, index)

        if verified_correct:
            # The candidate solution is verified as correct, so we add it to the list of failed attempts (to get a wrong answer)
            failed_attempts.append(candidate_solution)
            failed_attempts_verification_reasoning.append(verification_trace)
        else:
            found_failure = True

    audit = {
        "index": index,
        "problem": problem,
        "solution": solution,
        "attempts": failed_attempts,
        "attempts_verification_traces": failed_attempts_verification_reasoning,
        "candidate_solution": candidate_solution,
        "candidate_solution_verification_trace": verification_trace,
        "candidate_solution_verification_prefix": verification_prefix,
    }

    return ProcessResult(candidate_solution=candidate_solution, verification_trace=verification_trace, verification_prefix=verification_prefix, audit=audit)


async def process_data(df: pd.DataFrame) -> list[dict]:
    """
    For every row in the dataframe, generate solutions using a weaker model until one is found that is incorrect.
    Add the incorrect solution to the dataframe.

    Mutates given dataframe and returns a reference to it.
    """
    tasks = []
    for index in range(len(df)):
        tasks.append(process_row(df, index))

    results: list[ProcessResult] = []
    # Using tqdm.asyncio.tqdm to get a progress bar for each batch.
    for task in atqdm(asyncio.as_completed(tasks), total=len(df), desc=f"Processing {len(df)} rows"):
        # In the context of using asyncio.as_completed above, the tasks still run concurrenty, and this loop processes them as they complete.
        result = await task
        results.append(result)

    candidate_solutions = []
    candidate_solutions_verification_traces = []
    candidate_solutions_verification_prefixes = []
    audits = []
    for result in results:
        candidate_solutions.append(result.candidate_solution)
        candidate_solutions_verification_traces.append(result.verification_trace)
        candidate_solutions_verification_prefixes.append(result.verification_prefix)
        audits.append(result.audit)
    # Sort the audits by the index key
    audits = sorted(audits, key=lambda x: x['index'])
    audit_df = pd.DataFrame(audits)

    # attach the bad solution to the dataframe
    df["bad_solution"] = candidate_solutions
    df["bad_solution_verification_trace"] = candidate_solutions_verification_traces
    df["bad_solution_verification_prefix"] = candidate_solutions_verification_prefixes
    return df, audit_df


async def main():
    n = 5
    source_filename = "datasets/cn_k12_math_problems.csv"
    output_filename = f"datasets/cn_k12_math_problems_weak_solutions_{n}.csv"
    audit_filename = f"datasets/cn_k12_math_problems_weak_audits_{n}.csv"

    # Load dataframe
    print("Loading dataframe...")
    df = pd.read_csv(source_filename, nrows=n)
    print("Loaded dataframe!")

    # Process the dataframe
    print(f"Processing {n} rows...")
    processed_df, audit_df = await process_data(df)
    print(f"Finished processing {n} rows!")

    # Save results to CSV
    print("Saving results to CSV...")
    processed_df.to_csv(output_filename, index=False)
    print(f"Saved results to {output_filename}")
    audit_df.to_csv(audit_filename, index=False)
    print(f"Saved audit of data processing to {audit_filename}")

    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
