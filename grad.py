import os
import json
import gradio as gr
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

# Function to handle user input and LLM's response
def handle_user_input(chat, system_prompt, conversation_history, question_text, user_input):
    history_content = "\n".join([f"Q: {entry['question']}\nA: {entry['answer']}" for entry in conversation_history])
    combined_prompt = (f"{system_prompt}\n\nPrevious conversation history:\n{history_content}\n\n"
                       f"Current question: {question_text}\nUser's input: {user_input}\n\n"
                       "Respond naturally to any follow-up questions or requests for clarification."
                       " Provide the next question or end the interview when appropriate.")

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=combined_prompt)]
    response = chat.invoke(messages)
    return response.content.strip()

# Function to conduct the interview dynamically
def conduct_interview(questions, language="English", history_limit=5):
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise RuntimeError("OpenAI API key not found. Please add it to your .env file as OPENAI_API_KEY.")

    chat = ChatOpenAI(openai_api_key=openai_api_key, model="gpt-4", temperature=0.7, max_tokens=750)
    conversation_history = deque(maxlen=history_limit)
    system_prompt = f"You are Sarah, an empathetic HR interviewer conducting an interview in {language}."

    def gradio_interview(user_input, history):
        if not history:
            # Initial greeting and first question
            initial_message = (f"👋 Hello, I'm your AI HR assistant!\n"
                               f"I will ask you {len(questions)} questions.\n"
                               "Please answer honestly and to the best of your ability.")
            history = [{"role": "assistant", "content": initial_message}]
            current_question = questions[0]
            history.append({"role": "assistant", "content": f"First question: {current_question}"})
            return history, ""

        current_question_index = (len(history) - 2) // 2  # Adjust for assistant's intro
        if current_question_index < len(questions):
            current_question = questions[current_question_index]
            response = handle_user_input(chat, system_prompt, conversation_history, current_question, user_input)
            conversation_history.append({"question": current_question, "answer": user_input})
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": response})

            if current_question_index + 1 < len(questions):
                next_question = questions[current_question_index + 1]
                history.append({"role": "assistant", "content": f"Next question: {next_question}"})
            else:
                history.append({"role": "assistant", "content": "Thank you for your time. This concludes the interview."})

        return history, ""

    return gradio_interview

# Load questions and start Gradio app
def start_hr_chatbot():
    QUESTIONS_FILE_PATH = "questions.json"
    try:
        questions = read_questions_from_json(QUESTIONS_FILE_PATH)
    except Exception as e:
        print(f"Error: {e}")
        return

    interview_fn = conduct_interview(questions)

    with gr.Blocks(css=".gradio-container { font-family: Arial, sans-serif; max-width: 700px; margin: auto; }") as demo:
        gr.Markdown("## 🤖 HR Interview Chatbot")
        chatbot = gr.Chatbot(label="HR Chatbot", type="messages")
        user_input = gr.Textbox(label="💬 Your answer:", placeholder="Type your answer here and press Enter...", interactive=True)
        start_button = gr.Button("Start Interview")
        state = gr.State([])

        def on_start(history):
            return interview_fn("", history)

        def on_submit(user_input, history):
            history, new_input = interview_fn(user_input, history)
            return history, ""

        start_button.click(fn=on_start, inputs=[state], outputs=[chatbot, state])
        user_input.submit(fn=on_submit, inputs=[user_input, state], outputs=[chatbot, state])

        demo.launch(server_name="0.0.0.0", server_port=7860, debug=True)

if __name__ == "__main__":
    start_hr_chatbot()
