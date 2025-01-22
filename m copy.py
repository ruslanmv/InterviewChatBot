import gradio as gr
import tempfile
import os
from io import BytesIO
from collections import deque
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

# Placeholder imports for the manager application
from ai_config import convert_text_to_speech, load_model  # Placeholder, needs implementation
from knowledge_retrieval import generate_report, get_initial_question, get_next_response  # Placeholder, needs implementation
from prompt_instructions import get_interview_initial_message_hr  # Placeholder, needs implementation
from utils import save_interview_history  # Placeholder, needs implementation
from settings import language  # Placeholder, needs implementation


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
        self.document_loaded = False
        self.knowledge_retrieval_setup = False
        self.interview_chain = None
        self.report_chain = None
        self.current_questions = []


interview_state = InterviewState()


def reset_interview_action(voice):
    interview_state.reset(voice)
    n_of_questions = 5  # Default number of questions

    initial_text_message = (
        "👋 Hi there, I'm Sarah, your friendly AI HR assistant! "
        "I'll guide you through a series of interview questions to learn more about you. "
        "Take your time and answer each question thoughtfully."
    )

    print(f"[DEBUG] Interview reset. Voice: {voice}")

    # Convert the initial message to speech
    initial_audio_buffer = BytesIO()
    convert_text_to_speech(initial_text_message, initial_audio_buffer, voice)
    initial_audio_buffer.seek(0)

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        temp_audio_path = temp_file.name
        temp_file.write(initial_audio_buffer.getvalue())

    interview_state.temp_audio_files.append(temp_audio_path)

    return (
        [{"role": "assistant", "content": initial_text_message}],
        gr.Audio(value=temp_audio_path, autoplay=True),
        gr.Textbox(interactive=True),
    )


def start_interview():
    return reset_interview_action(interview_state.selected_interviewer)


def on_enter_submit_ui(history, user_response):
    if not user_response.strip():
        return history, None, ""  # Return placeholder values when input is empty

    # Simulate bot response
    bot_message = f"Thank you for your answer: {user_response}. Here’s the next question."
    voice = interview_state.get_voice_setting()

    # Generate and save audio response
    audio_buffer = BytesIO()
    convert_text_to_speech(bot_message, audio_buffer, voice)
    audio_buffer.seek(0)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        temp_audio_path = temp_file.name
        temp_file.write(audio_buffer.getvalue())

    interview_state.temp_audio_files.append(temp_audio_path)
    history.append({"role": "user", "content": user_response})
    history.append({"role": "assistant", "content": bot_message})

    return history, gr.Audio(value=temp_audio_path, autoplay=True), ""


def launch_candidate_app():
    with gr.Blocks(title="AI HR Interview Assistant") as candidate_app:
        gr.Markdown("<h1 style='text-align: center;'>👋 Welcome to Your AI HR Interview Assistant</h1>")
        start_btn = gr.Button("Start Interview", variant="primary")
        chatbot = gr.Chatbot(label="Interview Chat", height=650, type="messages")
        user_input = gr.Textbox(label="Your Response", placeholder="Type your answer here...", lines=1)
        audio_output = gr.Audio(autoplay=True)

        with gr.Row():
            submit_btn = gr.Button("Submit")
            clear_btn = gr.Button("Clear Chat")

        # Set up the button events
        start_btn.click(start_interview, inputs=[], outputs=[chatbot, audio_output])
        submit_btn.click(on_enter_submit_ui, inputs=[chatbot, user_input], outputs=[chatbot, audio_output, user_input])
        user_input.submit(on_enter_submit_ui, inputs=[chatbot, user_input], outputs=[chatbot, audio_output, user_input])
        clear_btn.click(lambda: ([], ""), inputs=[], outputs=[chatbot, user_input])

    return candidate_app


def create_manager_app():
    with gr.Blocks(title="AI HR Interviewer Manager") as manager_app:
        gr.HTML("<h1 style='text-align: center;'>AI HR Interviewer Manager</h1>")
        user_role = gr.Dropdown(choices=["Admin", "Candidate"], label="Select User Role", value="Candidate")
        proceed_button = gr.Button("👉 Proceed")
        candidate_ui = launch_candidate_app()
        candidate_ui.visible = False

        def show_selected_ui(role):
            if role == "Candidate":
                return gr.update(visible=True)
            return gr.update(visible=False)

        proceed_button.click(show_selected_ui, inputs=[user_role], outputs=[candidate_ui])

    return manager_app


if __name__ == "__main__":
    manager_app = create_manager_app()
    manager_app.launch(server_name="0.0.0.0", server_port=7860, share=True)
