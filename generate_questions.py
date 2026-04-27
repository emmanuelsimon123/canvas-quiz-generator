from groq import Groq
from dotenv import load_dotenv
import os
import json
import base64
import re

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def clean_math(text):
    """Clean up LaTeX formatting and unnecessary markup."""
    if not isinstance(text, str):
        return text
    # Remove \text{...} wrappers
    text = re.sub(r'\\?\(\\text\{([^}]*)\}\\?\)', r'\1', text)
    # Normalize special quote characters
    text = text.replace('\u00ab', '"').replace('\u00bb', '"')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
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
        if "explanation" in q:
            q["explanation"] = clean_math(q["explanation"])
    return questions_data


def validate_question(q):
    """Check that a question has all required fields for its type."""
    q_type = q.get("type")
    if q_type not in ("multiple_choice", "true_false", "fill_in_the_blank",
                       "multiple_answers", "numerical"):
        return False
    if "question" not in q or not q["question"]:
        return False
    if q_type == "multiple_choice":
        return (
            isinstance(q.get("options"), dict)
            and len(q["options"]) >= 2
            and q.get("correct_answer") in q["options"]
        )
    elif q_type == "true_false":
        return q.get("correct_answer") in ("True", "False")
    elif q_type == "fill_in_the_blank":
        return isinstance(q.get("correct_answers"), list) and len(q["correct_answers"]) > 0
    elif q_type == "multiple_answers":
        return (
            isinstance(q.get("options"), dict)
            and len(q["options"]) >= 2
            and isinstance(q.get("correct_answers"), list)
            and len(q["correct_answers"]) > 0
        )
    elif q_type == "numerical":
        try:
            float(q["correct_answer"])
            return True
        except (ValueError, TypeError, KeyError):
            return False
    return False


def fix_json_escapes(text):
    """Fix backslashes in AI-generated JSON that conflict with JSON escape sequences.

    The problem: LaTeX commands like \\times, \\frac, \\neq start with characters
    that are also valid JSON escapes (\\t = tab, \\f = form feed, \\n = newline, etc.).
    This function detects when those are actually LaTeX (followed by more letters)
    and double-escapes them so json.loads treats them as literal backslashes.
    """
    # First pass: catch LaTeX commands that START with a JSON escape character.
    # If \t, \b, \f, \n, \r, or \u is followed by another letter, it's LaTeX, not JSON.
    # Examples: \times, \theta, \frac, \neq, \right, \beta, \underset
    text = re.sub(r'\\([bfnrtu])([a-zA-Z])', r'\\\\\1\2', text)

    # Second pass: handle all other non-JSON backslash sequences
    # like \( \) $$ $$ \{ \} \^ \sqrt \cdot \pm etc.
    text = re.sub(r'\\(?!["\\/bfnrtu\\])', r'\\\\', text)

    return text


def build_prompt(num_questions, question_type, selected_types, include_graphs):
    """Build the instruction prompt."""
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
- Use np.sqrt(x), np.abs(x), np.log(x), np.exp(x), np.pi
- show_points and labels are optional
- Try to include 2-3 graph questions out of the total
- Graph questions should be multiple_choice type"""
    else:
        graph_instruction = ""

    prompt = f"""Generate exactly {num_questions} quiz questions based on the study material provided.

{type_instruction}

{graph_instruction}

CRITICAL: Only use LaTeX formatting for actual math expressions.
Do NOT wrap regular text in LaTeX. For example:
- WRONG: \\(\\text{{problem of evil}}\\)
- RIGHT: "problem of evil"
Only use \\(...\\) for things like equations, variables, and mathematical symbols.
Regular words, names, concepts, and phrases should be plain text with no LaTeX.

IMPORTANT MATH FORMATTING:
- For question text and multiple choice options: use LaTeX like \\(x^2 + 3x\\)
- For fill_in_the_blank correct_answers: use PLAIN TEXT with carets for exponents like x^2, -7x^2

CRITICAL RULES FOR FILL IN THE BLANK:
- Include MANY variations of how a student might type the answer
- Include versions with and without spaces and parentheses
- Example: if the answer is -7x^2, include: ["-7x^2", "-7x^(2)", "- 7x^2", "-7X^2"]

CRITICAL RULES FOR NUMERICAL:
- ONLY use numerical type when the answer is a PLAIN NUMBER like 8, -3.5, 42
- NEVER use numerical type when the answer contains variables

EXPLANATIONS:
- Every question MUST include an "explanation" field
- The explanation should help students understand WHY the answer is correct
- For math: show the solution steps
- For concepts: explain the reasoning
- Keep explanations clear and educational, 1-3 sentences
- Do NOT use LaTeX in explanations, use plain text with ^ for exponents

Return ONLY valid JSON. Each question MUST have a "type" field and an "explanation" field.
Here is the exact format for each type:

{{
  "questions": [
    {{
      "type": "multiple_choice",
      "question": "What is \\\\(2+2\\\\)?",
      "options": {{"A": "\\\\(3\\\\)", "B": "\\\\(4\\\\)", "C": "\\\\(5\\\\)", "D": "\\\\(6\\\\)"}},
      "correct_answer": "B",
      "explanation": "2 + 2 = 4, which is option B."
    }},
    {{
      "type": "true_false",
      "question": "The square root of 144 is 12.",
      "correct_answer": "True",
      "explanation": "12 x 12 = 144, so the square root of 144 is indeed 12."
    }},
    {{
      "type": "fill_in_the_blank",
      "question": "Simplify \\\\(-8y^3 - 5y^3\\\\). Use ^ for exponents.",
      "correct_answers": ["-13y^3", "-13y^(3)", "- 13y^3", "-13Y^3"],
      "explanation": "Combine like terms: -8y^3 - 5y^3 = (-8-5)y^3 = -13y^3."
    }},
    {{
      "type": "multiple_answers",
      "question": "Which are prime numbers? (Select all that apply)",
      "options": {{"A": "2", "B": "4", "C": "5", "D": "9"}},
      "correct_answers": ["A", "C"],
      "explanation": "2 and 5 are prime (only divisible by 1 and themselves). 4 = 2x2 and 9 = 3x3 are not prime."
    }},
    {{
      "type": "numerical",
      "question": "What is 5 + 3?",
      "correct_answer": 8,
      "margin": 0,
      "explanation": "5 + 3 = 8."
    }}
  ]
}}

Rules:
- Make questions directly based on the material shown
- Make wrong answers plausible but incorrect
- Every question MUST have an "explanation" field
- For fill_in_the_blank, include 3-5 variations of the correct answer
- For fill_in_the_blank with math, add hint "Use ^ for exponents" in the question
- For multiple_answers, always have 2-3 correct options out of 4
- For numerical, set margin to 0 unless rounding is expected
- Return ONLY the JSON, no extra text"""

    return prompt


def parse_and_validate(text):
    """Parse JSON response and validate questions."""
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]

    text = fix_json_escapes(text)

    result = json.loads(text.strip())
    valid_questions = [q for q in result.get("questions", []) if validate_question(q)]
    if not valid_questions:
        raise ValueError("No valid questions were returned by the AI.")
    result["questions"] = valid_questions
    result = apply_math_cleaning(result)
    return result


def _call_with_retry(messages, model, temperature=0.5, max_retries=3):
    """Send a request to the AI and retry on failure."""
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature
            )
            text = response.choices[0].message.content.strip()
            return parse_and_validate(text)
        except json.JSONDecodeError as e:
            if attempt == max_retries - 1:
                raise ValueError(
                    f"AI returned invalid JSON after {max_retries} attempts: {str(e)}"
                )
        except Exception:
            if attempt == max_retries - 1:
                raise


def generate_questions(image_path, num_questions=5, question_type="auto_mix",
                       selected_types=None, include_graphs=False,
                       model="meta-llama/llama-4-scout-17b-16e-instruct"):
    """Generate questions from an image file."""
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()
    prompt = "Look at this image of study material.\n\n"
    prompt += build_prompt(num_questions, question_type, selected_types, include_graphs)
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
        ]
    }]
    return _call_with_retry(messages, model)


def generate_questions_from_text(text_content, num_questions=5, question_type="auto_mix",
                                  selected_types=None, include_graphs=False,
                                  model="meta-llama/llama-4-scout-17b-16e-instruct"):
    """Generate questions from pasted text content."""
    prompt = "Here is the study material:\n\n" + text_content + "\n\n"
    prompt += build_prompt(num_questions, question_type, selected_types, include_graphs)
    messages = [{"role": "user", "content": prompt}]
    return _call_with_retry(messages, model)


def generate_questions_from_topic(subject, topic, specifics="", num_questions=5,
                                   question_type="auto_mix", selected_types=None,
                                   include_graphs=False,
                                   model="meta-llama/llama-4-scout-17b-16e-instruct"):
    """Generate questions from a subject and topic description."""
    topic_context = f"Subject: {subject}\nTopic: {topic}"
    if specifics:
        topic_context += f"\nSpecific areas to cover: {specifics}"
    prompt = "Generate quiz questions about the following:\n\n" + topic_context + "\n\n"
    prompt += build_prompt(num_questions, question_type, selected_types, include_graphs)
    messages = [{"role": "user", "content": prompt}]
    return _call_with_retry(messages, model)


def regenerate_single_question(original_question, context_text="",
                                image_path=None, question_type=None,
                                include_graphs=False,
                                model="meta-llama/llama-4-scout-17b-16e-instruct"):
    """Regenerate a single question, keeping the same type."""
    if question_type is None:
        question_type = original_question.get("type", "multiple_choice")
    regen_prompt = f"""Generate exactly 1 quiz question to replace this one.
The new question should be DIFFERENT but cover similar material.

Original question being replaced:
{json.dumps(original_question, indent=2)}

The new question MUST be of type: {question_type}

"""
    regen_prompt += build_prompt(1, question_type, None, include_graphs)
    if context_text:
        regen_prompt = "Based on this study material:\n" + context_text + "\n\n" + regen_prompt

    if image_path:
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": regen_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
            ]
        }]
    else:
        messages = [{"role": "user", "content": regen_prompt}]

    result = _call_with_retry(messages, model, temperature=0.7)
    if result["questions"]:
        return result["questions"][0]
    else:
        raise ValueError("No valid question returned.")
