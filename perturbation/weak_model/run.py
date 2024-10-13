import asyncio
import os
import re
from collections import namedtuple

import pandas as pd
import prompts
from cohere import AsyncClientV2
from dotenv import load_dotenv
from tqdm.asyncio import tqdm as atqdm

from ... import utils

load_dotenv()
co = AsyncClientV2(api_key=os.getenv("COHERE_API_KEY"))

ProcessResult = namedtuple("ProcessResult", ["candidate_solution", "audit"])

solution_model_name = (
    "command"  # Instruction-following conversational model that performs language tasks with high quality (4k ctx)
)
# solution_model_name = "command-light"  # Smaller, faster version of command; almost as capable (4k ctx)
# solution_model_name = "command-r-03-2024"  # Instruction-following conversational model (128k ctx)

verifier_model_name = "command-r-plus-08-2024"  # Most capable as of 10/12/2024


async def generate_candidate_solution(problem: str, index: int) -> str:
    try:
        response = asyncio.wait_for(
            co.chat(
                model=solution_model_name,
                messages=[{"role": "user", "content": prompts.generate_solution_prompt.format(problem=problem)}],
                temperature=0.5,
            ),
            timeout=45,
        )
    except asyncio.TimeoutError as e:
        print(f"Timeout occurred when generating candidate solution for row {index}: {e}")
        raise e
    return response.message.context[0].text


def extract_verification_result(verification_response: str) -> bool:
    """
    Given a verification response, return whether the verifiation response indicates that the candidate solution was correct.
    Given that we're looking for af ailed response, return True if an error is encountered
    """
    verification_pattern = r"<verification_result>(.*?)</verification_result>"
    match = re.search(verification_pattern, verification_response, re.DOTALL)

    if match:
        return match.group(1).strip().lower() == "correct"

    print(f"No match found for verification response: {verification_response}")
    return True  # Default to True if no match is found (indicating an error)


async def verify_solution(problem: str, solution: str, candidate_solution: str, index: int) -> bool:
    """
    Return whether a candidate_solution is correct, given a ground-truth problem and its solution
    Given that we're looking for a failed response, return True if an error is encountered.
    """
    try:
        response = asyncio.wait_for(
            co.chat(
                model=solution_model_name,
                messages=[
                    {
                        "role": "user",
                        "content": prompts.verify_solution_prompt.format(
                            problem=problem, solution=solution, candidate_solution=candidate_solution
                        ),
                    },
                ],
                temperature=0,  # Don't want any creativity on this, just an accurate True or False
            ),
            timeout=45,
        )
    except asyncio.TimeoutError as e:
        print(f"Timeout occurred when generating candidate solution for row {index}: {e}")
        return True  # Default to True if an error is encountered

    # Extract the verification result from the response
    return extract_verification_result(response.message.context[0].text)


async def process_row(df: pd.Dataframe, index: int) -> ProcessResult:
    row = df.iloc[index]
    problem = row["problem"]
    solution = row["solution"]
    index = row["index"]

    failed_attempts = []

    found_failure = False
    while not found_failure:
        candidate_solution = await generate_candidate_solution(problem, index)
        if not candidate_solution:  # Empty string indicates a timeout
            continue
        correct = not await verify_solution(problem, solution, candidate_solution, index)

        if correct:
            failed_attempts.append(candidate_solution)
        else:
            found_failure = True

    audit = {
        "problem": problem,
        "solution": solution,
        "attempts": failed_attempts,
        "candidate_solution": candidate_solution,
    }

    return ProcessResult(candidate_solution=candidate_solution, audit=audit)


async def process_data(df: pd.Dataframe) -> list[dict]:
    """
    For every row in the dataframe, generate solutions using a weaker model until one is found that is incorrect.
    Add the incorrect solution to the dataframe.

    Mutates given dataframe and returns a reference to it.
    """
    tasks = []
    for index in range(len(df)):
        tasks.append(process_row(df, index))

    results = []
    # Using tqdm.asyncio.tqdm to get a progress bar for each batch.
    for task in atqdm(asyncio.as_completed(tasks), total=len(df), desc=f"Processing {len(df)} rows"):
        # In the context of using asyncio.as_completed above, the tasks still run concurrenty, and this loop processes them as they complete.
        result = await task
        results.append(result)

    candidate_solutions = []
    audits = []
    for result in results:
        candidate_solutions.append(result.candidate_solution)
        audits.append(result.audit)

    # attach the bad solution to the dataframe
    df["bad_solution"] = candidate_solutions

    # save the audits
    output_filename = f"datasets/cn_k12_math_problems_weak_model_audits.csv"
    pd.DataFrame(audits).to_csv(output_filename, index=False)
    print(f"Saved audit of data processing to {output_filename}")

    return df


async def main():
    source_filename = "datasets/cn_k12_math_problems.csv"

    n = 10

    # Load dataframe
    df = pd.read_csv(source_filename, nrows=n)

    # Process the dataframe
    print(f"Processing {n} rows...")
    processed: pd.DataFrame = await process_data(df)
    print(f"Finished processing {len(processed)} rows!")

    # Save results to CSV
    output_filename = f"datasets/cn_k12_math_problems_bad_solutions_{n}.csv"
    processed.to_csv(output_filename, index=False)
    print(f"Saved results to {output_filename}")


if __name__ == "__main__":
    asyncio.run(main())
