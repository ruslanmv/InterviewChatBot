import grad as gr
import tempfile
import os
from io import BytesIO

from ai_config import convert_text_to_speech, load_model
from knowledge_retrieval import setup_knowledge_retrieval, get_next_response, generate_report, get_initial_question
from prompt_instructions import get_interview_initial_message_hr
from settings import language, n_of_questions
from utils import save_interview_history

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

def load_knowledge_base(file_input):
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
        return "✅ Knowledge base successfully updated. You can now start the interview."
    except Exception as e:
        print(f"[DEBUG] Error loading knowledge base: {e}")
        return f"❌ Error loading knowledge base: {e}"

def reset_interview_action(voice):
    interview_state.reset(voice)
    print(f"[DEBUG] Interview reset. Voice: {voice}")

    if not interview_state.knowledge_retrieval_setup:
        print("[DEBUG] Knowledge retrieval setup not completed.")
        return ("❌ Error: Knowledge base not set up. Please contact an admin to update the knowledge base.", 
                [], gr.Textbox(interactive=False))

    initial_message = {
        "role": "assistant",
        "content": "Hello, I am your HR interview assistant. Let's begin by introducing the purpose of this interview."
    }
    print(f"[DEBUG] Initial assistant message: {initial_message['content']}")

    initial_audio_buffer = BytesIO()
    convert_text_to_speech(initial_message["content"], initial_audio_buffer, voice)
    initial_audio_buffer.seek(0)

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        temp_audio_path = temp_file.name
        temp_file.write(initial_audio_buffer.getvalue())

    interview_state.temp_audio_files.append(temp_audio_path)
    print(f"[DEBUG] Audio file saved at {temp_audio_path}")

    return (
        [initial_message],
        gr.Audio(value=temp_audio_path, autoplay=True),
        gr.Textbox(interactive=True)
    )

def start_interview():
    print("[DEBUG] Start interview triggered.")
    return reset_interview_action(interview_state.selected_interviewer)

def create_app():
    with gr.Blocks(title="AI HR Interviewer") as demo:
        gr.Markdown("## 🧑‍💼 HR Interviewer\nThis chatbot conducts HR interviews using uploaded documents as a knowledge base. Admins can upload files to update the knowledge base, while candidates participate in the interview.")

        with gr.Row():
            user_role = gr.Dropdown(choices=["Admin", "Candidate"], label="Select User Role", value="Candidate")
            password_input = gr.Textbox(label="Enter Admin Password", type="password", visible=False)
            login_button = gr.Button("Login", visible=False)
            password_status = gr.Markdown("", visible=False)

        admin_tab = gr.Tab("Knowledge Base Update", visible=False)
        interview_tab = gr.Tab("Interview", visible=True)

        def show_admin_controls(role):
            print(f"[DEBUG] User role selected: {role}")
            if role == "Admin":
                return gr.update(visible=True), gr.update(visible=True), gr.update(visible=True), gr.update(visible=True)
            else:
                return gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=True)

        user_role.change(show_admin_controls, inputs=[user_role], outputs=[password_input, login_button, admin_tab, interview_tab])

        def authenticate_admin(password):
            if password == "password1":
                interview_state.admin_authenticated = True
                print("[DEBUG] Admin authenticated.")
                return "✅ Password correct", gr.update(visible=False), gr.update(visible=True)
            else:
                print("[DEBUG] Incorrect admin password.")
                return "❌ Incorrect password, please try again.", gr.update(visible=True), gr.update(visible=False)

        login_button.click(authenticate_admin, inputs=[password_input], outputs=[password_status, password_input, admin_tab])

        with admin_tab:
            gr.Markdown("### 📄 Upload Knowledge Base Document")
            file_input = gr.File(label="Upload a TXT, PDF, or DOCX file", type="filepath")
            update_button = gr.Button("Update Knowledge Base")
            update_status = gr.Markdown("")
            update_button.click(load_knowledge_base, inputs=[file_input], outputs=[update_status])

        with interview_tab:
            gr.Markdown("### 📝 Interview Chat Session")
            reset_button = gr.Button("Start Interview")
            chatbot = gr.Chatbot(label="Chat Session", type="messages")
            msg_input = gr.Textbox(label="💬 Type your message here...", interactive=True, placeholder="Type your answer here...")
            send_button = gr.Button("Send")
            audio_output = gr.Audio(label="🔊 Audio Output", visible=False)

            def user_input(user_message, history):
                print(f"[DEBUG] User message received: {user_message}")
                if interview_state.interview_finished:
                    print("[DEBUG] Interview finished. No more input accepted.")
                    return "", history
                history.append({"role": "user", "content": user_message})
                return "", history

            def bot_response(chatbot, message):
                if not interview_state.knowledge_retrieval_setup:
                    print("[DEBUG] Knowledge retrieval setup not completed.")
                    chatbot.append({"role": "system", "content": "Please contact an admin to update the knowledge base."})
                    return chatbot, None

                interview_state.question_count += 1
                voice = interview_state.get_voice_setting()
                print(f"[DEBUG] Generating response. Question count: {interview_state.question_count}")

                if interview_state.question_count == 1:
                    response = get_initial_question(interview_state.interview_chain)
                else:
                    response = get_next_response(
                        interview_state.interview_chain,
                        message["content"],
                        [msg["content"] for msg in chatbot if msg.get("role") == "user"],
                        interview_state.question_count
                    )

                if not isinstance(response, str):
                    print(f"[ERROR] Response is not a string: {response}")
                    response = "Sorry, I couldn't understand the response. Please try again."

                print(f"[DEBUG] Assistant response: {response}")

                audio_buffer = BytesIO()
                convert_text_to_speech(response, audio_buffer, voice)
                audio_buffer.seek(0)
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                    temp_audio_path = temp_file.name
                    temp_file.write(audio_buffer.getvalue())

                interview_state.temp_audio_files.append(temp_audio_path)
                chatbot.append({"role": "assistant", "content": response})

                if interview_state.question_count >= n_of_questions():
                    interview_state.interview_finished = True
                    conclusion_message = "Thank you for participating. I will now prepare a report."
                    print("[DEBUG] End of interview reached.")
                    chatbot.append({"role": "system", "content": conclusion_message})
                    report_content = generate_report(interview_state.report_chain, [msg["content"] for msg in chatbot], language)
                    txt_path = save_interview_history([msg["content"] for msg in chatbot], language)
                    return chatbot, gr.File(visible=True, value=txt_path)

                return chatbot, gr.Audio(value=temp_audio_path, autoplay=True)

            reset_button.click(
                start_interview,
                inputs=[],
                outputs=[chatbot, audio_output, msg_input]
            )

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
            print(f"[DEBUG] Deleting temp audio file: {audio_file}")
            os.unlink(audio_file)

if __name__ == "__main__":
    app = create_app()
    try:
        app.launch(server_name="0.0.0.0", server_port=7860, debug=True)
    finally:
        cleanup()
