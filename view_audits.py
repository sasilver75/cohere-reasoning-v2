import pandas as pd
from flask import Flask, render_template_string, request, redirect, url_for
import ast
import os

app = Flask(__name__)

# Load the CSV file
csv_path = "datasets/cn_k12_math_problems_weak_audits_3.csv"
if not os.path.exists(csv_path):
    print(f"Error: CSV file not found at {csv_path}")
    exit(1)

try:
    df = pd.read_csv(csv_path)
except Exception as e:
    print(f"Error reading CSV file: {e}")
    exit(1)

# Function to parse the attempts string into a list
def parse_attempts(attempts_str):
    try:
        return ast.literal_eval(attempts_str)
    except:
        return []

@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    if page < 1 or page > len(df):
        page = 1
    
    row = df.iloc[page-1]
    audit = {
        'problem': row.get('problem', 'N/A'),
        'solution': row.get('solution', 'N/A'),
        'attempts': parse_attempts(row.get('attempts', '[]')),
        'candidate_solution': row.get('candidate_solution', 'N/A')
    }

    return render_template_string('''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Math Problem Audits</title>
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
                max-width: 800px;
                margin: 0 auto;
            }
            .audit { 
                border: 1px solid #ddd; 
                padding: 20px; 
                margin-bottom: 20px;
            }
            h2 { color: #333; }
            .math-content { 
                background-color: #f4f4f4; 
                padding: 10px; 
                word-wrap: break-word;
                overflow-wrap: break-word;
                white-space: normal;
            }
            .attempts { margin-left: 20px; }
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
                overflow-x: auto;
                overflow-y: hidden;
            }
            .mjx-chtml.MJXc-display {
                max-width: 100%;
                overflow-x: auto;
                overflow-y: hidden;
                break-inside: avoid;
                break-before: auto;
                break-after: auto;
            }
            .mjx-math {
                white-space: normal !important;
                word-wrap: break-word !important;
            }
        </style>
    </head>
    <body>
        <h1>Math Problem Audit ({{ page }}/{{ total_pages }})</h1>
        <div class="audit">
            <h2>Problem:</h2>
            <div class="math-content">{{ audit.problem }}</div>
            
            <h2>Ground Truth Solution:</h2>
            <div class="math-content">{{ audit.solution }}</div>
            
            <h2>Candidate Solution (Incorrect):</h2>
            <div class="math-content">{{ audit.candidate_solution }}</div>
            
            <h2>Correct Attempts:</h2>
            <div class="attempts">
                {% for attempt in audit.attempts %}
                    <h3>Attempt {{ loop.index }}:</h3>
                    <div class="math-content">{{ attempt }}</div>
                {% endfor %}
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
    ''', audit=audit, page=page, total_pages=len(df))

if __name__ == '__main__':
    print(f"Starting server. CSV file path: {csv_path}")
    app.run(debug=True, host='localhost', port=5000)
