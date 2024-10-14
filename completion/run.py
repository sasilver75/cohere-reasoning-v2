import asyncio
import os
import re

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


def generate_completion(problem: str, prefix: str, index: int) -> str:
    user_turn = prompts.COMPLETION_PROMPT_USER.format(problem=problem)
    assistant_turn = prompts.COMPLETION_PROMPT_ASSISTANT.format(prefix=prefix)
    # TODO: Add a number of retries to get around timeout problems, which will be annoying when n=large
    # Consider using Tenacity library to do this.
    completion = co.chat(
        model=strong_completer_name,
        message=prompts.RAW_COMPLETION_TEMPLATE.format(
            user_turn=user_turn,
            assistant_turn=assistant_turn,
        ),
        raw_prompting=True,
    )
    return completion.text


def complete_row(row: pd.Series):
    index = row["index"]
    problem = row["problem"]
    prefix = row["bad_solution_verification_prefix"]
    return generate_completion(problem, prefix, index)


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


async def verify_completion(problem: str, solution: str, completion: str, index: int) -> tuple[bool, str, str]:
    retries_remaining = 3
    while retries_remaining:
        try:
            response = await asyncio.wait_for(
                co.chat(
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


async def verify_row(row: pd.Series) -> tuple[int, bool, str]:
    index = row["index"]
    problem = row["problem"]
    solution = row["solution"]
    completion = row["bad_solution_verification_prefix"] + row["completion"]

    verified_correct, verification_trace = await verify_completion(problem, solution, completion, index)

    return index, verified_correct, verification_trace


async def verify_data(df: pd.DataFrame) -> pd.DataFrame:
    tasks = []
    for index in range(len(df)):
        tasks.append(verify_row(df, index))
    results = []

    for task in atqdm(asyncio.as_completed(tasks), total=len(df), desc=f"Verifying {len(df)} rows"):
        result = await task
        results.append(result)

    # Sort results by index key
    results = [result[1] for result in sorted(results, key=lambda x: x[0])]


async def process_data(df: pd.DataFrame) -> pd.DataFrame:
    new_df = df.copy()

    # Let's synchronously generate completions for each row, first.
    completions = []
    print("Generation completions...")
    for _, row in tqdm(df.iterrows(), total=len(df), desc="Processing rows"):
        index = row["index"]
        completion = complete_row(row)
        completions.append((index, completion))
    completions = [completion[1] for completion in sorted(completions, key=lambda x: x[0])]
    new_df["completion"] = completions
    print("Completions generated!")

    # Now, let's verify those responses (we can do this async, which is kinda nice for speedup).
    print("Verifying completions...")
    for _, row in tqdm(new_df.iterrows(), total=len(new_df), desc="Processing rows"):
        index = row["index"]
        completion = row["completion"]
        verification_trace, verification_prefix = await verify_row(row)
        new_df.at[index, "verification_trace"] = verification_trace
        new_df.at[index, "verification_prefix"] = verification_prefix
    print("Completions verified!")

    return new_df


async def main():
    n = 10
    source_filename = "datasets/cn_k12_math_problems_weak_solutions_10.csv"
    output_filename = source_filename.replace("weak_solutions", "weak_solutions_completion")

    # Load dataframe
    print("Loading dataframe...")
    df = pd.read_csv(source_filename, nrows=n)
    print("Loaded dataframe!")

    # Process the dataframe
    print(f"Processing {n} rows...")
    processed_df = await process_data(df)
    print(f"Finished processing {n} rows!")

    # Save results to CSV
    print("Saving results to CSV...")
    processed_df.to_csv(output_filename, index=False)
    print(f"Saved results to {output_filename}")

    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
