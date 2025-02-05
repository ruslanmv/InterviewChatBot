import os
from datetime import datetime
import json
def store_interview_report(report_content, folder_path="reports"):
    """
    Stores the interview report in a specified reports folder.
    
    Args:
        report_content (str): The content of the report to store.
        folder_path (str): The directory where the report will be saved.
    
    Returns:
        str: The file path of the saved report.
    """
    os.makedirs(folder_path, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(folder_path, f"interview_report_{timestamp}.txt")
    
    try:
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(report_content)
        print(f"[DEBUG] Interview report saved at {file_path}")
        return file_path
    except Exception as e:
        print(f"[ERROR] Failed to save interview report: {e}")
        return None
    

# Function to read questions from JSON
def read_questions_from_json(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file '{file_path}' does not exist.")

    with open(file_path, 'r') as f:
        questions_list = json.load(f)

    if not questions_list:
        raise ValueError("The JSON file is empty or has invalid content.")

    return questions_list
    