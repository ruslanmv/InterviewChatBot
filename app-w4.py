import grad as gr
import tempfile
import os
import json
from io import BytesIO

from ai_config import convert_text_to_speech, load_model
from knowledge_retrieval import setup_knowledge_retrieval, get_next_response, generate_report, get_initial_question
from prompt_instructions import get_interview_initial_message_hr, get_default_hr_questions, get_interview_prompt_technical  # Import the new function
from settings import language
from utils import save_interview_history
from questions import generate_and_save_questions_from_pdf  # Import the function to generate questions from PDF

CONFIG_PATH = "config.json"
QUESTIONS_PATH = "questions.json"

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    else:
        return {"n_of_questions": 5, "type_of_interview": "Standard"}  # Default settings

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
    else:
        return []

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
        self.config = load_config()
        self.technical_questions = []

    def get_voice_setting(self):
        return self.selected_interviewer

interview_state = InterviewState()

def load_knowledge_base(file_input, n_questions_to_generate):
    if not file_input:
        print("[DEBUG] No file uploaded.")
        return "❌ Error: No document uploaded. Please upload a document to update the knowledge base."

    llm = load_model(os.getenv("OPENAI_API_KEY"))
    try:
        interview_chain, report_chain, retriever = setup_knowledge_retrieval(
            llm,
            language=language,
            file_path=file_input
        )
        interview_state.interview_chain = interview_chain
        interview_state.report_chain = report_chain
        interview_state.knowledge_retrieval_setup = True
        print("[DEBUG] Knowledge base successfully set up.")

        # Generate questions from the knowledge base PDF
        technical_questions = generate_and_save_questions_from_pdf(file_input, total_questions=n_questions_to_generate)
        save_questions(technical_questions)  # Save generated questions to questions.json
        print(f"[INFO] Generated {len(technical_questions)} questions.")

        return "✅ Knowledge base successfully updated and questions generated. You can now start the interview."
    except Exception as e:
        print(f"[DEBUG] Error loading knowledge base: {e}")
        return f"❌ Error loading knowledge base: {e}"

def reset_interview_action(voice):
    interview_state.reset(voice)
    config = interview_state.config
    n_of_questions = config.get("n_of_questions", 5)
    print(f"[DEBUG] Interview reset. Voice: {voice}")

    initial_message = {
        "role": "assistant",
        "content": get_interview_initial_message_hr(n_of_questions)
    }

    initial_audio_buffer = BytesIO()
    convert_text_to_speech(initial_message["content"], initial_audio_buffer, voice)
    initial_audio_buffer.seek(0)

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        temp_audio_path = temp_file.name
        temp_file.write(initial_audio_buffer.getvalue())

    interview_state.temp_audio_files.append(temp_audio_path)
    print(f"[DEBUG] Audio file saved at {temp_audio_path}")

    if config["type_of_interview"] == "Technical":
        interview_state.technical_questions = load_questions()

    return (
        [initial_message],
        gr.Audio(value=temp_audio_path, autoplay=True),
        gr.Textbox(interactive=True)
    )

def start_interview():
    interview_config = load_config()
    print(f"[DEBUG] Start interview triggered with config: {interview_config}")
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
    n_of_questions = config.get("n_of_questions", 5)
    interview_state.question_count += 1
    voice = interview_state.get_voice_setting()

    if config["type_of_interview"] == "Standard" or not interview_state.knowledge_retrieval_setup:
        response = get_default_hr_questions(interview_state.question_count)
    else:
        if interview_state.technical_questions:
            question = interview_state.technical_questions[interview_state.question_count - 1]
            response = get_interview_prompt_technical(language, n_of_questions, question)
        else:
            response = "No technical questions available. Please contact the admin."

    audio_buffer = BytesIO()
    convert_text_to_speech(response, audio_buffer, voice)
    audio_buffer.seek(0)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        temp_audio_path = temp_file.name
        temp_file.write(audio_buffer.getvalue())

    interview_state.temp_audio_files.append(temp_audio_path)
    chatbot.append({"role": "assistant", "content": response})

    if interview_state.question_count >= n_of_questions:
        interview_state.interview_finished = True
        conclusion_message = "Thank you for your time. The interview is complete. Please review your report."  
        chatbot.append({"role": "system", "content": conclusion_message})
        report_content = generate_report(interview_state.report_chain, [msg["content"] for msg in chatbot], language)
        txt_path = save_interview_history([msg["content"] for msg in chatbot], language)
        return chatbot, gr.File(visible=True, value=txt_path)

    return chatbot, gr.Audio(value=temp_audio_path, autoplay=True)

def create_app():
    with gr.Blocks(title="AI HR Interviewer") as demo:
        gr.Markdown("## 🧑‍💼 HR Interviewer This chatbot conducts HR interviews using uploaded documents as a knowledge base. Admins can upload files to update the knowledge base and set configurations, while candidates participate in the interview.")

        with gr.Row():
            user_role = gr.Dropdown(choices=["Admin", "Candidate"], label="Select User Role", value="Candidate")
            password_input = gr.Textbox(label="Enter Admin Password", type="password", visible=False)
            login_button = gr.Button("Login", visible=False)
            password_status = gr.Markdown("", visible=False)

        admin_tab = gr.Tab("Admin Settings", visible=False)
        interview_tab = gr.Tab("Interview", visible=True)

        def show_admin_controls(role):
            if role == "Admin":
                return gr.update(visible=True), gr.update(visible=True), gr.update(visible=True), gr.update(visible=True)
            else:
                return gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=True)

        user_role.change(show_admin_controls, inputs=[user_role], outputs=[password_input, login_button, admin_tab, interview_tab])

        def authenticate_admin(password):
            if password == "password1":
                interview_state.admin_authenticated = True
                return "✅ Password correct", gr.update(visible=False), gr.update(visible=True)
            else:
                return "❌ Incorrect password, please try again.", gr.update(visible=True), gr.update(visible=False)

        login_button.click(authenticate_admin, inputs=[password_input], outputs=[password_status, password_input, admin_tab])

        with admin_tab:
            gr.Markdown("### 📄 Upload Knowledge Base Document")
            file_input = gr.File(label="Upload a TXT, PDF, or DOCX file", type="filepath")
            n_questions_input = gr.Number(label="Number of Questions to Generate", value=10)
            update_button = gr.Button("Update Knowledge Base and Generate Questions")
            update_status = gr.Markdown("")
            update_button.click(update_knowledge_base_and_generate_questions, inputs=[file_input, n_questions_input], outputs=[update_status])

            gr.Markdown("### 🔧 Configure Interview Settings")
            n_questions_interview_input = gr.Number(label="Number of Questions for Interview", value=5)
            interview_type_input = gr.Dropdown(choices=["Standard", "Technical"], label="Type of Interview", value="Standard")
            save_config_button = gr.Button("Save Configuration")
            config_status = gr.Markdown("")
            save_config_button.click(update_config, inputs=[n_questions_interview_input, interview_type_input], outputs=[config_status])

        with interview_tab:
            gr.Markdown("### 📝 Interview Chat Session")
            reset_button = gr.Button("Start Interview")
            chatbot = gr.Chatbot(label="Chat Session", type="messages")
            msg_input = gr.Textbox(label="💬 Type your message here...", interactive=True, placeholder="Type your answer here...")
            send_button = gr.Button("Send")
            audio_output = gr.Audio(label="🔊 Audio Output", visible=False)

            reset_button.click(
                start_interview,
                inputs=[],
                outputs=[chatbot, audio_output, msg_input]
            )

            def user_input(user_message, history):
                history.append({"role": "user", "content": user_message})
                return "", history

            msg_input.submit(user_input, [msg_input, chatbot], [msg_input, chatbot], queue=False).then(
                bot_response, [chatbot, msg_input], [chatbot, audio_output]
            )
            send_button.click(user_input, [msg_input, chatbot], [msg_input, chatbot], queue=False).then(
                bot_response, [chatbot, msg_input], [chatbot, audio_output]
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
