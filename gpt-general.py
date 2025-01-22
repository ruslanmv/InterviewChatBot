import os
import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI  # Correct import from langchain-openai
from langchain.schema import HumanMessage, SystemMessage  # For creating structured chat messages

# Load environment variables
load_dotenv()

# Function to read questions from JSON
# The JSON is expected to contain a list of dictionaries or strings.
def read_questions_from_json(file_path):
    """
    Reads questions from a JSON file.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file '{file_path}' does not exist.")

    with open(file_path, 'r') as f:
        questions_list = json.load(f)

    if not questions_list:
        raise ValueError("The JSON file is empty or has invalid content.")

    return questions_list

# Function to generate interview questions using LLM and collect user answers
def conduct_interview_with_llm(questions, language="English"):
    """
    Generates interview questions using the LLM and collects user responses.
    """
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise RuntimeError("OpenAI API key not found. Please add it to your .env file as OPENAI_API_KEY.")

    chat = ChatOpenAI(
        openai_api_key=openai_api_key, model="gpt-4", temperature=0.7, max_tokens=750
    )

    interview_data = []
    print("\n--- Technical Interview Started ---\n")

    for index, question_text in enumerate(questions):
        # Create the system and user prompts
        system_prompt = f"You are Sarah, a compassionate and empathetic HR professional conducting a technical interview in {language}."  
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Generate the next interview question based on the context and previous history. Current question number: {index + 1}/{len(questions)}.")
        ]

        try:
            # Generate a question from the LLM
            print(f"Generating question {index + 1}...")
            response = chat.invoke(messages)
            llm_generated_question = response.content.strip()
            print(f"Q{index + 1}: {llm_generated_question}")

            # Collect the user’s answer
            user_answer = input("Your answer: ").strip()
            interview_data.append({"question": llm_generated_question, "answer": user_answer})

        except Exception as e:
            print(f"Error with OpenAI API: {e}")
            interview_data.append({"question": "An error occurred while generating the question.", "answer": "No answer recorded."})

    print("\n--- Technical Interview Completed ---\n")
    return interview_data

# Function to save interview to a text file
def save_interview_to_file(interview_data, file_path):
    """
    Saves the questions and answers to a text file.
    """
    with open(file_path, 'w') as f:
        for entry in interview_data:
            f.write(f"Q: {entry['question']}\n")
            f.write(f"A: {entry['answer']}\n\n")

    print(f"Interview saved to {file_path}")

if __name__ == "__main__":
    QUESTIONS_FILE_PATH = "questions.json"
    INTERVIEW_FILE_PATH = "interview.txt"

    try:
        # Read questions from JSON file
        questions = read_questions_from_json(QUESTIONS_FILE_PATH)

        # Conduct the interview
        interview_results = conduct_interview_with_llm(questions, language="English")

        # Save the interview to a text file
        save_interview_to_file(interview_results, INTERVIEW_FILE_PATH)

    except Exception as e:
        print(f"Error: {e}")
