import os
import json
from collections import deque
from dotenv import load_dotenv
import gradio as gr
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from openai import OpenAI
import tempfile
import time

# Load environment variables
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

# Function to convert text to speech
def convert_text_to_speech(text):
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.audio.speech.create(model="tts-1-hd", voice="alloy", input=text)

        # Save the audio stream to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            for chunk in response.iter_bytes():
                tmp_file.write(chunk)
            temp_audio_path = tmp_file.name

        return temp_audio_path

    except Exception as e:
        print(f"Error during text-to-speech conversion: {e}")
        return None

# Function to transcribe audio
def transcribe_audio(audio_file_path):
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        with open(audio_file_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        return transcription.text
    except Exception as e:
        print(f"Error during audio transcription: {e}")
        return None

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
    current_question_index = [0]  # Use a list to hold the index

    initial_message = ("👋 Hi there, I'm Sarah, your friendly AI HR assistant! "
                       "I'll guide you through a series of interview questions to learn more about you. "
                       "Take your time and answer each question thoughtfully.")
    final_message = "That wraps up our interview. Thank you so much for your responses—it's been great learning more about you!"

    def interview_step(user_input, audio_input, history):
        # Transcribe audio input if provided
        if audio_input:
            user_input = transcribe_audio(audio_input)
            print("Transcription:", user_input)

        if not user_input:
            return history, "Please provide a response.", None

        if user_input.lower() in ["exit", "quit"]:
            history.append((None, "The interview has ended at your request. Thank you for your time!"))
            return history, "", None

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

        # Convert response to speech
        audio_file_path = convert_text_to_speech(response_content)

        conversation_history.append({"question": question_text, "answer": user_input})
        interview_data.append({"question": question_text, "answer": user_input})
        history.append((user_input, None))
        history.append((None, response_content))

        if current_question_index[0] + 1 < len(questions):
            current_question_index[0] += 1
            next_question = f"Alright, let's move on. {questions[current_question_index[0]]}"
            next_question_audio_path = convert_text_to_speech(next_question)
            history.append((None, next_question))
            return history, "", next_question_audio_path
        else:
            # Convert final message to speech and play it
            final_message_audio_path = convert_text_to_speech(final_message)
            history.append((None, final_message))
            return history, "", final_message_audio_path

    return interview_step, initial_message, final_message

# Gradio interface
def main():
    QUESTIONS_FILE_PATH = "questions.json"  # Ensure you have a questions.json file with your interview questions

    try:
        questions = read_questions_from_json(QUESTIONS_FILE_PATH)
        interview_func, initial_message, final_message = conduct_interview(questions)

        with gr.Blocks() as demo:
            gr.Markdown("""
            <h1 style='text-align: center; margin-bottom: 1rem'>👋 Welcome to Your AI HR Interview Assistant</h1>
            """)

            start_btn = gr.Button("Start Interview", variant="primary")
            chatbot = gr.Chatbot(label="Interview Chat", height=500)
            audio_input = gr.Audio(sources=["microphone"], type="filepath", label="Record Your Answer")
            user_input = gr.Textbox(label="Your Response", placeholder="Type your answer or use the microphone...", lines=1)
            audio_output = gr.Audio(label="Response Audio", autoplay=True)

            with gr.Row():
                submit_btn = gr.Button("Submit", variant="primary")
                clear_btn = gr.Button("Clear Chat")

            def start_interview():
                history = []
                history.append((None, initial_message))
                initial_audio_path = convert_text_to_speech(initial_message)
                first_question = f"Let's begin! Here's your first question: {questions[0]}"
                first_question_audio_path = convert_text_to_speech(first_question)
                history.append((None, first_question))
                return history, "", first_question_audio_path

            def clear_interview():
                return [], "", None

            def interview_step_wrapper(user_response, audio_response, history):
                history, _, audio_path = interview_func(user_response, audio_response, history)
                time.sleep(0.5)
                return history, "", audio_path

            start_btn.click(start_interview, inputs=[], outputs=[chatbot, user_input, audio_output])
            submit_btn.click(interview_step_wrapper, inputs=[user_input, audio_input, chatbot], outputs=[chatbot, user_input, audio_output])
            clear_btn.click(clear_interview, inputs=[], outputs=[chatbot, user_input, audio_output])

        demo.launch()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
