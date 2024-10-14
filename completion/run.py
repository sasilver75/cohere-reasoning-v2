import os

import pandas as pd
import prompts
from cohere import Client
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()
# co = AsyncClientV2(api_key=os.getenv("COHERE_API_KEY"))
# Note that the raw completion feature is only available for the synchronous v1 Cilent.
co = Client(os.getenv("COHERE_API_KEY"))
completion_model_name = "command-r-plus-08-2024"  # Most capable as of 10/12/2024 (128k ctx)


def generate_completion(problem: str, prefix: str, index: int) -> str:
    user_turn = prompts.COMPLETION_PROMPT_USER.format(problem=problem)
    assistant_turn = prompts.COMPLETION_PROMPT_ASSISTANT.format(prefix=prefix)
    completion = co.chat(
        model=completion_model_name,  # Replace with your desired model
        message=prompts.RAW_COMPLETION_TEMPLATE.format(
            user_turn=user_turn,
            assistant_turn=assistant_turn,
        ),
        raw_prompting=True,
    )
    return completion.text


def process_row(row: pd.Series):
    index = row["index"]
    problem = row["problem"]
    prefix = row["bad_solution_verification_prefix"]
    return generate_completion(problem, prefix, index)


def process_data(df: pd.DataFrame) -> pd.DataFrame:
    completions = []
    # Collect the results of the tasks
    # Using tqdm.asyncio.tqdm to get a progress bar for each batch.
    for index, row in tqdm(df.iterrows(), total=len(df), desc="Processing rows"):
        print(f"Processing row {index}...")
        completions.append(process_row(row))

    # Create a new dataframe with the completions added as a new column
    new_df = df.copy()
    new_df["completion"] = completions
    return new_df


def main():
    n = 10
    source_filename = "datasets/cn_k12_math_problems_weak_solutions_10.csv"
    output_filename = source_filename.replace("weak_solutions", "weak_solutions_completion")

    # Load dataframe
    print("Loading dataframe...")
    df = pd.read_csv(source_filename, nrows=n)
    print("Loaded dataframe!")

    # Process the dataframe
    print(f"Processing {n} rows...")
    processed_df = process_data(df)
    print(f"Finished processing {n} rows!")

    # Save results to CSV
    print("Saving results to CSV...")
    processed_df.to_csv(output_filename, index=False)
    print(f"Saved results to {output_filename}")

    print("Done!")


if __name__ == "__main__":
    main()
