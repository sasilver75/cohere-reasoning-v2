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

ProcessResult = namedtuple(
    "ProcessResult", ["candidate_solution", "verification_trace", "verification_prefix", "strong_solution", "audit"]
)

weak_completer_name = "command-r-03-2024"  # Instruction-following conversational model (128k ctx)
strong_completer_name = "command-r-plus-08-2024"  # Most capable as of 10/12/2024 (128k ctx)
strong_verifier_name = "command-r-plus-08-2024"  # Most capable as of 10/12/2024 (128k ctx)


async def generate_strong_solution(problem: str, index: int) -> str:
    """
    The point of this function is to generate our strong model's completion of the problem, so as to have
    something to compare against the strong model's completion of the weak model's failed solution prefix.
    """
    retries_remaining = 5
    while retries_remaining:
        try:
            response = await asyncio.wait_for(
                co.chat(
                    model=strong_completer_name,
                    messages=[{"role": "user", "content": prompts.STRONG_COMPLETION_PROMPT.format(problem=problem)}],
                ),
                timeout=60,
            )
            return response.message.content[0].text
        except asyncio.TimeoutError as e:
            retries_remaining -= 1
            print(f"Timeout occurred when generating strong solution for row {index}. Retrying.")
            if not retries_remaining:
                print(f"Max retries reached for row {index}. Raising exception.")
                raise e
            await asyncio.sleep(1)  # Short delay before retrying


async def generate_candidate_solution(problem: str, index: int) -> str:
    retries_remaining = 5
    while retries_remaining:
        try:
            response = await asyncio.wait_for(
                co.chat(
                    model=weak_completer_name,
                    messages=[{"role": "user", "content": prompts.GENERATE_SOLUTION_PROMPT.format(problem=problem)}],
                    temperature=0.6,
                ),
                timeout=60,
            )
            return response.message.content[0].text
        except asyncio.TimeoutError as e:
            retries_remaining -= 1
            print(f"Timeout occurred when generating candidate solution for row {index}. Retrying.")
            if not retries_remaining:
                print(f"Max candidate_solution retries reached for row {index}. Raising exception.")
                raise e
            await asyncio.sleep(1)  # Short delay before retrying


def extract_verification_data(verification_response: str) -> tuple[bool, str, str]:
    """
    Given a verification response, return whether the verifiation response indicates that the candidate solution was correct.
    Given that we're looking for af ailed response, return True if an error is encountered
    """
    # Extract reasoning
    verification_reasoning_pattern = r"<verification_reasoning>(.*?)</verification_reasoning>"
    match = re.search(verification_reasoning_pattern, verification_response, re.DOTALL)
    if not match:
        print(f"Could not parse verification reasoning for {verification_response}")
    verification_reasoning = match.group(1).strip() if match else "(FAILED)"

    # Extract result
    verification_pattern = r"<verification_result>(.*?)</verification_result>"
    match = re.search(verification_pattern, verification_response, re.DOTALL)
    if not match:
        print(f"Could not parse verification result for {verification_response}")
    verified = (
        match.group(1).strip().lower() == "correct" if match else True
    )  # Default to True if no match is found (indicating an error)

    # Extract prefix
    verification_prefix_pattern = r"<verification_prefix>(.*?)</verification_prefix>"
    match = re.search(verification_prefix_pattern, verification_response, re.DOTALL)
    if not match:
        print(f"Could not parse verification prefix for {verification_response}")
    verification_prefix = match.group(1).strip() if match else "(FAILED)"

    return verified, verification_reasoning, verification_prefix


async def verify_solution(problem: str, solution: str, candidate_solution: str, index: int) -> tuple[bool, str, str]:
    """
    Return whether a candidate_solution is correct, given a ground-truth problem and its solution
    Given that we're looking for a failed response, return True if an error is encountered.
    """
    retries_remaining = 5
    while retries_remaining:
        try:
            response = await asyncio.wait_for(
                co.chat(
                    model=strong_verifier_name,
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
                timeout=60,
            )
            return extract_verification_data(response.message.content[0].text)
        except asyncio.TimeoutError as e:
            retries_remaining -= 1
            print(f"Timeout occurred when verifying candidate solution for row {index}. Retrying.")
            if not retries_remaining:
                print(f"Max verification retries reached for row {index}.")
                raise e
            await asyncio.sleep(1)  # Short delay before retrying


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
        verified_correct, verification_trace, verification_prefix = await verify_solution(
            problem, solution, candidate_solution, index
        )

        if verified_correct:
            # The candidate solution is verified as correct, so we add it to the list of failed attempts (to get a wrong answer)
            failed_attempts.append(candidate_solution)
            failed_attempts_verification_reasoning.append(verification_trace)
        else:
            found_failure = True

    strong_solution = await generate_strong_solution(problem, index)

    audit = {
        "index": index,
        "problem": problem,
        "solution": solution,
        "attempts": failed_attempts,
        "attempts_verification_traces": failed_attempts_verification_reasoning,
        "candidate_solution": candidate_solution,
        "candidate_solution_verification_trace": verification_trace,
        "candidate_solution_verification_prefix": verification_prefix,
        "strong_solution": strong_solution,
    }

    return ProcessResult(
        candidate_solution=candidate_solution,
        verification_trace=verification_trace,
        verification_prefix=verification_prefix,
        strong_solution=strong_solution,
        audit=audit,
    )


async def process_data(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    For every row in the dataframe, generate solutions using a weaker model until one is found that is incorrect.
    Add the incorrect solution to the dataframe.

    Mutates given dataframe and returns a reference to it.
    """
    tasks = []
    # Kick off the tasks
    for index in range(len(df)):
        tasks.append(process_row(df, index))

    results: list[ProcessResult] = []
    # Collect the results of the tasks
    # Using tqdm.asyncio.tqdm to get a progress bar for each batch.
    for task in atqdm(asyncio.as_completed(tasks), total=len(df), desc=f"Processing {len(df)} rows"):
        # In the context of using asyncio.as_completed above, the tasks still run concurrenty, and this loop processes them as they complete.
        result = await task
        results.append(result)

    # Sort results by index key
    results = sorted(results, key=lambda result: result.audit["index"])

    candidate_solutions = []
    candidate_solutions_verification_traces = []
    candidate_solutions_verification_prefixes = []
    strong_solutions = []
    audits = []
    for result in results:
        candidate_solutions.append(result.candidate_solution)
        candidate_solutions_verification_traces.append(result.verification_trace)
        candidate_solutions_verification_prefixes.append(result.verification_prefix)
        strong_solutions.append(result.strong_solution)
        audits.append(result.audit)

    # Create audit df
    audit_df = pd.DataFrame(audits)

    # attach the bad solution to the dataframe
    new_df = df.copy()
    new_df["bad_solution"] = candidate_solutions
    new_df["bad_solution_verification_trace"] = candidate_solutions_verification_traces
    new_df["bad_solution_verification_prefix"] = candidate_solutions_verification_prefixes
    new_df["strong_solution"] = strong_solutions
    return new_df, audit_df


async def main():
    n = 250
    source_filename = "datasets/original/cn_k12_math_problems.csv"
    output_filename = f"datasets/cn_k12_math_problems_weak_solutions_{n}.csv"
    audit_filename = f"datasets/cn_k12_math_problems_weak_audits_{n}.csv"

    # Load dataframe
    print("Loading dataframe...")
    # df = pd.read_csv(source_filename, nrows=n, skiprows=range(1, 15+1))
    df = pd.read_csv(source_filename, nrows=n)
    print(f"Loaded dataframe of {len(df)} records!")

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
