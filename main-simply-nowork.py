import gradio as gr
import tempfile
import os
import json
from io import BytesIO

# Imports from other modules
from generatorgr import (
    generate_and_save_questions as generate_questions_manager,
    update_max_questions,
)
from generator import (
    PROFESSIONS_FILE,
    TYPES_FILE,
    OUTPUT_FILE,
    load_json_data,
    generate_questions,
)
from gptgr import (
    read_questions_from_json,
    conduct_interview,
)
from splitgpt import (
    generate_and_save_questions_from_pdf,
)

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

def launch_candidate_app():
    QUESTIONS_FILE_PATH = "questions.json"
    try:
        questions = read_questions_from_json(QUESTIONS_FILE_PATH)
        interview_func, initial_message = conduct_interview(questions)

        def start_interview_ui():
            history = [{"role": "assistant", "content": initial_message}]
            history.append(
                {"role": "assistant", "content": "Let's begin! Here's your first question: " + questions[0]}
            )
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
            # Pass the function reference instead of rendering it directly
            candidate_app = launch_candidate_app()

        with admin_ui:
            gr.Markdown("## 🔒 Admin Panel")
            gr.Markdown("Admin operations and question generation will go here.")

        # Function to update the visibility of UI components
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
