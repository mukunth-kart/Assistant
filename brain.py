import os
import json
import openai
from pydantic import BaseModel, Field
from typing import Optional

# Import configuration
try:
    from config import GROQ_API_KEY
except ImportError:
    # Handle direct execution or script/scratch calls
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from config import GROQ_API_KEY

# Define the structured output model
class TaskExtraction(BaseModel):
    title: str = Field(description="The title of the task")
    duration_minutes: int = Field(description="Estimated duration in minutes")
    priority_score: int = Field(description="Priority score from 1 (lowest) to 10 (highest)")
    deadline: Optional[str] = Field(None, description="Deadline in YYYY-MM-DD format if mentioned, else None")

class TaskListExtraction(BaseModel):
    tasks: list[TaskExtraction]

# Lazy client initialization to prevent crash on import when keys are missing
_client = None

def get_client():
    global _client
    if _client is None:
        key = GROQ_API_KEY or os.environ.get("GROQ_API_KEY")
        if not key:
            raise ValueError("GROQ_API_KEY is missing. Please set it in your .env file.")
        _client = openai.OpenAI(
            api_key=key,
            base_url="https://api.groq.com/openai/v1"
        )
    return _client

def parse_input(text_content: str) -> list[TaskExtraction]:
    """
    Parses raw unstructured text using Groq to extract a list of structured tasks.
    """
    client = get_client()
    
    system_prompt = (
        "You are a helpful assistant. You must extract all tasks from the user's message "
        "and return a JSON object matching this schema:\n"
        "{\n"
        '  "tasks": [\n'
        "    {\n"
        '      "title": "String task description",\n'
        '      "duration_minutes": Integer duration,\n'
        '      "priority_score": Integer priority 1-10,\n'
        '      "deadline": "YYYY-MM-DD" or null\n'
        "    }\n"
        "  ]\n"
        "}"
    )
    
    prompt = f"User input: \"{text_content}\""
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    
    result_content = response.choices[0].message.content
    task_data = json.loads(result_content)
    
    # Handle variations in LLM response structure
    if isinstance(task_data, list):
        extracted_tasks = [TaskExtraction(**t) for t in task_data]
    elif isinstance(task_data, dict):
        if "tasks" in task_data:
            extracted_tasks = [TaskExtraction(**t) for t in task_data["tasks"]]
        else:
            extracted_tasks = [TaskExtraction(**task_data)]
    else:
        raise ValueError("Invalid format returned by LLM.")
            
    return extracted_tasks

if __name__ == "__main__":
    # Quick debug/manual check if keys are configured
    if GROQ_API_KEY:
        print("Testing task extraction parser...")
        test_text = "I need to debug PyTorch Geometric shapes (2h, priority 9) and also draft ChemETL email (30m, priority 4)"
        extracted = parse_input(test_text)
        print(f"Extracted {len(extracted)} Tasks:")
        for t in extracted:
            print(f"- {t.title} ({t.duration_minutes}m, Priority: {t.priority_score})")
    else:
        print("GROQ_API_KEY not configured. Skipping live test.")
