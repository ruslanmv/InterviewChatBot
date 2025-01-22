import os
import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

# Load environment variables
load_dotenv()

# File paths
PROFESSIONS_FILE = "professions.json"
TYPES_FILE = "types.json"
OUTPUT_FILE = "all_questions.json"

def generate_questions(profession, interview_type, description, max_questions):
    """
    Generates interview questions using the OpenAI API based on profession, type, and description.
    """
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not openai_api_key:
        raise RuntimeError(
            "OpenAI API key not found. Please add it to your .env file as OPENAI_API_KEY."
        )

    chat = ChatOpenAI(
        openai_api_key=openai_api_key, model="gpt-4", temperature=0.7, max_tokens=750
    )

    messages = [
        SystemMessage(
            content="You are an expert interviewer who generates concise technical interview questions for HR interviews. "
                    "Answer only with questions. Do not number the questions. Each question should be a separate string. "
                    "The questions should be appropriate for "
                    f"the {interview_type} stage of the interview process and relevant to the {profession} profession."
                    f" Generate no more than {max_questions} questions."

        ),
        HumanMessage(
            content=f"Generate interview questions for the role of '{profession}'. "
                    f"Interview Type: '{interview_type}'. "
                    f"Description of the role: '{description}'. "

        ),
    ]

    try:
        print(f"[DEBUG] Sending request to OpenAI for {profession} - {interview_type}")
        response = chat.invoke(messages)
        # Directly split the response into individual questions without numbering
        questions = [q.strip() for q in response.content.split("\n") if q.strip()]

    except Exception as e:
        print(f"[ERROR] Failed to generate questions: {e}")
        questions = ["An error occurred while generating questions."]

    return questions


def load_json_data(filepath):
    """Loads data from a JSON file."""
    with open(filepath, "r") as f:
        return json.load(f)


def save_questions_to_file(output_file, all_questions, overwrite=True):
    """
    Saves the questions to the specified JSON file.

    Args:
        output_file: The path to the output JSON file.
        all_questions: The list of question dictionaries to save.
        overwrite: If True, overwrites the file if it exists. If False, appends to the file.
    """
    if overwrite:
        with open(output_file, "w") as outfile:
            json.dump(all_questions, outfile, indent=4)
    else:
        try:
            existing_questions = load_json_data(output_file)
        except (FileNotFoundError, json.JSONDecodeError):
            existing_questions = []

        existing_questions.extend(all_questions)

        with open(output_file, "w") as outfile:
            json.dump(existing_questions, outfile, indent=4)


def main(overwrite_output=True):
    """
    Main function to generate and save interview questions.
    """
    try:
        professions_data = load_json_data(PROFESSIONS_FILE)
        types_data = load_json_data(TYPES_FILE)
    except FileNotFoundError as e:
        print(f"Error: File not found - {e}")
        return
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format in file - {e}")
        return

    all_questions = []

    for profession_info in professions_data:
        profession = profession_info["profession"]
        description = profession_info["description"]

        for interview_type_info in types_data:
            interview_type = interview_type_info["type"]
            max_questions = interview_type_info.get("max_questions", 5)

            questions = generate_questions(
                profession, interview_type, description, max_questions
            )

            all_questions.append(
                {
                    "profession": profession,
                    "interview_type": interview_type,
                    "description": description,
                    "max_questions": max_questions,
                    "questions": questions,
                }
            )
    # Save the questions, either overwriting or appending based on the parameter
    save_questions_to_file(OUTPUT_FILE, all_questions, overwrite=overwrite_output)
    print(f"[INFO] Questions saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    # Set overwrite_output to True to overwrite the existing file, False to append
    main(overwrite_output=True)