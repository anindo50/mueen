import google.generativeai as genai

class GenerativeTextEngine:
    def __init__(self, api_key):
        self.api_key = api_key
        self.model = None

    def configure(self):
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-pro')

    def generate_content(self, content):
        return self.model.generate_content(content)