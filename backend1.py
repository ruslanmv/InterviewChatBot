import gradio as gr
import tempfile
import os
import json
from io import BytesIO
from collections import deque
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from openai import OpenAI
import time

# Imports - Keep only what's actually used.  I've organized them.
from generatorgr import (
    generate_and_save_questions as generate_questions_manager,
    update_max_questions,
)
from generator import (
    PROFESSIONS_FILE,
    TYPES_FILE,
    OUTPUT_FILE,
    load_json_data,
    generate_questions,  # Keep if needed, but ensure it exists
)
from splitgpt import (
    generate_and_save_questions_from_pdf3,
    generate_questions_from_job_description,
)
from ai_config import convert_text_to_speech
from knowledge_retrieval import get_next_response, get_initial_question
from prompt_instructions import get_interview_initial_message_hr
from settings import language
from utils import save_interview_history
from tools import store_interview_report, read_questions_from_json

load_dotenv()  # Load .env variables

class InterviewState:
    """Manages the state of the interview."""

    def __init__(self):
        self.reset()

    def reset(self, voice="alloy"):
        self.question_count = 0
        # Corrected history format: List of [user_msg, bot_msg] pairs.
        self.interview_history = []
        self.selected_interviewer = voice
        self.interview_finished = False
        self.audio_enabled = True
        self.temp_audio_files = []
        self.initial_audio_path = None
        self.interview_chain = None
        self.report_chain = None
        self.current_questions = []
        self.history_limit = 5  # Limit the history (good for performance)

    def get_voice_setting(self):
        return self.selected_interviewer

interview_state = InterviewState()

def initialize_chains():
    """Initializes the LangChain LLM chains."""
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError(
            "OpenAI API key not found.  Set it in your .env file."
        )

    llm = ChatOpenAI(
        openai_api_key=openai_api_key, model="gpt-4", temperature=0.7, max_tokens=750
    )

    interview_prompt_template = """
    You are Sarah, an empathetic HR interviewer conducting a technical interview in {language}.

    Current Question: {current_question}

    Previous conversation history:
    {history}

    User's response to current question: {user_input}

    Your response:
    """
    interview_prompt = PromptTemplate(
        input_variables=["language", "current_question", "history", "user_input"],
        template=interview_prompt_template,
    )
    interview_state.interview_chain = LLMChain(prompt=interview_prompt, llm=llm)

    report_prompt_template = """
    You are an HR assistant tasked with generating a concise report based on the following interview transcript in {language}:

    {interview_transcript}

    Summarize the candidate's performance, highlighting strengths and areas for improvement. Keep it to 3-5 sentences.
    Report:
    """
    report_prompt = PromptTemplate(
        input_variables=["language", "interview_transcript"], template=report_prompt_template
    )
    interview_state.report_chain = LLMChain(prompt=report_prompt, llm=llm)

def generate_report(report_chain, history, language):
    """Generates a concise interview report."""
    if report_chain is None:
        raise ValueError("Report chain is not initialized.")

    # Convert the Gradio-style history to a plain text transcript.
    transcript = ""
    for user_msg, bot_msg in history:
        transcript += f"User: {user_msg}\nAssistant: {bot_msg}\n"

    report = report_chain.invoke({"language": language, "interview_transcript": transcript})
    return report["text"]

def reset_interview_action(voice):
    """Resets the interview state and prepares the initial message."""
    interview_state.reset(voice)
    initialize_chains()
    print(f"[DEBUG] Interview reset. Voice: {voice}")

    initial_message_text = get_interview_initial_message_hr(5)  # Get initial message

    # Convert to speech and save to a temporary file.
    initial_audio_buffer = BytesIO()
    convert_text_to_speech(initial_message_text, initial_audio_buffer, voice)
    initial_audio_buffer.seek(0)

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        temp_audio_path = temp_file.name
        temp_file.write(initial_audio_buffer.getvalue())

    interview_state.temp_audio_files.append(temp_audio_path)
    print(f"[DEBUG] Audio file saved at {temp_audio_path}")

    # Return values in the correct format for Gradio.
    return (
        [[None, initial_message_text]],  # [user_msg, bot_msg].  User starts with None.
        gr.Audio(value=temp_audio_path, autoplay=True),
        gr.Textbox(interactive=True),  # Enable the textbox
    )

def start_interview():
    """Starts the interview (used by the Gradio button)."""
    return reset_interview_action(interview_state.selected_interviewer)

def construct_history_string(history):
    """Constructs a history string for the LangChain prompt."""
    history_str = ""
    for user_msg, bot_msg in history:
        history_str += f"User: {user_msg}\nAssistant: {bot_msg}\n"
    return history_str

def bot_response(chatbot, user_message_text):
    """Handles the bot's response logic."""
    voice = interview_state.get_voice_setting()
    history_str = construct_history_string(chatbot)

    if interview_state.question_count < len(interview_state.current_questions):
        current_question = interview_state.current_questions[interview_state.question_count]

        response = interview_state.interview_chain.invoke(
            {
                "language": language,
                "current_question": current_question,
                "history": history_str,
                "user_input": user_message_text,
            }
        )["text"]

        interview_state.question_count += 1

        # Text-to-speech
        audio_buffer = BytesIO()
        convert_text_to_speech(response, audio_buffer, voice)
        audio_buffer.seek(0)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_audio_path = temp_file.name
            temp_file.write(audio_buffer.getvalue())
        interview_state.temp_audio_files.append(temp_audio_path)

        # Update chatbot history in the correct format.
        chatbot.append([user_message_text, response])  # Add user and bot messages

        return chatbot, gr.Audio(value=temp_audio_path, autoplay=True), gr.File(visible=False)

    else:  # Interview finished
        interview_state.interview_finished = True
        conclusion_message = "Thank you for your time. The interview is complete. Please review your report."

        # Text-to-speech for conclusion
        conclusion_audio_buffer = BytesIO()
        convert_text_to_speech(conclusion_message, conclusion_audio_buffer, voice)
        conclusion_audio_buffer.seek(0)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_conclusion_file:
            temp_conclusion_audio_path = temp_conclusion_file.name
            temp_conclusion_file.write(conclusion_audio_buffer.getvalue())
        interview_state.temp_audio_files.append(temp_conclusion_audio_path)

        # Update chatbot history.
        chatbot.append([user_message_text, conclusion_message])

        # Generate and save report.
        report_content = generate_report(
            interview_state.report_chain, chatbot, language
        )  # Pass Gradio history
        txt_path = save_interview_history(
            [f"User: {user}\nAssistant: {bot}" for user, bot in chatbot], language
        )  # Create plain text history
        report_file_path = store_interview_report(report_content)
        print(f"[DEBUG] Interview report saved at: {report_file_path}")

        return (
            chatbot,
            gr.Audio(value=temp_conclusion_audio_path, autoplay=True),
            gr.File(visible=True, value=txt_path),
        )

def convert_text_to_speech_updated(text, voice="alloy"):
    """Converts text to speech and returns the file path."""
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.audio.speech.create(model="tts-1", voice=voice, input=text)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            for chunk in response.iter_bytes():
                tmp_file.write(chunk)
            temp_audio_path = tmp_file.name
        return temp_audio_path

    except Exception as e:
        print(f"Error in text-to-speech: {e}")
        return None

def transcribe_audio(audio_file_path):
    """Transcribes audio to text."""
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        with open(audio_file_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1", file=audio_file
            )
        return transcription.text
    except Exception as e:
        print(f"Error in transcription: {e}")
        return ""

def conduct_interview_updated(questions, language="English", history_limit=5):
    """Conducts the interview (LangChain/OpenAI)."""
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise RuntimeError("OpenAI API key not found.")

    chat = ChatOpenAI(
        openai_api_key=openai_api_key, model="gpt-4o", temperature=0.7, max_tokens=750
    )

    conversation_history = deque(maxlen=history_limit)  # For LangChain, not Gradio
    system_prompt = (
        f"You are Sarah, an empathetic HR interviewer conducting a technical interview in {language}. "
        "Respond to user follow-up questions politely and concisely. Keep responses brief."
    )

    interview_data = []  # Store Q&A for potential later use
    current_question_index = [0]
    is_interview_finished = [False]

    initial_message = (
        "👋 Hi there, I'm Sarah, your friendly AI HR assistant! "
        "I'll guide you through a series of interview questions. "
        "Take your time."
    )
    final_message = "That wraps up our interview. Thank you for your responses!"

    def interview_step(user_input, audio_input, history):
        nonlocal current_question_index, is_interview_finished

        if is_interview_finished[0]:
            return history, "", None  # No further interaction

        if audio_input:
            user_input = transcribe_audio(audio_input)
            if not user_input:
                history.append([None, "I couldn't understand your audio. Could you please repeat or type?"])
                audio_path = convert_text_to_speech_updated(history[-1][1]) #Access the content
                return history, "", audio_path

        if user_input.lower() in ["exit", "quit"]:
            history.append([None, "The interview has ended. Thank you."])
            is_interview_finished[0] = True
            return history, "", None

        question_text = questions[current_question_index[0]]
        # Prepare history for LangChain (not Gradio chatbot format)
        history_content = "\n".join(
            [
                f"Q: {entry['question']}\nA: {entry['answer']}"
                for entry in conversation_history
            ]
        )
        combined_prompt = (
            f"{system_prompt}\n\nPrevious conversation history:\n{history_content}\n\n"
            f"Current question: {question_text}\nUser's input: {user_input}\n\n"
            "Respond warmly."
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=combined_prompt),
        ]

        response = chat.invoke(messages)
        response_content = response.content.strip()
        audio_path = convert_text_to_speech_updated(response_content)

        conversation_history.append({"question": question_text, "answer": user_input})
        interview_data.append({"question": question_text, "answer": user_input})

        # Update Gradio-compatible history.  Crucial for display.
        history.append([user_input, response_content])

        if current_question_index[0] + 1 < len(questions):
            current_question_index[0] += 1
            next_question = f"Next question: {questions[current_question_index[0]]}"
            next_question_audio_path = convert_text_to_speech_updated(next_question)
            # No need to add the "Next Question:" prompt to the displayed history.
            #  The bot will say it.  Adding it here would cause a double entry.
            return history, "", next_question_audio_path
        else:
            final_message_audio = convert_text_to_speech_updated(final_message)
            history.append([None, final_message])  # Final message, no user input.
            is_interview_finished[0] = True
            return history, "", final_message_audio

    return interview_step, initial_message, final_message


def launch_candidate_app_updated():
    """Launches the Gradio app for candidates."""
    QUESTIONS_FILE_PATH = "questions.json"

    try:
        questions = read_questions_from_json(QUESTIONS_FILE_PATH)
        if not questions:
            raise ValueError("No questions found.")
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        print(f"Error loading questions: {e}")
        with gr.Blocks() as error_app:
            gr.Markdown(f"# Error: {e}")
        return error_app

    interview_func, initial_message, _ = conduct_interview_updated(questions)

    def start_interview_ui():
        """Starts the interview."""
        history = []
        initial_combined = (
            initial_message + " Let's begin! Here's the first question: " + questions[0]
        )
        initial_audio_path = convert_text_to_speech_updated(initial_combined)
        history.append([None, initial_combined])  # Correct format: [user, bot]
        return history, "", initial_audio_path, gr.Textbox(interactive=True) # Return interactive textbox

    def clear_interview_ui():
        """Clears the interview and resets."""
        # Recreate the object in order to clear the history of the interview
        nonlocal interview_func, initial_message
        interview_func, initial_message, _ = conduct_interview_updated(questions)
        return [], "", None, gr.Textbox(interactive=True) # Return interactive textbox

    def interview_step_wrapper(user_response, audio_response, history):
        """Wrapper for the interview step function."""
        history, user_text, audio_path = interview_func(user_response, audio_response, history)
        # Always return interactive=True, except when interview is finished
        return history, "", audio_path, gr.Textbox(value=user_text, interactive=True if user_text is not None else False)
    with gr.Blocks(title="AI HR Interview Assistant") as candidate_app:
        gr.Markdown(
            "<h1 style='text-align: center;'>👋 Welcome to Your AI HR Interview Assistant</h1>"
        )
        start_btn = gr.Button("Start Interview", variant="primary")
        chatbot = gr.Chatbot(label="Interview Chat", height=650)
        audio_input = gr.Audio(
            sources=["microphone"], type="filepath", label="Record Your Answer"
        )
        user_input = gr.Textbox(
            label="Your Response",
            placeholder="Type your answer here or use the microphone...",
            lines=1,
            interactive=True,  # Make the textbox interactive initially
        )
        audio_output = gr.Audio(label="Response Audio", autoplay=True)

        with gr.Row():
            submit_btn = gr.Button("Submit", variant="primary")
            clear_btn = gr.Button("Clear Chat")

        def on_enter_submit(history, user_response):
            """Handles submission when Enter is pressed."""
            if not user_response.strip():
                return history, "", None, gr.Textbox(interactive=True)  # Prevent empty submissions, keep interactive
            history, _, audio_path, new_textbox = interview_step_wrapper(
                user_response, None, history
            )  # No audio on Enter
            return history, "", audio_path, new_textbox

        start_btn.click(
            start_interview_ui, inputs=[], outputs=[chatbot, user_input, audio_output, user_input] # Include user_input as output
        )
        audio_input.stop_recording(
            interview_step_wrapper,
            inputs=[user_input, audio_input, chatbot],
            outputs=[chatbot, user_input, audio_output, user_input], # Include user_input as output
        )
        submit_btn.click(
            interview_step_wrapper,
            inputs=[user_input, audio_input, chatbot],
            outputs=[chatbot, user_input, audio_output, user_input],  # Include user_input
        )
        user_input.submit(
            on_enter_submit,
            inputs=[chatbot, user_input],
            outputs=[chatbot, user_input, audio_output, user_input], # Include user_input
        )
        clear_btn.click(
            clear_interview_ui, inputs=[], outputs=[chatbot, user_input, audio_output, user_input] # Include user_input
        )

    return candidate_app
# --- (End of Candidate Interview Implementation) ---


def cleanup():
    """Cleans up temporary audio files."""
    for audio_file in interview_state.temp_audio_files:
        try:
            if os.path.exists(audio_file):
                os.unlink(audio_file)
        except Exception as e:
            print(f"Error deleting file {audio_file}: {e}")