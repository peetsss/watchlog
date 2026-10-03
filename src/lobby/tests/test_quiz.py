from uuid import uuid4

from django.test import SimpleTestCase

from lobby.quiz import (
    build_intent_text,
    get_question_pool,
    select_quiz_snapshot,
    snapshot_question_ids,
    validate_quiz_answers,
)
from lobby.rules import QUIZ_QUESTION_COUNT, QUIZ_VERSION


class QuizSnapshotTests(SimpleTestCase):
    def test_selects_exactly_three_questions_with_version(self):
        snapshot = select_quiz_snapshot(seed=1234)
        self.assertEqual(snapshot["version"], QUIZ_VERSION)
        self.assertEqual(len(snapshot["questions"]), QUIZ_QUESTION_COUNT)
        self.assertEqual(len(set(snapshot_question_ids(snapshot))), QUIZ_QUESTION_COUNT)

    def test_same_seed_gives_same_questions(self):
        seed = uuid4()
        first = select_quiz_snapshot(seed=seed)
        second = select_quiz_snapshot(seed=seed)
        self.assertEqual(snapshot_question_ids(first), snapshot_question_ids(second))

    def test_snapshot_is_json_serializable(self):
        import json

        snapshot = select_quiz_snapshot(seed=42)
        self.assertEqual(json.loads(json.dumps(snapshot)), snapshot)

    def test_unknown_pool_version_raises(self):
        with self.assertRaises(ValueError):
            get_question_pool("nope")


class QuizAnswerTests(SimpleTestCase):
    def setUp(self):
        self.snapshot = select_quiz_snapshot(seed=7)

    def valid_answers(self, key_index=0):
        return {q["id"]: q["options"][key_index]["key"] for q in self.snapshot["questions"]}

    def test_individual_differences_survive(self):
        first = self.valid_answers(0)
        second = self.valid_answers(1)
        self.assertNotEqual(first, second)
        self.assertEqual(validate_quiz_answers(self.snapshot, first), first)
        self.assertEqual(validate_quiz_answers(self.snapshot, second), second)
        self.assertNotEqual(
            build_intent_text(self.snapshot, first),
            build_intent_text(self.snapshot, second),
        )

    def test_missing_question_rejected(self):
        answers = self.valid_answers()
        answers.pop(next(iter(answers)))
        with self.assertRaises(ValueError):
            validate_quiz_answers(self.snapshot, answers)

    def test_unknown_question_rejected(self):
        answers = self.valid_answers()
        answers["nope"] = "light"
        with self.assertRaises(ValueError):
            validate_quiz_answers(self.snapshot, answers)

    def test_invalid_option_key_rejected(self):
        answers = self.valid_answers()
        first_qid = next(iter(answers))
        answers[first_qid] = "not-a-key"
        with self.assertRaises(ValueError):
            validate_quiz_answers(self.snapshot, answers)

    def test_intent_text_uses_descriptions_in_order(self):
        answers = self.valid_answers()
        text = build_intent_text(self.snapshot, answers)
        self.assertTrue(text.startswith("Tonight we want a movie that is "))
        for q in self.snapshot["questions"]:
            option = next(o for o in q["options"] if o["key"] == answers[q["id"]])
            self.assertIn(option["description"], text)

    def test_no_majority_collapse(self):
        # Three participants answering differently keep three distinct intents.
        intents = {build_intent_text(self.snapshot, self.valid_answers(i % 3)) for i in range(3)}
        self.assertEqual(len(intents), 3)
