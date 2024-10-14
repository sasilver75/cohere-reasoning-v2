import asyncio
import os
import re
from collections import namedtuple

import pandas as pd
import prompts
from cohere import AsyncClientV2, Client
from dotenv import load_dotenv
from tqdm import tqdm
from tqdm.asyncio import tqdm as atqdm

load_dotenv()
key = os.getenv("COHERE_API_KEY")
co = Client(key)
co_async = AsyncClientV2(key)
strong_completer_name = "command-r-plus-08-2024"  # Most capable as of 10/12/2024 (128k ctx)
strong_verifier_name = "command-r-plus-08-2024"

VerificationResult = namedtuple("VerificationResult", ["index", "verified", "verification_trace"])


def generate_completion(problem: str, prefix: str, index: int) -> str:
    user_turn = prompts.COMPLETION_PROMPT_USER.format(problem=problem)
    assistant_turn = prompts.COMPLETION_PROMPT_ASSISTANT.format(prefix=prefix)
    # TODO: Add a number of retries to get around timeout problems, which will be annoying when n=large
    # Consider using Tenacity library to do this.
    try:
        completion = co.chat(
            model=strong_completer_name,
            message=prompts.RAW_COMPLETION_TEMPLATE.format(
                user_turn=user_turn,
                assistant_turn=assistant_turn,
            ),
            raw_prompting=True,
        )
    except Exception as e:
        print(f"Error generating completion for row {index}: {e}")
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
    retries_remaining = 3
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
    completions = [completion[1] for completion in sorted(completions, key=lambda x: x[0])]

    new_df["completion"] = completions
    return new_df


async def main():
    n = 10
    source_filename = "datasets/cn_k12_math_problems_weak_solutions_10.csv"
    output_filename = source_filename.replace("weak_solutions", "weak_solutions_completion")

    # Load dataframe
    print("Loading dataframe...")
    df = pd.read_csv(source_filename, nrows=n)
    print("Loaded dataframe!")

    # Generate completions for the dataframe (sync)
    print(f"Completing {n} rows...")
    completed_df = complete_data(df)
    print(f"Finished processing {n} rows!")

    # Verify the completions (async)
    print(f"Verifying {n} completions...")
    verified_df = await verify_data(completed_df)
    print(f"Finished verifying {n} completions!")

    # Save results to CSV
    print("Saving results to CSV...")
    verified_df.to_csv(output_filename, index=False)
    print(f"Saved results to {output_filename}")

    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
