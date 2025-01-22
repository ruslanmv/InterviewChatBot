import gradio as gr
import tempfile
import os
import json
from io import BytesIO
import subprocess
from collections import deque
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

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
from splitgpt import (
    generate_and_save_questions_from_pdf3
)

# Placeholder imports for the manager application
# Ensure these modules and functions are correctly implemented in their respective files
from ai_config import convert_text_to_speech, load_model  # Placeholder, needs implementation
from knowledge_retrieval import (
    setup_knowledge_retrieval,
    get_next_response,
    generate_report,
    get_initial_question,
)  # Placeholder, needs implementation
from prompt_instructions import (
    get_interview_initial_message_hr,
    get_default_hr_questions,
)  # Placeholder, needs implementation
from settings import language  # Placeholder, needs implementation
from utils import save_interview_history  # Placeholder, needs implementation


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
        self.current_questions = [] # Store the current set of questions

    def get_voice_setting(self):
        return self.selected_interviewer


interview_state = InterviewState()


def reset_interview_action(voice):
    interview_state.reset(voice)
    n_of_questions = 5  # Default questions
    print(f"[DEBUG] Interview reset. Voice: {voice}")

    initial_message = {
        "role": "assistant",
        "content": get_interview_initial_message_hr(n_of_questions),
    }

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
        gr.Textbox(interactive=True),
    )


def start_interview():

    return reset_interview_action(interview_state.selected_interviewer)


def bot_response(chatbot, message):
    n_of_questions = 5  # Default value
    interview_state.question_count += 1
    voice = interview_state.get_voice_setting()

    if interview_state.question_count == 1:
        response = get_initial_question(interview_state.interview_chain)
    else:
        response = get_next_response(
            interview_state.interview_chain,
            message["content"],
            [msg["content"] for msg in chatbot if msg.get("role") == "user"],
            interview_state.question_count,
        )

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
        conclusion_message = (
            "Thank you for your time. The interview is complete. Please review your report."
        )

        # Generate audio for conclusion message
        conclusion_audio_buffer = BytesIO()
        convert_text_to_speech(conclusion_message, conclusion_audio_buffer, voice)
        conclusion_audio_buffer.seek(0)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_conclusion_file:
            temp_conclusion_audio_path = temp_conclusion_file.name
            temp_conclusion_file.write(conclusion_audio_buffer.getvalue())
        interview_state.temp_audio_files.append(temp_conclusion_audio_path)

        chatbot.append({"role": "system", "content": conclusion_message})
        report_content = generate_report(
            interview_state.report_chain,
            [msg["content"] for msg in chatbot],
            language,
        )
        txt_path = save_interview_history(
            [msg["content"] for msg in chatbot], language
        )
        return chatbot, gr.File(visible=True, value=txt_path), gr.Audio(value=temp_conclusion_audio_path, autoplay=True)

    return chatbot, gr.Audio(value=temp_audio_path, autoplay=True)


# --- Candidate Interview Implementation ---
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

    def start_interview_ui():
        # Reload questions every time the interview starts
        interview_state.current_questions = read_questions_from_json(QUESTIONS_FILE_PATH)
        interview_func, initial_message = conduct_interview(interview_state.current_questions)
        interview_state.interview_func = interview_func

        history = [{"role": "assistant", "content": initial_message}]
        history.append({"role": "assistant", "content": "Let's begin! Here's your first question: " + interview_state.current_questions[0]})
        return history, ""

    def clear_interview_ui():
        # Reset state when clearing the interview
        interview_state.reset()
        return [], ""

    def on_enter_submit_ui(history, user_response):
        if not user_response.strip():
            return history, ""
        history, _ = interview_state.interview_func(user_response, history)
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


def create_manager_app():
    with gr.Blocks(
        title="AI HR Interviewer Manager",
        css="""
        .tab-button {
            background-color: #f0f0f0;
            color: #333;
            padding: 10px 20px;
            border: none;
            cursor: pointer;
            font-size: 16px;
            transition: background-color 0.3s ease;
        }
        .tab-button:hover {
            background-color: #d0d0d0;
        }
        .tab-button.selected {
            background-color: #666;
            color: white;
        }
    """,
    ) as manager_app:
        gr.HTML(
            """
            <div style='text-align: center; margin-bottom: 20px;'>
                <h1 style='font-size: 36px; color: #333;'>AI HR Interviewer Manager</h1>
                <p style='font-size: 18px; color: #666;'>Select your role to start the interview process.</p>
            </div>
        """
        )

        with gr.Row():
            user_role = gr.Dropdown(
                choices=["Admin", "Candidate"],
                label="Select User Role",
                value="Candidate",
            )
            proceed_button = gr.Button("👉 Proceed")

        candidate_ui = gr.Column(visible=False)
        admin_ui = gr.Column(visible=False)

        with candidate_ui:
            gr.Markdown("## 🚀 Candidate Interview")
            candidate_app = launch_candidate_app()

        with admin_ui:
            gr.Markdown("## 🔒 Admin Panel")
            with gr.Tab("Generate Questions"):
                try:
                    professions_data = load_json_data(PROFESSIONS_FILE)
                    types_data = load_json_data(TYPES_FILE)
                except (FileNotFoundError, json.JSONDecodeError) as e:
                    print(f"Error loading data from JSON files: {e}")
                    professions_data = []
                    types_data = []

                profession_names = [
                    item["profession"] for item in professions_data
                ]
                interview_types = [item["type"] for item in types_data]

                with gr.Row():
                    profession_input = gr.Dropdown(
                        label="Select Profession", choices=profession_names
                    )
                    interview_type_input = gr.Dropdown(
                        label="Select Interview Type", choices=interview_types
                    )

                num_questions_input = gr.Number(
                    label="Number of Questions (1-20)",
                    value=5,
                    precision=0,
                    minimum=1,
                    maximum=20,
                )
                overwrite_input = gr.Checkbox(
                    label="Overwrite all_questions.json?", value=True
                )
                # Update num_questions_input when interview_type_input changes
                interview_type_input.change(
                    fn=update_max_questions,
                    inputs=interview_type_input,
                    outputs=num_questions_input,
                )
                generate_button = gr.Button("Generate Questions")

                output_text = gr.Textbox(label="Output")
                question_output = gr.JSON(label="Generated Questions")

                generate_button.click(
                    generate_questions_manager,
                    inputs=[
                        profession_input,
                        interview_type_input,
                        num_questions_input,
                        overwrite_input,
                    ],
                    outputs=[output_text, question_output],
                )

     #       with gr.Tab("Generate from PDF"):
     #           gr.Markdown("### 📄 Upload PDF for Question Generation")
     #           pdf_file_input = gr.File(
     #               label="Upload PDF File", type="filepath"
     #           )
     #           num_questions_pdf_input = gr.Number(
     #               label="Number of Questions", value=5, precision=0
     #           )
     #           generate_pdf_button = gr.Button("Generate Questions from PDF")
     #           pdf_output_text = gr.Textbox(label="Output", visible=False) # Set to invisible
     #           pdf_question_output = gr.JSON(label="Generated Questions", visible=False) # Set to invisible

      #          generate_pdf_button.click(
      #              generate_and_save_questions_from_pdf,
      #              inputs=[pdf_file_input, num_questions_pdf_input],
      #              outputs=[pdf_output_text, pdf_question_output],
      #          )
                


            with gr.Tab("Generate from PDF"):
                gr.Markdown("### 📄 Upload PDF for Question Generation")
                pdf_file_input = gr.File(label="Upload PDF File", type="filepath")
                num_questions_pdf_input = gr.Number(label="Number of Questions", value=5, precision=0)
                
                pdf_status_output = gr.Textbox(label="Status", lines=3)
                pdf_question_output = gr.JSON(label="Generated Questions")
                
                generate_pdf_button = gr.Button("Generate Questions from PDF")

                def update_pdf_ui(pdf_path, num_questions):
                    for status, questions in generate_and_save_questions_from_pdf3(pdf_path, num_questions):
                        yield gr.update(value=status), gr.update(value=questions)

                generate_pdf_button.click(
                    update_pdf_ui,
                    inputs=[pdf_file_input, num_questions_pdf_input],
                    outputs=[pdf_status_output, pdf_question_output],
                )




        def show_selected_ui(role):
            if role == "Candidate":
                return {candidate_ui: gr.Column(visible=True), admin_ui: gr.Column(visible=False)}

            elif role == "Admin":
                return {candidate_ui: gr.Column(visible=False), admin_ui: gr.Column(visible=True)}
            else:
                return {candidate_ui: gr.Column(visible=False), admin_ui: gr.Column(visible=False)}


        proceed_button.click(
            show_selected_ui,
            inputs=[user_role],
            outputs=[candidate_ui, admin_ui],
        )

    return manager_app

def cleanup():
    for audio_file in interview_state.temp_audio_files:
        try:
            if os.path.exists(audio_file):
                os.unlink(audio_file)
        except Exception as e:
            print(f"Error deleting file {audio_file}: {e}")


if __name__ == "__main__":
    manager_app = create_manager_app()
    try:
        manager_app.launch(server_name="0.0.0.0", server_port=7860, debug=True)
    finally:
        cleanup()    