import asyncio
import os
import re
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor, TimeoutError

import pandas as pd
import prompts
from cohere import AsyncClientV2, Client
from dotenv import load_dotenv
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from tqdm import tqdm
from tqdm.asyncio import tqdm as atqdm

load_dotenv()
key = os.getenv("COHERE_API_KEY")
co = Client(key)
co_async = AsyncClientV2(key)
strong_completer_name = "command-r-plus-08-2024"  # Most capable as of 10/12/2024 (128k ctx)
strong_verifier_name = "command-r-plus-08-2024"

VerificationResult = namedtuple("VerificationResult", ["index", "verified", "verification_trace"])


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def generate_completion(problem: str, prefix: str, index: int) -> str:
    """It seems that this is working well, errors are occurring about every 50 or so when processing 250, and recovering.
    The error isn't really printing out well though. I think it's because of timeouts."""
    user_turn = prompts.COMPLETION_PROMPT_USER.format(problem=problem)
    assistant_turn = prompts.COMPLETION_PROMPT_ASSISTANT.format(prefix=prefix)

    def api_call():
        return co.chat(
            model=strong_completer_name,
            message=prompts.RAW_COMPLETION_TEMPLATE.format(
                user_turn=user_turn,
                assistant_turn=assistant_turn,
            ),
            raw_prompting=True,
        )

    try:
        with ThreadPoolExecutor() as executor:
            future = executor.submit(api_call)
            completion = future.result(timeout=60)
    except Exception as e:
        print(f"Unexpected error generating completion for row {index}: {e}")
        if isinstance(e, TimeoutError):
            print(f"Error above is an instance of TimeoutError")
        raise e

    return completion.text


def complete_row(row: pd.Series):
    index = row["index"]
    problem = row["problem"]
    prefix = row["bad_solution_verification_prefix"]
    return generate_completion(problem, prefix, index)


def extract_verification_data(verification_response: str) -> tuple[bool, str]:
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

    return verified, verification_reasoning


async def verify_completion(problem: str, solution: str, completion: str, index: int) -> tuple[bool, str]:
    """
    Given a problem, solution, and completion, verify the correctness of the completion using a strong verifier model.
    Return a tuple with whether the verification was correct, and the verification reasoniong trace.
    """
    retries_remaining = 5
    while retries_remaining:
        try:
            response = await asyncio.wait_for(
                co_async.chat(
                    model=strong_verifier_name,
                    messages=[
                        {
                            "role": "user",
                            "content": prompts.VERIFY_SOLUTION_PROMPT.format(
                                problem=problem, solution=solution, candidate_solution=completion
                            ),
                        },
                    ],
                    temperature=0,  # Don't want any creativity on this, just an accurate True or False
                ),
                timeout=45,
            )
            return extract_verification_data(response.message.content[0].text)
        except asyncio.TimeoutError as e:
            retries_remaining -= 1
            print(f"Timeout occurred when verifying candidate solution for row {index}. Retrying.")
            if not retries_remaining:
                print(f"Max verification retries reached for row {index}.")
                raise e
            await asyncio.sleep(1)  # Short delay before retrying


async def verify_row(row: pd.Series) -> VerificationResult:
    """
    Given a dataframe row with a "bad_solution_verification_prefix" and "completion" column, verify the correctness of the completion
    Return a VerificationResult with the index, whether the verification was correct, and the verification reasoniong trace.
    """
    index = row["index"]
    problem = row["problem"]
    solution = row["solution"]
    completion = row["bad_solution_verification_prefix"] + row["completion"]

    verified_correct, verification_trace = await verify_completion(problem, solution, completion, index)

    return VerificationResult(index, verified_correct, verification_trace)


async def verify_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Given a dataframe with a "bad_solution_verification_prefix" and "completion" column, verify the correctness of the completion
    Return both a boolean of whether the answer is correct, as well as a trace of the verification reasoning.
    """
    tasks = []
    for _, row in df.iterrows():
        tasks.append(verify_row(row))
    results: VerificationResult = []

    for task in atqdm(asyncio.as_completed(tasks), total=len(df), desc=f"Verifying {len(df)} rows (Async)"):
        result = await task
        results.append(result)

    # Sort results by index
    results.sort(key=lambda x: x.index)
    verifications = [result.verified for result in results]
    verification_traces = [result.verification_trace for result in results]

    new_df = df.copy()
    new_df["completion_verified"] = verifications
    new_df["completion_verification_trace"] = verification_traces

    return new_df


def complete_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Synchronously generation completions for each row, and then asynchronously verify the completions.
    """
    new_df = df.copy()

    # Let's synchronously generate completions for each row, first.
    completions = []
    for _, row in tqdm(df.iterrows(), total=len(df), desc=f"Completing {len(df)} rows (Sync)"):
        index = row["index"]
        completion = complete_row(row)
        completions.append((index, completion))
    # Because these tasks will resolve out-of-order, we need to sort them by index before adding them to the dataframe
    completions = [completion[1] for completion in sorted(completions, key=lambda x: x[0])]

    new_df["completion"] = completions
    return new_df


async def generate_strong_solution(problem: str, index: int) -> str:
    """
    The point of this function is to generate our strong model's completion of the problem, so as to have
    something to compare against the strong model's completion of the weak model's failed solution prefix.
    """
    retries_remaining = 5
    while retries_remaining:
        try:
            # For the strong solution, we want to use the same user prompt that we later use to generate strong completions of weak prefixes
            response = await asyncio.wait_for(
                co_async.chat(
                    model=strong_completer_name,
                    messages=[{"role": "user", "content": prompts.COMPLETION_PROMPT_USER.format(problem=problem)}],
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


StraightShotResult = namedtuple("StraightShotResult", ["straight_shot_solution", "verification_trace", "verification"])


async def solve_row(df: pd.DataFrame, index: int) -> pd.Series:
    row = df.iloc[index]
    problem = row["problem"]
    solution = row["solution"]
    index = row["index"]

    # Get the straight shot solutoin
    straight_shot_solution = await generate_strong_solution(problem, index)

    # Verify it!
    verified_correct, verification_trace = await verify_completion(problem, solution, straight_shot_solution, index)

    # Package it up
    return StraightShotResult(straight_shot_solution, verification_trace, verified_correct)


async def solve_data(df: pd.DataFrame) -> pd.DataFrame:

    tasks = []
    for index in range(len(df)):
        tasks.append(solve_row(df, index))

    results: list[StraightShotResult] = []
    for task in atqdm(asyncio.as_completed(tasks), total=len(df), desc=f"Solving and verifying {len(df)} rows (Async)"):
        result = await task
        results.append(result)

    straight_shot_solutions = []
    straight_shot_verifications = []
    straight_shot_verification_traces = []
    for result in results:
        straight_shot_solutions.append(result.straight_shot_solution)
        straight_shot_verification_traces.append(result.verification_trace)
        straight_shot_verifications.append(result.verification)

    # Now let's attach this stuff to a new dataframe
    new_df = df.copy()
    new_df["straight_shot_solution"] = straight_shot_solutions
    new_df["straight_shot_verification"] = straight_shot_verifications
    new_df["straight_shot_verification_trace"] = straight_shot_verification_traces

    return new_df


async def main():
    n = None  # n = None means all records
    source_filename = "datasets/cn_k12_math_problems_weak_solutions_3.csv"
    output_filename = source_filename.replace("weak_solutions", "weak_solutions_completion")

    # Load dataframe
    print("Loading dataframe...")
    df = pd.read_csv(source_filename, nrows=n) if n is not None else pd.read_csv(source_filename)
    len_df = len(df)
    print(f"Loaded dataframe of {len_df} rows!")

    # Generate straight-shot solutions and verify them (async)
    print(f"Generating {len_df} straight-shot solutions...")
    solved_df = await solve_data(df)
    print(f"Finished generating {len_df} straight-shot solutions!")

    # Generate completions for the dataframe (sync, since it's the completions API)
    print(f"Completing {len_df} rows...")
    completed_df = complete_data(solved_df)
    print(f"Finished processing {len_df} rows!")
    # Verify the completions (async)
    print(f"Verifying {len_df} completions...")
    verified_df = await verify_data(completed_df)
    print(f"Finished verifying {len_df} completions!")

    # Save results to CSV
    print("Saving results to CSV...")
    verified_df.to_csv(output_filename, index=False)
    print(f"Saved results to {output_filename}")

    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
