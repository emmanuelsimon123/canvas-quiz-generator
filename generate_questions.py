from groq import Groq
from dotenv import load_dotenv
import os
import json
import base64
import re

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def clean_math(text):
    if not isinstance(text, str):
        return text
    text = re.sub(r'\$\$(.+?)\$\$', r'\$$\1\$$', text)
    text = re.sub(r'\$(.+?)\$', r'\\(\1\\)', text)
    return text

def apply_math_cleaning(questions_data):
    for q in questions_data["questions"]:
        q["question"] = clean_math(q["question"])
        q_type = q.get("type", "multiple_choice")

        if q_type in ["multiple_choice", "multiple_answers"]:
            for letter in q.get("options", {}):
                q["options"][letter] = clean_math(q["options"][letter])

        if "correct_text" in q:
            q["correct_text"] = clean_math(q["correct_text"])

    return questions_data

def generate_questions(image_path, num_questions=5, question_type="auto_mix", selected_types=None, include_graphs=False):
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()

    if question_type == "auto_mix":
        type_instruction = """Use a smart VARIETY of these question types, choosing whichever fits best for each question:
- multiple_choice
- true_false
- fill_in_the_blank
- multiple_answers
- numerical
Try to use at least 3 different types. Pick the type that best fits each piece of content."""

    elif question_type == "pick_and_choose" and selected_types:
        types_list = "\n".join([f"- {t}" for t in selected_types])
        type_instruction = f"""Use ONLY these question types, distributing evenly across them:
{types_list}
Try to use each type at least once if possible."""

    else:
        type_instruction = f"ALL questions must be of type: {question_type}"

    if include_graphs:
        graph_instruction = """
GRAPH QUESTIONS:
- For some questions, include a "graph" field that defines a graph to show with the question
- Great for: identifying equations from graphs, finding intercepts, analyzing behavior
- The graph field must use this EXACT format:
  "graph": {
    "equations": ["x**2 - 4"],
    "x_range": [-5, 5],
    "y_range": [-10, 10],
    "title": "",
    "labels": ["f(x)"],
    "show_points": [{"x": 2, "y": 0, "label": "(2, 0)"}]
  }

CRITICAL GRAPH RULES:
- equations must be valid Python/numpy expressions using x as the variable
- Use ** for exponents: x**2 not x^2
- Use np.sin(x), np.cos(x), np.tan(x) for trig
- Use np.sqrt(x) for square root
- Use np.abs(x) for absolute value
- Use np.log(x) for natural log
- Use np.exp(x) for e^x
- Use np.pi for pi
- show_points is optional, use it to highlight key points like intercepts or vertices
- labels is optional
- Try to include 2-3 graph questions out of the total
- Graph questions should be multiple_choice type (students pick the equation or answer)"""
    else:
        graph_instruction = ""

    prompt = f"""Look at this image of study material.
Generate exactly {num_questions} quiz questions based on it.

{type_instruction}

{graph_instruction}

IMPORTANT MATH FORMATTING:
- For question text and multiple choice options: use LaTeX like \\(x^2 + 3x\\)
- For fill_in_the_blank correct_answers: use PLAIN TEXT with carets for exponents like x^2, -7x^2
  Do NOT use LaTeX in fill_in_the_blank answers since students type them manually

CRITICAL RULES FOR FILL IN THE BLANK:
- Include MANY variations of how a student might type the answer
- Include versions with and without spaces
- Include versions with and without parentheses
- Example: if the answer is -7x^2, include: ["-7x^2", "-7x^(2)", "- 7x^2", "-7X^2"]

CRITICAL RULES FOR NUMERICAL:
- ONLY use numerical type when the answer is a PLAIN NUMBER like 8, -3.5, 42
- NEVER use numerical type when the answer contains variables like x, y, n
- If the answer has variables, use fill_in_the_blank or multiple_choice instead

Return ONLY valid JSON. Each question MUST have a "type" field.
Here is the exact format for each type:

{{
  "questions": [
    {{
      "type": "multiple_choice",
      "question": "What is \\\\(2+2\\\\)?",
      "options": {{"A": "\\\\(3\\\\)", "B": "\\\\(4\\\\)", "C": "\\\\(5\\\\)", "D": "\\\\(6\\\\)"}},
      "correct_answer": "B"
    }},
    {{
      "type": "true_false",
      "question": "The square root of 144 is 12.",
      "correct_answer": "True"
    }},
    {{
      "type": "fill_in_the_blank",
      "question": "Simplify \\\\(-8y^3 - 5y^3\\\\). Use ^ for exponents.",
      "correct_answers": ["-13y^3", "-13y^(3)", "- 13y^3", "-13Y^3"]
    }},
    {{
      "type": "multiple_answers",
      "question": "Which are prime numbers? (Select all that apply)",
      "options": {{"A": "2", "B": "4", "C": "5", "D": "9"}},
      "correct_answers": ["A", "C"]
    }},
    {{
      "type": "numerical",
      "question": "What is 5 + 3?",
      "correct_answer": 8,
      "margin": 0
    }},
    {{
      "type": "multiple_choice",
      "question": "Which equation matches the graph shown?",
      "graph": {{
        "equations": ["x**2 - 4"],
        "x_range": [-5, 5],
        "y_range": [-6, 10],
        "title": "",
        "labels": ["f(x)"],
        "show_points": [{{"x": -2, "y": 0, "label": "(-2, 0)"}}, {{"x": 2, "y": 0, "label": "(2, 0)"}}]
      }},
      "options": {{"A": "\\\\(y = x^2 - 4\\\\)", "B": "\\\\(y = x^2 + 4\\\\)", "C": "\\\\(y = -x^2 - 4\\\\)", "D": "\\\\(y = 2x - 4\\\\)"}},
      "correct_answer": "A"
    }}
  ]
}}

Rules:
- Make questions directly based on the material shown
- Make wrong answers plausible but incorrect
- For fill_in_the_blank, include 3-5 variations of the correct answer
- For fill_in_the_blank with math, add hint "Use ^ for exponents" in the question
- For multiple_answers, always have 2-3 correct options out of 4
- For numerical, set margin to 0 unless rounding is expected
- Return ONLY the JSON, no extra text"""

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
            ]
        }],
        temperature=0.5
    )

    text = response.choices[0].message.content.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]

    result = json.loads(text.strip())
    result = apply_math_cleaning(result)
    return result