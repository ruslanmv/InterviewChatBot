import os
import json
from collections import deque
from dotenv import load_dotenv
import gradio as gr
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

# Conduct interview and handle user input
def conduct_interview(questions, language="English", history_limit=5):
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise RuntimeError("OpenAI API key not found. Please add it to your .env file as OPENAI_API_KEY.")

    chat = ChatOpenAI(
        openai_api_key=openai_api_key, model="gpt-4", temperature=0.7, max_tokens=750
    )

    conversation_history = deque(maxlen=history_limit)
    system_prompt = (f"You are Sarah, an empathetic HR interviewer conducting a technical interview in {language}. "
                     "Respond to user follow-up questions politely and concisely. If the user is confused, provide clear clarification.")

    interview_data = []
    current_question_index = 0

    initial_message = (f"👋 Hello, I'm Sarah, your AI HR assistant!\n"
                       f"I will ask you {len(questions)} questions during this interview.\n"
                       "Please answer honestly and to the best of your ability.\n"
                       "If you need to stop at any point, you can type 'exit'. Let's get started!")

    def interview_step(user_input, history):
        nonlocal current_question_index

        if not history:  # Show the initial message and the first question when the interview starts
            first_question = questions[current_question_index]
            history.append(["AI", initial_message])
            history.append(["AI", first_question])
            return history, ""

        if user_input.lower() in ["exit", "quit"]:
            history.append(["AI", "Interview terminated as requested."])
            return history, "The interview has ended. Thank you for your time!"

        question_text = questions[current_question_index]
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

        conversation_history.append({"question": question_text, "answer": user_input})
        interview_data.append({"question": question_text, "answer": user_input})
        history.append(["User", user_input])
        history.append(["AI", response_content])

        if current_question_index + 1 < len(questions):
            current_question_index += 1
            next_question = questions[current_question_index]
            history.append(["AI", next_question])
            return history, ""
        else:
            history.append(["AI", "This concludes the interview. Thank you for your responses!"])
            return history, ""

    return interview_step

# Gradio interface
def main():
    QUESTIONS_FILE_PATH = "questions.json"

    try:
        questions = read_questions_from_json(QUESTIONS_FILE_PATH)
        interview_step = conduct_interview(questions)

        with gr.Blocks() as demo:
            gr.Markdown("## 👋 Welcome to Your AI HR Interview Assistant\nI will ask you a series of questions. Please answer honestly and thoughtfully.")

            chatbot = gr.Chatbot(label="Interview Chat")
            user_input = gr.Textbox(label="Your Response", placeholder="Type your answer here...")
            submit_btn = gr.Button("Submit")
            clear_btn = gr.Button("Clear Chat")

            def interact(history, user_response):
                history, new_input = interview_step(user_response, history)
                return history, new_input

            submit_btn.click(interact, inputs=[chatbot, user_input], outputs=[chatbot, user_input])
            clear_btn.click(lambda: ([], ""), inputs=[], outputs=[chatbot, user_input])

        demo.launch()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
