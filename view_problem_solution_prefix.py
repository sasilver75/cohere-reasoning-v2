import os

import pandas as pd
from flask import Flask, render_template_string, request

app = Flask(__name__)

# Load the CSV file
csv_path = "datasets/cn_k12_math_problems_weak_audits_10.csv"
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
    audit_data = {
        "index": row.get("index", "N/A"),
        "problem": row.get("problem", "N/A"),
        "solution": row.get("solution", "N/A"),
        "bad_solution_verification_prefix": row.get("bad_solution_verification_prefix", "N/A"),
    }

    return render_template_string(
        """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Completion Audit Viewer</title>
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
                max-width: 1200px;
                margin: 0 auto;
            }
            .audit { 
                border: 1px solid #ddd; 
                padding: 20px; 
                margin-bottom: 20px;
            }
            h2, h3 { color: #333; }
            .math-content { 
                background-color: #f4f4f4; 
                padding: 10px; 
                word-wrap: break-word;
                overflow-wrap: break-word;
                white-space: normal;
                margin-bottom: 10px;
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
        <h1>Completion Audit Viewer ({{ page }}/{{ total_pages }})</h1>
        <div class="audit">
            <h2>Index: {{ audit_data.index }}</h2>
            
            <h2>Problem:</h2>
            <div class="math-content">{{ audit_data.problem }}</div>
            
            <h2>Solution:</h2>
            <div class="math-content">{{ audit_data.solution }}</div>
            
            <h2>Bad Solution Verification Prefix:</h2>
            <div class="math-content">{{ audit_data.bad_solution_verification_prefix }}</div>
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
        audit_data=audit_data,
        page=page,
        total_pages=len(df),
    )


if __name__ == "__main__":
    print(f"Starting server. CSV file path: {csv_path}")
    app.run(debug=True, host="localhost", port=5000)
