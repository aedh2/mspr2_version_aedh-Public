import unittest

from etl_common import (
    hours_to_minutes,
    normalize_gender_fr,
    normalize_meal_type,
    normalize_sleep_disorder,
    parse_blood_pressure,
    to_float,
)


class TestEtlHelpers(unittest.TestCase):
    def test_normalize_gender(self):
        self.assertEqual(normalize_gender_fr("Male"), "Homme")
        self.assertEqual(normalize_gender_fr("female"), "Femme")
        self.assertEqual(normalize_gender_fr(None), "Inconnu")

    def test_normalize_meal_type(self):
        self.assertEqual(normalize_meal_type("Breakfast"), "PetitDejeuner")
        self.assertEqual(normalize_meal_type("Lunch"), "Dejeuner")
        self.assertEqual(normalize_meal_type("Snack"), "Collation")

    def test_normalize_sleep_disorder(self):
        self.assertEqual(normalize_sleep_disorder("None"), "Aucun")
        self.assertEqual(normalize_sleep_disorder("Sleep Apnea"), "Apnee")
        self.assertEqual(normalize_sleep_disorder("Insomnia"), "Insomnie")

    def test_parse_blood_pressure(self):
        self.assertEqual(parse_blood_pressure("126/83"), (126, 83))
        self.assertEqual(parse_blood_pressure("bad-value"), (None, None))

    def test_conversions(self):
        self.assertEqual(to_float("1.75"), 1.75)
        self.assertEqual(hours_to_minutes("1.5"), 90)


if __name__ == "__main__":
    unittest.main()
