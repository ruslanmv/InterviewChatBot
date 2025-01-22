import os
import json
from collections import deque
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

# Load environment variables
load_dotenv()

# Function to read questions from JSON
def read_questions_from_json(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file '{file_path}' does not exist.")

    with open(file_path, 'r') as f:
        questions_list = json.load(f)

    if not questions_list:
        raise ValueError("The JSON file is empty or has invalid content.")

    return questions_list

# Function to handle user input and responses from the LLM
def handle_user_input(chat, system_prompt, conversation_history, question_text):
    print("\nPlease take your time to respond. If you'd like to exit at any point, type 'exit' or 'quit'.")

    while True:
        user_input = input(f"Your response: ").strip()
        if user_input.lower() in ["exit", "quit"]:
            print("Interview terminated as requested.")
            return "[Interview Terminated by User]", True

        history_content = "\n".join([f"Q: {entry['question']}\nA: {entry['answer']}" for entry in conversation_history])
        combined_prompt = (f"{system_prompt}\n\nPrevious conversation history:\n{history_content}\n\n"
                           f"Current question: {question_text}\nUser's input: {user_input}\n\n"
                           "Respond naturally to any follow-up questions or requests for clarification, "
                           "and let the user know when you're ready to proceed.")

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=combined_prompt)
        ]

        response = chat.invoke(messages)
        response_content = response.content.strip()

        if "proceed" in response_content.lower() or "continue" in response_content.lower():
            print("Understood. Let’s continue to the next question.")
            return user_input, False
        else:
            print(f"\n🤖 LLM's Response: {response_content}")
            print("Whenever you're ready, just let me know by typing 'proceed', or feel free to ask further clarifications.")

# Function to conduct the interview
def conduct_interview_with_user_input(questions, language="English", history_limit=5):
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise RuntimeError("OpenAI API key not found. Please add it to your .env file as OPENAI_API_KEY.")

    chat = ChatOpenAI(
        openai_api_key=openai_api_key, model="gpt-4", temperature=0.7, max_tokens=750
    )

    interview_data = []
    conversation_history = deque(maxlen=history_limit)
    system_prompt = (f"You are Sarah, an empathetic HR interviewer conducting a technical interview in {language}. "
                     "Respond to user follow-up questions politely and concisely. If the user is confused, provide clear clarification.")

    initial_message = (f"👋 Hello, I'm Sarah, your AI HR assistant!\n"
                       f"I will ask you {len(questions)} questions during this interview.\n"
                       "Please answer honestly and to the best of your ability.\n"
                       "If you need to stop at any point, you can type 'exit'. Let's get started!")
    print(initial_message)

    print("\n--- Technical Interview Started ---\n")

    for index, question_text in enumerate(questions):
        print(f"{index + 1}/{len(questions)}: {question_text}")
        try:
            user_answer, terminate = handle_user_input(chat, system_prompt, conversation_history, question_text)
            if terminate:
                break

            conversation_history.append({"question": question_text, "answer": user_answer})
            interview_data.append({"question": question_text, "answer": user_answer})

            if index + 1 == len(questions):
                print("Thank you for your time. This concludes the interview. We will prepare a report based on the gathered information.")

        except Exception as e:
            print(f"Error during the interview process: {e}")
            interview_data.append({"question": question_text, "answer": "No answer recorded due to an error."})

    print("\n--- Technical Interview Completed ---\n")
    return interview_data

# Function to save interview to a text file
def save_interview_to_file(interview_data, file_path):
    with open(file_path, 'w') as f:
        for entry in interview_data:
            f.write(f"Q: {entry['question']}\n")
            f.write(f"A: {entry['answer']}\n\n")

    print(f"Interview saved to {file_path}")

if __name__ == "__main__":
    QUESTIONS_FILE_PATH = "questions.json"
    INTERVIEW_FILE_PATH = "interview.txt"

    try:
        questions = read_questions_from_json(QUESTIONS_FILE_PATH)
        interview_results = conduct_interview_with_user_input(questions, language="English")
        save_interview_to_file(interview_results, INTERVIEW_FILE_PATH)

    except Exception as e:
        print(f"Error: {e}")
