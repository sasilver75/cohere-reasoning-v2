import pandas as pd
from flask import Flask, render_template_string, request
import os

app = Flask(__name__)

# Load the CSV file
csv_path = "datasets/cn_k12_math_problems_weak_audits_5.csv"
if not os.path.exists(csv_path):
    print(f"Error: CSV file not found at {csv_path}")
    exit(1)

try:
    df = pd.read_csv(csv_path)
except Exception as e:
    print(f"Error reading CSV file: {e}")
    exit(1)

@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    if page < 1 or page > len(df):
        page = 1
    
    row = df.iloc[page-1]
    comparison = {
        'index': row.get('index', 'N/A'),
        'problem': row.get('problem', 'N/A'),
        'candidate_solution': row.get('candidate_solution', 'N/A'),
        'candidate_solution_verification_prefix': row.get('candidate_solution_verification_prefix', 'N/A')
    }

    return render_template_string('''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Solution Comparison</title>
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
            .comparison { 
                display: flex;
                justify-content: space-between;
                margin-bottom: 20px;
            }
            .column {
                width: 48%;
                border: 1px solid #ddd;
                padding: 10px;
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
        <h1>Solution Comparison ({{ page }}/{{ total_pages }})</h1>
        <h2>Index: {{ comparison.index }}</h2>
        <h2>Problem:</h2>
        <div class="math-content">{{ comparison.problem }}</div>
        <div class="comparison">
            <div class="column">
                <h3>Candidate Solution:</h3>
                <div class="math-content">{{ comparison.candidate_solution }}</div>
            </div>
            <div class="column">
                <h3>Verification Prefix:</h3>
                <div class="math-content">{{ comparison.candidate_solution_verification_prefix }}</div>
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
    ''', comparison=comparison, page=page, total_pages=len(df))

if __name__ == '__main__':
    print(f"Starting server. CSV file path: {csv_path}")
    app.run(debug=True, host='localhost', port=6000)
