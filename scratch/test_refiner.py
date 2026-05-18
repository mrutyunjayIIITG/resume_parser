import json
from app.parser import refiner

# Mock a Gemini response that is a list
class MockResponse:
    def __init__(self, text):
        self.text = text

# Let's override refiner.model.generate_content
class MockModel:
    def __init__(self, return_text):
        self.return_text = return_text
    def generate_content(self, prompt):
        return MockResponse(self.return_text)

# Test 1: Gemini returns a list of dictionary
refiner.model = MockModel('[{"candidate_name": "Test Candidate", "skills": ["Python"]}]')
res = refiner.refine({"skills": ["React"]}, "resume text")
print("Test 1 Result Type:", type(res))
print("Test 1 Result:", res)

# Test 2: Gemini returns a dictionary
refiner.model = MockModel('{"candidate_name": "Test Candidate", "skills": ["Python"]}')
res = refiner.refine({"skills": ["React"]}, "resume text")
print("Test 2 Result Type:", type(res))
print("Test 2 Result:", res)

# Test 3: Gemini returns a list of strings
refiner.model = MockModel('["React", "Python"]')
res = refiner.refine({"skills": ["React"]}, "resume text")
print("Test 3 Result Type:", type(res))
print("Test 3 Result:", res)
