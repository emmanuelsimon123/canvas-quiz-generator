"""Tests for build_qti_zip() covering all supported question types."""
import io
import zipfile
import unittest

from build_qti import build_qti_zip


SAMPLE_QUESTIONS = {
    "questions": [
        {
            "type": "multiple_choice",
            "question": "What is 2 + 2?",
            "options": {"A": "3", "B": "4", "C": "5", "D": "6"},
            "correct_answer": "B",
        },
        {
            "type": "true_false",
            "question": "The sky is blue.",
            "correct_answer": "True",
        },
        {
            "type": "fill_in_the_blank",
            "question": "The capital of France is ___.",
            "correct_answers": ["Paris", "paris"],
        },
        {
            "type": "multiple_answers",
            "question": "Which of the following are prime numbers? (Select all that apply)",
            "options": {"A": "2", "B": "4", "C": "5", "D": "9"},
            "correct_answers": ["A", "C"],
        },
        {
            "type": "numerical",
            "question": "What is 5 + 3?",
            "correct_answer": 8,
            "margin": 0,
        },
    ]
}


class TestBuildQtiZip(unittest.TestCase):
    def _get_zip(self, questions=None, title="Test Quiz", graphs=None):
        data = questions or SAMPLE_QUESTIONS
        result = build_qti_zip(data, quiz_title=title, graph_images=graphs or {})
        return result

    def test_returns_bytesio(self):
        result = self._get_zip()
        self.assertIsInstance(result, io.BytesIO)

    def test_zip_is_valid(self):
        result = self._get_zip()
        self.assertTrue(zipfile.is_zipfile(result))

    def test_zip_contains_quiz_xml(self):
        result = self._get_zip()
        with zipfile.ZipFile(result) as zf:
            self.assertIn("quiz.xml", zf.namelist())

    def test_zip_contains_imsmanifest(self):
        result = self._get_zip()
        with zipfile.ZipFile(result) as zf:
            self.assertIn("imsmanifest.xml", zf.namelist())

    def test_quiz_xml_has_all_items(self):
        result = self._get_zip()
        with zipfile.ZipFile(result) as zf:
            xml_content = zf.read("quiz.xml").decode("utf-8")
        # Each question produces one <item> element
        self.assertEqual(xml_content.count("<item "), len(SAMPLE_QUESTIONS["questions"]))

    def test_multiple_choice_question_type(self):
        questions = {"questions": [SAMPLE_QUESTIONS["questions"][0]]}
        result = self._get_zip(questions=questions)
        with zipfile.ZipFile(result) as zf:
            xml_content = zf.read("quiz.xml").decode("utf-8")
        self.assertIn("multiple_choice_question", xml_content)

    def test_true_false_question_type(self):
        questions = {"questions": [SAMPLE_QUESTIONS["questions"][1]]}
        result = self._get_zip(questions=questions)
        with zipfile.ZipFile(result) as zf:
            xml_content = zf.read("quiz.xml").decode("utf-8")
        self.assertIn("true_false_question", xml_content)

    def test_fill_in_the_blank_question_type(self):
        questions = {"questions": [SAMPLE_QUESTIONS["questions"][2]]}
        result = self._get_zip(questions=questions)
        with zipfile.ZipFile(result) as zf:
            xml_content = zf.read("quiz.xml").decode("utf-8")
        self.assertIn("short_answer_question", xml_content)

    def test_multiple_answers_question_type(self):
        questions = {"questions": [SAMPLE_QUESTIONS["questions"][3]]}
        result = self._get_zip(questions=questions)
        with zipfile.ZipFile(result) as zf:
            xml_content = zf.read("quiz.xml").decode("utf-8")
        self.assertIn("multiple_answers_question", xml_content)

    def test_numerical_question_type(self):
        questions = {"questions": [SAMPLE_QUESTIONS["questions"][4]]}
        result = self._get_zip(questions=questions)
        with zipfile.ZipFile(result) as zf:
            xml_content = zf.read("quiz.xml").decode("utf-8")
        self.assertIn("numerical_question", xml_content)

    def test_numerical_with_non_numeric_answer_falls_back_to_fib(self):
        questions = {
            "questions": [
                {
                    "type": "numerical",
                    "question": "What is x?",
                    "correct_answer": "x + 1",
                    "margin": 0,
                }
            ]
        }
        result = self._get_zip(questions=questions)
        with zipfile.ZipFile(result) as zf:
            xml_content = zf.read("quiz.xml").decode("utf-8")
        # Should fall back to short_answer_question
        self.assertIn("short_answer_question", xml_content)

    def test_quiz_title_in_xml(self):
        result = self._get_zip(title="My Awesome Quiz")
        with zipfile.ZipFile(result) as zf:
            xml_content = zf.read("quiz.xml").decode("utf-8")
        self.assertIn("My Awesome Quiz", xml_content)

    def test_empty_questions(self):
        result = self._get_zip(questions={"questions": []})
        self.assertTrue(zipfile.is_zipfile(result))

    def test_graph_image_embedded_in_xml(self):
        import base64
        fake_png = base64.b64encode(b"\x89PNG\r\n\x1a\n").decode()
        questions = {"questions": [SAMPLE_QUESTIONS["questions"][0]]}
        result = self._get_zip(questions=questions, graphs={0: fake_png})
        with zipfile.ZipFile(result) as zf:
            xml_content = zf.read("quiz.xml").decode("utf-8")
        self.assertIn("data:image/png;base64,", xml_content)


if __name__ == "__main__":
    unittest.main()
