import gradio as gr
import tempfile
import os
import json
from io import BytesIO
from collections import deque
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

# Load environment variables
load_dotenv()

class InterviewState:
    def __init__(self):
        self.reset()

    def reset(self, voice="alloy"):
        self.question_count = 0
        self.interview_history = []
        self.selected_interviewer = voice
        self.interview_finished = False
        self.audio_enabled = True
        self.temp_audio_files = []
        self.initial_audio_path = None
        self.admin_authenticated = False
        self.document_loaded = False
        self.knowledge_retrieval_setup = False
        self.interview_chain = None
        self.report_chain = None

    def get_voice_setting(self):
        return self.selected_interviewer

interview_state = InterviewState()

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
    current_question_index = [0]

    initial_message = ("👋 Hi there, I'm Sarah, your friendly AI HR assistant! "
                       "I'll guide you through a series of interview questions to learn more about you. "
                       "Take your time and answer each question thoughtfully.")

    def interview_step(user_input, history):
        if user_input.lower() in ["exit", "quit"]:
            history.append({"role": "assistant", "content": "The interview has ended at your request. Thank you for your time!"})
            return history, ""

        question_text = questions[current_question_index[0]]
        history_content = "\n".join([f"Q: {entry['question']}\nA: {entry['answer']}" for entry in conversation_history])
        combined_prompt = (f"{system_prompt}\n\nPrevious conversation history:\n{history_content}\n\n"
                           f"Current question: {question_text}\nUser's input: {user_input}\n\n"
                           "Respond in a warm and conversational way, offering natural follow-ups if needed.")

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=combined_prompt)
        ]

        response = chat.invoke(messages)
        response_content = response.content.strip()

        conversation_history.append({"question": question_text, "answer": user_input})
        interview_data.append({"question": question_text, "answer": user_input})
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": response_content})

        if current_question_index[0] + 1 < len(questions):
            current_question_index[0] += 1
            next_question = f"Alright, let's move on. {questions[current_question_index[0]]}"
            history.append({"role": "assistant", "content": next_question})
            return history, ""
        else:
            history.append({"role": "assistant", "content": "That wraps up our interview. Thank you so much for your responses—it's been great learning more about you!"})
            return history, ""

    return interview_step, initial_message

def launch_candidate_app():
    QUESTIONS_FILE_PATH = "questions.json"
    try:
        questions = read_questions_from_json(QUESTIONS_FILE_PATH)
        interview_func, initial_message = conduct_interview(questions)

        def start_interview_ui():
            history = [{"role": "assistant", "content": initial_message}]
            history.append({"role": "assistant", "content": "Let's begin! Here's your first question: " + questions[0]})
            return history, ""

        def clear_interview_ui():
            return [], ""

        def on_enter_submit_ui(history, user_response):
            if not user_response.strip():
                return history, ""
            history, _ = interview_func(user_response, history)
            return history, ""

        with gr.Blocks(title="AI HR Interview Assistant") as candidate_app:
            gr.Markdown("<h1 style='text-align: center;'>👋 Welcome to Your AI HR Interview Assistant</h1>")
            start_btn = gr.Button("Start Interview", variant="primary")
            chatbot = gr.Chatbot(label="Interview Chat", height=650, type="messages")
            user_input = gr.Textbox(label="Your Response", placeholder="Type your answer here...", lines=1)
            with gr.Row():
                submit_btn = gr.Button("Submit")
                clear_btn = gr.Button("Clear Chat")

            start_btn.click(start_interview_ui, inputs=[], outputs=[chatbot, user_input])
            submit_btn.click(on_enter_submit_ui, inputs=[chatbot, user_input], outputs=[chatbot, user_input])
            user_input.submit(on_enter_submit_ui, inputs=[chatbot, user_input], outputs=[chatbot, user_input])
            clear_btn.click(clear_interview_ui, inputs=[], outputs=[chatbot, user_input])

        return candidate_app

    except Exception as e:
        print(f"Error: {e}")
        return None

def create_manager_app():
    with gr.Blocks(title="AI HR Interviewer Manager") as manager_app:
        gr.HTML("<h1 style='text-align: center;'>AI HR Interviewer Manager</h1>")
        user_role = gr.Dropdown(choices=["Admin", "Candidate"], label="Select User Role", value="Candidate")
        proceed_button = gr.Button("👉 Proceed")

        candidate_ui = gr.Column(visible=False)
        admin_ui = gr.Column(visible=False)

        with candidate_ui:
            gr.Markdown("## 🚀 Candidate Interview")
            candidate_app = launch_candidate_app()

        with admin_ui:
            gr.Markdown("## 🔒 Admin Panel")
            gr.Markdown("Admin operations and question generation will go here.")

        def show_selected_ui(role):
            if role == "Candidate":
                return gr.update(visible=True), gr.update(visible=False)
            elif role == "Admin":
                return gr.update(visible=False), gr.update(visible=True)
            else:
                return gr.update(visible=False), gr.update(visible=False)

        proceed_button.click(show_selected_ui, inputs=[user_role], outputs=[candidate_ui, admin_ui])

    return manager_app

def cleanup():
    for audio_file in interview_state.temp_audio_files:
        if os.path.exists(audio_file):
            os.unlink(audio_file)

if __name__ == "__main__":
    manager_app = create_manager_app()
    try:
        manager_app.launch(server_name="0.0.0.0", server_port=7860, debug=True)
    finally:
        cleanup()
