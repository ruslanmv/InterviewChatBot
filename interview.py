import json
import os

def read_questions_from_json(file_path):
    """
    Reads questions from a JSON file.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file '{file_path}' does not exist.")

    with open(file_path, 'r') as f:
        questions = json.load(f)

    if not questions:
        raise ValueError("The JSON file is empty or has invalid content.")

    return questions

def conduct_interview(questions):
    """
    Conducts an interview by printing each question, taking input for the answer,
    and storing the questions and answers in a list.
    """
    interview_data = []
    print("\n--- Interview Started ---\n")

    for question in questions:
        print(f"{question}")
        answer = input("Your answer: ").strip()
        interview_data.append({"question": question, "answer": answer})

    print("\n--- Interview Completed ---\n")
    return interview_data

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
        interview_data = conduct_interview(questions)

        # Save the interview to a text file
        save_interview_to_file(interview_data, INTERVIEW_FILE_PATH)

    except Exception as e:
        print(f"Error: {e}")
