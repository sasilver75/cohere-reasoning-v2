import os

import pandas as pd
from flask import Flask, render_template_string, request

app = Flask(__name__)

# Load the CSV file
csv_path = "datasets/cn_k12_math_problems_weak_solutions_completion_3.csv"
if not os.path.exists(csv_path):
    print(f"Error: CSV file not found at {csv_path}")
    exit(1)

try:
    df = pd.read_csv(csv_path)
except Exception as e:
    print(f"Error reading CSV file: {e}")
    exit(1)


@app.route("/")
def index():
    page = request.args.get("page", 1, type=int)
    if page < 1 or page > len(df):
        page = 1

    row = df.iloc[page - 1]
    completion_data = {
        "index": row.get("index", "N/A"),
        "problem": row.get("problem", "N/A"),
        "solution": row.get("solution", "N/A"),
        "strong_solution": row.get("strong_solution", "N/A"),
        "bad_solution": row.get("bad_solution", "No weak solution available"),
        "bad_solution_verification_prefix": row.get("bad_solution_verification_prefix", "N/A"),
        "bad_solution_verification_trace": row.get("bad_solution_verification_trace", "N/A"),
        "completion": row.get("completion", "N/A"),
        "completion_verified": row.get("completion_verified", "N/A"),
        "completion_verification_trace": row.get("completion_verification_trace", "N/A"),
        "straight_shot_solution": row.get("straight_shot_solution", "N/A"),
        "straight_shot_verification": row.get("straight_shot_verification", "N/A"),
        "straight_shot_verification_trace": row.get("straight_shot_verification_trace", "N/A"),
    }

    return render_template_string(
        """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Completion Viewer</title>
        <script src="https://polyfill.io/v3/polyfill.min.js?features=es6"></script>
        <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
        <script>
            MathJax = {
                tex: {
                    inlineMath: [['$', '$'], ['\\(', '\\)']],
                    displayMath: [['$$', '$$'], ['\\[', '\\]']],
                    processEscapes: true,
                    processEnvironments: true
                },
                options: {
                    skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre']
                }
            };
        </script>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                line-height: 1.6; 
                padding: 20px;
                max-width: 1800px; /* Increased max-width for more horizontal space */
                margin: 0 auto;
            }
            .completion { 
                border: 1px solid #ddd; 
                padding: 20px; 
                margin-bottom: 20px;
                display: flex;
                flex-wrap: wrap;
                justify-content: space-between;
            }
            .section {
                width: 48%; /* Adjusted width for better distribution */
                margin-bottom: 20px;
            }
            h2, h3 { color: #333; }
            .math-content, .connected-content, .verification-trace { 
                background-color: #f4f4f4; 
                padding: 10px; 
                word-wrap: break-word;
                overflow-wrap: break-word;
                white-space: normal;
                margin-bottom: 10px;
            }
            .connected-content {
                background-color: #e0ffe0; /* Light green color for connected sections */
            }
            .verification-trace {
                background-color: #e6f3ff;
            }
            .completion-verified {
                padding: 10px;
                word-wrap: break-word;
                overflow-wrap: break-word;
                white-space: normal;
                margin-bottom: 10px;
                background-color: {{ 'green' if completion_data.completion_verified == 'True' else 'red' }};
            }
            .navigation { 
                display: flex; 
                justify-content: space-between; 
                margin-top: 20px;
            }
            .navigation a { 
                text-decoration: none; 
                color: #333; 
                padding: 10px; 
                border: 1px solid #ddd;
            }
            .mjx-chtml { 
                max-width: 100%;
            }
            .mjx-math {
                white-space: normal !important;
                word-wrap: break-word !important;
            }
        </style>
    </head>
    <body>
        <h1>Completion Viewer ({{ page }}/{{ total_pages }})</h1>
        <h2>Problem Index: {{ completion_data.index }}</h2>
        <div class="completion">
            <div class="section">
                <h2>Problem:</h2>
                <div class="math-content">{{ completion_data.problem }}</div>
                
                <h2>Ground-Truth Solution:</h2>
                <div class="math-content">{{ completion_data.solution }}</div>
                
                <h2>Straight Shot Solution:</h2>
                <div class="math-content">{{ completion_data.straight_shot_solution }}</div>
                
                <h3>Straight Shot Verification:</h3>
                <div class="completion-verified">{{ completion_data.straight_shot_verification }}</div>
                
                <h3>Straight Shot Verification Trace:</h3>
                <div class="verification-trace">{{ completion_data.straight_shot_verification_trace }}</div>
            </div>
            <div class="section">
                <h2>Weak Completer Incorrect Solution:</h2>
                <div class="math-content">{{ completion_data.bad_solution }}</div>
                
                <h2>Weak Completer Solution Prefix:</h2>
                <div class="connected-content">{{ completion_data.bad_solution_verification_prefix }}</div>
                
                <h3>Weak Solution Verification Trace:</h3>
                <div class="verification-trace">{{ completion_data.bad_solution_verification_trace }}</div>
                
                <h2>Strong Completion:</h2>
                <div class="connected-content">{{ completion_data.completion }}</div>
                
                <h2>Strong Completion Verification:</h2>
                <div class="completion-verified">{{ completion_data.completion_verified }}</div>
                
                <h3>Strong Completion Verification Trace:</h3>
                <div class="verification-trace">{{ completion_data.completion_verification_trace }}</div>
            </div>
        </div>
        <div class="navigation">
            {% if page > 1 %}
                <a href="{{ url_for('index', page=page-1) }}">Back</a>
            {% else %}
                <span></span>
            {% endif %}
            {% if page < total_pages %}
                <a href="{{ url_for('index', page=page+1) }}">Next</a>
            {% else %}
                <span></span>
            {% endif %}
        </div>
    </body>
    </html>
    """,
        completion_data=completion_data,
        page=page,
        total_pages=len(df),
    )


if __name__ == "__main__":
    print(f"Starting server. CSV file path: {csv_path}")
    app.run(debug=True, host="localhost", port=5000)
