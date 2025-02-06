import os
import json
import time
import tempfile
from collections import deque

import gradio as gr
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage, AIMessage  # Import AIMessage
from openai import OpenAI

# Load environment variables
load_dotenv()

# Function to read questions from JSON
def read_questions_from_json(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file '{file_path}' does not exist.")
    with open(file_path, 'r', encoding='utf-8') as f:
        questions_list = json.load(f)
    if not questions_list:
        raise ValueError("The JSON file is empty or has invalid content.")
    return questions_list


# Function to convert text to speech (OpenAI's TTS usage, adjust if needed)
def convert_text_to_speech(text):
    start_time = time.time()
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.audio.speech.create(model="tts-1", voice="alloy", input=text)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            for chunk in response.iter_bytes():
                tmp_file.write(chunk)
            temp_audio_path = tmp_file.name

        print(f"DEBUG - Text-to-speech conversion time: {time.time() - start_time:.2f} seconds")
        return temp_audio_path
    except Exception as e:
        print(f"Error during text-to-speech conversion: {e}")
        return None


# Function to transcribe audio (OpenAI Whisper usage, adjust if needed)
def transcribe_audio(audio_file_path):
    start_time = time.time()
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        with open(audio_file_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
        print(f"DEBUG - Audio transcription time: {time.time() - start_time:.2f} seconds")
        return transcription.text
    except Exception as e:
        print(f"Error during audio transcription: {e}")
        return None


def conduct_interview(questions, language="English", history_limit=5):
    """
    Sets up a function (interview_step) that handles each round of Q&A.
    Returns (interview_step, initial_message, final_message).
    """
    start_time = time.time()
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise RuntimeError("OpenAI API key not found. Please add it to your .env or set it in env variables.")

    # LangChain-based ChatOpenAI
    chat = ChatOpenAI(
        openai_api_key=openai_api_key,
        model="gpt-4o",  # or "gpt-3.5-turbo", etc.
        temperature=0.7,
        max_tokens=750
    )

    conversation_history = deque(maxlen=history_limit)
    system_prompt = (
        f"You are Sarah, an empathetic HR interviewer conducting a technical interview in {language}. "
        "You respond politely, concisely, and provide clarifications if needed.  "
        "Ask only ONE question at a time.  Wait for the user to respond before asking the next question.  "
        "Provide a very brief, positive acknowledgement of the user's response, *then* ask the next question."
    )


    current_question_index = [0]  # Store index in a list so it's mutable in nested func
    is_interview_finished = [False]  # Use a list for mutability
    waiting_for_answer = [False]


    initial_message = (
        "👋 Hi there, I'm Sarah, your friendly AI HR assistant! "
        "I'll guide you through a series of interview questions to learn more about you. "
        "Take your time and answer each question thoughtfully."
    )
    final_message = (
        "That wraps up our interview. Thank you for your responses—it's been great learning more about you!"
    )

    print(f"DEBUG - conduct_interview setup time: {time.time() - start_time:.2f} seconds")

    def interview_step(user_input, audio_input, history):
        """
        Called each time the user clicks submit or finishes audio recording.
        `history` is a list of { 'role': '...', 'content': '...' } messages.
        We must return an updated version of that list in the same format.
        """
        nonlocal current_question_index, is_interview_finished, waiting_for_answer

        step_start_time = time.time()

        # If there's audio, transcribe it.
        if audio_input:
            transcript = transcribe_audio(audio_input)
            user_input = transcript if transcript else user_input  # Use transcribed text if available

        # If user typed "exit" or "quit"
        if user_input.strip().lower() in ["exit", "quit"]:
            history.append({
                "role": "assistant",
                "content": "The interview has ended at your request. Thank you for your time!"
            })
            is_interview_finished[0] = True
            return history, "", None

        # If the interview is already finished, do nothing.
        if is_interview_finished[0]:
            return history, "", None
        
        # Add user's input to history
        history.append({"role": "user", "content": user_input})


        if not waiting_for_answer[0]:
          #This is a new user response, add to the short history
          conversation_history.append({
              "question": questions[current_question_index[0]-1] if current_question_index[0] > 0 else "",
              "answer": user_input
          })

        # Build the prompt
        short_history = "\n".join([
            f"Q: {entry['question']}\nA: {entry['answer']}"
            for entry in conversation_history
        ])

        if not waiting_for_answer[0]:
            #Normal question flow
            combined_prompt = (
                f"{system_prompt}\n\nPrevious Q&A:\n{short_history}\n\n"
                f"User's input: {user_input}\n\n"
                 "Acknowledge the user's answer briefly, then ask the *next* question."
            )
        else:
            #We are still processing a follow up from the *same* previous question
            combined_prompt = (
                f"{system_prompt}\n\nPrevious Q&A:\n{short_history}\n\n"  # Include full history
                f"Current question: {questions[current_question_index[0]]}\nUser's input:{user_input}\n\n"
                "Acknowledge the user's response briefly, then ask the *next* question, if there are more."
            )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=combined_prompt),
        ]

        # Ask ChatOpenAI
        response = chat.invoke(messages)
        response_content = response.content.strip()
        
        history.append({"role": "assistant", "content": response_content})

        # Convert the LLM's answer to speech
        audio_file_path = convert_text_to_speech(response_content)

        # Check for follow-up questions using a simple heuristic (you can improve this)
        if "?" in response_content:
             waiting_for_answer[0] = True  # Set flag: LLM is asking something
             print("DEBUG - Waiting for answer to follow-up (within same question).")
             print(f"DEBUG - Interview step time: {time.time() - step_start_time:.2f} seconds")
             return history, "", audio_file_path

        #If no follow-up, and we have more question, advance the question.
        waiting_for_answer[0] = False
        if current_question_index[0] < len(questions) -1 :  # Check against len(questions) - 1
            current_question_index[0] += 1
            print(f"DEBUG - question index {current_question_index[0]}")
            print("DEBUG - Moving to next main question.")
            print(f"DEBUG - Interview step time: {time.time() - step_start_time:.2f} seconds")
            return history, "", audio_file_path  # Return current audio
        else:
            # No more questions - finalize
            final_audio_path = convert_text_to_speech(final_message)
            history.append({"role": "assistant", "content": final_message})
            is_interview_finished[0] = True
            print("DEBUG - Interview finished.")
            print(f"DEBUG - Interview step time: {time.time() - step_start_time:.2f} seconds")
            return history, "", final_audio_path


    # Return the step function plus initial/final text
    return interview_step, initial_message, final_message


def main():
    QUESTIONS_FILE_PATH = "questions.json"
    try:
        questions = read_questions_from_json(QUESTIONS_FILE_PATH)
    except Exception as e:
        print(f"Error reading questions: {e}")
        return

    try:
        interview_func, initial_message, final_message = conduct_interview(questions)
    except Exception as e:
        print(f"Error setting up interview: {e}")
        return

    css = """
    .contain { display: flex; flex-direction: column; }
    .gradio-container { height: 100vh !important; overflow-y: auto; }
    #component-0 { height: 100%; }
    .chatbot { flex-grow: 1; overflow: auto; height: 650px; }
    .user > div > .message { background-color: #dcf8c6 !important }
    .bot > div > .message { background-color: #f7f7f8 !important }
    """

    # Build Gradio interface
    with gr.Blocks(css=css) as demo:
        gr.Markdown(
            "<h1 style='text-align:center;'>👋 AI HR Interview Assistant</h1>"
        )
        gr.Markdown(
            "I will ask you a series of questions. Please answer honestly and thoughtfully. "
            "When you are ready, click **Start Interview** to begin."
        )

        start_btn = gr.Button("Start Interview", variant="primary")
        chatbot = gr.Chatbot(
            label="Interview Chat",
            height=650,
            type='messages'  # must return a list of dicts: {"role":..., "content":...}
        )
        audio_input = gr.Audio(
            sources=["microphone"],
            type="filepath",
            label="Record Your Answer"
        )
        user_input = gr.Textbox(
            label="Your Response",
            placeholder="Type your answer here or use the microphone...",
            lines=1,
        )
        audio_output = gr.Audio(label="Response Audio", autoplay=True)

        with gr.Row():
            submit_btn = gr.Button("Submit", variant="primary")
            clear_btn = gr.Button("Clear Chat")

        # --- Gradio callback functions ---

        def start_interview():
            """
            Resets the chat and provides an initial greeting and first question.
            Must return a list of {'role':'assistant','content':'...'} messages
            plus empty text for user_input and path for audio_output.
            """
            history = []
            # Combine initial + the first question
            if questions:
                first_q_text = f" Let's begin! Here's your first question: {questions[0]}"
            else:
                first_q_text = ""

            combined = initial_message + first_q_text
            tts_path = convert_text_to_speech(combined)

            # Return one assistant message to the Chatbot
            history.append({"role": "assistant", "content": combined})
            return history, "", tts_path

        def interview_step_wrapper(user_response, audio_response, history):
            """
            Wrap the 'interview_func' so we always return the correct format:
            (list_of_dicts, str, audio_file_path).
            """
            new_history, _, audio_path = interview_func(user_response, audio_response, history)
            return new_history, "", audio_path

        def on_enter_submit(history, user_text):
            """
            If user presses Enter in the textbox. Return updated Chatbot history,
            empty user_input, and any audio.
            """
            if not user_text.strip():
                # If empty, do nothing
                return history, "", None
            new_history, _, audio_path = interview_func(user_text, None, history)
            return new_history, "", audio_path

        def clear_chat():
            """
            Re-initialize the interview function entirely
            to start from scratch, clearing the Chatbot.
            """
            nonlocal interview_func, initial_message, final_message
            interview_func, initial_msg, final_msg = conduct_interview(questions)
            return [], "", None

        # --- Wire up the event handlers ---

        # 1) Start button
        start_btn.click(
            start_interview,
            inputs=[],
            outputs=[chatbot, user_input, audio_output]
        )

        # 2) Audio: when recording stops
        audio_input.stop_recording(
            interview_step_wrapper,
            inputs=[user_input, audio_input, chatbot],
            outputs=[chatbot, user_input, audio_output]
        )

        # 3) Submit button
        submit_btn.click(
            interview_step_wrapper,
            inputs=[user_input, audio_input, chatbot],
            outputs=[chatbot, user_input, audio_output]
        )

        # 4) Pressing Enter in the textbox
        user_input.submit(
            on_enter_submit,
            inputs=[chatbot, user_input],
            outputs=[chatbot, user_input, audio_output]
        )

        # 5) Clear button
        clear_btn.click(
            clear_chat,
            inputs=[],
            outputs=[chatbot, user_input, audio_output]
        )

    # Launch Gradio (remove `share=True` if it keeps failing)
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        # share=True  # Remove or comment out if you get share-link errors
    )


if __name__ == "__main__":
    main()