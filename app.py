import grad as gr
import tempfile
import os
import json
from io import BytesIO
from gpt import read_questions_from_json, conduct_interview_with_user_input  # Import from gpt.py
from ai_config import convert_text_to_speech, load_model
from knowledge_retrieval import setup_knowledge_retrieval, generate_report
from prompt_instructions import get_interview_initial_message_hr, get_default_hr_questions
from settings import language
from utils import save_interview_history
from questions import generate_and_save_questions_from_pdf

CONFIG_PATH = "config.json"
QUESTIONS_PATH = "questions.json"

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
        self.admin_authenticated = False
        self.config = load_config()
        self.technical_questions = []

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    else:
        return {"n_of_questions": 5, "type_of_interview": "Standard"}

def save_config(config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)

def save_questions(questions):
    with open(QUESTIONS_PATH, "w") as f:
        json.dump(questions, f, indent=4)

def load_questions():
    if os.path.exists(QUESTIONS_PATH):
        with open(QUESTIONS_PATH, "r") as f:
            return json.load(f)
    return []

interview_state = InterviewState()

# Load knowledge base and generate technical questions
def load_knowledge_base(file_input, n_questions_to_generate):
    if not file_input:
        return "❌ Error: No document uploaded."

    llm = load_model(os.getenv("OPENAI_API_KEY"))
    try:
        _, _, retriever = setup_knowledge_retrieval(llm, language=language, file_path=file_input)
        technical_questions = generate_and_save_questions_from_pdf(file_input, n_questions_to_generate)
        save_questions(technical_questions)

        return f"✅ {len(technical_questions)} technical questions generated and saved."
    except Exception as e:
        return f"❌ Error: {e}"

def reset_interview_action(voice):
    interview_state.reset(voice)
    config = interview_state.config
    n_of_questions = config.get("n_of_questions", 5)
    initial_message = {
        "role": "assistant",
        "content": get_interview_initial_message_hr(n_of_questions)
    }

    if config["type_of_interview"] == "Technical":
        technical_questions = load_questions()

        if not technical_questions:
            return [{"role": "assistant", "content": "No technical questions available. Please contact the admin."}], None, gr.Textbox(interactive=False)

        # Prepare for displaying questions one at a time
        interview_state.technical_questions = technical_questions
        interview_state.question_count = 0
        return (
            [initial_message],
            None,
            gr.Textbox(interactive=True, placeholder="Technical interview started. Answer the questions below...")
        )
    else:
        initial_audio_buffer = BytesIO()
        convert_text_to_speech(initial_message["content"], initial_audio_buffer, voice)
        initial_audio_buffer.seek(0)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_audio_path = temp_file.name
            temp_file.write(initial_audio_buffer.getvalue())

        interview_state.temp_audio_files.append(temp_audio_path)
        return (
            [initial_message],
            gr.Audio(value=temp_audio_path, autoplay=True),
            gr.Textbox(interactive=True, placeholder="Type your answer here...")
        )

def start_interview():
    interview_config = load_config()
    interview_state.config = interview_config
    return reset_interview_action(interview_state.selected_interviewer)

def update_config(n_of_questions, interview_type):
    config = {
        "n_of_questions": int(n_of_questions),
        "type_of_interview": interview_type
    }
    save_config(config)
    return "✅ Configuration updated successfully."

def update_knowledge_base_and_generate_questions(file_input, n_questions_to_generate):
    return load_knowledge_base(file_input, n_questions_to_generate)

def bot_response(chatbot, message):
    config = interview_state.config

    if config["type_of_interview"] == "Standard":
        response = get_default_hr_questions(interview_state.question_count + 1)
        chatbot.append({"role": "assistant", "content": response})
        interview_state.question_count += 1
    else:
        if interview_state.question_count < len(interview_state.technical_questions):
            question = interview_state.technical_questions[interview_state.question_count]
            chatbot.append({"role": "assistant", "content": f"Q{interview_state.question_count + 1}: {question}"})
            interview_state.question_count += 1
            chatbot.append({"role": "user", "content": message})  # Append user response after the question
        else:
            chatbot.append({"role": "assistant", "content": "All questions completed."})
            interview_state.interview_finished = True

    if interview_state.interview_finished:
        report_content = generate_report(interview_state.report_chain, [msg["content"] for msg in chatbot if msg["role"] == "user"], language)
        txt_path = save_interview_history([msg["content"] for msg in chatbot], language)
        return chatbot, gr.File(visible=True, value=txt_path)

    return chatbot, None

def create_app():
    with gr.Blocks(title="AI HR Interviewer") as demo:
        gr.Markdown("## 🧑‍💼 HR Interviewer Application")

        with gr.Row():
            user_role = gr.Dropdown(choices=["Admin", "Candidate"], label="Select User Role", value="Candidate")
            password_input = gr.Textbox(label="Enter Admin Password", type="password", visible=False)
            login_button = gr.Button("Login", visible=False)
            password_status = gr.Markdown("", visible=False)

        admin_tab = gr.Tab("Admin Settings", visible=False)
        interview_tab = gr.Tab("Interview", visible=True)

        user_role.change(lambda role: (gr.update(visible=role == "Admin"),) * 2, inputs=[user_role], outputs=[password_input, login_button])

        def authenticate_admin(password):
            if password == "password1":
                interview_state.admin_authenticated = True
                return "✅ Password correct", gr.update(visible=False), gr.update(visible=True)
            else:
                return "❌ Incorrect password.", gr.update(visible=True), gr.update(visible=False)

        login_button.click(authenticate_admin, inputs=[password_input], outputs=[password_status, password_input, admin_tab])

        with admin_tab:
            file_input = gr.File(label="Upload Knowledge Base Document", type="filepath")
            n_questions_input = gr.Number(label="Number of Questions", value=10)
            update_button = gr.Button("Update Knowledge Base")
            update_status = gr.Markdown("")
            update_button.click(update_knowledge_base_and_generate_questions, inputs=[file_input, n_questions_input], outputs=[update_status])

            n_questions_interview_input = gr.Number(label="Number of Questions for Interview", value=5)
            interview_type_input = gr.Dropdown(choices=["Standard", "Technical"], label="Type of Interview", value="Standard")
            save_config_button = gr.Button("Save Configuration")
            config_status = gr.Markdown("")
            save_config_button.click(update_config, inputs=[n_questions_interview_input, interview_type_input], outputs=[config_status])

        with interview_tab:
            reset_button = gr.Button("Start Interview")
            chatbot = gr.Chatbot(label="Chat Session", type="messages")
            msg_input = gr.Textbox(label="💬 Type your message here...", interactive=True)
            send_button = gr.Button("Send")

            reset_button.click(start_interview, inputs=[], outputs=[chatbot])

            msg_input.submit(lambda msg, hist: ("", hist + [{"role": "user", "content": msg}]), inputs=[msg_input, chatbot], outputs=[msg_input, chatbot]).then(
                bot_response, [chatbot, msg_input], [chatbot]
            )

            send_button.click(lambda msg, hist: ("", hist + [{"role": "user", "content": msg}]), inputs=[msg_input, chatbot], outputs=[msg_input, chatbot]).then(
                bot_response, [chatbot, msg_input], [chatbot]
            )

    return demo

def cleanup():
    for audio_file in interview_state.temp_audio_files:
        if os.path.exists(audio_file):
            os.unlink(audio_file)

if __name__ == "__main__":
    app = create_app()
    try:
        app.launch(server_name="0.0.0.0", server_port=7860, debug=True)
    finally:
        cleanup()
