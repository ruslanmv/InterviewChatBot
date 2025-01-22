import grad as gr
import tempfile
import os
from io import BytesIO

from ai_config import convert_text_to_speech, load_model
from knowledge_retrieval import (
    setup_knowledge_retrieval,
    get_next_response,
    generate_report,
    get_initial_question,
)
from prompt_instructions import (
    get_interview_initial_message_hr,
    get_interview_initial_message_sarah,
    get_interview_initial_message_aaron,
    get_default_hr_questions,
    get_interview_prompt_hr,
    get_interview_prompt_sarah_v3,
    get_interview_prompt_aaron,
)
from utils import save_interview_history, load_config, save_config


class InterviewState:
    def __init__(self):
        self.config = load_config()
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
        self.n_of_questions = self.config.get(
            "n_of_questions", 5
        )  # Load from config
        self.interview_type = self.config.get("interview_type", "hr")
        self.language = self.config.get("language", "english")

    def get_voice_setting(self):
        return self.selected_interviewer

    def set_num_questions(self, num_questions):
        """Sets the number of questions for the interview."""
        self.n_of_questions = num_questions

    def set_interview_type(self, interview_type):
        """Sets the type of interview."""
        self.interview_type = interview_type

    def set_language(self, language):
        """Sets the language of the interview."""
        self.language = language


interview_state = InterviewState()


def load_knowledge_base(file_input):
    if not file_input:
        print("[DEBUG] No file uploaded.")
        return (
            "❌ Error: No document uploaded. Please upload a document to update the knowledge base.",
            gr.update(value=None),
        )

    llm = load_model(os.getenv("OPENAI_API_KEY"))
    try:
        interview_chain, report_chain, retriever = setup_knowledge_retrieval(
            llm, language=interview_state.language, file_path=file_input
        )
        interview_state.interview_chain = interview_chain
        interview_state.report_chain = report_chain
        interview_state.knowledge_retrieval_setup = True
        print("[DEBUG] Knowledge base successfully set up.")
        return (
            "✅ Knowledge base successfully updated. You can now start the interview.",
            gr.update(value=None),
        )
    except Exception as e:
        print(f"[DEBUG] Error loading knowledge base: {e}")
        return (
            f"❌ Error loading knowledge base: {e}",
            gr.update(value=None),
        )


def reset_interview_action(voice):
    interview_state.reset(voice)
    print(f"[DEBUG] Interview reset. Voice: {voice}")

    # Select the initial message based on interview type
    if interview_state.interview_type == "hr":
        initial_message_content = get_interview_initial_message_hr(
            interview_state.n_of_questions
        )
    elif interview_state.interview_type == "sarah":
        initial_message_content = get_interview_initial_message_sarah(
            interview_state.n_of_questions
        )
    elif interview_state.interview_type == "aaron":
        initial_message_content = get_interview_initial_message_aaron(
            interview_state.n_of_questions
        )
    else:
        initial_message_content = "Invalid interview type selected."

    initial_message = {
        "role": "assistant",
        "content": initial_message_content,
    }

    if (
        not interview_state.knowledge_retrieval_setup
        and interview_state.interview_type == "hr"
    ):
        print(
            "[DEBUG] Knowledge base not set up. Defaulting to basic HR questions."
        )
        initial_message["content"] = get_interview_initial_message_hr(
            interview_state.n_of_questions
        )
        
    interview_state.interview_history = [initial_message]

    initial_audio_buffer = BytesIO()
    convert_text_to_speech(
        initial_message["content"], initial_audio_buffer, voice
    )
    initial_audio_buffer.seek(0)

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        temp_audio_path = temp_file.name
        temp_file.write(initial_audio_buffer.getvalue())

    interview_state.temp_audio_files.append(temp_audio_path)
    print(f"[DEBUG] Audio file saved at {temp_audio_path}")

    return (
        [initial_message],
        gr.Audio(value=temp_audio_path, autoplay=True, visible=True),
        gr.Textbox(interactive=True),
    )


def start_interview():
    print("[DEBUG] Start interview triggered.")
    return reset_interview_action(interview_state.selected_interviewer)


def create_app():
    with gr.Blocks(title="AI HR Interviewer") as demo:
        gr.Markdown(
            "## 🧑‍💼 AI HR Interviewer\nThis chatbot conducts HR interviews using uploaded documents as a knowledge base. Admins can upload files, set the number of interview questions, while candidates participate in the interview."
        )

        with gr.Row():
            user_role = gr.Dropdown(
                choices=["Admin", "Candidate"],
                label="Select User Role",
                value="Candidate",
            )
            password_input = gr.Textbox(
                label="Enter Admin Password", type="password", visible=False
            )
            login_button = gr.Button("Login", visible=False)
            password_status = gr.Markdown("", visible=False)

        admin_tab = gr.Tab("Admin Settings", visible=False)
        interview_tab = gr.Tab("Interview", visible=True)

        def show_admin_controls(role):
            if role == "Admin":
                return (
                    gr.update(visible=True),
                    gr.update(visible=True),
                    gr.update(visible=True),
                    gr.update(visible=False),
                )
            else:
                return (
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=True),
                )

        user_role.change(
            show_admin_controls,
            inputs=[user_role],
            outputs=[
                password_input,
                login_button,
                admin_tab,
                interview_tab,
            ],
        )

        def authenticate_admin(password):
            if (
                password == "password1"
            ):  # **Important: Change this to a secure authentication method**
                interview_state.admin_authenticated = True
                return (
                    "✅ Password correct",
                    gr.update(visible=False),
                    gr.update(visible=True),
                )
            else:
                return (
                    "❌ Incorrect password, please try again.",
                    gr.update(visible=True),
                    gr.update(visible=False),
                )

        login_button.click(
            authenticate_admin,
            inputs=[password_input],
            outputs=[password_status, password_input, admin_tab],
        )

        with admin_tab:
            gr.Markdown("### 📄 Upload Knowledge Base Document")
            file_input = gr.File(
                label="Upload a TXT, PDF, or DOCX file",
                type="filepath",
                file_types=[".txt", ".pdf", ".docx"],
            )
            update_button = gr.Button("Update Knowledge Base")
            update_status = gr.Markdown("")

            gr.Markdown("### ⚙️ Interview Settings")
            num_questions_input = gr.Number(
                label="Number of Interview Questions",
                value=interview_state.n_of_questions,
                precision=0,
                interactive=True,
            )

            interview_type_input = gr.Dropdown(
                choices=["hr", "sarah", "aaron"],
                label="Interview Type",
                value=interview_state.interview_type,
                interactive=True,
            )

            language_input = gr.Dropdown(
                choices=["english", "spanish", "french", "german"],
                label="Interview Language",
                value=interview_state.language,
                interactive=True,
            )

            def set_interview_settings(
                num_questions, interview_type, language
            ):
                """Updates the interview settings in the interview state and config file."""
                interview_state.set_num_questions(num_questions)
                interview_state.set_interview_type(interview_type)
                interview_state.set_language(language)

                # Update config file
                config = {
                    "n_of_questions": num_questions,
                    "interview_type": interview_type,
                    "language": language,
                }
                if save_config(config):
                    config_message = "✅ Interview settings updated and saved."
                else:
                    config_message = (
                        "❌ Error saving config. Interview settings updated in memory only."
                    )

                return (
                    f"✅ Number of questions set to {num_questions}",
                    f"✅ Interview type set to {interview_type}",
                    f"✅ Interview language set to {language}",
                    config_message,
                )

            set_questions_button = gr.Button("Save Interview Settings")
            questions_status = gr.Markdown("")
            interview_type_status = gr.Markdown("")
            language_status = gr.Markdown("")
            config_status = gr.Markdown("")

            set_questions_button.click(
                set_interview_settings,
                inputs=[
                    num_questions_input,
                    interview_type_input,
                    language_input,
                ],
                outputs=[
                    questions_status,
                    interview_type_status,
                    language_status,
                    config_status,
                ],
            )

            update_button.click(
                load_knowledge_base,
                inputs=[file_input],
                outputs=[update_status, file_input],
            )

        with interview_tab:
            gr.Markdown("### 📝 Interview Chat Session")
            reset_button = gr.Button("Start Interview")
            chatbot = gr.Chatbot(label="Chat Session", type="messages")
            msg_input = gr.Textbox(
                label="💬 Type your message here...",
                interactive=True,
                placeholder="Type your answer here...",
            )
            send_button = gr.Button("Send")
            audio_output = gr.Audio(label="🔊 Audio Output", visible=True)

            def user_input(user_message, history):
                history.append({"role": "user", "content": user_message})
                return "", history
###

            def bot_response(history):
                print(f"[DEBUG] bot_response called. History: {history}")
                if not interview_state.interview_history:
                    print("[DEBUG] Interview history is empty. Resetting.")
                    reset_interview_action(interview_state.selected_interviewer)

                if interview_state.interview_history[-1]["role"] == "user":
                    interview_state.question_count += 1

                print(f"[DEBUG] question_count: {interview_state.question_count}")
                print(f"[DEBUG] n_of_questions: {interview_state.n_of_questions}")

                voice = interview_state.get_voice_setting()

                if interview_state.question_count > interview_state.n_of_questions:
                    response = "That's all for now. Thank you for your time!"
                    interview_state.interview_finished = True

                else:
                    # Select prompts based on interview type
                    if interview_state.interview_type == "hr":
                        if not interview_state.knowledge_retrieval_setup:
                            response = get_default_hr_questions(
                                interview_state.question_count
                            )
                        else:
                            if interview_state.question_count == 1:
                                response = get_initial_question(
                                    interview_state.interview_chain
                                )
                            else:
                                response = get_next_response(
                                    interview_state.interview_chain,
                                    interview_state.interview_history[-1]["content"] if interview_state.interview_history[-1]["role"] == "user" else "",
                                    [
                                        msg["content"]
                                        for msg in interview_state.interview_history
                                        if msg.get("role") == "user"
                                    ],
                                    interview_state.question_count,
                                )
                    elif interview_state.interview_type == "sarah":
                        response = get_next_response(
                            interview_state.interview_chain,
                            interview_state.interview_history[-1]["content"] if interview_state.interview_history[-1]["role"] == "user" else "",
                            [
                                msg["content"]
                                for msg in interview_state.interview_history
                                if msg.get("role") == "user"
                            ],
                            interview_state.question_count,
                        )
                    elif interview_state.interview_type == "aaron":
                        response = get_next_response(
                            interview_state.interview_chain,
                            interview_state.interview_history[-1]["content"] if interview_state.interview_history[-1]["role"] == "user" else "",
                            [
                                msg["content"]
                                for msg in interview_state.interview_history
                                if msg.get("role") == "user"
                            ],
                            interview_state.question_count,
                        )

                    else:
                        response = "Invalid interview type."

                audio_buffer = BytesIO()
                convert_text_to_speech(response, audio_buffer, voice)
                audio_buffer.seek(0)
                with tempfile.NamedTemporaryFile(
                    suffix=".mp3", delete=False
                ) as temp_file:
                    temp_audio_path = temp_file.name
                    temp_file.write(audio_buffer.getvalue())
                interview_state.temp_audio_files.append(temp_audio_path)

                history.append({"role": "assistant", "content": response})
                interview_state.interview_history.append({"role": "assistant", "content": response})

                if interview_state.interview_finished:
                    conclusion_message = "Thank you for being here. We will review your responses and provide feedback soon."
                    history.append(
                        {"role": "system", "content": conclusion_message}
                    )
                    interview_state.interview_history.append({"role": "system", "content": conclusion_message})

                    txt_path = save_interview_history(
                        [msg["content"] for msg in history if msg["role"] != "system"], interview_state.language
                    )
                    if txt_path:
                        return (
                            history,
                            gr.Audio(
                                value=temp_audio_path,
                                autoplay=True,
                                visible=True,
                            ),
                            gr.File(visible=True, value=txt_path),
                            gr.Textbox(interactive=False)
                        )
                    else:
                        return (
                            history,
                            gr.Audio(
                                value=temp_audio_path,
                                autoplay=True,
                                visible=True,
                            ),
                            None,
                            gr.Textbox(interactive=False)
                        )

                return (
                    history,
                    gr.Audio(
                        value=temp_audio_path, autoplay=True, visible=True
                    ),
                    None,
                    gr.Textbox(interactive=True)
                )

###
            reset_button.click(
                start_interview,
                inputs=[],
                outputs=[chatbot, audio_output, msg_input],
            )

            msg_input.submit(
                user_input,
                [msg_input, chatbot],
                [msg_input, chatbot],
                queue=False,
            ).then(
                bot_response,
                [chatbot],
                [chatbot, audio_output, gr.File(), msg_input],
            )

            send_button.click(
                user_input,
                [msg_input, chatbot],
                [msg_input, chatbot],
                queue=False,
            ).then(
                bot_response,
                [chatbot],
                [chatbot, audio_output, gr.File(), msg_input],
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